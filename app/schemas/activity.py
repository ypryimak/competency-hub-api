from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ActivityLogOut(BaseModel):
    id: int
    user_id: int
    entity_type: str
    entity_id: int
    event_type: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
