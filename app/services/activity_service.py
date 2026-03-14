import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ActivityLog

logger = logging.getLogger(__name__)


class ActivityService:
    async def log(
        self,
        db: AsyncSession,
        user_id: int,
        entity_type: str,
        entity_id: int,
        event_type: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
    ) -> None:
        try:
            entry = ActivityLog(
                user_id=user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                event_type=event_type,
                old_value=old_value,
                new_value=new_value,
            )
            db.add(entry)
        except Exception:
            logger.exception(
                "Failed to log activity for user %s entity %s/%s",
                user_id,
                entity_type,
                entity_id,
            )


activity_service = ActivityService()
