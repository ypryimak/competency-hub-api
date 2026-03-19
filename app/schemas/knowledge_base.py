from typing import Literal, Optional

from pydantic import BaseModel, Field


CompetencyType = Literal["skill/competence", "knowledge"]
LabelType = Literal["preferred", "alternative", "hidden"]
ProfessionCompetencyLinkType = Literal[
    "esco_essential",
    "esco_optional",
    "job_derived",
    "manual",
]
ManualProfessionCompetencyLinkType = Literal["manual"]
CompetencyRelationType = Literal["essential", "optional", "related"]


class ProfessionGroupCreate(BaseModel):
    esco_uri: Optional[str] = None
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    parent_group_id: Optional[int] = None


class ProfessionGroupUpdate(BaseModel):
    esco_uri: Optional[str] = None
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    parent_group_id: Optional[int] = None


class ProfessionGroupOut(BaseModel):
    id: int
    esco_uri: Optional[str] = None
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    parent_group_id: Optional[int] = None

    model_config = {"from_attributes": True}


class ProfessionListOut(BaseModel):
    id: int
    esco_uri: Optional[str] = None
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    profession_group_id: int
    parent_profession_id: Optional[int] = None
    aliases: list[str] = []

    model_config = {"from_attributes": True}


class ProfessionListPageOut(BaseModel):
    items: list["ProfessionListOut"]
    total: int


class ProfessionCreate(BaseModel):
    esco_uri: Optional[str] = None
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    profession_group_id: int
    parent_profession_id: Optional[int] = None


class ProfessionUpdate(BaseModel):
    esco_uri: Optional[str] = None
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    profession_group_id: Optional[int] = None
    parent_profession_id: Optional[int] = None


class ProfessionOut(BaseModel):
    id: int
    esco_uri: Optional[str] = None
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    profession_group_id: int
    parent_profession_id: Optional[int] = None

    model_config = {"from_attributes": True}


class SimilarProfessionOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    profession_group_id: int
    parent_profession_id: Optional[int] = None
    similarity_score: float
    overlap_ratio: float
    shared_competency_count: int
    same_group: bool
    same_parent: bool
    direct_hierarchy_match: bool


class ProfessionLabelCreate(BaseModel):
    label: str
    label_type: LabelType = Field(
        description=(
            "Valid values: preferred, alternative, hidden. "
            "preferred = primary display label, alternative = synonym, "
            "hidden = search-only alias."
        )
    )
    lang: str = "en"

    model_config = {
        "json_schema_extra": {
            "example": {
                "label": "Backend Developer",
                "label_type": "alternative",
                "lang": "en",
            }
        }
    }


class ProfessionLabelUpdate(BaseModel):
    label: Optional[str] = None
    label_type: Optional[LabelType] = Field(
        default=None,
        description=(
            "Valid values: preferred, alternative, hidden. "
            "preferred = primary display label, alternative = synonym, "
            "hidden = search-only alias."
        ),
    )
    lang: Optional[str] = None


class ProfessionLabelOut(BaseModel):
    id: int
    profession_id: int
    label: str
    label_type: LabelType = Field(
        description=(
            "Label classification. Valid values: preferred, alternative, hidden. "
            "preferred = primary display label, alternative = synonym, hidden = search-only alias."
        )
    )
    lang: str

    model_config = {"from_attributes": True}


class CompetencyGroupCreate(BaseModel):
    esco_uri: Optional[str] = None
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    parent_group_id: Optional[int] = None


class CompetencyGroupUpdate(BaseModel):
    esco_uri: Optional[str] = None
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    parent_group_id: Optional[int] = None


class CompetencyGroupOut(BaseModel):
    id: int
    esco_uri: Optional[str] = None
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    parent_group_id: Optional[int] = None

    model_config = {"from_attributes": True}


class CompetencyCreate(BaseModel):
    esco_uri: Optional[str] = None
    name: str
    description: Optional[str] = None
    competency_type: Optional[CompetencyType] = Field(
        default=None,
        description=(
            "Valid values: skill/competence, knowledge. "
            "Use skill/competence for practical abilities and knowledge for conceptual knowledge areas."
        ),
    )


class CompetencyUpdate(BaseModel):
    esco_uri: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    competency_type: Optional[CompetencyType] = Field(
        default=None,
        description=(
            "Valid values: skill/competence, knowledge. "
            "Use skill/competence for practical abilities and knowledge for conceptual knowledge areas."
        ),
    )


class CompetencyOut(BaseModel):
    id: int
    esco_uri: Optional[str] = None
    name: str
    description: Optional[str] = None
    competency_type: Optional[CompetencyType] = Field(
        default=None,
        description=(
            "Valid values: skill/competence, knowledge. "
            "Use skill/competence for practical abilities and knowledge for conceptual knowledge areas."
        ),
    )

    model_config = {"from_attributes": True}


class CompetencyListOut(CompetencyOut):
    aliases: list[str] = []
    group_names: list[str] = []
    collection_names: list[str] = []


class CompetencyListPageOut(BaseModel):
    items: list["CompetencyListOut"]
    total: int


class CompetencyDetailOut(CompetencyOut):
    collections: list["CompetencyCollectionOut"] = []


class CompetencyProfessionOut(BaseModel):
    profession_id: int
    profession_name: str
    profession_group_id: Optional[int]
    profession_group_name: Optional[str] = None
    link_types: list[ProfessionCompetencyLinkType] = Field(
        description=(
            "All link types between this profession and the competency. "
            "Values: esco_essential, esco_optional, job_derived, manual."
        )
    )
    weight: float
    aliases: list[str] = []


class CompetencyLabelCreate(BaseModel):
    label: str
    label_type: LabelType = Field(
        description=(
            "Valid values: preferred, alternative, hidden. "
            "preferred = primary display label, alternative = synonym, "
            "hidden = search-only alias."
        )
    )
    lang: str = "en"

    model_config = {
        "json_schema_extra": {
            "example": {
                "label": "Python programming",
                "label_type": "alternative",
                "lang": "en",
            }
        }
    }


class CompetencyLabelUpdate(BaseModel):
    label: Optional[str] = None
    label_type: Optional[LabelType] = Field(
        default=None,
        description=(
            "Valid values: preferred, alternative, hidden. "
            "preferred = primary display label, alternative = synonym, "
            "hidden = search-only alias."
        ),
    )
    lang: Optional[str] = None


class CompetencyLabelOut(BaseModel):
    id: int
    competency_id: int
    label: str
    label_type: LabelType = Field(
        description=(
            "Label classification. Valid values: preferred, alternative, hidden. "
            "preferred = primary display label, alternative = synonym, hidden = search-only alias."
        )
    )
    lang: str

    model_config = {"from_attributes": True}


class CompetencyGroupMemberCreate(BaseModel):
    group_id: int


class CompetencyGroupMemberOut(BaseModel):
    competency_id: int
    group_id: int

    model_config = {"from_attributes": True}


class ProfessionCompetencyCreate(BaseModel):
    competency_id: int
    link_type: ManualProfessionCompetencyLinkType = Field(
        description=(
            "Valid value: manual. "
            "ESCO and job-derived links are generated by seed and parsing workflows, not by direct API creation."
        )
    )
    weight: Optional[float] = Field(
        default=None,
        description=(
            "Manual weight assigned through the API. "
            "Required for manual links created through this endpoint."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "competency_id": 123,
                "link_type": "manual",
                "weight": 0.85,
            }
        }
    }


class ProfessionCompetencyDetailOut(BaseModel):
    competency_id: int
    competency_name: str
    competency_type: Optional[str] = None
    aliases: list[str] = []
    group_names: list[str] = []
    link_types: list[ProfessionCompetencyLinkType]
    weight: float


class ProfessionCompetencyUpdate(BaseModel):
    weight: Optional[float] = Field(
        default=None,
        description="Only manual links can be updated through the API. Provide the manual weight.",
    )


class ProfessionCompetencyOut(BaseModel):
    competency_id: int
    competency_name: str
    link_type: ProfessionCompetencyLinkType = Field(
        description=(
            "Valid values: esco_essential, esco_optional, job_derived, manual. "
            "esco_essential and esco_optional come from the ESCO dataset, "
            "job_derived is recalculated from parsed vacancies, and manual is added by users through the API."
        )
    )
    weight: Optional[float] = None

    model_config = {"from_attributes": True}


class CompetencyRelationCreate(BaseModel):
    source_competency_id: int
    target_competency_id: int
    relation_type: CompetencyRelationType = Field(
        description=(
            "Valid values: essential, optional, related. "
            "essential and optional come from ESCO-like semantic links; related is a generic custom relation."
        )
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "source_competency_id": 101,
                "target_competency_id": 202,
                "relation_type": "related",
            }
        }
    }


class CompetencyRelationOut(BaseModel):
    source_competency_id: int
    target_competency_id: int
    relation_type: CompetencyRelationType = Field(
        description=(
            "Valid values: essential, optional, related. "
            "essential and optional come from ESCO-like semantic links; related is a generic custom relation."
        )
    )
    source_competency_name: Optional[str] = None
    target_competency_name: Optional[str] = None

    model_config = {"from_attributes": True}


class CompetencyCollectionCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class CompetencyCollectionUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class CompetencyCollectionOut(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class CompetencyCollectionMemberCreate(BaseModel):
    competency_id: int


class CompetencyCollectionMemberOut(BaseModel):
    collection_id: int
    competency_id: int

    model_config = {"from_attributes": True}


class ProfessionCollectionCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class ProfessionCollectionUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class ProfessionCollectionOut(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class ProfessionCollectionMemberCreate(BaseModel):
    profession_id: int


class ProfessionCollectionMemberOut(BaseModel):
    collection_id: int
    profession_id: int

    model_config = {"from_attributes": True}


class JobCreate(BaseModel):
    title: str
    description: str
    profession_id: int


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    profession_id: Optional[int] = None


class JobOut(BaseModel):
    id: int
    title: str
    description: str
    profession_id: int

    model_config = {"from_attributes": True}


class JobCompetencyCreate(BaseModel):
    competency_id: int


class JobCompetencyOut(BaseModel):
    job_id: int
    competency_id: int
    competency_name: Optional[str] = None

    model_config = {"from_attributes": True}


class JobWithCompetencies(JobOut):
    competencies: list[CompetencyOut] = []


class ParseCompetenciesRequest(BaseModel):
    text: str


class ParseCompetenciesResponse(BaseModel):
    matched_competency_ids: list[int]
    matched_competency_names: list[str]
    unrecognized_tokens: list[str]


class RecalculateProfessionCompetenciesResponse(BaseModel):
    profession_id: int
    updated_count: int
