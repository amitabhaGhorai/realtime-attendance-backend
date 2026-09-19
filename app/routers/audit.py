"""Audit Logging and System Administration Configuration Endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import AuditLog, User
from app.schemas import AuditLogResponse
from app.auth import get_current_user, require_roles
from app.config import settings

router = APIRouter(tags=["Audit & Administration"])

@router.get("/audit-logs", response_model=List[AuditLogResponse], dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def get_audit_logs(
    limit: int = Query(50, le=200),
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AuditLog).options(selectinload(AuditLog.user)).order_by(AuditLog.timestamp.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    responses = []
    for log in logs:
        responses.append(AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            user_name=log.user.full_name if log.user else "System",
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            old_state=log.old_state,
            new_state=log.new_state,
            reason=log.reason,
            ip_address=log.ip_address,
            timestamp=log.timestamp
        ))
    return responses

@router.get("/settings", dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def get_system_settings():
    return {
        "institution_name": settings.INSTITUTION_NAME,
        "institution_code": settings.INSTITUTION_CODE,
        "default_grace_period_minutes": settings.DEFAULT_GRACE_PERIOD_MINUTES,
        "default_confidence_threshold": settings.DEFAULT_CONFIDENCE_THRESHOLD,
        "laplacian_sharpness_threshold": settings.DEFAULT_LAPLACIAN_THRESHOLD,
        "min_face_size": settings.MIN_FACE_SIZE,
        "biometric_retention_days": 365,
        "version": settings.VERSION
    }

@router.post("/settings", dependencies=[Depends(require_roles("SUPER_ADMIN"))])
async def update_system_settings(data: dict):
    if "default_grace_period_minutes" in data:
        settings.DEFAULT_GRACE_PERIOD_MINUTES = int(data["default_grace_period_minutes"])
    if "default_confidence_threshold" in data:
        settings.DEFAULT_CONFIDENCE_THRESHOLD = float(data["default_confidence_threshold"])
    return {"message": "Settings updated successfully", "settings": data}
