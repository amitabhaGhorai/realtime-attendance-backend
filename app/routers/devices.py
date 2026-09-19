"""Device Fleet & Camera Health Monitoring Endpoints."""
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Device, Room, User
from app.schemas import DeviceCreate, DeviceResponse
from app.auth import get_current_user, require_roles

router = APIRouter(prefix="/devices", tags=["Device & Camera Monitoring"])

@router.get("", response_model=List[DeviceResponse])
async def list_devices(db: AsyncSession = Depends(get_db)):
    stmt = select(Device).options(selectinload(Device.room)).order_by(Device.name)
    result = await db.execute(stmt)
    devices = result.scalars().all()

    now = datetime.utcnow()
    responses = []
    for d in devices:
        # If heartbeat was > 5 minutes ago, mark offline
        is_alive = (now - d.last_heartbeat) < timedelta(minutes=5) if d.last_heartbeat else False
        live_status = "ONLINE" if is_alive else "OFFLINE"
        if d.status != live_status:
            d.status = live_status

        responses.append(DeviceResponse(
            id=d.id,
            name=d.name,
            device_code=d.device_code,
            room_id=d.room_id,
            ip_address=d.ip_address,
            status=live_status,
            last_heartbeat=d.last_heartbeat,
            software_version=d.software_version,
            room_number=d.room.room_number if d.room else None
        ))
    await db.commit()
    return responses

@router.post("", response_model=DeviceResponse, dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def register_device(data: DeviceCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Device).where(Device.device_code == data.device_code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Device with code {data.device_code} already registered")

    new_device = Device(
        name=data.name,
        device_code=data.device_code,
        room_id=data.room_id,
        ip_address=data.ip_address,
        software_version=data.software_version,
        status="ONLINE",
        last_heartbeat=datetime.utcnow()
    )
    db.add(new_device)
    await db.commit()
    await db.refresh(new_device)
    return new_device

@router.post("/{id}/heartbeat")
async def device_heartbeat(id: int, db: AsyncSession = Depends(get_db)):
    device = await db.get(Device, id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.last_heartbeat = datetime.utcnow()
    device.status = "ONLINE"
    await db.commit()
    return {"message": "Heartbeat acknowledged", "status": "ONLINE", "timestamp": device.last_heartbeat}
