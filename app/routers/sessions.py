"""Attendance Sessions Lifecycle & Control Endpoints."""
from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import AttendanceSession, CourseOffering, Course, Teacher, Room, Enrollment, AttendanceRecord, Student, User
from app.schemas import AttendanceSessionCreate, AttendanceSessionResponse
from app.auth import get_current_user, require_roles
from app.websockets.connection_manager import ws_manager

router = APIRouter(prefix="/attendance/sessions", tags=["Attendance Sessions"])

@router.get("", response_model=List[AttendanceSessionResponse])
async def list_sessions(
    date_str: Optional[str] = None,
    teacher_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AttendanceSession).options(
        selectinload(AttendanceSession.course_offering).selectinload(CourseOffering.course),
        selectinload(AttendanceSession.teacher),
        selectinload(AttendanceSession.room),
        selectinload(AttendanceSession.attendance_records)
    )
    if date_str:
        stmt = stmt.where(AttendanceSession.date == date_str)
    if teacher_id:
        stmt = stmt.where(AttendanceSession.teacher_id == teacher_id)
    if status_filter:
        stmt = stmt.where(AttendanceSession.status == status_filter)

    result = await db.execute(stmt.order_by(AttendanceSession.start_time.desc()))
    sessions = result.scalars().all()

    responses = []
    for s in sessions:
        # Count enrollments
        enr_count_stmt = select(func.count(Enrollment.id)).where(Enrollment.course_offering_id == s.course_offering_id)
        enr_res = await db.execute(enr_count_stmt)
        total_enrolled = enr_res.scalar_one() or 0

        present_count = sum(1 for r in s.attendance_records if r.status == "PRESENT")
        late_count = sum(1 for r in s.attendance_records if r.status == "LATE")
        absent_count = sum(1 for r in s.attendance_records if r.status == "ABSENT")

        responses.append(AttendanceSessionResponse(
            id=s.id,
            course_offering_id=s.course_offering_id,
            room_id=s.room_id,
            teacher_id=s.teacher_id,
            title=s.title,
            date=s.date,
            start_time=s.start_time,
            end_time=s.end_time,
            grace_period_minutes=s.grace_period_minutes,
            status=s.status,
            course_name=s.course_offering.course.course_name if s.course_offering and s.course_offering.course else None,
            teacher_name=s.teacher.name if s.teacher else None,
            room_number=s.room.room_number if s.room else None,
            total_enrolled=total_enrolled,
            present_count=present_count,
            late_count=late_count,
            absent_count=absent_count
        ))
    return responses

@router.get("/{id}", response_model=AttendanceSessionResponse)
async def get_session(id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(AttendanceSession).options(
        selectinload(AttendanceSession.course_offering).selectinload(CourseOffering.course),
        selectinload(AttendanceSession.teacher),
        selectinload(AttendanceSession.room),
        selectinload(AttendanceSession.attendance_records)
    ).where(AttendanceSession.id == id)
    result = await db.execute(stmt)
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Attendance session not found")

    enr_count_stmt = select(func.count(Enrollment.id)).where(Enrollment.course_offering_id == s.course_offering_id)
    total_enrolled = (await db.execute(enr_count_stmt)).scalar_one() or 0

    present_count = sum(1 for r in s.attendance_records if r.status == "PRESENT")
    late_count = sum(1 for r in s.attendance_records if r.status == "LATE")
    absent_count = sum(1 for r in s.attendance_records if r.status == "ABSENT")

    return AttendanceSessionResponse(
        id=s.id,
        course_offering_id=s.course_offering_id,
        room_id=s.room_id,
        teacher_id=s.teacher_id,
        title=s.title,
        date=s.date,
        start_time=s.start_time,
        end_time=s.end_time,
        grace_period_minutes=s.grace_period_minutes,
        status=s.status,
        course_name=s.course_offering.course.course_name if s.course_offering and s.course_offering.course else None,
        teacher_name=s.teacher.name if s.teacher else None,
        room_number=s.room.room_number if s.room else None,
        total_enrolled=total_enrolled,
        present_count=present_count,
        late_count=late_count,
        absent_count=absent_count
    )

@router.post("", response_model=AttendanceSessionResponse, dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN", "TEACHER"))])
async def create_session(
    data: AttendanceSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    today_str = date.today().isoformat()
    now = datetime.utcnow()

    new_session = AttendanceSession(
        course_offering_id=data.course_offering_id,
        room_id=data.room_id,
        teacher_id=data.teacher_id,
        title=data.title,
        date=today_str,
        start_time=now,
        grace_period_minutes=data.grace_period_minutes,
        status="ACTIVE"
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    # Broadcast event
    await ws_manager.broadcast_global({
        "event": "SESSION_CREATED",
        "session_id": new_session.id,
        "title": new_session.title,
        "status": new_session.status
    })

    return await get_session(new_session.id, db)

@router.post("/{id}/start", dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN", "TEACHER"))])
async def start_session(id: int, db: AsyncSession = Depends(get_db)):
    session = await db.get(AttendanceSession, id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "CLOSED":
        raise HTTPException(status_code=400, detail="Cannot reopen a closed session")

    session.status = "ACTIVE"
    await db.commit()
    await ws_manager.broadcast_to_session(id, {"event": "SESSION_STATUS_CHANGED", "status": "ACTIVE", "session_id": id})
    return {"message": "Session started and active", "status": "ACTIVE"}

@router.post("/{id}/pause", dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN", "TEACHER"))])
async def pause_session(id: int, db: AsyncSession = Depends(get_db)):
    session = await db.get(AttendanceSession, id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "PAUSED"
    await db.commit()
    await ws_manager.broadcast_to_session(id, {"event": "SESSION_STATUS_CHANGED", "status": "PAUSED", "session_id": id})
    return {"message": "Session paused", "status": "PAUSED"}

@router.post("/{id}/close", dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN", "TEACHER"))])
async def close_session(id: int, db: AsyncSession = Depends(get_db)):
    session = await db.get(AttendanceSession, id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = "CLOSED"
    session.end_time = datetime.utcnow()

    # Automatically mark all remaining enrolled students without attendance as ABSENT
    enrolled_stmt = select(Enrollment.student_id).where(Enrollment.course_offering_id == session.course_offering_id)
    enrolled_ids = (await db.execute(enrolled_stmt)).scalars().all()

    existing_recs_stmt = select(AttendanceRecord.student_id).where(AttendanceRecord.session_id == session.id)
    marked_ids = set((await db.execute(existing_recs_stmt)).scalars().all())

    for sid in enrolled_ids:
        if sid not in marked_ids:
            absent_record = AttendanceRecord(
                session_id=session.id,
                student_id=sid,
                status="ABSENT",
                marked_at=datetime.utcnow(),
                verification_method="SYSTEM_AUTO_ABSENT",
                notes="Unrecorded upon session close"
            )
            db.add(absent_record)

    await db.commit()
    await ws_manager.broadcast_to_session(id, {"event": "SESSION_STATUS_CHANGED", "status": "CLOSED", "session_id": id})
    return {"message": "Session closed and unrecorded students marked absent", "status": "CLOSED"}
