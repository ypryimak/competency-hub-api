from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import aliased, selectinload

from app.models.models import (
    Competency,
    CompetencyCollection,
    CompetencyCollectionMember,
    CompetencyGroup,
    CompetencyGroupMember,
    CompetencyLabel,
    CompetencyRelation,
    Job,
    JobCompetency,
    Profession,
    ProfessionCollection,
    ProfessionCollectionMember,
    ProfessionCompetency,
    ProfessionGroup,
    ProfessionLabel,
)
from app.schemas.knowledge_base import (
    CompetencyCollectionCreate,
    CompetencyCollectionUpdate,
    CompetencyCreate,
    CompetencyGroupCreate,
    CompetencyGroupUpdate,
    CompetencyLabelCreate,
    CompetencyLabelUpdate,
    CompetencyRelationCreate,
    CompetencyUpdate,
    JobCreate,
    JobUpdate,
    ParseCompetenciesResponse,
    ProfessionCollectionCreate,
    ProfessionCollectionUpdate,
    ProfessionCompetencyCreate,
    ProfessionCompetencyUpdate,
    ProfessionCreate,
    ProfessionGroupCreate,
    ProfessionGroupUpdate,
    ProfessionLabelCreate,
    ProfessionLabelUpdate,
    ProfessionUpdate,
    RecalculateProfessionCompetenciesResponse,
)
from app.services.document_processing_service import document_processing_service


LINK_TYPE_ESCO_ESSENTIAL = "esco_essential"
LINK_TYPE_ESCO_OPTIONAL = "esco_optional"
LINK_TYPE_JOB_DERIVED = "job_derived"
LINK_TYPE_MANUAL = "manual"

EDITABLE_LINK_TYPES = {LINK_TYPE_MANUAL}


class KnowledgeBaseService:
    async def get_profession_groups(self, db: AsyncSession) -> Sequence[ProfessionGroup]:
        result = await db.execute(select(ProfessionGroup).order_by(ProfessionGroup.name))
        return result.scalars().all()

    async def get_profession_group(self, db: AsyncSession, group_id: int) -> ProfessionGroup:
        result = await db.execute(select(ProfessionGroup).where(ProfessionGroup.id == group_id))
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Profession group not found")
        return obj

    async def create_profession_group(
        self, db: AsyncSession, data: ProfessionGroupCreate
    ) -> ProfessionGroup:
        if data.parent_group_id is not None:
            await self.get_profession_group(db, data.parent_group_id)
        obj = ProfessionGroup(
            esco_uri=data.esco_uri or f"manual:profession-group:{data.name.lower()}",
            code=data.code,
            name=data.name,
            description=data.description,
            parent_group_id=data.parent_group_id,
        )
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def update_profession_group(
        self, db: AsyncSession, group_id: int, data: ProfessionGroupUpdate
    ) -> ProfessionGroup:
        obj = await self.get_profession_group(db, group_id)
        if data.parent_group_id is not None:
            await self.get_profession_group(db, data.parent_group_id)
            obj.parent_group_id = data.parent_group_id
        if data.esco_uri is not None:
            obj.esco_uri = data.esco_uri
        if data.code is not None:
            obj.code = data.code
        if data.name is not None:
            obj.name = data.name
        if data.description is not None:
            obj.description = data.description
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_profession_group(self, db: AsyncSession, group_id: int) -> None:
        await db.delete(await self.get_profession_group(db, group_id))

    async def get_professions(self, db: AsyncSession) -> Sequence[Profession]:
        result = await db.execute(select(Profession).order_by(Profession.name))
        return result.scalars().all()

    async def get_profession(self, db: AsyncSession, profession_id: int) -> Profession:
        result = await db.execute(
            select(Profession)
            .where(Profession.id == profession_id)
            .options(
                selectinload(Profession.profession_competencies),
                selectinload(Profession.labels),
                selectinload(Profession.collection_memberships),
            )
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Profession not found")
        return obj

    async def create_profession(self, db: AsyncSession, data: ProfessionCreate) -> Profession:
        await self.get_profession_group(db, data.profession_group_id)
        if data.parent_profession_id is not None:
            await self.get_profession(db, data.parent_profession_id)
        obj = Profession(
            esco_uri=data.esco_uri or f"manual:profession:{data.name.lower()}",
            code=data.code,
            name=data.name,
            description=data.description,
            profession_group_id=data.profession_group_id,
            parent_profession_id=data.parent_profession_id,
        )
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def update_profession(
        self, db: AsyncSession, profession_id: int, data: ProfessionUpdate
    ) -> Profession:
        obj = await self.get_profession(db, profession_id)
        if data.profession_group_id is not None:
            await self.get_profession_group(db, data.profession_group_id)
            obj.profession_group_id = data.profession_group_id
        if data.parent_profession_id is not None:
            await self.get_profession(db, data.parent_profession_id)
            obj.parent_profession_id = data.parent_profession_id
        if data.esco_uri is not None:
            obj.esco_uri = data.esco_uri
        if data.code is not None:
            obj.code = data.code
        if data.name is not None:
            obj.name = data.name
        if data.description is not None:
            obj.description = data.description
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_profession(self, db: AsyncSession, profession_id: int) -> None:
        await db.delete(await self.get_profession(db, profession_id))

    async def get_profession_labels(
        self, db: AsyncSession, profession_id: int
    ) -> Sequence[ProfessionLabel]:
        await self.get_profession(db, profession_id)
        result = await db.execute(
            select(ProfessionLabel)
            .where(ProfessionLabel.profession_id == profession_id)
            .order_by(ProfessionLabel.lang, ProfessionLabel.label_type, ProfessionLabel.label)
        )
        return result.scalars().all()

    async def get_profession_label(self, db: AsyncSession, label_id: int) -> ProfessionLabel:
        result = await db.execute(select(ProfessionLabel).where(ProfessionLabel.id == label_id))
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Profession label not found")
        return obj

    async def create_profession_label(
        self, db: AsyncSession, profession_id: int, data: ProfessionLabelCreate
    ) -> ProfessionLabel:
        await self.get_profession(db, profession_id)
        await self._ensure_missing(
            db,
            select(ProfessionLabel).where(
                ProfessionLabel.profession_id == profession_id,
                ProfessionLabel.label == data.label,
                ProfessionLabel.label_type == data.label_type,
                ProfessionLabel.lang == data.lang,
            ),
            "Profession label already exists",
        )
        obj = ProfessionLabel(
            profession_id=profession_id,
            label=data.label,
            label_type=data.label_type,
            lang=data.lang,
        )
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def update_profession_label(
        self, db: AsyncSession, profession_id: int, label_id: int, data: ProfessionLabelUpdate
    ) -> ProfessionLabel:
        await self.get_profession(db, profession_id)
        obj = await self.get_profession_label(db, label_id)
        if obj.profession_id != profession_id:
            raise HTTPException(status_code=404, detail="Profession label not found")
        if data.label is not None:
            obj.label = data.label
        if data.label_type is not None:
            obj.label_type = data.label_type
        if data.lang is not None:
            obj.lang = data.lang
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_profession_label(self, db: AsyncSession, profession_id: int, label_id: int) -> None:
        await self.get_profession(db, profession_id)
        obj = await self.get_profession_label(db, label_id)
        if obj.profession_id != profession_id:
            raise HTTPException(status_code=404, detail="Profession label not found")
        await db.delete(obj)

    async def get_competency_groups(self, db: AsyncSession) -> Sequence[CompetencyGroup]:
        result = await db.execute(select(CompetencyGroup).order_by(CompetencyGroup.name))
        return result.scalars().all()

    async def get_competency_group(self, db: AsyncSession, group_id: int) -> CompetencyGroup:
        result = await db.execute(select(CompetencyGroup).where(CompetencyGroup.id == group_id))
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Competency group not found")
        return obj

    async def create_competency_group(
        self, db: AsyncSession, data: CompetencyGroupCreate
    ) -> CompetencyGroup:
        if data.parent_group_id is not None:
            await self.get_competency_group(db, data.parent_group_id)
        obj = CompetencyGroup(
            esco_uri=data.esco_uri or f"manual:competency-group:{data.name.lower()}",
            code=data.code,
            name=data.name,
            description=data.description,
            parent_group_id=data.parent_group_id,
        )
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def update_competency_group(
        self, db: AsyncSession, group_id: int, data: CompetencyGroupUpdate
    ) -> CompetencyGroup:
        obj = await self.get_competency_group(db, group_id)
        if data.parent_group_id is not None:
            await self.get_competency_group(db, data.parent_group_id)
            obj.parent_group_id = data.parent_group_id
        if data.esco_uri is not None:
            obj.esco_uri = data.esco_uri
        if data.code is not None:
            obj.code = data.code
        if data.name is not None:
            obj.name = data.name
        if data.description is not None:
            obj.description = data.description
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_competency_group(self, db: AsyncSession, group_id: int) -> None:
        await db.delete(await self.get_competency_group(db, group_id))

    async def get_competencies(self, db: AsyncSession) -> Sequence[Competency]:
        result = await db.execute(select(Competency).order_by(Competency.name))
        return result.scalars().all()

    async def get_competency(self, db: AsyncSession, competency_id: int) -> Competency:
        result = await db.execute(select(Competency).where(Competency.id == competency_id))
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Competency not found")
        return obj

    async def create_competency(self, db: AsyncSession, data: CompetencyCreate) -> Competency:
        obj = Competency(
            esco_uri=data.esco_uri,
            name=data.name,
            description=data.description,
            competency_type=data.competency_type,
        )
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def update_competency(
        self, db: AsyncSession, competency_id: int, data: CompetencyUpdate
    ) -> Competency:
        obj = await self.get_competency(db, competency_id)
        if data.esco_uri is not None:
            obj.esco_uri = data.esco_uri
        if data.name is not None:
            obj.name = data.name
        if data.description is not None:
            obj.description = data.description
        if data.competency_type is not None:
            obj.competency_type = data.competency_type
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_competency(self, db: AsyncSession, competency_id: int) -> None:
        await db.delete(await self.get_competency(db, competency_id))

    async def get_competency_labels(
        self, db: AsyncSession, competency_id: int
    ) -> Sequence[CompetencyLabel]:
        await self.get_competency(db, competency_id)
        result = await db.execute(
            select(CompetencyLabel)
            .where(CompetencyLabel.competency_id == competency_id)
            .order_by(CompetencyLabel.lang, CompetencyLabel.label_type, CompetencyLabel.label)
        )
        return result.scalars().all()

    async def get_competency_label(self, db: AsyncSession, label_id: int) -> CompetencyLabel:
        result = await db.execute(select(CompetencyLabel).where(CompetencyLabel.id == label_id))
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Competency label not found")
        return obj

    async def create_competency_label(
        self, db: AsyncSession, competency_id: int, data: CompetencyLabelCreate
    ) -> CompetencyLabel:
        await self.get_competency(db, competency_id)
        await self._ensure_missing(
            db,
            select(CompetencyLabel).where(
                CompetencyLabel.competency_id == competency_id,
                CompetencyLabel.label == data.label,
                CompetencyLabel.label_type == data.label_type,
                CompetencyLabel.lang == data.lang,
            ),
            "Competency label already exists",
        )
        obj = CompetencyLabel(
            competency_id=competency_id,
            label=data.label,
            label_type=data.label_type,
            lang=data.lang,
        )
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def update_competency_label(
        self, db: AsyncSession, competency_id: int, label_id: int, data: CompetencyLabelUpdate
    ) -> CompetencyLabel:
        await self.get_competency(db, competency_id)
        obj = await self.get_competency_label(db, label_id)
        if obj.competency_id != competency_id:
            raise HTTPException(status_code=404, detail="Competency label not found")
        if data.label is not None:
            obj.label = data.label
        if data.label_type is not None:
            obj.label_type = data.label_type
        if data.lang is not None:
            obj.lang = data.lang
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_competency_label(self, db: AsyncSession, competency_id: int, label_id: int) -> None:
        await self.get_competency(db, competency_id)
        obj = await self.get_competency_label(db, label_id)
        if obj.competency_id != competency_id:
            raise HTTPException(status_code=404, detail="Competency label not found")
        await db.delete(obj)

    async def get_competency_group_memberships(
        self, db: AsyncSession, competency_id: int
    ) -> Sequence[CompetencyGroupMember]:
        await self.get_competency(db, competency_id)
        result = await db.execute(
            select(CompetencyGroupMember)
            .where(CompetencyGroupMember.competency_id == competency_id)
            .order_by(CompetencyGroupMember.group_id)
        )
        return result.scalars().all()

    async def add_competency_to_group(
        self, db: AsyncSession, competency_id: int, group_id: int
    ) -> CompetencyGroupMember:
        await self.get_competency(db, competency_id)
        await self.get_competency_group(db, group_id)
        await self._ensure_missing(
            db,
            select(CompetencyGroupMember).where(
                CompetencyGroupMember.competency_id == competency_id,
                CompetencyGroupMember.group_id == group_id,
            ),
            "Competency group membership already exists",
        )
        obj = CompetencyGroupMember(competency_id=competency_id, group_id=group_id)
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def remove_competency_from_group(
        self, db: AsyncSession, competency_id: int, group_id: int
    ) -> None:
        result = await db.execute(
            select(CompetencyGroupMember).where(
                CompetencyGroupMember.competency_id == competency_id,
                CompetencyGroupMember.group_id == group_id,
            )
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Competency group membership not found")
        await db.delete(obj)

    async def get_profession_competencies(self, db: AsyncSession, profession_id: int) -> list[dict]:
        await self.get_profession(db, profession_id)
        result = await db.execute(
            select(ProfessionCompetency, Competency.name)
            .join(Competency, Competency.id == ProfessionCompetency.competency_id)
            .where(ProfessionCompetency.profession_id == profession_id)
        )
        rows = [self._profession_competency_row_to_dict(row) for row in result.all()]
        return sorted(rows, key=self._profession_competency_sort_key)

    async def add_profession_competency(
        self, db: AsyncSession, profession_id: int, data: ProfessionCompetencyCreate
    ) -> dict:
        await self.get_profession(db, profession_id)
        await self.get_competency(db, data.competency_id)
        if data.link_type != LINK_TYPE_MANUAL:
            raise HTTPException(
                status_code=400,
                detail="Only manual profession competency links can be created through the API",
            )
        await self._ensure_missing(
            db,
            select(ProfessionCompetency).where(
                ProfessionCompetency.profession_id == profession_id,
                ProfessionCompetency.competency_id == data.competency_id,
                ProfessionCompetency.link_type == data.link_type,
            ),
            "Profession competency link already exists",
        )
        self._validate_profession_competency_weight(data.link_type, data.weight)
        obj = ProfessionCompetency(
            profession_id=profession_id,
            competency_id=data.competency_id,
            link_type=data.link_type,
            weight=data.weight,
        )
        db.add(obj)
        await db.flush()
        return await self._get_profession_competency_dict(
            db, profession_id, data.competency_id, data.link_type
        )

    async def update_profession_competency(
        self,
        db: AsyncSession,
        profession_id: int,
        competency_id: int,
        link_type: str,
        data: ProfessionCompetencyUpdate,
    ) -> dict:
        obj = await self._get_profession_competency(
            db, profession_id, competency_id, link_type
        )
        if obj.link_type not in EDITABLE_LINK_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Only manual profession competency links can be updated",
            )
        if data.weight is not None:
            obj.weight = data.weight
        self._validate_profession_competency_weight(obj.link_type, obj.weight)
        await db.flush()
        return await self._get_profession_competency_dict(
            db, profession_id, competency_id, link_type
        )

    async def delete_profession_competency(
        self, db: AsyncSession, profession_id: int, competency_id: int, link_type: str
    ) -> None:
        await db.delete(
            await self._get_profession_competency(db, profession_id, competency_id, link_type)
        )

    async def get_competency_relations(
        self, db: AsyncSession, competency_id: int | None = None
    ) -> list[dict]:
        source_competency = aliased(Competency)
        target_competency = aliased(Competency)
        query = (
            select(
                CompetencyRelation,
                source_competency.name.label("source_name"),
                target_competency.name.label("target_name"),
            )
            .join(source_competency, source_competency.id == CompetencyRelation.source_competency_id)
            .join(target_competency, target_competency.id == CompetencyRelation.target_competency_id)
            .order_by(
                CompetencyRelation.relation_type,
                source_competency.name,
                target_competency.name,
            )
        )
        if competency_id is not None:
            await self.get_competency(db, competency_id)
            query = query.where(
                or_(
                    CompetencyRelation.source_competency_id == competency_id,
                    CompetencyRelation.target_competency_id == competency_id,
                )
            )
        result = await db.execute(query)
        return [
            {
                "source_competency_id": row.CompetencyRelation.source_competency_id,
                "target_competency_id": row.CompetencyRelation.target_competency_id,
                "relation_type": row.CompetencyRelation.relation_type,
                "source_competency_name": row.source_name,
                "target_competency_name": row.target_name,
            }
            for row in result.all()
        ]

    async def create_competency_relation(
        self, db: AsyncSession, data: CompetencyRelationCreate
    ) -> CompetencyRelation:
        await self.get_competency(db, data.source_competency_id)
        await self.get_competency(db, data.target_competency_id)
        await self._ensure_missing(
            db,
            select(CompetencyRelation).where(
                CompetencyRelation.source_competency_id == data.source_competency_id,
                CompetencyRelation.target_competency_id == data.target_competency_id,
                CompetencyRelation.relation_type == data.relation_type,
            ),
            "Competency relation already exists",
        )
        obj = CompetencyRelation(
            source_competency_id=data.source_competency_id,
            target_competency_id=data.target_competency_id,
            relation_type=data.relation_type,
        )
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_competency_relation(
        self, db: AsyncSession, source_competency_id: int, target_competency_id: int, relation_type: str
    ) -> None:
        result = await db.execute(
            select(CompetencyRelation).where(
                CompetencyRelation.source_competency_id == source_competency_id,
                CompetencyRelation.target_competency_id == target_competency_id,
                CompetencyRelation.relation_type == relation_type,
            )
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Competency relation not found")
        await db.delete(obj)

    async def get_competency_collections(self, db: AsyncSession) -> Sequence[CompetencyCollection]:
        result = await db.execute(select(CompetencyCollection).order_by(CompetencyCollection.name))
        return result.scalars().all()

    async def get_competency_collection(
        self, db: AsyncSession, collection_id: int
    ) -> CompetencyCollection:
        result = await db.execute(
            select(CompetencyCollection).where(CompetencyCollection.id == collection_id)
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Competency collection not found")
        return obj

    async def create_competency_collection(
        self, db: AsyncSession, data: CompetencyCollectionCreate
    ) -> CompetencyCollection:
        obj = CompetencyCollection(code=data.code, name=data.name, description=data.description)
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def update_competency_collection(
        self, db: AsyncSession, collection_id: int, data: CompetencyCollectionUpdate
    ) -> CompetencyCollection:
        obj = await self.get_competency_collection(db, collection_id)
        if data.code is not None:
            obj.code = data.code
        if data.name is not None:
            obj.name = data.name
        if data.description is not None:
            obj.description = data.description
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_competency_collection(self, db: AsyncSession, collection_id: int) -> None:
        await db.delete(await self.get_competency_collection(db, collection_id))

    async def get_competency_collection_members(
        self, db: AsyncSession, collection_id: int
    ) -> Sequence[CompetencyCollectionMember]:
        await self.get_competency_collection(db, collection_id)
        result = await db.execute(
            select(CompetencyCollectionMember)
            .where(CompetencyCollectionMember.collection_id == collection_id)
            .order_by(CompetencyCollectionMember.competency_id)
        )
        return result.scalars().all()

    async def add_competency_collection_member(
        self, db: AsyncSession, collection_id: int, competency_id: int
    ) -> CompetencyCollectionMember:
        await self.get_competency_collection(db, collection_id)
        await self.get_competency(db, competency_id)
        await self._ensure_missing(
            db,
            select(CompetencyCollectionMember).where(
                CompetencyCollectionMember.collection_id == collection_id,
                CompetencyCollectionMember.competency_id == competency_id,
            ),
            "Competency collection membership already exists",
        )
        obj = CompetencyCollectionMember(collection_id=collection_id, competency_id=competency_id)
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_competency_collection_member(
        self, db: AsyncSession, collection_id: int, competency_id: int
    ) -> None:
        result = await db.execute(
            select(CompetencyCollectionMember).where(
                CompetencyCollectionMember.collection_id == collection_id,
                CompetencyCollectionMember.competency_id == competency_id,
            )
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Competency collection membership not found")
        await db.delete(obj)

    async def get_profession_collections(self, db: AsyncSession) -> Sequence[ProfessionCollection]:
        result = await db.execute(select(ProfessionCollection).order_by(ProfessionCollection.name))
        return result.scalars().all()

    async def get_profession_collection(
        self, db: AsyncSession, collection_id: int
    ) -> ProfessionCollection:
        result = await db.execute(
            select(ProfessionCollection).where(ProfessionCollection.id == collection_id)
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Profession collection not found")
        return obj

    async def create_profession_collection(
        self, db: AsyncSession, data: ProfessionCollectionCreate
    ) -> ProfessionCollection:
        obj = ProfessionCollection(code=data.code, name=data.name, description=data.description)
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def update_profession_collection(
        self, db: AsyncSession, collection_id: int, data: ProfessionCollectionUpdate
    ) -> ProfessionCollection:
        obj = await self.get_profession_collection(db, collection_id)
        if data.code is not None:
            obj.code = data.code
        if data.name is not None:
            obj.name = data.name
        if data.description is not None:
            obj.description = data.description
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_profession_collection(self, db: AsyncSession, collection_id: int) -> None:
        await db.delete(await self.get_profession_collection(db, collection_id))

    async def get_profession_collection_members(
        self, db: AsyncSession, collection_id: int
    ) -> Sequence[ProfessionCollectionMember]:
        await self.get_profession_collection(db, collection_id)
        result = await db.execute(
            select(ProfessionCollectionMember)
            .where(ProfessionCollectionMember.collection_id == collection_id)
            .order_by(ProfessionCollectionMember.profession_id)
        )
        return result.scalars().all()

    async def add_profession_collection_member(
        self, db: AsyncSession, collection_id: int, profession_id: int
    ) -> ProfessionCollectionMember:
        await self.get_profession_collection(db, collection_id)
        await self.get_profession(db, profession_id)
        await self._ensure_missing(
            db,
            select(ProfessionCollectionMember).where(
                ProfessionCollectionMember.collection_id == collection_id,
                ProfessionCollectionMember.profession_id == profession_id,
            ),
            "Profession collection membership already exists",
        )
        obj = ProfessionCollectionMember(collection_id=collection_id, profession_id=profession_id)
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_profession_collection_member(
        self, db: AsyncSession, collection_id: int, profession_id: int
    ) -> None:
        result = await db.execute(
            select(ProfessionCollectionMember).where(
                ProfessionCollectionMember.collection_id == collection_id,
                ProfessionCollectionMember.profession_id == profession_id,
            )
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Profession collection membership not found")
        await db.delete(obj)

    async def get_jobs(self, db: AsyncSession, profession_id: int | None = None) -> Sequence[Job]:
        query = select(Job).order_by(Job.id)
        if profession_id:
            query = query.where(Job.profession_id == profession_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_job(self, db: AsyncSession, job_id: int) -> Job:
        result = await db.execute(
            select(Job)
            .where(Job.id == job_id)
            .options(selectinload(Job.job_competencies).selectinload(JobCompetency.competency))
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Job not found")
        return obj

    async def create_job(self, db: AsyncSession, data: JobCreate) -> Job:
        await self.get_profession(db, data.profession_id)
        obj = Job(title=data.title, description=data.description, profession_id=data.profession_id)
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def update_job(self, db: AsyncSession, job_id: int, data: JobUpdate) -> Job:
        obj = await self.get_job(db, job_id)
        if data.title is not None:
            obj.title = data.title
        if data.description is not None:
            obj.description = data.description
        if data.profession_id is not None:
            await self.get_profession(db, data.profession_id)
            obj.profession_id = data.profession_id
        await db.flush()
        await db.refresh(obj)
        return obj

    async def delete_job(self, db: AsyncSession, job_id: int) -> None:
        await db.delete(await self.get_job(db, job_id))

    async def get_job_competencies(self, db: AsyncSession, job_id: int) -> list[dict]:
        await self.get_job(db, job_id)
        result = await db.execute(
            select(JobCompetency, Competency.name)
            .join(Competency, Competency.id == JobCompetency.competency_id)
            .where(JobCompetency.job_id == job_id)
            .order_by(Competency.name)
        )
        return [
            {
                "job_id": row.JobCompetency.job_id,
                "competency_id": row.JobCompetency.competency_id,
                "competency_name": row.name,
            }
            for row in result.all()
        ]

    async def add_job_competency(self, db: AsyncSession, job_id: int, competency_id: int) -> dict:
        await self.get_job(db, job_id)
        await self.get_competency(db, competency_id)
        await self._ensure_missing(
            db,
            select(JobCompetency).where(
                JobCompetency.job_id == job_id,
                JobCompetency.competency_id == competency_id,
            ),
            "Job competency already exists",
        )
        obj = JobCompetency(job_id=job_id, competency_id=competency_id)
        db.add(obj)
        await db.flush()
        result = await db.execute(
            select(JobCompetency, Competency.name)
            .join(Competency, Competency.id == JobCompetency.competency_id)
            .where(JobCompetency.job_id == job_id, JobCompetency.competency_id == competency_id)
        )
        row = result.one()
        return {
            "job_id": row.JobCompetency.job_id,
            "competency_id": row.JobCompetency.competency_id,
            "competency_name": row.name,
        }

    async def delete_job_competency(self, db: AsyncSession, job_id: int, competency_id: int) -> None:
        result = await db.execute(
            select(JobCompetency).where(
                JobCompetency.job_id == job_id,
                JobCompetency.competency_id == competency_id,
            )
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Job competency not found")
        await db.delete(obj)

    async def parse_job_competencies(self, db: AsyncSession, job_id: int) -> ParseCompetenciesResponse:
        job = await self.get_job(db, job_id)
        competency_map = await self._get_competency_map(db)
        return await self._parse_job_with_competency_map(db, job, competency_map)

    async def parse_all_jobs_for_profession(
        self, db: AsyncSession, profession_id: int
    ) -> list[ParseCompetenciesResponse]:
        jobs = await self.get_jobs(db, profession_id=profession_id)
        competency_map = await self._get_competency_map(db)
        results = []
        for job in jobs:
            job_id = job.id
            try:
                results.append(
                    await self._parse_job_with_competency_map(db, job, competency_map)
                )
            except Exception:
                await db.rollback()
                results.append(
                    ParseCompetenciesResponse(
                        matched_competency_ids=[],
                        matched_competency_names=[],
                        unrecognized_tokens=[f"[error parsing job {job_id}]"],
                    )
                )
        return results

    async def recalculate_profession_competencies(
        self, db: AsyncSession, profession_id: int
    ) -> RecalculateProfessionCompetenciesResponse:
        await self.get_profession(db, profession_id)
        total_result = await db.execute(
            select(func.count(Job.id)).where(Job.profession_id == profession_id)
        )
        total_jobs = total_result.scalar_one() or 0
        if total_jobs == 0:
            return RecalculateProfessionCompetenciesResponse(profession_id=profession_id, updated_count=0)
        counts_result = await db.execute(
            select(
                JobCompetency.competency_id,
                func.count(JobCompetency.job_id).label("cnt"),
            )
            .join(Job, Job.id == JobCompetency.job_id)
            .where(Job.profession_id == profession_id)
            .group_by(JobCompetency.competency_id)
        )
        competency_counts = counts_result.all()
        await db.execute(
            delete(ProfessionCompetency).where(
                ProfessionCompetency.profession_id == profession_id,
                ProfessionCompetency.link_type == LINK_TYPE_JOB_DERIVED,
            )
        )
        for row in competency_counts:
            db.add(
                ProfessionCompetency(
                    profession_id=profession_id,
                    competency_id=row.competency_id,
                    link_type=LINK_TYPE_JOB_DERIVED,
                    weight=round(row.cnt / total_jobs, 4),
                )
            )
        await db.flush()
        return RecalculateProfessionCompetenciesResponse(
            profession_id=profession_id,
            updated_count=len(competency_counts),
        )

    async def _get_profession_competency(
        self, db: AsyncSession, profession_id: int, competency_id: int, link_type: str
    ) -> ProfessionCompetency:
        result = await db.execute(
            select(ProfessionCompetency).where(
                ProfessionCompetency.profession_id == profession_id,
                ProfessionCompetency.competency_id == competency_id,
                ProfessionCompetency.link_type == link_type,
            )
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Profession competency link not found")
        return obj

    async def _get_profession_competency_dict(
        self, db: AsyncSession, profession_id: int, competency_id: int, link_type: str
    ) -> dict:
        result = await db.execute(
            select(ProfessionCompetency, Competency.name)
            .join(Competency, Competency.id == ProfessionCompetency.competency_id)
            .where(
                ProfessionCompetency.profession_id == profession_id,
                ProfessionCompetency.competency_id == competency_id,
                ProfessionCompetency.link_type == link_type,
            )
        )
        return self._profession_competency_row_to_dict(result.one())

    def _profession_competency_row_to_dict(self, row) -> dict:
        return {
            "competency_id": row.ProfessionCompetency.competency_id,
            "competency_name": row.name,
            "link_type": row.ProfessionCompetency.link_type,
            "weight": None if row.ProfessionCompetency.weight is None else float(row.ProfessionCompetency.weight),
        }

    def _profession_competency_sort_key(self, row: dict) -> tuple[float, str, str]:
        weight = row["weight"] if row["weight"] is not None else 0.0
        return (
            -self._profession_competency_score(row["link_type"], weight),
            row["link_type"],
            row["competency_name"],
        )

    def _profession_competency_score(self, link_type: str, weight: float) -> float:
        base_scores = {
            LINK_TYPE_ESCO_ESSENTIAL: 2.0,
            LINK_TYPE_MANUAL: 1.5,
            LINK_TYPE_ESCO_OPTIONAL: 1.0,
            LINK_TYPE_JOB_DERIVED: 0.0,
        }
        return base_scores.get(link_type, 0.0) + float(weight or 0.0)

    def _validate_profession_competency_weight(self, link_type: str, weight: float | None) -> None:
        if link_type in (LINK_TYPE_ESCO_ESSENTIAL, LINK_TYPE_ESCO_OPTIONAL) and weight is not None:
            raise HTTPException(
                status_code=400,
                detail="ESCO profession competency links must not include a weight",
            )
        if link_type in (LINK_TYPE_JOB_DERIVED, LINK_TYPE_MANUAL) and weight is None:
            raise HTTPException(
                status_code=400,
                detail="Manual and job-derived profession competency links require a weight",
            )

    async def _ensure_missing(self, db: AsyncSession, query, detail: str) -> None:
        result = await db.execute(query)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail=detail)

    async def _get_competency_map(self, db: AsyncSession) -> dict[int, str]:
        result = await db.execute(select(Competency.id, Competency.name))
        return {row.id: row.name for row in result.all()}

    async def _parse_job_with_competency_map(
        self,
        db: AsyncSession,
        job: Job,
        competency_map: dict[int, str],
    ) -> ParseCompetenciesResponse:
        matched_ids, matched_names, unrecognized = document_processing_service.parse_text(
            text=job.description,
            competency_map=competency_map,
        )
        await db.execute(delete(JobCompetency).where(JobCompetency.job_id == job.id))
        if matched_ids:
            rows = [{"job_id": job.id, "competency_id": competency_id} for competency_id in matched_ids]
            stmt = pg_insert(JobCompetency.__table__).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["job_id", "competency_id"])
            await db.execute(stmt)
        return ParseCompetenciesResponse(
            matched_competency_ids=matched_ids,
            matched_competency_names=matched_names,
            unrecognized_tokens=unrecognized,
        )


knowledge_base_service = KnowledgeBaseService()
