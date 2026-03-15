import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import ModelStatus
from app.models.models import (
    Alternative,
    AlternativeRank,
    Competency,
    CompetencyModel,
    Criterion,
    CriterionRank,
    CustomCompetency,
    ExpertInvite,
    ModelExpert,
    Profession,
    ProfessionCompetency,
    User,
)
from app.schemas.competency_model import (
    AlternativeCreate,
    AlternativeOut,
    AlternativeRecommendation,
    CompetencyModelCreate,
    CompetencyModelDetail,
    CompetencyModelUpdate,
    CriterionCreate,
    CriterionUpdate,
    CustomCompetencyCreate,
    CustomCompetencyOut,
    CustomCompetencyUpdate,
    ExpertAlternativeRankOut,
    ExpertCompetencyModelDetail,
    ExpertCriterionRankOut,
    ExpertInviteCreate,
    ExpertInviteOut,
    ExpertInviteUpdate,
    ExpertReorderRequest,
    ExpertEvaluationStatus,
    ExpertEvaluationSubmit,
    ModelExpertCreate,
    ModelExpertDetailOut,
    ModelExpertUpdate,
    ModelSubmitRequest,
    OPAResult,
)
from app.schemas.common import UserSummaryOut
from app.services.opa_service import (
    AlternativeInput,
    CriterionInput,
    ExpertInput,
    run_opa,
)
from app.services.email_service import email_service
from app.services.activity_service import activity_service

LINK_TYPE_SCORES = {
    "esco_essential": 2.0,
    "manual": 1.5,
    "esco_optional": 1.0,
    "job_derived": 0.0,
}


class CompetencyModelService:
    async def list_models(self, db: AsyncSession, user_id: int) -> Sequence[CompetencyModel]:
        result = await db.execute(
            select(CompetencyModel)
            .where(CompetencyModel.user_id == user_id)
            .order_by(CompetencyModel.created_at.desc())
        )
        return result.scalars().all()

    async def get_model(self, db: AsyncSession, model_id: int, user_id: int) -> CompetencyModelDetail:
        model = await self._get_model_orm(db, model_id, user_id)
        return await self._build_model_detail(db, model)

    async def get_model_as_expert(
        self, db: AsyncSession, model_id: int, user_id: int
    ) -> ExpertCompetencyModelDetail:
        expert = await self._get_expert_by_user(db, model_id, user_id)
        model = await self._get_model_with_relations(db, model_id)
        criterion_ranks = (
            await db.execute(
                select(CriterionRank)
                .where(CriterionRank.expert_id == expert.id)
                .order_by(CriterionRank.rank, CriterionRank.criterion_id)
            )
        ).scalars().all()
        alternative_ranks = (
            await db.execute(
                select(AlternativeRank)
                .where(AlternativeRank.expert_id == expert.id)
                .order_by(AlternativeRank.criterion_id, AlternativeRank.rank, AlternativeRank.alternative_id)
            )
        ).scalars().all()
        return await self._build_model_detail(
            db,
            model,
            current_criterion_ranks=[
                ExpertCriterionRankOut(criterion_id=item.criterion_id, rank=item.rank)
                for item in criterion_ranks
            ],
            current_alternative_ranks=[
                ExpertAlternativeRankOut(
                    alternative_id=item.alternative_id,
                    criterion_id=item.criterion_id,
                    rank=item.rank,
                )
                for item in alternative_ranks
            ],
        )

    async def create_model(
        self, db: AsyncSession, data: CompetencyModelCreate, user_id: int
    ) -> CompetencyModel:
        await self._ensure_profession_exists(db, data.profession_id)
        model = CompetencyModel(
            user_id=user_id,
            name=data.name,
            profession_id=data.profession_id,
            status=ModelStatus.DRAFT,
        )
        db.add(model)
        await db.flush()
        await self._load_default_alternatives(db, model)
        await db.refresh(model)
        return model

    async def update_model(
        self, db: AsyncSession, model_id: int, user_id: int, data: CompetencyModelUpdate
    ) -> CompetencyModel:
        model = await self._get_model_orm(db, model_id, user_id)
        allowed_statuses = {ModelStatus.DRAFT, ModelStatus.EXPERT_EVALUATION, ModelStatus.COMPLETED}
        if model.status not in allowed_statuses:
            raise HTTPException(status_code=400, detail="Model cannot be updated in its current status")

        is_draft = model.status == ModelStatus.DRAFT
        is_expert_eval = model.status == ModelStatus.EXPERT_EVALUATION
        is_completed = model.status == ModelStatus.COMPLETED
        updated_fields = data.model_fields_set

        if is_draft:
            if "name" in updated_fields:
                model.name = data.name
            if data.profession_id is not None:
                await self._ensure_profession_exists(db, data.profession_id)
                model.profession_id = data.profession_id

        if is_draft or is_expert_eval:
            if "evaluation_deadline" in updated_fields:
                self._validate_evaluation_deadline(data.evaluation_deadline)
                model.evaluation_deadline = data.evaluation_deadline

        if is_draft or is_expert_eval or is_completed:
            if "min_competency_weight" in updated_fields:
                model.min_competency_weight = data.min_competency_weight
            if "max_competency_rank" in updated_fields:
                model.max_competency_rank = data.max_competency_rank
            if (
                (is_expert_eval or is_completed)
                and (
                    "min_competency_weight" in updated_fields
                    or "max_competency_rank" in updated_fields
                )
                and model.min_competency_weight is None
                and model.max_competency_rank is None
            ):
                raise HTTPException(
                    status_code=400,
                    detail="At least one competency filter is required: minimum weight or maximum rank",
                )

        await db.flush()
        await db.refresh(model)
        return model

    async def delete_model(self, db: AsyncSession, model_id: int, user_id: int) -> None:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        await db.delete(model)

    async def add_expert(
        self, db: AsyncSession, model_id: int, user_id: int, data: ModelExpertCreate
    ) -> ModelExpert:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        user = await self._get_user(db, data.user_id)
        await self._ensure_user_not_already_expert(db, model_id, data.user_id)
        await self._ensure_no_pending_invite_for_email(db, model_id, user.email)
        await self._check_expert_rank_unique(db, model_id, data.rank)
        expert = ModelExpert(model_id=model_id, user_id=data.user_id, rank=data.rank)
        db.add(expert)
        await db.flush()
        await db.refresh(expert)
        return expert

    async def list_expert_invites(
        self, db: AsyncSession, model_id: int, user_id: int
    ) -> list[ExpertInviteOut]:
        model = await self._get_model_orm(db, model_id, user_id)
        result = await db.execute(
            select(ExpertInvite)
            .where(ExpertInvite.model_id == model_id)
            .order_by(ExpertInvite.created_at, ExpertInvite.id)
        )
        invites = [invite for invite in result.scalars().all() if invite.accepted_by_user_id is None]
        matched_users = await self._get_users_by_emails(db, [invite.email for invite in invites])
        return [
            self._serialize_expert_invite(
                invite,
                model_name=model.name,
                profession_id=model.profession_id,
                status="added" if model.status == ModelStatus.DRAFT else "invited",
                matched_user=matched_users.get(invite.email.strip().lower()),
            )
            for invite in invites
        ]

    async def create_expert_invite(
        self, db: AsyncSession, model_id: int, user_id: int, data: ExpertInviteCreate
    ) -> ExpertInviteOut:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        normalized_email = data.email.strip().lower()
        await self._ensure_invite_email_missing(db, model_id, normalized_email)
        await self._ensure_email_not_already_expert(db, model_id, normalized_email)
        await self._check_expert_rank_unique(db, model_id, data.rank)
        invite = ExpertInvite(
            model_id=model_id,
            email=normalized_email,
            rank=data.rank,
            token=secrets.token_urlsafe(24),
        )
        db.add(invite)
        await db.flush()
        await db.refresh(invite)
        matched_user = (await self._get_users_by_emails(db, [normalized_email])).get(normalized_email)
        return self._serialize_expert_invite(
            invite,
            model_name=model.name,
            profession_id=model.profession_id,
            status="added",
            matched_user=matched_user,
        )

    async def update_expert_invite(
        self,
        db: AsyncSession,
        model_id: int,
        invite_id: int,
        user_id: int,
        data: ExpertInviteUpdate,
    ) -> ExpertInviteOut:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        invite = await self._get_expert_invite(db, invite_id, model_id)
        if invite.accepted_by_user_id is not None:
            raise HTTPException(status_code=400, detail="Accepted invite cannot be updated")
        if data.email is not None:
            normalized_email = data.email.strip().lower()
            if normalized_email != invite.email:
                await self._ensure_invite_email_missing(db, model_id, normalized_email, exclude_id=invite.id)
                await self._ensure_email_not_already_expert(db, model_id, normalized_email)
                invite.email = normalized_email
        if data.rank is not None and data.rank != invite.rank:
            await self._check_expert_rank_unique(db, model_id, data.rank, exclude_invite_id=invite.id)
            invite.rank = data.rank
        await db.flush()
        await db.refresh(invite)
        matched_user = (await self._get_users_by_emails(db, [invite.email])).get(invite.email.strip().lower())
        return self._serialize_expert_invite(
            invite,
            model_name=model.name,
            profession_id=model.profession_id,
            status="added",
            matched_user=matched_user,
        )

    async def delete_expert_invite(
        self, db: AsyncSession, model_id: int, invite_id: int, user_id: int
    ) -> None:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        invite = await self._get_expert_invite(db, invite_id, model_id)
        await db.delete(invite)

    async def update_expert(
        self, db: AsyncSession, model_id: int, expert_id: int, user_id: int, data: ModelExpertUpdate
    ) -> ModelExpert:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        expert = await self._get_expert(db, expert_id, model_id)
        if data.rank is not None and data.rank != expert.rank:
            await self._check_expert_rank_unique(db, model_id, data.rank)
            expert.rank = data.rank
        await db.flush()
        await db.refresh(expert)
        return expert

    async def reorder_experts(
        self, db: AsyncSession, model_id: int, user_id: int, data: ExpertReorderRequest
    ) -> None:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)

        # Load all experts and pending invites for this model
        experts_result = await db.execute(
            select(ModelExpert).where(ModelExpert.model_id == model_id)
        )
        invites_result = await db.execute(
            select(ExpertInvite).where(
                ExpertInvite.model_id == model_id,
                ExpertInvite.accepted_by_user_id.is_(None),
            )
        )
        expert_map = {e.id: e for e in experts_result.scalars().all()}
        invite_map = {i.id: i for i in invites_result.scalars().all()}

        for item in data.ranks:
            if item.kind == "expert":
                if item.id not in expert_map:
                    raise HTTPException(status_code=404, detail=f"Expert {item.id} not found in this model")
            else:
                if item.id not in invite_map:
                    raise HTTPException(status_code=404, detail=f"Invite {item.id} not found in this model")

        # Apply all rank changes in one flush — uniqueness is guaranteed by schema-level validation
        for item in data.ranks:
            if item.kind == "expert":
                expert_map[item.id].rank = item.rank
            else:
                invite_map[item.id].rank = item.rank
        await db.flush()

    async def remove_expert(self, db: AsyncSession, model_id: int, expert_id: int, user_id: int) -> None:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        expert = await self._get_expert(db, expert_id, model_id)
        await db.delete(expert)

    async def add_criterion(
        self, db: AsyncSession, model_id: int, user_id: int, data: CriterionCreate
    ) -> Criterion:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        criterion = Criterion(model_id=model_id, name=data.name, description=data.description)
        db.add(criterion)
        await db.flush()
        await db.refresh(criterion)
        return criterion

    async def update_criterion(
        self, db: AsyncSession, model_id: int, criterion_id: int, user_id: int, data: CriterionUpdate
    ) -> Criterion:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        criterion = await self._get_criterion(db, criterion_id, model_id)
        if data.name is not None:
            criterion.name = data.name
        if data.description is not None:
            criterion.description = data.description
        await db.flush()
        await db.refresh(criterion)
        return criterion

    async def remove_criterion(
        self, db: AsyncSession, model_id: int, criterion_id: int, user_id: int
    ) -> None:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        criterion = await self._get_criterion(db, criterion_id, model_id)
        await db.delete(criterion)

    async def list_custom_competencies(
        self,
        db: AsyncSession,
        model_id: int,
        user_id: int,
    ) -> list[CustomCompetency]:
        await self._get_model_orm(db, model_id, user_id)
        result = await db.execute(
            select(CustomCompetency)
            .where(CustomCompetency.model_id == model_id)
            .order_by(CustomCompetency.created_at, CustomCompetency.id)
        )
        return result.scalars().all()

    async def create_custom_competency(
        self,
        db: AsyncSession,
        model_id: int,
        user_id: int,
        data: CustomCompetencyCreate,
    ) -> CustomCompetency:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        normalized_name = data.name.strip()
        await self._ensure_missing(
            db,
            select(CustomCompetency).where(
                CustomCompetency.model_id == model_id,
                func.lower(CustomCompetency.name) == normalized_name.lower(),
            ),
            "Custom competency with this name already exists in the model",
        )
        await self._ensure_missing(
            db,
            select(Competency).where(func.lower(Competency.name) == normalized_name.lower()),
            "A competency with this name already exists in the knowledge base",
        )
        custom_competency = CustomCompetency(
            model_id=model_id,
            name=normalized_name,
            description=data.description,
        )
        db.add(custom_competency)
        await db.flush()
        db.add(
            Alternative(
                model_id=model_id,
                custom_competency_id=custom_competency.id,
            )
        )
        await db.flush()
        await db.refresh(custom_competency)
        return custom_competency

    async def update_custom_competency(
        self,
        db: AsyncSession,
        model_id: int,
        custom_competency_id: int,
        user_id: int,
        data: CustomCompetencyUpdate,
    ) -> CustomCompetency:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        custom_competency = await self._get_custom_competency(db, custom_competency_id, model_id)
        if data.name is not None:
            normalized_name = data.name.strip()
            if normalized_name.lower() != custom_competency.name.lower():
                await self._ensure_missing(
                    db,
                    select(CustomCompetency).where(
                        CustomCompetency.model_id == model_id,
                        func.lower(CustomCompetency.name) == normalized_name.lower(),
                        CustomCompetency.id != custom_competency_id,
                    ),
                    "Custom competency with this name already exists in the model",
                )
            custom_competency.name = normalized_name
        if data.description is not None:
            custom_competency.description = data.description
        await db.flush()
        await db.refresh(custom_competency)
        return custom_competency

    async def delete_custom_competency(
        self,
        db: AsyncSession,
        model_id: int,
        custom_competency_id: int,
        user_id: int,
    ) -> None:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        custom_competency = await self._get_custom_competency(db, custom_competency_id, model_id)
        await db.delete(custom_competency)

    async def add_alternative(
        self, db: AsyncSession, model_id: int, user_id: int, data: AlternativeCreate
    ) -> AlternativeOut:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        existing = await db.execute(
            select(Alternative).where(
                Alternative.model_id == model_id,
                Alternative.competency_id == data.competency_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Competency is already an alternative in this model",
            )
        await self._ensure_competency_exists(db, data.competency_id)
        alt = Alternative(model_id=model_id, competency_id=data.competency_id)
        db.add(alt)
        await db.flush()
        result = await db.execute(
            select(Alternative)
            .where(Alternative.id == alt.id)
            .options(selectinload(Alternative.competency), selectinload(Alternative.custom_competency))
        )
        return self._serialize_alternative(result.scalar_one())

    async def remove_alternative(
        self, db: AsyncSession, model_id: int, alternative_id: int, user_id: int
    ) -> None:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        alt = await self._get_alternative(db, alternative_id, model_id)
        await db.delete(alt)

    async def submit_model(
        self, db: AsyncSession, model_id: int, user_id: int, data: ModelSubmitRequest
    ) -> CompetencyModel:
        model = await self._get_model_orm(db, model_id, user_id)
        self._require_status(model, ModelStatus.DRAFT)
        pending_invites = [
            invite for invite in model.expert_invites if invite.accepted_by_user_id is None
        ]
        if not model.experts and not pending_invites:
            raise HTTPException(status_code=400, detail="Add at least one expert or invite")
        if not model.criteria:
            raise HTTPException(status_code=400, detail="Add at least one criterion")
        if len(model.alternatives) < 2:
            raise HTTPException(status_code=400, detail="Add at least two competency alternatives")
        self._validate_evaluation_deadline(data.evaluation_deadline)
        model.min_competency_weight = data.min_competency_weight
        model.max_competency_rank = data.max_competency_rank
        model.evaluation_deadline = data.evaluation_deadline
        model.status = ModelStatus.EXPERT_EVALUATION
        await db.flush()
        await activity_service.log(db, model.user_id, "model", model.id, "status_change", "draft", "expert_evaluation")
        for invite in pending_invites:
            await email_service.send_competency_model_invite(db, invite.id)
        await db.refresh(model)
        return model

    async def list_pending_invites_for_user(
        self, db: AsyncSession, user_id: int
    ) -> list[ExpertInviteOut]:
        user = await self._get_user(db, user_id)
        normalized_email = user.email.strip().lower()
        result = await db.execute(
            select(ExpertInvite, CompetencyModel)
            .join(CompetencyModel, CompetencyModel.id == ExpertInvite.model_id)
            .where(
                ExpertInvite.accepted_by_user_id.is_(None),
                func.lower(ExpertInvite.email) == normalized_email,
                CompetencyModel.status == ModelStatus.EXPERT_EVALUATION,
            )
            .order_by(ExpertInvite.created_at.desc())
        )
        return [
            self._serialize_expert_invite(
                invite,
                model_name=model.name,
                profession_id=model.profession_id,
                status="invited",
                matched_user=user,
            )
            for invite, model in result.all()
        ]

    async def accept_expert_invite(
        self, db: AsyncSession, token: str, user_id: int
    ) -> ModelExpert:
        user = await self._get_user(db, user_id)
        invite = await self._get_expert_invite_by_token(db, token)
        normalized_email = user.email.strip().lower()
        if invite.email != normalized_email:
            raise HTTPException(status_code=403, detail="Invite email does not match current user")
        if invite.accepted_by_user_id is not None:
            raise HTTPException(status_code=409, detail="Invite has already been accepted")
        model = await self._get_model_for_status_check(db, invite.model_id)
        if model.status == ModelStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="Model has been cancelled")
        if model.status == ModelStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Model is already completed")
        if model.status != ModelStatus.EXPERT_EVALUATION:
            raise HTTPException(status_code=400, detail="Invite is not active yet")
        await self._ensure_user_not_already_expert(db, invite.model_id, user.id)
        await self._check_expert_rank_unique(db, invite.model_id, invite.rank, exclude_invite_id=invite.id)
        expert = ModelExpert(model_id=invite.model_id, user_id=user.id, rank=invite.rank)
        db.add(expert)
        invite.accepted_by_user_id = user.id
        await db.flush()
        await db.refresh(expert)
        await activity_service.log(db, model.user_id, "model", model.id, "invite_accepted", None, user.email)
        await email_service.send_competency_model_invite_accepted(db, invite.model_id, user.id)
        return expert

    async def cancel_model(self, db: AsyncSession, model_id: int, user_id: int) -> CompetencyModel:
        model = await self._get_model_orm(db, model_id, user_id)
        if model.status in (ModelStatus.COMPLETED, ModelStatus.CANCELLED):
            raise HTTPException(status_code=400, detail="Model is already terminal")
        old_status = "draft" if model.status == ModelStatus.DRAFT else "expert_evaluation"
        model.status = ModelStatus.CANCELLED
        await db.flush()
        await activity_service.log(db, model.user_id, "model", model.id, "status_change", old_status, "cancelled")
        await db.refresh(model)
        return model

    async def submit_expert_evaluation(
        self, db: AsyncSession, model_id: int, current_user_id: int, data: ExpertEvaluationSubmit
    ) -> ExpertEvaluationStatus:
        expert = await self._get_expert_by_user(db, model_id, current_user_id)
        model = await self._get_model_for_status_check(db, model_id)
        if model.status != ModelStatus.EXPERT_EVALUATION:
            raise HTTPException(status_code=400, detail="Model is not in expert evaluation status")
        if model.evaluation_deadline:
            deadline = model.evaluation_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > deadline:
                raise HTTPException(status_code=400, detail="Evaluation deadline has passed")

        model_criteria = (
            await db.execute(select(Criterion.id).where(Criterion.model_id == model_id))
        ).scalars().all()
        model_alternatives = (
            await db.execute(select(Alternative.id).where(Alternative.model_id == model_id))
        ).scalars().all()
        model_criterion_ids = set(model_criteria)
        model_alternative_ids = set(model_alternatives)

        submitted_criterion_ids = [item.criterion_id for item in data.criterion_ranks]
        if set(submitted_criterion_ids) != model_criterion_ids or len(submitted_criterion_ids) != len(
            model_criterion_ids
        ):
            raise HTTPException(
                status_code=400,
                detail="Criterion ranks must include each criterion of the model exactly once",
            )

        submitted_pairs = [(item.criterion_id, item.alternative_id) for item in data.alternative_ranks]
        expected_pairs = {
            (criterion_id, alternative_id)
            for criterion_id in model_criterion_ids
            for alternative_id in model_alternative_ids
        }
        if set(submitted_pairs) != expected_pairs or len(submitted_pairs) != len(expected_pairs):
            raise HTTPException(
                status_code=400,
                detail="Alternative ranks must cover every model alternative for every model criterion exactly once",
            )

        n_criteria = len(data.criterion_ranks)
        criterion_ranks = [item.rank for item in data.criterion_ranks]
        if sorted(criterion_ranks) != list(range(1, n_criteria + 1)):
            raise HTTPException(status_code=400, detail="Criterion ranks must be unique and continuous")

        alt_ranks_by_criterion: dict[int, list[int]] = defaultdict(list)
        for item in data.alternative_ranks:
            alt_ranks_by_criterion[item.criterion_id].append(item.rank)
        for ranks in alt_ranks_by_criterion.values():
            if sorted(ranks) != list(range(1, len(ranks) + 1)):
                raise HTTPException(status_code=400, detail="Alternative ranks must be unique and continuous per criterion")

        had_existing_submission = (
            await db.execute(select(func.count(CriterionRank.criterion_id)).where(CriterionRank.expert_id == expert.id))
        ).scalar_one() > 0
        await db.execute(delete(CriterionRank).where(CriterionRank.expert_id == expert.id))
        await db.execute(delete(AlternativeRank).where(AlternativeRank.expert_id == expert.id))

        for item in data.criterion_ranks:
            db.add(CriterionRank(criterion_id=item.criterion_id, expert_id=expert.id, rank=item.rank))
        for item in data.alternative_ranks:
            db.add(
                AlternativeRank(
                    alternative_id=item.alternative_id,
                    expert_id=expert.id,
                    criterion_id=item.criterion_id,
                    rank=item.rank,
                )
            )

        await db.flush()
        if not had_existing_submission:
            await activity_service.log(db, model.user_id, "model", model_id, "evaluation_submitted", None, str(expert.id))
            await email_service.send_competency_model_submission_received(db, model_id, current_user_id)
        return await self.get_expert_evaluation_status(db, model_id, current_user_id)

    async def get_expert_evaluation_status(
        self, db: AsyncSession, model_id: int, user_id: int
    ) -> ExpertEvaluationStatus:
        expert = await self._get_expert_by_user(db, model_id, user_id)
        criteria_total = (
            await db.execute(select(func.count(Criterion.id)).where(Criterion.model_id == model_id))
        ).scalar_one()
        alternatives_per_criterion = (
            await db.execute(select(func.count(Alternative.id)).where(Alternative.model_id == model_id))
        ).scalar_one()
        criteria_ranked = (
            await db.execute(select(func.count(CriterionRank.criterion_id)).where(CriterionRank.expert_id == expert.id))
        ).scalar_one()
        alternatives_ranked = (
            await db.execute(select(func.count()).where(AlternativeRank.expert_id == expert.id))
        ).scalar_one()
        total = criteria_total * alternatives_per_criterion
        return ExpertEvaluationStatus(
            expert_id=expert.id,
            criteria_ranked=criteria_ranked,
            criteria_total=criteria_total,
            alternatives_ranked=alternatives_ranked,
            alternatives_total=total,
            is_complete=criteria_ranked == criteria_total and alternatives_ranked == total,
        )

    async def calculate_opa(self, db: AsyncSession, model_id: int, user_id: int) -> OPAResult:
        model = await self._get_model_orm(db, model_id, user_id)
        return await self._calculate_opa_for_model(db, model)

    async def calculate_opa_for_deadline(self, db: AsyncSession, model_id: int) -> OPAResult:
        model = await self._get_model_for_status_check(db, model_id)
        return await self._calculate_opa_for_model(db, model)

    async def _calculate_opa_for_model(
        self,
        db: AsyncSession,
        model: CompetencyModel,
    ) -> OPAResult:
        if model.status != ModelStatus.EXPERT_EVALUATION:
            raise HTTPException(status_code=400, detail="OPA can only run in expert evaluation status")

        model_id = model.id
        experts = (
            await db.execute(select(ModelExpert).where(ModelExpert.model_id == model_id))
        ).scalars().all()
        crit_ranks = (
            await db.execute(
                select(CriterionRank)
                .join(ModelExpert, ModelExpert.id == CriterionRank.expert_id)
                .where(ModelExpert.model_id == model_id)
            )
        ).scalars().all()
        alt_ranks = (
            await db.execute(
                select(AlternativeRank)
                .join(ModelExpert, ModelExpert.id == AlternativeRank.expert_id)
                .where(ModelExpert.model_id == model_id)
            )
        ).scalars().all()

        if not crit_ranks and not alt_ranks:
            model.status = ModelStatus.CANCELLED
            await db.flush()
            await activity_service.log(db, model.user_id, "model", model.id, "status_change", "expert_evaluation", "cancelled")
            return OPAResult(
                expert_weights={},
                criterion_weights={},
                alternative_weights={},
                filtered_alternatives=[],
                status="no_evaluations",
            )

        expert_inputs = [ExpertInput(id=item.id, rank=item.rank) for item in experts]
        criterion_inputs = [
            CriterionInput(id=item.criterion_id, expert_id=item.expert_id, rank=item.rank)
            for item in crit_ranks
        ]
        alternative_inputs = [
            AlternativeInput(
                id=item.alternative_id,
                expert_id=item.expert_id,
                criterion_id=item.criterion_id,
                rank=item.rank,
            )
            for item in alt_ranks
        ]
        opa_result = run_opa(expert_inputs, criterion_inputs, alternative_inputs)
        if not opa_result.solved:
            raise HTTPException(status_code=500, detail=f"OPA failed: {opa_result.message}")

        for expert in experts:
            expert.weight = opa_result.expert_weights.get(expert.id)
        for criterion in (
            await db.execute(select(Criterion).where(Criterion.model_id == model_id))
        ).scalars().all():
            criterion.weight = opa_result.criterion_weights.get(criterion.id)
        alternatives = (
            await db.execute(
                select(Alternative)
                .where(Alternative.model_id == model_id)
                .options(
                    selectinload(Alternative.competency),
                    selectinload(Alternative.custom_competency),
                )
            )
        ).scalars().all()
        for alt in alternatives:
            alt.weight = opa_result.alternative_weights.get(alt.id)

        filtered = self._filter_alternatives(model, alternatives, opa_result.alternative_weights)
        total_weight = sum(opa_result.alternative_weights.get(alt.id, 0) for alt in filtered)
        for alt in alternatives:
            if alt in filtered and total_weight > 0:
                alt.final_weight = round(opa_result.alternative_weights.get(alt.id, 0) / total_weight, 6)
            else:
                alt.final_weight = None

        model.status = ModelStatus.COMPLETED
        await db.flush()
        await activity_service.log(db, model.user_id, "model", model.id, "status_change", "expert_evaluation", "completed")

        return OPAResult(
            expert_weights=opa_result.expert_weights,
            criterion_weights=opa_result.criterion_weights,
            alternative_weights=opa_result.alternative_weights,
            filtered_alternatives=[self._serialize_alternative(alt) for alt in filtered],
            status="success",
        )

    async def get_recommendations(
        self, db: AsyncSession, model_id: int, user_id: int
    ) -> list[AlternativeRecommendation]:
        model = await self._get_model_orm(db, model_id, user_id)
        if not model.profession_id:
            return []

        profession = (
            await db.execute(select(Profession).where(Profession.id == model.profession_id))
        ).scalar_one_or_none()
        if not profession:
            return []

        existing_ids = {alt.competency_id for alt in model.alternatives}
        direct_rows = (
            await db.execute(
                select(ProfessionCompetency, Competency)
                .join(Competency, Competency.id == ProfessionCompetency.competency_id)
                .where(ProfessionCompetency.profession_id == model.profession_id)
            )
        ).all()

        if direct_rows:
            recommendations: dict[int, AlternativeRecommendation] = {}
            for link, competency in direct_rows:
                score = LINK_TYPE_SCORES.get(link.link_type, 0.0) + float(link.weight or 0)
                current = recommendations.get(link.competency_id)
                if current is None or score > current.score:
                    recommendations[link.competency_id] = AlternativeRecommendation(
                        competency_id=link.competency_id,
                        competency_name=competency.name,
                        score=round(score, 4),
                        already_added=link.competency_id in existing_ids,
                    )
            return sorted(recommendations.values(), key=lambda item: item.score, reverse=True)[:10]

        similar_ids = (
            await db.execute(
                select(Profession.id)
                .where(
                    func.similarity(Profession.name, profession.name) > 0.3,
                    Profession.id != model.profession_id,
                )
                .order_by(func.similarity(Profession.name, profession.name).desc())
                .limit(5)
            )
        ).scalars().all()
        if not similar_ids:
            return []

        rows = (
            await db.execute(
                select(
                    ProfessionCompetency.competency_id,
                    ProfessionCompetency.link_type,
                    ProfessionCompetency.weight,
                    Competency.name,
                )
                .join(Competency, Competency.id == ProfessionCompetency.competency_id)
                .where(ProfessionCompetency.profession_id.in_(similar_ids))
            )
        ).all()

        recommendations: dict[int, AlternativeRecommendation] = {}
        for row in rows:
            score = LINK_TYPE_SCORES.get(row.link_type, 0.0) + float(row.weight or 0)
            current = recommendations.get(row.competency_id)
            if current is None or score > current.score:
                recommendations[row.competency_id] = AlternativeRecommendation(
                    competency_id=row.competency_id,
                    competency_name=row.name,
                    score=round(score, 4),
                    already_added=row.competency_id in existing_ids,
                )

        return sorted(
            recommendations.values(),
            key=lambda item: item.score,
            reverse=True,
        )[:10]

    def _filter_alternatives(
        self,
        model: CompetencyModel,
        alternatives: list[Alternative],
        weights: dict[int, float],
    ) -> list[Alternative]:
        sorted_alts = sorted(alternatives, key=lambda alt: weights.get(alt.id, 0), reverse=True)
        if model.max_competency_rank:
            return sorted_alts[: model.max_competency_rank]
        if model.min_competency_weight:
            return [alt for alt in sorted_alts if weights.get(alt.id, 0) >= model.min_competency_weight]
        return sorted_alts

    def _validate_evaluation_deadline(self, deadline: datetime | None) -> None:
        if deadline is None:
            raise HTTPException(status_code=400, detail="Evaluation deadline is required")

        now = datetime.now(deadline.tzinfo or timezone.utc)
        tomorrow = (now + timedelta(days=1)).date()
        if deadline.date() < tomorrow:
            raise HTTPException(
                status_code=400,
                detail="Evaluation deadline must be tomorrow or later",
            )

    def _require_status(self, model: CompetencyModel, required: ModelStatus) -> None:
        if model.status is None or model.status != required:
            current = ModelStatus(model.status).name if model.status is not None else "None"
            raise HTTPException(status_code=400, detail=f"Operation is unavailable in status {current}")

    async def _get_model_orm(self, db: AsyncSession, model_id: int, user_id: int) -> CompetencyModel:
        model = await self._get_model_with_relations(db, model_id)
        if model.user_id != user_id:
            raise HTTPException(status_code=404, detail="Competency model not found")
        return model

    async def _get_model_with_relations(self, db: AsyncSession, model_id: int) -> CompetencyModel:
        result = await db.execute(
            select(CompetencyModel)
            .where(CompetencyModel.id == model_id)
            .options(
                selectinload(CompetencyModel.profession),
                selectinload(CompetencyModel.experts).selectinload(ModelExpert.user),
                selectinload(CompetencyModel.expert_invites),
                selectinload(CompetencyModel.criteria),
                selectinload(CompetencyModel.custom_competencies),
                selectinload(CompetencyModel.alternatives).selectinload(Alternative.competency),
                selectinload(CompetencyModel.alternatives).selectinload(Alternative.custom_competency),
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            raise HTTPException(status_code=404, detail="Competency model not found")
        return model

    async def _get_model_for_status_check(self, db: AsyncSession, model_id: int) -> CompetencyModel:
        result = await db.execute(select(CompetencyModel).where(CompetencyModel.id == model_id))
        model = result.scalar_one_or_none()
        if not model:
            raise HTTPException(status_code=404, detail="Competency model not found")
        return model

    async def _get_expert(self, db: AsyncSession, expert_id: int, model_id: int) -> ModelExpert:
        result = await db.execute(
            select(ModelExpert).where(ModelExpert.id == expert_id, ModelExpert.model_id == model_id)
        )
        expert = result.scalar_one_or_none()
        if not expert:
            raise HTTPException(status_code=404, detail="Expert not found")
        return expert

    async def _get_expert_by_user(self, db: AsyncSession, model_id: int, user_id: int) -> ModelExpert:
        result = await db.execute(
            select(ModelExpert).where(ModelExpert.model_id == model_id, ModelExpert.user_id == user_id)
        )
        expert = result.scalar_one_or_none()
        if not expert:
            raise HTTPException(status_code=403, detail="Current user is not an expert for this model")
        return expert

    async def _get_expert_invite(
        self, db: AsyncSession, invite_id: int, model_id: int
    ) -> ExpertInvite:
        result = await db.execute(
            select(ExpertInvite).where(
                ExpertInvite.id == invite_id,
                ExpertInvite.model_id == model_id,
            )
        )
        invite = result.scalar_one_or_none()
        if not invite:
            raise HTTPException(status_code=404, detail="Expert invite not found")
        return invite

    async def _get_expert_invite_by_token(self, db: AsyncSession, token: str) -> ExpertInvite:
        result = await db.execute(select(ExpertInvite).where(ExpertInvite.token == token))
        invite = result.scalar_one_or_none()
        if not invite:
            raise HTTPException(status_code=404, detail="Expert invite not found")
        return invite

    async def _get_criterion(self, db: AsyncSession, criterion_id: int, model_id: int) -> Criterion:
        result = await db.execute(
            select(Criterion).where(Criterion.id == criterion_id, Criterion.model_id == model_id)
        )
        criterion = result.scalar_one_or_none()
        if not criterion:
            raise HTTPException(status_code=404, detail="Criterion not found")
        return criterion

    async def _get_alternative(self, db: AsyncSession, alternative_id: int, model_id: int) -> Alternative:
        result = await db.execute(
            select(Alternative).where(Alternative.id == alternative_id, Alternative.model_id == model_id)
        )
        alt = result.scalar_one_or_none()
        if not alt:
            raise HTTPException(status_code=404, detail="Alternative not found")
        return alt

    async def _get_custom_competency(
        self,
        db: AsyncSession,
        custom_competency_id: int,
        model_id: int,
    ) -> CustomCompetency:
        result = await db.execute(
            select(CustomCompetency).where(
                CustomCompetency.id == custom_competency_id,
                CustomCompetency.model_id == model_id,
            )
        )
        custom_competency = result.scalar_one_or_none()
        if not custom_competency:
            raise HTTPException(status_code=404, detail="Custom competency not found")
        return custom_competency

    async def _check_expert_rank_unique(
        self,
        db: AsyncSession,
        model_id: int,
        rank: int,
        exclude_invite_id: int | None = None,
    ) -> None:
        result = await db.execute(
            select(ModelExpert).where(ModelExpert.model_id == model_id, ModelExpert.rank == rank)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Rank {rank} is already taken")
        invite_query = select(ExpertInvite).where(
            ExpertInvite.model_id == model_id,
            ExpertInvite.rank == rank,
            ExpertInvite.accepted_by_user_id.is_(None),
        )
        if exclude_invite_id is not None:
            invite_query = invite_query.where(ExpertInvite.id != exclude_invite_id)
        invite_result = await db.execute(invite_query)
        if invite_result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Rank {rank} is already taken")

    async def _ensure_invite_email_missing(
        self,
        db: AsyncSession,
        model_id: int,
        email: str,
        exclude_id: int | None = None,
    ) -> None:
        query = select(ExpertInvite).where(
            ExpertInvite.model_id == model_id,
            func.lower(ExpertInvite.email) == email,
        )
        if exclude_id is not None:
            query = query.where(ExpertInvite.id != exclude_id)
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Invite for this email already exists")

    async def _ensure_email_not_already_expert(self, db: AsyncSession, model_id: int, email: str) -> None:
        result = await db.execute(
            select(ModelExpert)
            .join(User, User.id == ModelExpert.user_id)
            .where(
                ModelExpert.model_id == model_id,
                func.lower(User.email) == email,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="User with this email is already an expert")

    async def _ensure_no_pending_invite_for_email(self, db: AsyncSession, model_id: int, email: str) -> None:
        normalized_email = email.strip().lower()
        result = await db.execute(
            select(ExpertInvite).where(
                ExpertInvite.model_id == model_id,
                func.lower(ExpertInvite.email) == normalized_email,
                ExpertInvite.accepted_by_user_id.is_(None),
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Pending invite for this email already exists")

    async def _get_user(self, db: AsyncSession, user_id: int) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    async def _ensure_competency_exists(self, db: AsyncSession, competency_id: int) -> None:
        result = await db.execute(select(Competency.id).where(Competency.id == competency_id))
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Competency not found")

    async def _ensure_user_not_already_expert(self, db: AsyncSession, model_id: int, user_id: int) -> None:
        result = await db.execute(
            select(ModelExpert).where(ModelExpert.model_id == model_id, ModelExpert.user_id == user_id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="User is already an expert in this model")

    async def _load_default_alternatives(self, db: AsyncSession, model: CompetencyModel) -> None:
        if not model.profession_id:
            return
        rows = (
            await db.execute(
                select(ProfessionCompetency)
                .where(
                    ProfessionCompetency.profession_id == model.profession_id,
                    ProfessionCompetency.link_type == "esco_essential",
                )
            )
        ).scalars().all()
        rows = sorted(rows, key=lambda row: -(float(row.weight or 0)))
        for row in rows:
            db.add(Alternative(model_id=model.id, competency_id=row.competency_id))
        await db.flush()

    def _serialize_alternative(self, alternative: Alternative) -> AlternativeOut:
        if alternative.custom_competency is not None:
            return AlternativeOut(
                id=alternative.id,
                model_id=alternative.model_id,
                competency_id=None,
                custom_competency_id=alternative.custom_competency_id,
                competency_name=alternative.custom_competency.name,
                source_type="custom",
                weight=alternative.weight,
                final_weight=alternative.final_weight,
            )
        return AlternativeOut(
            id=alternative.id,
            model_id=alternative.model_id,
            competency_id=alternative.competency_id,
            custom_competency_id=None,
            competency_name=alternative.competency.name if alternative.competency else None,
            source_type="system",
            weight=alternative.weight,
            final_weight=alternative.final_weight,
        )

    def _serialize_model_expert(self, expert: ModelExpert) -> ModelExpertDetailOut:
        return ModelExpertDetailOut(
            id=expert.id,
            model_id=expert.model_id,
            user_id=expert.user_id,
            rank=expert.rank,
            weight=float(expert.weight) if expert.weight is not None else None,
            user=(
                UserSummaryOut(
                    id=expert.user.id,
                    name=expert.user.name,
                    email=expert.user.email,
                )
                if expert.user is not None
                else None
            ),
        )

    def _serialize_expert_invite(
        self,
        invite: ExpertInvite,
        *,
        model_name: str | None,
        profession_id: int | None,
        status: str,
        matched_user: User | None,
    ) -> ExpertInviteOut:
        return ExpertInviteOut(
            id=invite.id,
            model_id=invite.model_id,
            email=invite.email,
            rank=invite.rank,
            token=invite.token,
            accepted_by_user_id=invite.accepted_by_user_id,
            created_at=invite.created_at,
            model_name=model_name,
            profession_id=profession_id,
            status=status,
            user=(
                UserSummaryOut(
                    id=matched_user.id,
                    name=matched_user.name,
                    email=matched_user.email,
                )
                if matched_user is not None
                else None
            ),
        )

    async def _get_users_by_emails(self, db: AsyncSession, emails: list[str]) -> dict[str, User]:
        normalized_emails = sorted({email.strip().lower() for email in emails if email})
        if not normalized_emails:
            return {}
        rows = (
            await db.execute(
                select(User).where(func.lower(User.email).in_(normalized_emails))
            )
        ).scalars().all()
        return {user.email.strip().lower(): user for user in rows}

    async def _ensure_missing(self, db: AsyncSession, query, detail: str) -> None:
        result = await db.execute(query)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail=detail)

    async def _ensure_profession_exists(self, db: AsyncSession, profession_id: int) -> None:
        result = await db.execute(select(Profession.id).where(Profession.id == profession_id))
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Profession not found")

    async def list_models_as_expert(self, db: AsyncSession, user_id: int) -> Sequence[CompetencyModel]:
        result = await db.execute(
            select(CompetencyModel)
            .join(ModelExpert, ModelExpert.model_id == CompetencyModel.id)
            .where(
                ModelExpert.user_id == user_id,
                CompetencyModel.status.in_(
                    (ModelStatus.EXPERT_EVALUATION, ModelStatus.COMPLETED)
                ),
            )
            .order_by(CompetencyModel.evaluation_deadline)
        )
        return result.scalars().all()

    async def _build_model_detail(
        self,
        db: AsyncSession,
        model: CompetencyModel,
        current_criterion_ranks: list[ExpertCriterionRankOut] | None = None,
        current_alternative_ranks: list[ExpertAlternativeRankOut] | None = None,
    ) -> ExpertCompetencyModelDetail:
        invite_users = await self._get_users_by_emails(
            db,
            [invite.email for invite in model.expert_invites if invite.accepted_by_user_id is None],
        )
        pending_invites = [
            self._serialize_expert_invite(
                invite,
                model_name=model.name,
                profession_id=model.profession_id,
                status="added" if model.status == ModelStatus.DRAFT else "invited",
                matched_user=invite_users.get(invite.email.strip().lower()),
            )
            for invite in model.expert_invites
            if invite.accepted_by_user_id is None
        ]

        return ExpertCompetencyModelDetail(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            profession_id=model.profession_id,
            profession_name=model.profession.name if model.profession else None,
            min_competency_weight=model.min_competency_weight,
            max_competency_rank=model.max_competency_rank,
            evaluation_deadline=model.evaluation_deadline,
            status_code=model.status,
            created_at=model.created_at,
            experts=[self._serialize_model_expert(item) for item in model.experts],
            expert_invites=pending_invites,
            criteria=model.criteria,
            custom_competencies=[CustomCompetencyOut.model_validate(item) for item in model.custom_competencies],
            alternatives=[self._serialize_alternative(alt) for alt in model.alternatives],
            current_criterion_ranks=current_criterion_ranks or [],
            current_alternative_ranks=current_alternative_ranks or [],
        )


competency_model_service = CompetencyModelService()
