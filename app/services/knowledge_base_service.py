from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import aliased, selectinload

from app.core.config import settings
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
    SimilarProfessionOut,
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

    async def get_professions(self, db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(Profession)
            .options(selectinload(Profession.labels))
            .order_by(Profession.name)
        )
        rows = result.scalars().all()
        return [
            {
                "id": p.id,
                "esco_uri": p.esco_uri,
                "code": p.code,
                "name": p.name,
                "description": p.description,
                "profession_group_id": p.profession_group_id,
                "parent_profession_id": p.parent_profession_id,
                "aliases": [lbl.label for lbl in p.labels if lbl.label_type != "preferred"],
            }
            for p in rows
        ]

    async def get_professions_page(
        self,
        db: AsyncSession,
        *,
        limit: int | None = None,
        offset: int = 0,
        search: str | None = None,
        group_id: int | None = None,
    ) -> tuple[list[dict], int]:
        base_query = select(Profession.id)
        base_query = await self._apply_profession_list_filters(
            db,
            base_query,
            search=search,
            group_id=group_id,
        )

        total = (
            await db.execute(select(func.count()).select_from(base_query.subquery()))
        ).scalar_one()

        id_query = base_query.order_by(Profession.name, Profession.id).offset(offset)
        if limit is not None:
            id_query = id_query.limit(limit)
        profession_ids = (await db.execute(id_query)).scalars().all()
        if not profession_ids:
            return [], total

        result = await db.execute(
            select(Profession)
            .where(Profession.id.in_(profession_ids))
            .options(selectinload(Profession.labels))
        )
        profession_map = {profession.id: profession for profession in result.scalars().all()}
        ordered_rows = [profession_map[profession_id] for profession_id in profession_ids]
        return [
            {
                "id": p.id,
                "esco_uri": p.esco_uri,
                "code": p.code,
                "name": p.name,
                "description": p.description,
                "profession_group_id": p.profession_group_id,
                "parent_profession_id": p.parent_profession_id,
                "aliases": [lbl.label for lbl in p.labels if lbl.label_type != "preferred"],
            }
            for p in ordered_rows
        ], total

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

    async def get_similar_professions(
        self,
        db: AsyncSession,
        profession_id: int,
        limit: int = 5,
    ) -> list[SimilarProfessionOut]:
        target = await self.get_profession(db, profession_id)
        target_competency_ids = set(
            (
                await db.execute(
                    select(ProfessionCompetency.competency_id).where(
                        ProfessionCompetency.profession_id == profession_id
                    )
                )
            ).scalars().all()
        )
        shared_profession_ids = set()
        if target_competency_ids:
            shared_profession_ids.update(
                (
                    await db.execute(
                        select(ProfessionCompetency.profession_id)
                        .where(
                            ProfessionCompetency.competency_id.in_(target_competency_ids),
                            ProfessionCompetency.profession_id != profession_id,
                        )
                        .distinct()
                    )
                ).scalars().all()
            )

        result = await db.execute(select(Profession))
        profession_rows = result.scalars().all()

        candidate_ids = {
            profession.id
            for profession in profession_rows
            if profession.id != profession_id
            and (
                profession.id in shared_profession_ids
                or profession.profession_group_id == target.profession_group_id
                or (
                    target.parent_profession_id is not None
                    and profession.parent_profession_id == target.parent_profession_id
                )
                or profession.parent_profession_id == profession_id
                or target.parent_profession_id == profession.id
            )
        }
        if not candidate_ids:
            return []

        rows = (
            await db.execute(
                select(
                    ProfessionCompetency.profession_id,
                    ProfessionCompetency.competency_id,
                ).where(ProfessionCompetency.profession_id.in_(candidate_ids))
            )
        ).all()
        competency_sets: dict[int, set[int]] = {}
        for row in rows:
            competency_sets.setdefault(row.profession_id, set()).add(row.competency_id)

        scored: list[SimilarProfessionOut] = []
        for profession in profession_rows:
            if profession.id not in candidate_ids:
                continue
            candidate_competencies = competency_sets.get(profession.id, set())
            shared_count = len(target_competency_ids & candidate_competencies)
            union_count = len(target_competency_ids | candidate_competencies)
            overlap_score = (shared_count / union_count) if union_count else 0.0
            same_group_bonus = 1.0 if profession.profession_group_id == target.profession_group_id else 0.0
            same_parent_bonus = (
                2.0
                if target.parent_profession_id is not None
                and profession.parent_profession_id == target.parent_profession_id
                else 0.0
            )
            direct_hierarchy_bonus = (
                1.5
                if profession.parent_profession_id == target.id or target.parent_profession_id == profession.id
                else 0.0
            )
            score = round(overlap_score * 10 + same_group_bonus + same_parent_bonus + direct_hierarchy_bonus, 4)
            if score <= 0:
                continue
            scored.append(
                SimilarProfessionOut(
                    id=profession.id,
                    name=profession.name,
                    description=profession.description,
                    profession_group_id=profession.profession_group_id,
                    parent_profession_id=profession.parent_profession_id,
                    similarity_score=score,
                    shared_competency_count=shared_count,
                )
            )

        return sorted(
            scored,
            key=lambda item: (-item.similarity_score, -item.shared_competency_count, item.name),
        )[:limit]

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

    async def get_competencies(
        self,
        db: AsyncSession,
        group_id: int | None = None,
        collection_id: int | None = None,
    ) -> list[dict]:
        q = (
            select(Competency)
            .options(
                selectinload(Competency.labels),
                selectinload(Competency.group_memberships).selectinload(CompetencyGroupMember.group),
                selectinload(Competency.collection_memberships).selectinload(CompetencyCollectionMember.collection),
            )
            .order_by(Competency.name)
        )
        if group_id is not None:
            q = q.join(
                CompetencyGroupMember,
                (CompetencyGroupMember.competency_id == Competency.id)
                & (CompetencyGroupMember.group_id == group_id),
            )
        if collection_id is not None:
            q = q.join(
                CompetencyCollectionMember,
                (CompetencyCollectionMember.competency_id == Competency.id)
                & (CompetencyCollectionMember.collection_id == collection_id),
            )
        result = await db.execute(q)
        rows = result.scalars().unique().all()
        return [
            {
                "id": c.id,
                "esco_uri": c.esco_uri,
                "name": c.name,
                "description": c.description,
                "competency_type": c.competency_type,
                "aliases": [lbl.label for lbl in c.labels if lbl.label_type != "preferred"],
                "group_names": [m.group.name for m in c.group_memberships],
                "collection_names": [m.collection.name for m in c.collection_memberships],
            }
            for c in rows
        ]

    async def get_competencies_page(
        self,
        db: AsyncSession,
        *,
        limit: int | None = None,
        offset: int = 0,
        search: str | None = None,
        competency_type: str | None = None,
        group_id: int | None = None,
        collection_id: int | None = None,
    ) -> tuple[list[dict], int]:
        base_query = select(Competency.id)
        base_query = self._apply_competency_list_filters(
            base_query,
            search=search,
            competency_type=competency_type,
            group_id=group_id,
            collection_id=collection_id,
        )

        total = (
            await db.execute(select(func.count()).select_from(base_query.subquery()))
        ).scalar_one()

        id_query = base_query.order_by(Competency.name, Competency.id).offset(offset)
        if limit is not None:
            id_query = id_query.limit(limit)
        competency_ids = (await db.execute(id_query)).scalars().all()
        if not competency_ids:
            return [], total

        result = await db.execute(
            select(Competency)
            .where(Competency.id.in_(competency_ids))
            .options(
                selectinload(Competency.labels),
                selectinload(Competency.group_memberships).selectinload(CompetencyGroupMember.group),
                selectinload(Competency.collection_memberships).selectinload(CompetencyCollectionMember.collection),
            )
        )
        competency_map = {competency.id: competency for competency in result.scalars().unique().all()}
        ordered_rows = [competency_map[competency_id] for competency_id in competency_ids]
        return [
            {
                "id": c.id,
                "esco_uri": c.esco_uri,
                "name": c.name,
                "description": c.description,
                "competency_type": c.competency_type,
                "aliases": [lbl.label for lbl in c.labels if lbl.label_type != "preferred"],
                "group_names": [m.group.name for m in c.group_memberships],
                "collection_names": [m.collection.name for m in c.collection_memberships],
            }
            for c in ordered_rows
        ], total

    async def get_competency(self, db: AsyncSession, competency_id: int) -> Competency:
        result = await db.execute(select(Competency).where(Competency.id == competency_id))
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Competency not found")
        return obj

    async def get_competency_detail(self, db: AsyncSession, competency_id: int) -> dict:
        result = await db.execute(
            select(Competency)
            .where(Competency.id == competency_id)
            .options(
                selectinload(Competency.collection_memberships).selectinload(
                    CompetencyCollectionMember.collection
                )
            )
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Competency not found")
        return {
            "id": obj.id,
            "esco_uri": obj.esco_uri,
            "name": obj.name,
            "description": obj.description,
            "competency_type": obj.competency_type,
            "collections": [
                {"id": m.collection.id, "code": m.collection.code, "name": m.collection.name, "description": m.collection.description}
                for m in obj.collection_memberships
            ],
        }

    LINK_WEIGHT_MAP = {
        "esco_essential": 0.7,
        "esco_optional": 0.3,
    }

    async def get_competency_professions(self, db: AsyncSession, competency_id: int) -> list[dict]:
        await self.get_competency(db, competency_id)
        result = await db.execute(
            select(
                ProfessionCompetency.profession_id,
                Profession.name.label("profession_name"),
                Profession.profession_group_id,
                ProfessionGroup.name.label("profession_group_name"),
                ProfessionCompetency.link_type,
                ProfessionCompetency.weight,
            )
            .join(Profession, Profession.id == ProfessionCompetency.profession_id)
            .outerjoin(ProfessionGroup, ProfessionGroup.id == Profession.profession_group_id)
            .where(ProfessionCompetency.competency_id == competency_id)
        )
        rows = result.all()

        # Load aliases for each profession
        profession_ids = list({row.profession_id for row in rows})
        alias_result = await db.execute(
            select(ProfessionLabel.profession_id, ProfessionLabel.label)
            .where(
                ProfessionLabel.profession_id.in_(profession_ids),
                ProfessionLabel.label_type != "preferred",
            )
        )
        aliases_by_profession: dict[int, list[str]] = {}
        for a_row in alias_result.all():
            aliases_by_profession.setdefault(a_row.profession_id, []).append(a_row.label)

        # Deduplicate by profession_id: keep max computed weight, collect all link types
        deduplicated: dict[int, dict] = {}
        for row in rows:
            computed_weight = self.LINK_WEIGHT_MAP.get(row.link_type, 0.0)
            pid = row.profession_id
            if pid not in deduplicated:
                deduplicated[pid] = {
                    "profession_id": pid,
                    "profession_name": row.profession_name,
                    "profession_group_id": row.profession_group_id,
                    "profession_group_name": row.profession_group_name,
                    "link_types": [row.link_type],
                    "weight": computed_weight,
                    "aliases": aliases_by_profession.get(pid, []),
                }
            else:
                existing = deduplicated[pid]
                if row.link_type not in existing["link_types"]:
                    existing["link_types"].append(row.link_type)
                if computed_weight > existing["weight"]:
                    existing["weight"] = computed_weight

        return sorted(deduplicated.values(), key=lambda r: -r["weight"])

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
            select(
                ProfessionCompetency.competency_id,
                ProfessionCompetency.link_type,
                Competency.name.label("competency_name"),
                Competency.competency_type,
            )
            .join(Competency, Competency.id == ProfessionCompetency.competency_id)
            .where(ProfessionCompetency.profession_id == profession_id)
        )
        rows = result.all()

        competency_ids = list({row.competency_id for row in rows})
        label_result = await db.execute(
            select(CompetencyLabel.competency_id, CompetencyLabel.label)
            .where(
                CompetencyLabel.competency_id.in_(competency_ids),
                CompetencyLabel.label_type != "preferred",
            )
        )
        aliases_by_comp: dict[int, list[str]] = {}
        for lr in label_result.all():
            aliases_by_comp.setdefault(lr.competency_id, []).append(lr.label)

        group_result = await db.execute(
            select(CompetencyGroupMember.competency_id, CompetencyGroup.name)
            .join(CompetencyGroup, CompetencyGroup.id == CompetencyGroupMember.group_id)
            .where(CompetencyGroupMember.competency_id.in_(competency_ids))
        )
        groups_by_comp: dict[int, list[str]] = {}
        for gr in group_result.all():
            groups_by_comp.setdefault(gr.competency_id, []).append(gr.name)

        deduplicated: dict[int, dict] = {}
        for row in rows:
            computed_weight = self.LINK_WEIGHT_MAP.get(row.link_type, 0.0)
            cid = row.competency_id
            if cid not in deduplicated:
                deduplicated[cid] = {
                    "competency_id": cid,
                    "competency_name": row.competency_name,
                    "competency_type": row.competency_type,
                    "aliases": aliases_by_comp.get(cid, []),
                    "group_names": groups_by_comp.get(cid, []),
                    "link_types": [row.link_type],
                    "weight": computed_weight,
                }
            else:
                existing = deduplicated[cid]
                if row.link_type not in existing["link_types"]:
                    existing["link_types"].append(row.link_type)
                if computed_weight > existing["weight"]:
                    existing["weight"] = computed_weight

        return sorted(deduplicated.values(), key=lambda r: -r["weight"])

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
        competency_map = await self._get_job_competency_map(db, job.profession_id)
        return await self._parse_job_with_competency_map(db, job, competency_map)

    async def parse_all_jobs_for_profession(
        self, db: AsyncSession, profession_id: int
    ) -> list[ParseCompetenciesResponse]:
        jobs = await self.get_jobs(db, profession_id=profession_id)
        competency_map = await self._get_job_competency_map(db, profession_id)
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
            frequency = round(row.cnt / total_jobs, 4)
            if row.cnt < settings.JOB_DERIVED_MIN_COUNT:
                continue
            if frequency < settings.JOB_DERIVED_MIN_FREQUENCY:
                continue
            db.add(
                ProfessionCompetency(
                    profession_id=profession_id,
                    competency_id=row.competency_id,
                    link_type=LINK_TYPE_JOB_DERIVED,
                    weight=frequency,
                )
            )
        await db.flush()
        return RecalculateProfessionCompetenciesResponse(
            profession_id=profession_id,
            updated_count=(
                len(
                    [
                        row
                        for row in competency_counts
                        if row.cnt >= settings.JOB_DERIVED_MIN_COUNT
                        and round(row.cnt / total_jobs, 4) >= settings.JOB_DERIVED_MIN_FREQUENCY
                    ]
                )
            ),
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

    async def _apply_profession_list_filters(
        self,
        db: AsyncSession,
        query,
        *,
        search: str | None,
        group_id: int | None,
    ):
        if search:
            normalized = f"%{search.strip().lower()}%"
            label_match = (
                select(ProfessionLabel.id)
                .where(
                    ProfessionLabel.profession_id == Profession.id,
                    ProfessionLabel.label_type != "preferred",
                    func.lower(ProfessionLabel.label).like(normalized),
                )
                .exists()
            )
            query = query.where(
                or_(
                    func.lower(Profession.name).like(normalized),
                    label_match,
                )
            )
        if group_id is not None:
            descendant_ids = await self._get_profession_group_descendant_ids(db, group_id)
            query = query.where(Profession.profession_group_id.in_(descendant_ids))
        return query

    def _apply_competency_list_filters(
        self,
        query,
        *,
        search: str | None,
        competency_type: str | None,
        group_id: int | None,
        collection_id: int | None,
    ):
        if search:
            normalized = f"%{search.strip().lower()}%"
            label_match = (
                select(CompetencyLabel.id)
                .where(
                    CompetencyLabel.competency_id == Competency.id,
                    CompetencyLabel.label_type != "preferred",
                    func.lower(CompetencyLabel.label).like(normalized),
                )
                .exists()
            )
            query = query.where(
                or_(
                    func.lower(Competency.name).like(normalized),
                    label_match,
                )
            )
        if competency_type is not None:
            if competency_type == "unknown":
                query = query.where(Competency.competency_type.is_(None))
            else:
                query = query.where(Competency.competency_type == competency_type)
        if group_id is not None:
            query = query.where(
                select(CompetencyGroupMember.group_id)
                .where(
                    CompetencyGroupMember.competency_id == Competency.id,
                    CompetencyGroupMember.group_id == group_id,
                )
                .exists()
            )
        if collection_id is not None:
            query = query.where(
                select(CompetencyCollectionMember.collection_id)
                .where(
                    CompetencyCollectionMember.competency_id == Competency.id,
                    CompetencyCollectionMember.collection_id == collection_id,
                )
                .exists()
            )
        return query

    async def _get_profession_group_descendant_ids(
        self,
        db: AsyncSession,
        group_id: int,
    ) -> list[int]:
        result = await db.execute(select(ProfessionGroup.id, ProfessionGroup.parent_group_id))
        children_by_parent: dict[int | None, list[int]] = {}
        for row in result.all():
            children_by_parent.setdefault(row.parent_group_id, []).append(row.id)

        descendant_ids: list[int] = []
        queue = [group_id]
        seen: set[int] = set()
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            descendant_ids.append(current)
            queue.extend(children_by_parent.get(current, []))
        return descendant_ids

    async def _get_competency_map(self, db: AsyncSession) -> dict[int, str]:
        result = await db.execute(select(Competency.id, Competency.name))
        return {row.id: row.name for row in result.all()}

    async def _get_job_competency_map(
        self,
        db: AsyncSession,
        profession_id: int,
    ) -> dict[int, list[str]]:
        profession_row = (
            await db.execute(
                select(
                    Profession.id,
                    Profession.profession_group_id,
                    Profession.parent_profession_id,
                ).where(Profession.id == profession_id)
            )
        ).one_or_none()
        if not profession_row:
            return await self._get_competency_map(db)

        current_profession_link_types = (
            LINK_TYPE_ESCO_ESSENTIAL,
            LINK_TYPE_ESCO_OPTIONAL,
            LINK_TYPE_MANUAL,
        )
        neighbor_profession_ids: set[int] = {profession_id}
        if profession_row.parent_profession_id is not None:
            neighbor_profession_ids.add(profession_row.parent_profession_id)
        child_ids = (
            await db.execute(select(Profession.id).where(Profession.parent_profession_id == profession_id))
        ).scalars().all()
        neighbor_profession_ids.update(child_ids)

        if profession_row.profession_group_id is not None:
            group_profession_ids = (
                await db.execute(
                    select(Profession.id).where(
                        Profession.profession_group_id == profession_row.profession_group_id
                    )
                )
            ).scalars().all()
            neighbor_profession_ids.update(group_profession_ids)

        direct_candidate_ids = set(
            (
                await db.execute(
                    select(ProfessionCompetency.competency_id).where(
                        ProfessionCompetency.profession_id == profession_id,
                        ProfessionCompetency.link_type.in_(current_profession_link_types),
                    )
                )
            ).scalars().all()
        )
        neighborhood_candidate_ids = set(
            (
                await db.execute(
                    select(ProfessionCompetency.competency_id)
                    .where(
                        ProfessionCompetency.profession_id.in_(neighbor_profession_ids),
                        ProfessionCompetency.link_type.in_(
                            (LINK_TYPE_ESCO_ESSENTIAL, LINK_TYPE_ESCO_OPTIONAL)
                        ),
                    )
                    .distinct()
                )
            ).scalars().all()
        )
        candidate_ids = direct_candidate_ids | neighborhood_candidate_ids

        if not candidate_ids:
            return await self._get_competency_map(db)

        result = await db.execute(
            select(
                Competency.id,
                Competency.name,
                CompetencyLabel.label,
            )
            .select_from(Competency)
            .outerjoin(
                CompetencyLabel,
                and_(
                    CompetencyLabel.competency_id == Competency.id,
                    CompetencyLabel.label_type.in_(("preferred", "alternative")),
                ),
            )
            .where(Competency.id.in_(candidate_ids))
            .order_by(Competency.id)
        )
        alias_map: dict[int, list[str]] = {}
        seen_per_competency: dict[int, set[str]] = {}
        for competency_id, name, label in result.all():
            alias_map.setdefault(competency_id, [])
            seen_per_competency.setdefault(competency_id, set())
            for term in (name, label):
                if not term:
                    continue
                normalized = term.strip().lower()
                if not normalized or normalized in seen_per_competency[competency_id]:
                    continue
                seen_per_competency[competency_id].add(normalized)
                alias_map[competency_id].append(term.strip())
        return alias_map

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
