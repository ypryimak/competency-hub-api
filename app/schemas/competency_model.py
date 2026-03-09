from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class CompetencyModelCreate(BaseModel):
    name: Optional[str] = None
    profession_id: int


class CompetencyModelUpdate(BaseModel):
    name: Optional[str] = None
    profession_id: Optional[int] = None


class CompetencyModelOut(BaseModel):
    id: int
    user_id: int
    name: Optional[str]
    profession_id: Optional[int]
    min_competency_weight: Optional[float]
    max_competency_rank: Optional[int]
    evaluation_deadline: Optional[datetime]
    status: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class CompetencyModelDetail(CompetencyModelOut):
    profession_name: Optional[str] = None
    experts: list["ModelExpertOut"] = []
    expert_invites: list["ExpertInviteOut"] = []
    criteria: list["CriterionOut"] = []
    alternatives: list["AlternativeOut"] = []


class ModelExpertCreate(BaseModel):
    user_id: int
    rank: int


class ModelExpertUpdate(BaseModel):
    rank: Optional[int] = None


class ModelExpertOut(BaseModel):
    id: int
    model_id: int
    user_id: Optional[int]
    rank: int
    weight: Optional[float]

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class ExpertInviteCreate(BaseModel):
    email: str
    rank: int


class ExpertInviteUpdate(BaseModel):
    email: Optional[str] = None
    rank: Optional[int] = None


class ExpertInviteOut(BaseModel):
    id: int
    model_id: int
    email: str
    rank: int
    token: str
    accepted_by_user_id: Optional[int] = None
    created_at: datetime
    model_name: Optional[str] = None
    profession_id: Optional[int] = None

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class CriterionCreate(BaseModel):
    name: str


class CriterionUpdate(BaseModel):
    name: Optional[str] = None


class CriterionOut(BaseModel):
    id: int
    model_id: int
    name: str
    weight: Optional[float]

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class AlternativeRecommendation(BaseModel):
    competency_id: int
    competency_name: str
    score: float
    already_added: bool


class AlternativeCreate(BaseModel):
    competency_id: int


class AlternativeOut(BaseModel):
    id: int
    model_id: int
    competency_id: int
    competency_name: Optional[str] = None
    weight: Optional[float]
    final_weight: Optional[float]

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class CriterionRankSubmit(BaseModel):
    criterion_id: int
    rank: int


class AlternativeRankSubmit(BaseModel):
    alternative_id: int
    criterion_id: int
    rank: int


class ExpertEvaluationSubmit(BaseModel):
    criterion_ranks: list[CriterionRankSubmit]
    alternative_ranks: list[AlternativeRankSubmit]


class ExpertEvaluationStatus(BaseModel):
    expert_id: int
    criteria_ranked: int
    criteria_total: int
    alternatives_ranked: int
    alternatives_total: int
    is_complete: bool


class OPAResult(BaseModel):
    expert_weights: dict[int, float]
    criterion_weights: dict[int, float]
    alternative_weights: dict[int, float]
    filtered_alternatives: list[AlternativeOut]
    status: str


class ModelSubmitRequest(BaseModel):
    min_competency_weight: Optional[float] = None
    max_competency_rank: Optional[int] = None
    evaluation_deadline: Optional[datetime] = None

    @model_validator(mode="after")
    def at_least_one_filter(self) -> "ModelSubmitRequest":
        if self.min_competency_weight is None and self.max_competency_rank is None:
            raise ValueError(
                "At least one filter is required: min_competency_weight or max_competency_rank"
            )
        return self


CompetencyModelDetail.model_rebuild()
