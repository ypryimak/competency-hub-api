from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.models import ActivityLog, User
from app.schemas.activity import ActivityLogOut

router = APIRouter(prefix="/activity", tags=["Activity"])


@router.get("", response_model=list[ActivityLogOut])
async def list_activity(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Останні події для поточного користувача."""
    result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.user_id == current_user.id)
        .order_by(desc(ActivityLog.created_at))
        .limit(limit)
    )
    return result.scalars().all()
