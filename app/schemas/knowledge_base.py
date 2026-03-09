from typing import Optional

from pydantic import BaseModel


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


class ProfessionLabelCreate(BaseModel):
    label: str
    label_type: str
    lang: str = "en"


class ProfessionLabelUpdate(BaseModel):
    label: Optional[str] = None
    label_type: Optional[str] = None
    lang: Optional[str] = None


class ProfessionLabelOut(BaseModel):
    id: int
    profession_id: int
    label: str
    label_type: str
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
    competency_type: Optional[str] = None


class CompetencyUpdate(BaseModel):
    esco_uri: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    competency_type: Optional[str] = None


class CompetencyOut(BaseModel):
    id: int
    esco_uri: Optional[str] = None
    name: str
    description: Optional[str] = None
    competency_type: Optional[str] = None

    model_config = {"from_attributes": True}


class CompetencyLabelCreate(BaseModel):
    label: str
    label_type: str
    lang: str = "en"


class CompetencyLabelUpdate(BaseModel):
    label: Optional[str] = None
    label_type: Optional[str] = None
    lang: Optional[str] = None


class CompetencyLabelOut(BaseModel):
    id: int
    competency_id: int
    label: str
    label_type: str
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
    relation_type: str
    weight: Optional[float] = None
    source: Optional[str] = None


class ProfessionCompetencyUpdate(BaseModel):
    weight: Optional[float] = None
    source: Optional[str] = None


class ProfessionCompetencyOut(BaseModel):
    competency_id: int
    competency_name: str
    relation_type: str
    weight: Optional[float] = None
    source: Optional[str] = None

    model_config = {"from_attributes": True}


class CompetencyRelationCreate(BaseModel):
    source_competency_id: int
    target_competency_id: int
    relation_type: str


class CompetencyRelationOut(BaseModel):
    source_competency_id: int
    target_competency_id: int
    relation_type: str
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
