"""Biometric Face Enrollment and Privacy Lifecycle Endpoints."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Student, FaceTemplate, AuditLog, User
from app.schemas import FaceEnrollmentRequest, FaceEnrollmentResponse
from app.auth import get_current_user, require_roles
from app.ai.face_engine import face_engine
from app.ai.quality_checker import QualityChecker
from app.ai.anti_spoof import AntiSpoofDetector

router = APIRouter(prefix="/biometrics", tags=["Biometrics & Face Templates"])

@router.post("/enroll", response_model=FaceEnrollmentResponse, dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN", "TEACHER"))])
async def enroll_face(
    req: FaceEnrollmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    student = await db.get(Student, req.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if not req.samples or len(req.samples) == 0:
        raise HTTPException(status_code=400, detail="At least 1 face capture sample is required")

    embeddings = []
    quality_scores = []

    for idx, sample_b64 in enumerate(req.samples):
        img = face_engine.decode_base64_image(sample_b64)
        if img is None:
            continue

        faces = face_engine.detect_faces(img)
        if not faces:
            continue

        face_box = faces[0]
        is_acceptable, q_score, q_metrics = QualityChecker.evaluate(img, face_box)
        quality_scores.append(q_score)

        emb = face_engine.extract_embedding(img, face_box)
        embeddings.append(emb)

    if not embeddings:
        raise HTTPException(
            status_code=400,
            detail="Failed to detect or extract biometric features. Ensure clear lighting, centered face, and minimum blur."
        )

    # Compute centroid from multiple samples
    centroid_vector = face_engine.compute_centroid(embeddings)
    mean_quality = float(round(sum(quality_scores) / len(quality_scores), 3))

    # Deactivate existing active templates for this student
    stmt = select(FaceTemplate).where(
        FaceTemplate.student_id == student.id,
        FaceTemplate.is_active == True
    )
    existing = await db.execute(stmt)
    for t in existing.scalars().all():
        t.is_active = False

    # Insert new FaceTemplate
    new_template = FaceTemplate(
        student_id=student.id,
        embedding=json.dumps(centroid_vector),
        model_version="OpenCV_FeatureExtract_v1",
        quality_score=mean_quality,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(new_template)

    # Record sensitive audit log
    audit_entry = AuditLog(
        user_id=current_user.id,
        action="FACE_ENROLLMENT",
        entity_type="FaceTemplate",
        entity_id=student.id,
        new_state=f"Enrolled with {len(embeddings)} samples, quality={mean_quality}",
        reason="Authorized biometric enrollment",
        timestamp=datetime.utcnow()
    )
    db.add(audit_entry)

    await db.commit()

    return FaceEnrollmentResponse(
        student_id=student.id,
        success=True,
        quality_score=mean_quality,
        message=f"Biometric template successfully enrolled using {len(embeddings)} sample(s).",
        model_version=new_template.model_version
    )

@router.delete("/templates/{student_id}", dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def revoke_biometrics(
    student_id: int,
    reason: str = "Student privacy revocation request",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    stmt = select(FaceTemplate).where(FaceTemplate.student_id == student_id)
    templates = (await db.execute(stmt)).scalars().all()

    if not templates:
        return {"message": "No biometric templates found for this student"}

    for t in templates:
        await db.delete(t)

    audit_entry = AuditLog(
        user_id=current_user.id,
        action="BIOMETRIC_REVOKED_AND_DELETED",
        entity_type="FaceTemplate",
        entity_id=student_id,
        reason=reason,
        timestamp=datetime.utcnow()
    )
    db.add(audit_entry)
    await db.commit()

    return {"message": f"All biometric face templates for student {student.name} ({student.roll_number}) have been permanently deleted in accordance with data privacy rules."}
