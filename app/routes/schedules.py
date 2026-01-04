import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from ..database import get_db
from ..models import User, Client, Schedule
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedules", tags=["Schedules"])


class ScheduleCreate(BaseModel):
    clientId: int
    title: str
    description: Optional[str] = None
    serviceType: Optional[str] = None
    scheduledDate: datetime
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    durationMinutes: Optional[int] = None
    notes: Optional[str] = None
    address: Optional[str] = None
    assignedTo: Optional[str] = None
    price: Optional[float] = None
    isRecurring: Optional[bool] = False
    recurrencePattern: Optional[str] = None


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    serviceType: Optional[str] = None
    scheduledDate: Optional[datetime] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    durationMinutes: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    address: Optional[str] = None
    assignedTo: Optional[str] = None
    price: Optional[float] = None
    isRecurring: Optional[bool] = None
    recurrencePattern: Optional[str] = None


class ScheduleResponse(BaseModel):
    id: int
    clientId: int
    clientName: str
    title: str
    description: Optional[str]
    serviceType: Optional[str]
    scheduledDate: datetime
    startTime: Optional[str]
    endTime: Optional[str]
    durationMinutes: Optional[int]
    status: str
    notes: Optional[str]
    address: Optional[str]
    assignedTo: Optional[str]
    price: Optional[float]
    isRecurring: bool
    recurrencePattern: Optional[str]
    createdAt: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[ScheduleResponse])
async def get_schedules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all schedules for the current user"""
    schedules = db.query(Schedule).filter(Schedule.user_id == current_user.id).order_by(Schedule.scheduled_date.asc()).all()
    result = []
    for s in schedules:
        client = db.query(Client).filter(Client.id == s.client_id).first()
        result.append(ScheduleResponse(
            id=s.id,
            clientId=s.client_id,
            clientName=client.business_name if client else "Unknown",
            title=s.title,
            description=s.description,
            serviceType=s.service_type,
            scheduledDate=s.scheduled_date,
            startTime=s.start_time,
            endTime=s.end_time,
            durationMinutes=s.duration_minutes,
            status=s.status,
            notes=s.notes,
            address=s.address,
            assignedTo=s.assigned_to,
            price=s.price,
            isRecurring=s.is_recurring or False,
            recurrencePattern=s.recurrence_pattern,
            createdAt=s.created_at
        ))
    return result


@router.post("", response_model=ScheduleResponse)
async def create_schedule(
    data: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new schedule"""
    logger.info(f"📥 Creating schedule for user_id: {current_user.id}")
    
    client = db.query(Client).filter(Client.id == data.clientId, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    schedule = Schedule(
        user_id=current_user.id,
        client_id=data.clientId,
        title=data.title,
        description=data.description,
        service_type=data.serviceType,
        scheduled_date=data.scheduledDate,
        start_time=data.startTime,
        end_time=data.endTime,
        duration_minutes=data.durationMinutes,
        notes=data.notes,
        address=data.address,
        assigned_to=data.assignedTo,
        price=data.price,
        is_recurring=data.isRecurring,
        recurrence_pattern=data.recurrencePattern,
        status="scheduled"
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    
    logger.info(f"✅ Schedule created: id={schedule.id}")
    return ScheduleResponse(
        id=schedule.id,
        clientId=schedule.client_id,
        clientName=client.business_name,
        title=schedule.title,
        description=schedule.description,
        serviceType=schedule.service_type,
        scheduledDate=schedule.scheduled_date,
        startTime=schedule.start_time,
        endTime=schedule.end_time,
        durationMinutes=schedule.duration_minutes,
        status=schedule.status,
        notes=schedule.notes,
        address=schedule.address,
        assignedTo=schedule.assigned_to,
        price=schedule.price,
        isRecurring=schedule.is_recurring or False,
        recurrencePattern=schedule.recurrence_pattern,
        createdAt=schedule.created_at
    )


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a schedule"""
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.user_id == current_user.id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    if data.title is not None:
        schedule.title = data.title
    if data.description is not None:
        schedule.description = data.description
    if data.serviceType is not None:
        schedule.service_type = data.serviceType
    if data.scheduledDate is not None:
        schedule.scheduled_date = data.scheduledDate
    if data.startTime is not None:
        schedule.start_time = data.startTime
    if data.endTime is not None:
        schedule.end_time = data.endTime
    if data.durationMinutes is not None:
        schedule.duration_minutes = data.durationMinutes
    if data.status is not None:
        schedule.status = data.status
    if data.notes is not None:
        schedule.notes = data.notes
    if data.address is not None:
        schedule.address = data.address
    if data.assignedTo is not None:
        schedule.assigned_to = data.assignedTo
    if data.price is not None:
        schedule.price = data.price
    if data.isRecurring is not None:
        schedule.is_recurring = data.isRecurring
    if data.recurrencePattern is not None:
        schedule.recurrence_pattern = data.recurrencePattern
    
    db.commit()
    db.refresh(schedule)
    
    client = db.query(Client).filter(Client.id == schedule.client_id).first()
    return ScheduleResponse(
        id=schedule.id,
        clientId=schedule.client_id,
        clientName=client.business_name if client else "Unknown",
        title=schedule.title,
        description=schedule.description,
        serviceType=schedule.service_type,
        scheduledDate=schedule.scheduled_date,
        startTime=schedule.start_time,
        endTime=schedule.end_time,
        durationMinutes=schedule.duration_minutes,
        status=schedule.status,
        notes=schedule.notes,
        address=schedule.address,
        assignedTo=schedule.assigned_to,
        price=schedule.price,
        isRecurring=schedule.is_recurring or False,
        recurrencePattern=schedule.recurrence_pattern,
        createdAt=schedule.created_at
    )


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a schedule"""
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.user_id == current_user.id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    db.delete(schedule)
    db.commit()
    return {"message": "Schedule deleted"}
