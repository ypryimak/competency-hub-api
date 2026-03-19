from datetime import datetime
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, EmailStr, Field, computed_field

from app.core.enums import CandidateCVParseStatus, WorkflowStatusName, get_workflow_status_name
from app.schemas.common import UserSummaryOut


class SelectionCreate(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_id: int
    evaluation_deadline: Optional[datetime] = None


class SelectionUpdate(BaseModel):
    evaluation_deadline: Optional[datetime] = None


class SelectionOut(BaseModel):
    id: int
    user_id: int
    model_id: Optional[int]
    evaluation_deadline: Optional[datetime]
    status_code: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("status_code", "status"),
        description="Legacy numeric workflow status code.",
    )
    created_at: datetime

    @computed_field
    @property
    def status(self) -> Optional[WorkflowStatusName]:
        return get_workflow_status_name(self.status_code)

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class SelectionDetail(SelectionOut):
    candidates: list["CandidateSelectionOut"] = []
    experts: list["SelectionExpertDetailOut"] = []
    criteria: list["SelectionCriterionOut"] = []
    expert_invites: list["SelectionExpertInviteOut"] = []


class CandidateCreate(BaseModel):
    name: Optional[str] = None
    email: EmailStr
    profession_id: int


class CandidateOut(BaseModel):
    id: int
    user_id: int
    name: Optional[str]
    email: Optional[str]
    profession_id: int
    cv_file_path: Optional[str]
    cv_original_filename: Optional[str]
    cv_mime_type: Optional[str]
    cv_uploaded_at: Optional[datetime]
    cv_parse_status: CandidateCVParseStatus
    cv_parsed_at: Optional[datetime]
    cv_parse_error: Optional[str]
    matched_competency_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateWithCompetencies(CandidateOut):
    competencies: list["CompetencyShort"] = []


class CompetencyShort(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    link_types: list[str] = []

    model_config = {"from_attributes": True}


class CandidateSelectionOut(BaseModel):
    candidate_id: int
    selection_id: int
    score: Optional[float]
    rank: Optional[int]
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None

    model_config = {"from_attributes": True}


class AddCandidateToSelection(BaseModel):
    candidate_id: int


class CVParseResponse(BaseModel):
    candidate_id: int
    matched_competency_ids: list[int]
    matched_competency_names: list[str]
    unrecognized_tokens: list[str]


class CandidateCVSignedUrl(BaseModel):
    url: str
    expires_in: int


class SelectionExpertCreate(BaseModel):
    user_id: int
    weight: Optional[float] = None


class SelectionExpertOut(BaseModel):
    id: int
    selection_id: int
    user_id: Optional[int]
    weight: Optional[float]
    is_complete: bool = False

    model_config = {"from_attributes": True}


class SelectionExpertDetailOut(SelectionExpertOut):
    user: Optional[UserSummaryOut] = None


class SelectionExpertInviteCreate(BaseModel):
    email: str
    weight: Optional[float] = None


class SelectionExpertInviteUpdate(BaseModel):
    email: Optional[str] = None
    weight: Optional[float] = None


class SelectionExpertInviteOut(BaseModel):
    id: int
    selection_id: int
    email: str
    weight: Optional[float]
    token: str
    accepted_by_user_id: Optional[int] = None
    created_at: datetime
    status: Literal["added", "invited"]
    user: Optional[UserSummaryOut] = None

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class CandidateScoreSubmit(BaseModel):
    candidate_id: int
    selection_criterion_id: int
    score: int


class ExpertScoringSubmit(BaseModel):
    scores: list[CandidateScoreSubmit]


class ExpertScoringStatus(BaseModel):
    expert_id: int
    scored: int
    total: int
    is_complete: bool


class ExpertCandidateScoreOut(BaseModel):
    candidate_id: int
    selection_criterion_id: int
    score: int


class ExpertSelectionDetail(SelectionDetail):
    current_scores: list[ExpertCandidateScoreOut] = []


class CandidateRankOut(BaseModel):
    candidate_id: int
    candidate_name: Optional[str]
    score: float
    rank: int


class VIKORResult(BaseModel):
    ranked_candidates: list[CandidateRankOut]
    status: str


class SelectionCriterionOut(BaseModel):
    id: int
    selection_id: int
    alternative_id: Optional[int] = None
    competency_id: Optional[int] = None
    custom_competency_id: Optional[int] = None
    name: str
    weight: Optional[float] = None

    model_config = {"from_attributes": True, "protected_namespaces": ()}


SelectionDetail.model_rebuild()
CandidateWithCompetencies.model_rebuild()
