from typing import Optional, List
from datetime import datetime
from sqlmodel import select, col
from warehouse.database import get_session
from warehouse.models import EventLog, EventType

async def create_log_entry(
    event_type: EventType,
    description: str,
    details: Optional[str] = None
) -> EventLog:
    async with get_session() as session:
        log_entry = EventLog(
            event_type=event_type,
            description=description,
            details=details
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        return log_entry

async def get_logs(limit: int = 100, offset: int = 0) -> List[EventLog]:
    async with get_session() as session:
        statement = select(EventLog).order_by(col(EventLog.timestamp).desc()).offset(offset).limit(limit)
        result = await session.execute(statement)
        return result.scalars().all()
