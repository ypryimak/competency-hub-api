from typing import Optional

from pydantic import BaseModel


class UserSummaryOut(BaseModel):
    id: int
    name: Optional[str] = None
    email: Optional[str] = None

    model_config = {"from_attributes": True}


class ExpertWorkspaceSummaryOut(BaseModel):
    has_workspace_access: bool
    pending_invites: int
    open_model_evaluations: int
    open_candidate_scorings: int
    completed_tasks: int
    total_notifications: int
