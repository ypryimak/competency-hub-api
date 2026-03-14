from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_admin
from app.db.session import get_db
from app.models.models import User
from app.schemas.knowledge_base import (
    CompetencyCollectionCreate,
    CompetencyCollectionMemberCreate,
    CompetencyCollectionMemberOut,
    CompetencyCollectionOut,
    CompetencyProfessionOut,
    CompetencyCollectionUpdate,
    CompetencyCreate,
    CompetencyGroupCreate,
    CompetencyGroupMemberCreate,
    CompetencyGroupMemberOut,
    CompetencyGroupOut,
    CompetencyGroupUpdate,
    CompetencyLabelCreate,
    CompetencyLabelOut,
    CompetencyLabelUpdate,
    CompetencyDetailOut,
    CompetencyListOut,
    CompetencyOut,
    CompetencyRelationCreate,
    CompetencyRelationOut,
    CompetencyUpdate,
    JobCompetencyCreate,
    JobCompetencyOut,
    JobCreate,
    JobOut,
    JobUpdate,
    JobWithCompetencies,
    ParseCompetenciesResponse,
    ProfessionCollectionCreate,
    ProfessionCollectionMemberCreate,
    ProfessionCollectionMemberOut,
    ProfessionCollectionOut,
    ProfessionCollectionUpdate,
    ProfessionCompetencyCreate,
    ProfessionCompetencyDetailOut,
    ProfessionCompetencyOut,
    ProfessionCompetencyUpdate,
    ProfessionCreate,
    ProfessionGroupCreate,
    ProfessionGroupOut,
    ProfessionGroupUpdate,
    ProfessionLabelCreate,
    ProfessionLabelOut,
    ProfessionLabelUpdate,
    ProfessionListOut,
    ProfessionOut,
    ProfessionUpdate,
    RecalculateProfessionCompetenciesResponse,
    SimilarProfessionOut,
)
from app.services.knowledge_base_service import knowledge_base_service

TAG_PROFESSION_GROUPS = "Knowledge Base: Profession Groups"
TAG_PROFESSIONS = "Knowledge Base: Professions"
TAG_COMPETENCY_GROUPS = "Knowledge Base: Competency Groups"
TAG_COMPETENCIES = "Knowledge Base: Competencies"
TAG_COMPETENCY_RELATIONS = "Knowledge Base: Competency Relations"
TAG_COMPETENCY_COLLECTIONS = "Knowledge Base: Competency Collections"
TAG_PROFESSION_COLLECTIONS = "Knowledge Base: Profession Collections"
TAG_JOBS = "Knowledge Base: Jobs"

router = APIRouter()
profession_groups_router = APIRouter(tags=[TAG_PROFESSION_GROUPS])
professions_router = APIRouter(tags=[TAG_PROFESSIONS])
competency_groups_router = APIRouter(tags=[TAG_COMPETENCY_GROUPS])
competencies_router = APIRouter(tags=[TAG_COMPETENCIES])
competency_relations_router = APIRouter(tags=[TAG_COMPETENCY_RELATIONS])
competency_collections_router = APIRouter(tags=[TAG_COMPETENCY_COLLECTIONS])
profession_collections_router = APIRouter(tags=[TAG_PROFESSION_COLLECTIONS])
jobs_router = APIRouter(tags=[TAG_JOBS])


@profession_groups_router.get("/profession-groups", response_model=list[ProfessionGroupOut])
async def list_profession_groups(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_profession_groups(db)


@profession_groups_router.get("/profession-groups/{group_id}", response_model=ProfessionGroupOut)
async def get_profession_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_profession_group(db, group_id)


@profession_groups_router.post("/profession-groups", response_model=ProfessionGroupOut, status_code=201)
async def create_profession_group(
    data: ProfessionGroupCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.create_profession_group(db, data)


@profession_groups_router.patch("/profession-groups/{group_id}", response_model=ProfessionGroupOut)
async def update_profession_group(
    group_id: int,
    data: ProfessionGroupUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.update_profession_group(db, group_id, data)


@profession_groups_router.delete("/profession-groups/{group_id}", status_code=204)
async def delete_profession_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_profession_group(db, group_id)


@professions_router.get("/professions")
async def list_professions(
    limit: Optional[int] = Query(None, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    group_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = await knowledge_base_service.get_professions_page(
        db,
        limit=limit,
        offset=offset,
        search=search,
        group_id=group_id,
    )
    return {"items": [ProfessionListOut(**item) for item in items], "total": total}


@professions_router.get("/professions/{profession_id}", response_model=ProfessionOut)
async def get_profession(
    profession_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_profession(db, profession_id)


@professions_router.get("/professions/{profession_id}/similar", response_model=list[SimilarProfessionOut])
async def get_similar_professions(
    profession_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_similar_professions(db, profession_id)


@professions_router.get("/professions/{profession_id}/labels", response_model=list[ProfessionLabelOut])
async def list_profession_labels(
    profession_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_profession_labels(db, profession_id)


@professions_router.post("/professions/{profession_id}/labels", response_model=ProfessionLabelOut, status_code=201)
async def create_profession_label(
    profession_id: int,
    data: ProfessionLabelCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.create_profession_label(db, profession_id, data)


@professions_router.patch("/professions/{profession_id}/labels/{label_id}", response_model=ProfessionLabelOut)
async def update_profession_label(
    profession_id: int,
    label_id: int,
    data: ProfessionLabelUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.update_profession_label(db, profession_id, label_id, data)


@professions_router.delete("/professions/{profession_id}/labels/{label_id}", status_code=204)
async def delete_profession_label(
    profession_id: int,
    label_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_profession_label(db, profession_id, label_id)


@professions_router.get("/professions/{profession_id}/competencies", response_model=list[ProfessionCompetencyDetailOut])
async def get_profession_competencies(
    profession_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_profession_competencies(db, profession_id)


@professions_router.post("/professions/{profession_id}/competencies", response_model=ProfessionCompetencyOut, status_code=201)
async def add_profession_competency(
    profession_id: int,
    data: ProfessionCompetencyCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.add_profession_competency(db, profession_id, data)


@professions_router.patch(
    "/professions/{profession_id}/competencies/{competency_id}/{link_type}",
    response_model=ProfessionCompetencyOut,
)
async def update_profession_competency(
    profession_id: int,
    competency_id: int,
    link_type: str,
    data: ProfessionCompetencyUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.update_profession_competency(
        db,
        profession_id,
        competency_id,
        link_type,
        data,
    )


@professions_router.delete("/professions/{profession_id}/competencies/{competency_id}/{link_type}", status_code=204)
async def delete_profession_competency(
    profession_id: int,
    competency_id: int,
    link_type: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_profession_competency(
        db, profession_id, competency_id, link_type
    )


@professions_router.post("/professions", response_model=ProfessionOut, status_code=201)
async def create_profession(
    data: ProfessionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.create_profession(db, data)


@professions_router.patch("/professions/{profession_id}", response_model=ProfessionOut)
async def update_profession(
    profession_id: int,
    data: ProfessionUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.update_profession(db, profession_id, data)


@professions_router.delete("/professions/{profession_id}", status_code=204)
async def delete_profession(
    profession_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_profession(db, profession_id)


@competency_groups_router.get("/competency-groups", response_model=list[CompetencyGroupOut])
async def list_competency_groups(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_competency_groups(db)


@competency_groups_router.get("/competency-groups/{group_id}", response_model=CompetencyGroupOut)
async def get_competency_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_competency_group(db, group_id)


@competency_groups_router.post("/competency-groups", response_model=CompetencyGroupOut, status_code=201)
async def create_competency_group(
    data: CompetencyGroupCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.create_competency_group(db, data)


@competency_groups_router.patch("/competency-groups/{group_id}", response_model=CompetencyGroupOut)
async def update_competency_group(
    group_id: int,
    data: CompetencyGroupUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.update_competency_group(db, group_id, data)


@competency_groups_router.delete("/competency-groups/{group_id}", status_code=204)
async def delete_competency_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_competency_group(db, group_id)


@competencies_router.get("/competencies")
async def list_competencies(
    limit: Optional[int] = Query(None, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    competency_type: Optional[str] = Query(None),
    group_id: Optional[int] = Query(None),
    collection_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = await knowledge_base_service.get_competencies_page(
        db,
        limit=limit,
        offset=offset,
        search=search,
        competency_type=competency_type,
        group_id=group_id,
        collection_id=collection_id,
    )
    return {"items": [CompetencyListOut(**item) for item in items], "total": total}


@competencies_router.get("/competencies/{competency_id}", response_model=CompetencyDetailOut)
async def get_competency(
    competency_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_competency_detail(db, competency_id)


@competencies_router.get("/competencies/{competency_id}/professions", response_model=list[CompetencyProfessionOut])
async def list_competency_professions(
    competency_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_competency_professions(db, competency_id)


@competencies_router.get("/competencies/{competency_id}/labels", response_model=list[CompetencyLabelOut])
async def list_competency_labels(
    competency_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_competency_labels(db, competency_id)


@competencies_router.post("/competencies/{competency_id}/labels", response_model=CompetencyLabelOut, status_code=201)
async def create_competency_label(
    competency_id: int,
    data: CompetencyLabelCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.create_competency_label(db, competency_id, data)


@competencies_router.patch("/competencies/{competency_id}/labels/{label_id}", response_model=CompetencyLabelOut)
async def update_competency_label(
    competency_id: int,
    label_id: int,
    data: CompetencyLabelUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.update_competency_label(db, competency_id, label_id, data)


@competencies_router.delete("/competencies/{competency_id}/labels/{label_id}", status_code=204)
async def delete_competency_label(
    competency_id: int,
    label_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_competency_label(db, competency_id, label_id)


@competencies_router.get("/competencies/{competency_id}/groups", response_model=list[CompetencyGroupMemberOut])
async def list_competency_group_memberships(
    competency_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_competency_group_memberships(db, competency_id)


@competencies_router.post("/competencies/{competency_id}/groups", response_model=CompetencyGroupMemberOut, status_code=201)
async def add_competency_to_group(
    competency_id: int,
    data: CompetencyGroupMemberCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.add_competency_to_group(db, competency_id, data.group_id)


@competencies_router.delete("/competencies/{competency_id}/groups/{group_id}", status_code=204)
async def remove_competency_from_group(
    competency_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.remove_competency_from_group(db, competency_id, group_id)



@competencies_router.post("/competencies", response_model=CompetencyOut, status_code=201)
async def create_competency(
    data: CompetencyCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.create_competency(db, data)


@competencies_router.patch("/competencies/{competency_id}", response_model=CompetencyOut)
async def update_competency(
    competency_id: int,
    data: CompetencyUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.update_competency(db, competency_id, data)


@competencies_router.delete("/competencies/{competency_id}", status_code=204)
async def delete_competency(
    competency_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_competency(db, competency_id)


@competency_relations_router.get("/competency-relations", response_model=list[CompetencyRelationOut])
async def list_competency_relations(
    competency_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_competency_relations(db, competency_id=competency_id)


@competency_relations_router.post("/competency-relations", response_model=CompetencyRelationOut, status_code=201)
async def create_competency_relation(
    data: CompetencyRelationCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    relation = await knowledge_base_service.create_competency_relation(db, data)
    return CompetencyRelationOut(
        source_competency_id=relation.source_competency_id,
        target_competency_id=relation.target_competency_id,
        relation_type=relation.relation_type,
    )


@competency_relations_router.delete(
    "/competency-relations/{source_competency_id}/{target_competency_id}/{relation_type}",
    status_code=204,
)
async def delete_competency_relation(
    source_competency_id: int,
    target_competency_id: int,
    relation_type: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_competency_relation(
        db, source_competency_id, target_competency_id, relation_type
    )


@competency_collections_router.get("/competency-collections", response_model=list[CompetencyCollectionOut])
async def list_competency_collections(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_competency_collections(db)


@competency_collections_router.get(
    "/competency-collections/{collection_id}",
    response_model=CompetencyCollectionOut,
)
async def get_competency_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_competency_collection(db, collection_id)


@competency_collections_router.post("/competency-collections", response_model=CompetencyCollectionOut, status_code=201)
async def create_competency_collection(
    data: CompetencyCollectionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.create_competency_collection(db, data)


@competency_collections_router.patch("/competency-collections/{collection_id}", response_model=CompetencyCollectionOut)
async def update_competency_collection(
    collection_id: int,
    data: CompetencyCollectionUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.update_competency_collection(db, collection_id, data)


@competency_collections_router.delete("/competency-collections/{collection_id}", status_code=204)
async def delete_competency_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_competency_collection(db, collection_id)


@competency_collections_router.get(
    "/competency-collections/{collection_id}/members",
    response_model=list[CompetencyCollectionMemberOut],
)
async def list_competency_collection_members(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_competency_collection_members(db, collection_id)


@competency_collections_router.post(
    "/competency-collections/{collection_id}/members",
    response_model=CompetencyCollectionMemberOut,
    status_code=201,
)
async def add_competency_collection_member(
    collection_id: int,
    data: CompetencyCollectionMemberCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.add_competency_collection_member(
        db, collection_id, data.competency_id
    )


@competency_collections_router.delete(
    "/competency-collections/{collection_id}/members/{competency_id}",
    status_code=204,
)
async def delete_competency_collection_member(
    collection_id: int,
    competency_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_competency_collection_member(db, collection_id, competency_id)


@profession_collections_router.get("/profession-collections", response_model=list[ProfessionCollectionOut])
async def list_profession_collections(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_profession_collections(db)


@profession_collections_router.get(
    "/profession-collections/{collection_id}",
    response_model=ProfessionCollectionOut,
)
async def get_profession_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_profession_collection(db, collection_id)


@profession_collections_router.post("/profession-collections", response_model=ProfessionCollectionOut, status_code=201)
async def create_profession_collection(
    data: ProfessionCollectionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.create_profession_collection(db, data)


@profession_collections_router.patch("/profession-collections/{collection_id}", response_model=ProfessionCollectionOut)
async def update_profession_collection(
    collection_id: int,
    data: ProfessionCollectionUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.update_profession_collection(db, collection_id, data)


@profession_collections_router.delete("/profession-collections/{collection_id}", status_code=204)
async def delete_profession_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_profession_collection(db, collection_id)


@profession_collections_router.get(
    "/profession-collections/{collection_id}/members",
    response_model=list[ProfessionCollectionMemberOut],
)
async def list_profession_collection_members(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_profession_collection_members(db, collection_id)


@profession_collections_router.post(
    "/profession-collections/{collection_id}/members",
    response_model=ProfessionCollectionMemberOut,
    status_code=201,
)
async def add_profession_collection_member(
    collection_id: int,
    data: ProfessionCollectionMemberCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.add_profession_collection_member(
        db, collection_id, data.profession_id
    )


@profession_collections_router.delete(
    "/profession-collections/{collection_id}/members/{profession_id}",
    status_code=204,
)
async def delete_profession_collection_member(
    collection_id: int,
    profession_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_profession_collection_member(db, collection_id, profession_id)


@jobs_router.get("/jobs", response_model=list[JobOut])
async def list_jobs(
    profession_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_jobs(db, profession_id=profession_id)


@jobs_router.get("/jobs/{job_id}", response_model=JobWithCompetencies)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    job = await knowledge_base_service.get_job(db, job_id)
    return JobWithCompetencies(
        id=job.id,
        title=job.title,
        description=job.description,
        profession_id=job.profession_id,
        competencies=[
            CompetencyOut(
                id=jc.competency.id,
                esco_uri=jc.competency.esco_uri,
                name=jc.competency.name,
                description=jc.competency.description,
                competency_type=jc.competency.competency_type,
            )
            for jc in job.job_competencies
        ],
    )


@jobs_router.get("/jobs/{job_id}/competencies", response_model=list[JobCompetencyOut])
async def list_job_competencies(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await knowledge_base_service.get_job_competencies(db, job_id)


@jobs_router.post("/jobs/{job_id}/competencies", response_model=JobCompetencyOut, status_code=201)
async def add_job_competency(
    job_id: int,
    data: JobCompetencyCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.add_job_competency(db, job_id, data.competency_id)


@jobs_router.delete("/jobs/{job_id}/competencies/{competency_id}", status_code=204)
async def delete_job_competency(
    job_id: int,
    competency_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_job_competency(db, job_id, competency_id)


@jobs_router.post("/jobs", response_model=JobOut, status_code=201)
async def create_job(
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.create_job(db, data)


@jobs_router.patch("/jobs/{job_id}", response_model=JobOut)
async def update_job(
    job_id: int,
    data: JobUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.update_job(db, job_id, data)


@jobs_router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await knowledge_base_service.delete_job(db, job_id)


@jobs_router.post("/jobs/{job_id}/parse-competencies", response_model=ParseCompetenciesResponse)
async def parse_job_competencies(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.parse_job_competencies(db, job_id)


@professions_router.post(
    "/professions/{profession_id}/parse-all-jobs",
    response_model=list[ParseCompetenciesResponse],
)
async def parse_all_jobs_for_profession(
    profession_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.parse_all_jobs_for_profession(db, profession_id)


@professions_router.post(
    "/professions/{profession_id}/recalculate-competencies",
    response_model=RecalculateProfessionCompetenciesResponse,
)
async def recalculate_profession_competencies(
    profession_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await knowledge_base_service.recalculate_profession_competencies(db, profession_id)


router.include_router(profession_groups_router)
router.include_router(professions_router)
router.include_router(competency_groups_router)
router.include_router(competencies_router)
router.include_router(competency_relations_router)
router.include_router(competency_collections_router)
router.include_router(profession_collections_router)
router.include_router(jobs_router)
