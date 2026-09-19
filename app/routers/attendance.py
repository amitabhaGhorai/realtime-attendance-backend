"""Attendance Records and Manual Correction Endpoints."""
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import AttendanceRecord, AttendanceSession, Student, AuditLog, User
from app.schemas import AttendanceRecordResponse, AttendanceRecordOverride
from app.auth import get_current_user, require_roles
from app.websockets.connection_manager import ws_manager

router = APIRouter(prefix="/attendance", tags=["Attendance Engine"])

@router.get("/sessions/{session_id}/records", response_model=List[AttendanceRecordResponse])
async def get_session_records(session_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(AttendanceRecord).options(
        selectinload(AttendanceRecord.student)
    ).where(AttendanceRecord.session_id == session_id).order_by(AttendanceRecord.marked_at.desc())
    
    result = await db.execute(stmt)
    records = result.scalars().all()

    responses = []
    for r in records:
        responses.append(AttendanceRecordResponse(
            id=r.id,
            session_id=r.session_id,
            student_id=r.student_id,
            student_name=r.student.name if r.student else "Unknown",
            roll_number=r.student.roll_number if r.student else "N/A",
            status=r.status,
            marked_at=r.marked_at,
            verification_method=r.verification_method,
            confidence_score=r.confidence_score,
            notes=r.notes
        ))
    return responses

@router.patch("/records/{record_id}/override", dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN", "TEACHER"))])
async def override_attendance_record(
    record_id: int,
    data: AttendanceRecordOverride,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not data.reason or len(data.reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="A valid justification reason is mandatory for manual corrections")

    valid_statuses = ["PRESENT", "LATE", "ABSENT", "EXCUSED"]
    if data.status.upper() not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid_statuses}")

    stmt = select(AttendanceRecord).options(
        selectinload(AttendanceRecord.student),
        selectinload(AttendanceRecord.session)
    ).where(AttendanceRecord.id == record_id)
    
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    old_status = record.status
    record.status = data.status.upper()
    record.verification_method = "MANUAL_OVERRIDE"
    record.marked_by_user_id = current_user.id
    record.notes = f"Overridden by {current_user.full_name}: {data.reason}"

    # Audit log creation
    audit_entry = AuditLog(
        user_id=current_user.id,
        action="MANUAL_ATTENDANCE_OVERRIDE",
        entity_type="AttendanceRecord",
        entity_id=record.id,
        old_state=f"status={old_status}",
        new_state=f"status={record.status}",
        reason=data.reason,
        timestamp=datetime.utcnow()
    )
    db.add(audit_entry)
    await db.commit()

    # Broadcast update to live dashboard
    await ws_manager.broadcast_to_session(record.session_id, {
        "event": "ATTENDANCE_OVERRIDE",
        "record_id": record.id,
        "student_id": record.student_id,
        "student_name": record.student.name if record.student else "Student",
        "roll_number": record.student.roll_number if record.student else "N/A",
        "status": record.status,
        "reason": data.reason
    })

    return {
        "message": f"Attendance record updated to {record.status}",
        "old_status": old_status,
        "new_status": record.status,
        "record_id": record.id
    }
