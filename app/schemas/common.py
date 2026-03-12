from typing import Optional

from pydantic import BaseModel


class UserSummaryOut(BaseModel):
    id: int
    name: Optional[str] = None
    email: Optional[str] = None

    model_config = {"from_attributes": True}
