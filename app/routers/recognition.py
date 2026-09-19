"""Live Camera Frame Verification & Face Recognition Integration Endpoint."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import (
    AttendanceSession, AttendanceRecord, Student, FaceTemplate,
    Enrollment, RecognitionEvent, CourseOffering
)
from app.schemas import RecognitionVerifyRequest, RecognitionVerifyResponse
from app.ai.face_engine import face_engine
from app.ai.quality_checker import QualityChecker
from app.ai.anti_spoof import AntiSpoofDetector
from app.websockets.connection_manager import ws_manager
from app.config import settings

router = APIRouter(prefix="/recognition", tags=["Camera & AI Recognition Engine"])

@router.post("/verify", response_model=RecognitionVerifyResponse)
async def verify_camera_frame(req: RecognitionVerifyRequest, db: AsyncSession = Depends(get_db)):
    # 1. Fetch active session
    session_stmt = select(AttendanceSession).options(
        selectinload(AttendanceSession.course_offering)
    ).where(AttendanceSession.id == req.session_id)
    session_res = await db.execute(session_stmt)
    active_session = session_res.scalar_one_or_none()

    if not active_session:
        raise HTTPException(status_code=404, detail="Attendance session not found")

    if active_session.status != "ACTIVE":
        return RecognitionVerifyResponse(
            success=False,
            result="SESSION_NOT_ACTIVE",
            message=f"Attendance session is currently {active_session.status}. New scans are paused/closed."
        )

    # 2. Decode image
    img = face_engine.decode_base64_image(req.image_base64)
    if img is None:
        return RecognitionVerifyResponse(
            success=False,
            result="INVALID_IMAGE",
            message="Unable to decode camera image frame."
        )

    # 3. Detect face
    faces = face_engine.detect_faces(img)
    if not faces:
        return RecognitionVerifyResponse(
            success=False,
            result="NO_FACE_DETECTED",
            message="No face detected in camera viewport."
        )

    primary_face = faces[0]

    # 4. Quality evaluation
    is_acceptable, q_score, q_metrics = QualityChecker.evaluate(img, primary_face)
    if not is_acceptable:
        return RecognitionVerifyResponse(
            success=False,
            result="LOW_QUALITY",
            confidence=q_score,
            message="Image quality below threshold (low lighting or blurry motion)."
        )

    # 5. Anti-spoofing / liveness check
    is_live, liveness_conf, liveness_details = AntiSpoofDetector.check_liveness(img)
    if not is_live:
        # Log spoof attempt
        event = RecognitionEvent(
            session_id=active_session.id,
            device_id=req.device_id,
            result="SPOOF_DETECTED",
            error_message="Presentation attack detected (potential paper/screen print)",
            timestamp=datetime.utcnow()
        )
        db.add(event)
        await db.commit()

        await ws_manager.broadcast_to_session(active_session.id, {
            "event": "RECOGNITION_FAILED",
            "reason": "Presentation attack detected (liveness check failed)",
            "details": liveness_details
        })
        return RecognitionVerifyResponse(
            success=False,
            result="SPOOF_DETECTED",
            confidence=liveness_conf,
            message="Presentation attack / spoof detected. Please present live in person."
        )

    # 6. Extract face embedding
    query_emb = face_engine.extract_embedding(img, primary_face)

    # 7. Query active templates for all enrolled students in this course offering
    enrolled_stmt = select(Enrollment.student_id).where(
        Enrollment.course_offering_id == active_session.course_offering_id
    )
    enrolled_student_ids = (await db.execute(enrolled_stmt)).scalars().all()

    # Load templates
    templates_stmt = select(FaceTemplate, Student).join(Student, FaceTemplate.student_id == Student.id).where(
        FaceTemplate.is_active == True,
        FaceTemplate.student_id.in_(enrolled_student_ids) if enrolled_student_ids else False
    )
    templates_res = await db.execute(templates_stmt)
    template_rows = templates_res.all()

    formatted_templates = []
    for t, s in template_rows:
        formatted_templates.append({
            "student_id": s.id,
            "name": s.name,
            "roll_number": s.roll_number,
            "embedding": t.embedding
        })

    # If no enrolled students have templates yet, also check any other active student templates
    if not formatted_templates:
        fallback_stmt = select(FaceTemplate, Student).join(Student, FaceTemplate.student_id == Student.id).where(
            FaceTemplate.is_active == True
        )
        fallback_rows = (await db.execute(fallback_stmt)).all()
        for t, s in fallback_rows:
            formatted_templates.append({
                "student_id": s.id,
                "name": s.name,
                "roll_number": s.roll_number,
                "embedding": t.embedding
            })

    # 8. Match against templates
    best_match, match_confidence = face_engine.match_against_templates(
        query_emb,
        formatted_templates,
        threshold=settings.DEFAULT_CONFIDENCE_THRESHOLD
    )

    if not best_match:
        # Unknown face or low confidence
        result_type = "LOW_CONFIDENCE" if match_confidence > 0.4 else "UNKNOWN"
        event = RecognitionEvent(
            session_id=active_session.id,
            device_id=req.device_id,
            confidence=match_confidence,
            result=result_type,
            error_message="Unrecognized face or confidence below threshold",
            timestamp=datetime.utcnow()
        )
        db.add(event)
        await db.commit()

        await ws_manager.broadcast_to_session(active_session.id, {
            "event": "MANUAL_VERIFICATION_REQUIRED" if result_type == "LOW_CONFIDENCE" else "UNKNOWN_FACE",
            "confidence": round(match_confidence, 2),
            "message": "Unrecognized face detected at camera"
        })

        return RecognitionVerifyResponse(
            success=False,
            result=result_type,
            confidence=round(match_confidence, 3),
            message="Unrecognized face. Please ensure you are enrolled or verify with the instructor."
        )

    matched_student_id = best_match["student_id"]
    student_name = best_match["name"]
    roll_number = best_match["roll_number"]

    # 9. Verify student belongs to this course offering
    if matched_student_id not in enrolled_student_ids:
        event = RecognitionEvent(
            session_id=active_session.id,
            device_id=req.device_id,
            recognized_student_id=matched_student_id,
            confidence=match_confidence,
            result="NOT_ENROLLED",
            error_message=f"Student {student_name} is not enrolled in this course session",
            timestamp=datetime.utcnow()
        )
        db.add(event)
        await db.commit()

        await ws_manager.broadcast_to_session(active_session.id, {
            "event": "RECOGNITION_FAILED",
            "student_id": matched_student_id,
            "student_name": student_name,
            "roll_number": roll_number,
            "reason": "Student is not enrolled in this course"
        })

        return RecognitionVerifyResponse(
            success=False,
            result="NOT_ENROLLED",
            student_id=matched_student_id,
            student_name=student_name,
            roll_number=roll_number,
            confidence=round(match_confidence, 3),
            message=f"{student_name} is not enrolled in this course."
        )

    # 10. Check duplicate attendance
    dup_stmt = select(AttendanceRecord).where(
        AttendanceRecord.session_id == active_session.id,
        AttendanceRecord.student_id == matched_student_id
    )
    dup_res = await db.execute(dup_stmt)
    existing_record = dup_res.scalar_one_or_none()

    if existing_record:
        # Log duplicate scan
        event = RecognitionEvent(
            session_id=active_session.id,
            device_id=req.device_id,
            recognized_student_id=matched_student_id,
            confidence=match_confidence,
            result="DUPLICATE",
            timestamp=datetime.utcnow()
        )
        db.add(event)
        await db.commit()

        await ws_manager.broadcast_to_session(active_session.id, {
            "event": "DUPLICATE_SCAN",
            "student_id": matched_student_id,
            "student_name": student_name,
            "roll_number": roll_number,
            "status": existing_record.status,
            "marked_at": existing_record.marked_at.strftime("%H:%M:%S")
        })

        return RecognitionVerifyResponse(
            success=True,
            result="DUPLICATE",
            student_id=matched_student_id,
            student_name=student_name,
            roll_number=roll_number,
            status=existing_record.status,
            confidence=round(match_confidence, 3),
            message=f"Attendance already marked ({existing_record.status}) for {student_name}."
        )

    # 11. Calculate Present vs Late
    now = datetime.utcnow()
    elapsed_minutes = (now - active_session.start_time).total_seconds() / 60.0
    status_assigned = "PRESENT" if elapsed_minutes <= active_session.grace_period_minutes else "LATE"

    # 12. Create Attendance Record
    new_record = AttendanceRecord(
        session_id=active_session.id,
        student_id=matched_student_id,
        status=status_assigned,
        marked_at=now,
        verification_method="FACE_RECOGNITION",
        confidence_score=float(round(match_confidence, 4)),
        notes=f"Recognized automatically (Confidence: {round(match_confidence*100, 1)}%)"
    )
    db.add(new_record)

    # 13. Log successful recognition event
    event = RecognitionEvent(
        session_id=active_session.id,
        device_id=req.device_id,
        recognized_student_id=matched_student_id,
        confidence=match_confidence,
        result="SUCCESS",
        timestamp=now
    )
    db.add(event)

    await db.commit()
    await db.refresh(new_record)

    # 14. Broadcast live ATTENDANCE_MARKED event via WebSocket
    await ws_manager.broadcast_to_session(active_session.id, {
        "event": "ATTENDANCE_MARKED",
        "record_id": new_record.id,
        "session_id": active_session.id,
        "student_id": matched_student_id,
        "student_name": student_name,
        "roll_number": roll_number,
        "status": status_assigned,
        "confidence": round(match_confidence, 3),
        "marked_at": now.strftime("%H:%M:%S")
    })

    return RecognitionVerifyResponse(
        success=True,
        result="SUCCESS",
        student_id=matched_student_id,
        student_name=student_name,
        roll_number=roll_number,
        status=status_assigned,
        confidence=round(match_confidence, 3),
        message=f"Attendance recorded as {status_assigned} for {student_name} ({roll_number})."
    )
