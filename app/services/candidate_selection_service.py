import io
import secrets
from datetime import datetime, timezone
from typing import Optional, Sequence

from docx import Document
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.enums import CandidateCVParseStatus, ModelStatus, SelectionStatus
from app.models.models import (
    Alternative,
    Candidate,
    CandidateCompetency,
    CandidateScore,
    CandidateSelection,
    Competency,
    CompetencyModel,
    Profession,
    Selection,
    SelectionCriterion,
    SelectionExpert,
    SelectionExpertInvite,
    User,
)
from app.schemas.candidate_selection import (
    CVParseResponse,
    CandidateCreate,
    CandidateCVSignedUrl,
    CandidateOut,
    CandidateSelectionOut,
    CandidateWithCompetencies,
    CandidateRankOut,
    CompetencyShort,
    ExpertScoringStatus,
    ExpertScoringSubmit,
    SelectionCreate,
    SelectionCriterionOut,
    SelectionDetail,
    SelectionExpertCreate,
    SelectionExpertDetailOut,
    SelectionExpertInviteCreate,
    SelectionExpertInviteOut,
    SelectionExpertInviteUpdate,
    SelectionExpertOut,
    SelectionOut,
    SelectionUpdate,
    VIKORResult,
)
from app.schemas.common import UserSummaryOut
from app.services.activity_service import activity_service
from app.services.document_processing_service import document_processing_service
from app.services.email_service import email_service
from app.services.storage_service import storage_service
from app.services.vikor_service import VIKORInput, run_vikor


class CandidateSelectionService:
    async def list_selections(self, db: AsyncSession, user_id: int) -> Sequence[Selection]:
        result = await db.execute(
            select(Selection)
            .where(Selection.user_id == user_id)
            .order_by(Selection.created_at.desc())
        )
        return result.scalars().all()

    async def get_selection(self, db: AsyncSession, selection_id: int, user_id: int) -> SelectionDetail:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        return self._serialize_selection_detail(selection)

    async def create_selection(self, db: AsyncSession, data: SelectionCreate, user_id: int) -> Selection:
        model = (
            await db.execute(
                select(CompetencyModel).where(
                    CompetencyModel.id == data.model_id,
                    CompetencyModel.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if not model:
            raise HTTPException(status_code=404, detail="Competency model not found")
        if model.status != ModelStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Only completed competency models can be used")
        final_alternatives = (
            await db.execute(
                select(Alternative)
                .options(
                    selectinload(Alternative.competency),
                    selectinload(Alternative.custom_competency),
                )
                .where(
                    Alternative.model_id == data.model_id,
                    Alternative.final_weight.isnot(None),
                )
            )
        ).scalars().all()
        if not final_alternatives:
            raise HTTPException(status_code=400, detail="Competency model has no final competencies")
        selection = Selection(
            user_id=user_id,
            model_id=data.model_id,
            evaluation_deadline=data.evaluation_deadline,
            status=SelectionStatus.DRAFT,
        )
        db.add(selection)
        await db.flush()
        for alternative in final_alternatives:
            db.add(
                SelectionCriterion(
                    selection_id=selection.id,
                    alternative_id=alternative.id,
                    competency_id=alternative.competency_id,
                    custom_competency_id=alternative.custom_competency_id,
                    name=self._resolve_selection_criterion_name(alternative),
                    weight=alternative.final_weight,
                )
            )
        await db.flush()
        await db.refresh(selection)
        return selection

    async def update_selection(
        self, db: AsyncSession, selection_id: int, user_id: int, data: SelectionUpdate
    ) -> Selection:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        self._require_status(selection, SelectionStatus.DRAFT)
        if data.evaluation_deadline is not None:
            selection.evaluation_deadline = data.evaluation_deadline
        await db.flush()
        await db.refresh(selection)
        return selection

    async def delete_selection(self, db: AsyncSession, selection_id: int, user_id: int) -> None:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        self._require_status(selection, SelectionStatus.DRAFT)
        await db.delete(selection)

    async def list_candidates(self, db: AsyncSession, user_id: int) -> list[CandidateOut]:
        result = await db.execute(
            select(
                Candidate,
                func.count(CandidateCompetency.competency_id).label("matched_competency_count"),
            )
            .outerjoin(CandidateCompetency, CandidateCompetency.candidate_id == Candidate.id)
            .where(Candidate.user_id == user_id)
            .group_by(Candidate.id)
            .order_by(Candidate.created_at.desc())
        )
        return [
            self._serialize_candidate_summary(candidate, matched_competency_count)
            for candidate, matched_competency_count in result.all()
        ]

    async def get_candidate(
        self, db: AsyncSession, candidate_id: int, user_id: int
    ) -> CandidateWithCompetencies:
        candidate = await self._get_candidate_orm(db, candidate_id, user_id)
        return self._serialize_candidate(candidate)

    async def create_candidate(self, db: AsyncSession, data: CandidateCreate, user_id: int) -> CandidateOut:
        profession = (
            await db.execute(select(Profession).where(Profession.id == data.profession_id))
        ).scalar_one_or_none()
        if not profession:
            raise HTTPException(status_code=404, detail="Profession not found")
        candidate = Candidate(
            user_id=user_id,
            name=data.name,
            email=data.email,
            profession_id=data.profession_id,
            cv_parse_status=CandidateCVParseStatus.NOT_UPLOADED,
        )
        db.add(candidate)
        await db.flush()
        await db.refresh(candidate)
        return self._serialize_candidate_summary(candidate, 0)

    async def upload_candidate_cv(
        self,
        db: AsyncSession,
        candidate_id: int,
        user_id: int,
        filename: str | None,
        content_type: str | None,
        content: bytes,
    ) -> CandidateOut:
        candidate = await self._get_candidate_orm(db, candidate_id, user_id)
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        old_path = candidate.cv_file_path
        new_path = await storage_service.upload_candidate_cv(
            user_id=user_id,
            candidate_id=candidate_id,
            filename=filename,
            content=content,
            content_type=content_type,
        )
        candidate.cv_file_path = new_path
        candidate.cv_original_filename = filename
        candidate.cv_mime_type = content_type
        candidate.cv_uploaded_at = datetime.now(timezone.utc)
        candidate.cv_parse_status = CandidateCVParseStatus.UPLOADED
        candidate.cv_parsed_at = None
        candidate.cv_parse_error = None
        await db.execute(
            delete(CandidateCompetency).where(CandidateCompetency.candidate_id == candidate_id)
        )
        await db.flush()
        await db.refresh(candidate)
        if old_path:
            try:
                await storage_service.delete_cv(old_path)
            except Exception:
                pass
        return self._serialize_candidate_summary(candidate, 0)

    async def delete_candidate_cv(self, db: AsyncSession, candidate_id: int, user_id: int) -> CandidateOut:
        candidate = await self._get_candidate_orm(db, candidate_id, user_id)
        if not candidate.cv_file_path:
            raise HTTPException(status_code=404, detail="Candidate CV is not uploaded")
        path = candidate.cv_file_path
        candidate.cv_file_path = None
        candidate.cv_original_filename = None
        candidate.cv_mime_type = None
        candidate.cv_uploaded_at = None
        candidate.cv_parse_status = CandidateCVParseStatus.NOT_UPLOADED
        candidate.cv_parsed_at = None
        candidate.cv_parse_error = None
        await db.execute(
            delete(CandidateCompetency).where(CandidateCompetency.candidate_id == candidate_id)
        )
        await db.flush()
        try:
            await storage_service.delete_cv(path)
        except Exception:
            pass
        await db.refresh(candidate)
        return self._serialize_candidate_summary(candidate, 0)

    async def get_candidate_cv_url(
        self, db: AsyncSession, candidate_id: int, user_id: int
    ) -> CandidateCVSignedUrl:
        candidate = await self._get_candidate_orm(db, candidate_id, user_id)
        if not candidate.cv_file_path:
            raise HTTPException(status_code=404, detail="Candidate CV is not uploaded")
        url = await storage_service.create_signed_cv_url(candidate.cv_file_path)
        return CandidateCVSignedUrl(
            url=url,
            expires_in=settings.CV_SIGNED_URL_EXPIRE_SECONDS,
        )

    async def parse_candidate_cv(
        self, db: AsyncSession, candidate_id: int, user_id: int
    ) -> CVParseResponse:
        candidate = await self._get_candidate_orm(db, candidate_id, user_id)
        if not candidate.cv_file_path:
            raise HTTPException(status_code=400, detail="Upload CV before parsing")
        candidate.cv_parse_status = CandidateCVParseStatus.PROCESSING
        candidate.cv_parse_error = None
        await db.commit()

        try:
            content = await storage_service.download_cv(candidate.cv_file_path)
            cv_text = self._extract_text(
                content=content,
                filename=candidate.cv_original_filename,
                content_type=candidate.cv_mime_type,
            )
            competency_map = {
                row.id: row.name
                for row in (
                    await db.execute(select(Competency.id, Competency.name))
                ).all()
            }
            matched_ids, matched_names, unrecognized = document_processing_service.parse_text(
                text=cv_text,
                competency_map=competency_map,
            )
            await db.execute(
                delete(CandidateCompetency).where(CandidateCompetency.candidate_id == candidate_id)
            )
            for competency_id in matched_ids:
                db.add(CandidateCompetency(candidate_id=candidate_id, competency_id=competency_id))
            candidate.cv_parse_status = CandidateCVParseStatus.PARSED
            candidate.cv_parsed_at = datetime.now(timezone.utc)
            candidate.cv_parse_error = None
            await db.flush()
            return CVParseResponse(
                candidate_id=candidate_id,
                matched_competency_ids=matched_ids,
                matched_competency_names=matched_names,
                unrecognized_tokens=unrecognized,
            )
        except HTTPException as exc:
            await self._persist_candidate_parse_failure(db, candidate_id, user_id, exc.detail)
            raise
        except Exception as exc:
            await self._persist_candidate_parse_failure(db, candidate_id, user_id, str(exc))
            raise HTTPException(status_code=500, detail="Failed to parse candidate CV") from exc

    async def add_candidate_to_selection(
        self, db: AsyncSession, selection_id: int, user_id: int, candidate_id: int
    ) -> CandidateSelection:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        self._require_status(selection, SelectionStatus.DRAFT)
        await self._get_candidate_orm(db, candidate_id, user_id)
        existing = (
            await db.execute(
                select(CandidateSelection).where(
                    CandidateSelection.candidate_id == candidate_id,
                    CandidateSelection.selection_id == selection_id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Candidate is already in this selection")
        cs = CandidateSelection(candidate_id=candidate_id, selection_id=selection_id)
        db.add(cs)
        await db.flush()
        await db.refresh(cs)
        return cs

    async def remove_candidate_from_selection(
        self, db: AsyncSession, selection_id: int, user_id: int, candidate_id: int
    ) -> None:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        self._require_status(selection, SelectionStatus.DRAFT)
        await self._get_candidate_orm(db, candidate_id, user_id)
        await db.execute(
            delete(CandidateSelection).where(
                CandidateSelection.candidate_id == candidate_id,
                CandidateSelection.selection_id == selection_id,
            )
        )

    async def add_expert(
        self, db: AsyncSession, selection_id: int, user_id: int, data: SelectionExpertCreate
    ) -> SelectionExpert:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        self._require_status(selection, SelectionStatus.DRAFT)
        user = await self._get_user(db, data.user_id)
        await self._ensure_user_not_already_expert(db, selection_id, data.user_id)
        await self._ensure_no_pending_invite_for_email(db, selection_id, user.email)
        expert = SelectionExpert(
            selection_id=selection_id,
            user_id=data.user_id,
            weight=data.weight,
        )
        db.add(expert)
        await db.flush()
        await db.refresh(expert)
        return expert

    async def remove_expert(self, db: AsyncSession, selection_id: int, user_id: int, expert_id: int) -> None:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        self._require_status(selection, SelectionStatus.DRAFT)
        expert = await self._get_expert(db, expert_id, selection_id)
        await db.delete(expert)

    async def list_expert_invites(
        self, db: AsyncSession, selection_id: int, user_id: int
    ) -> list[SelectionExpertInvite]:
        await self._get_selection_orm(db, selection_id, user_id)
        result = await db.execute(
            select(SelectionExpertInvite)
            .where(SelectionExpertInvite.selection_id == selection_id)
            .order_by(SelectionExpertInvite.created_at, SelectionExpertInvite.id)
        )
        return result.scalars().all()

    async def create_expert_invite(
        self,
        db: AsyncSession,
        selection_id: int,
        user_id: int,
        data: SelectionExpertInviteCreate,
    ) -> SelectionExpertInvite:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        self._require_status(selection, SelectionStatus.DRAFT)
        normalized_email = data.email.strip().lower()
        await self._ensure_invite_email_missing(db, selection_id, normalized_email)
        await self._ensure_email_not_already_expert(db, selection_id, normalized_email)
        invite = SelectionExpertInvite(
            selection_id=selection_id,
            email=normalized_email,
            weight=data.weight,
            token=secrets.token_urlsafe(24),
        )
        db.add(invite)
        await db.flush()
        await db.refresh(invite)
        await email_service.send_selection_invite(db, invite.id)
        return invite

    async def update_expert_invite(
        self,
        db: AsyncSession,
        selection_id: int,
        invite_id: int,
        user_id: int,
        data: SelectionExpertInviteUpdate,
    ) -> SelectionExpertInvite:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        self._require_status(selection, SelectionStatus.DRAFT)
        invite = await self._get_expert_invite(db, invite_id, selection_id)
        if invite.accepted_by_user_id is not None:
            raise HTTPException(status_code=400, detail="Accepted invite cannot be updated")
        if data.email is not None:
            normalized_email = data.email.strip().lower()
            if normalized_email != invite.email:
                await self._ensure_invite_email_missing(
                    db,
                    selection_id,
                    normalized_email,
                    exclude_id=invite.id,
                )
                await self._ensure_email_not_already_expert(db, selection_id, normalized_email)
                invite.email = normalized_email
        if data.weight is not None:
            invite.weight = data.weight
        await db.flush()
        await db.refresh(invite)
        return invite

    async def delete_expert_invite(
        self, db: AsyncSession, selection_id: int, invite_id: int, user_id: int
    ) -> None:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        self._require_status(selection, SelectionStatus.DRAFT)
        invite = await self._get_expert_invite(db, invite_id, selection_id)
        await db.delete(invite)

    async def submit_selection(self, db: AsyncSession, selection_id: int, user_id: int) -> Selection:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        self._require_status(selection, SelectionStatus.DRAFT)
        pending_invites = [invite for invite in selection.expert_invites if invite.accepted_by_user_id is None]
        if not selection.candidates:
            raise HTTPException(status_code=400, detail="Add at least one candidate")
        if not selection.experts and not pending_invites:
            raise HTTPException(status_code=400, detail="Add at least one expert or invite")
        selection.status = SelectionStatus.EXPERT_EVALUATION
        await db.flush()
        await activity_service.log(db, selection.user_id, "selection", selection.id, "status_change", "draft", "expert_evaluation")
        await db.refresh(selection)
        return selection

    async def cancel_selection(self, db: AsyncSession, selection_id: int, user_id: int) -> Selection:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        if selection.status in (SelectionStatus.COMPLETED, SelectionStatus.CANCELLED):
            raise HTTPException(status_code=400, detail="Selection is already terminal")
        old_status = "draft" if selection.status == SelectionStatus.DRAFT else "expert_evaluation"
        selection.status = SelectionStatus.CANCELLED
        await db.flush()
        await activity_service.log(db, selection.user_id, "selection", selection.id, "status_change", old_status, "cancelled")
        await db.refresh(selection)
        return selection

    async def submit_expert_scores(
        self,
        db: AsyncSession,
        selection_id: int,
        current_user_id: int,
        data: ExpertScoringSubmit,
    ) -> ExpertScoringStatus:
        expert = await self._get_expert_by_user(db, selection_id, current_user_id)
        selection = await self._get_selection_for_status_check(db, selection_id)
        if selection.status != SelectionStatus.EXPERT_EVALUATION:
            raise HTTPException(status_code=400, detail="Selection is not in expert evaluation status")
        if selection.evaluation_deadline:
            deadline = selection.evaluation_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > deadline:
                raise HTTPException(status_code=400, detail="Evaluation deadline has passed")
        for item in data.scores:
            if not (1 <= item.score <= 5):
                raise HTTPException(status_code=400, detail=f"Score must be between 1 and 5, got {item.score}")

        candidate_ids = await self._get_selection_candidate_ids(db, selection_id)
        criterion_ids = await self._get_selection_criterion_ids(db, selection_id)
        expected_pairs = {
            (candidate_id, criterion_id)
            for candidate_id in candidate_ids
            for criterion_id in criterion_ids
        }
        submitted_pairs = [(item.candidate_id, item.selection_criterion_id) for item in data.scores]
        if set(submitted_pairs) != expected_pairs or len(submitted_pairs) != len(expected_pairs):
            raise HTTPException(
                status_code=400,
                detail="Scores must cover every candidate for every final competency exactly once",
            )

        had_existing_submission = (
            await db.execute(select(func.count()).where(CandidateScore.expert_id == expert.id))
        ).scalar_one() > 0
        await db.execute(delete(CandidateScore).where(CandidateScore.expert_id == expert.id))
        for item in data.scores:
            db.add(
                CandidateScore(
                    candidate_id=item.candidate_id,
                    expert_id=expert.id,
                    selection_criterion_id=item.selection_criterion_id,
                    score=item.score,
                )
            )
        await db.flush()
        if not had_existing_submission:
            await activity_service.log(db, selection.user_id, "selection", selection_id, "evaluation_submitted", None, str(expert.id))
            await email_service.send_selection_submission_received(db, selection_id, current_user_id)
        return await self.get_expert_scoring_status(db, selection_id, current_user_id)

    async def get_expert_scoring_status(
        self, db: AsyncSession, selection_id: int, user_id: int
    ) -> ExpertScoringStatus:
        expert = await self._get_expert_by_user(db, selection_id, user_id)
        selection = await self._get_selection_for_status_check(db, selection_id)
        candidate_ids = await self._get_selection_candidate_ids(db, selection_id)
        criterion_ids = await self._get_selection_criterion_ids(db, selection_id)
        total = len(candidate_ids) * len(criterion_ids)
        scored = (
            await db.execute(select(func.count()).where(CandidateScore.expert_id == expert.id))
        ).scalar_one()
        return ExpertScoringStatus(
            expert_id=expert.id,
            scored=scored,
            total=total,
            is_complete=scored == total and total > 0,
        )

    async def list_selections_as_expert(self, db: AsyncSession, user_id: int) -> Sequence[Selection]:
        result = await db.execute(
            select(Selection)
            .join(SelectionExpert, SelectionExpert.selection_id == Selection.id)
            .where(
                SelectionExpert.user_id == user_id,
                Selection.status == SelectionStatus.EXPERT_EVALUATION,
            )
            .order_by(Selection.evaluation_deadline)
        )
        return result.scalars().all()

    async def list_pending_invites_for_user(
        self, db: AsyncSession, user_id: int
    ) -> list[SelectionExpertInviteOut]:
        user = await self._get_user(db, user_id)
        normalized_email = user.email.strip().lower()
        result = await db.execute(
            select(SelectionExpertInvite)
            .join(Selection, Selection.id == SelectionExpertInvite.selection_id)
            .where(
                SelectionExpertInvite.accepted_by_user_id.is_(None),
                func.lower(SelectionExpertInvite.email) == normalized_email,
                Selection.status != SelectionStatus.CANCELLED,
            )
            .order_by(SelectionExpertInvite.created_at.desc())
        )
        return [self._serialize_expert_invite(invite) for invite in result.scalars().all()]

    async def accept_expert_invite(
        self, db: AsyncSession, token: str, user_id: int
    ) -> SelectionExpert:
        user = await self._get_user(db, user_id)
        invite = await self._get_expert_invite_by_token(db, token)
        normalized_email = user.email.strip().lower()
        if invite.email != normalized_email:
            raise HTTPException(status_code=403, detail="Invite email does not match current user")
        if invite.accepted_by_user_id is not None:
            raise HTTPException(status_code=409, detail="Invite has already been accepted")
        selection = await self._get_selection_for_status_check(db, invite.selection_id)
        if selection.status == SelectionStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="Selection has been cancelled")
        if selection.status == SelectionStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Selection is already completed")
        await self._ensure_user_not_already_expert(db, invite.selection_id, user.id)
        expert = SelectionExpert(
            selection_id=invite.selection_id,
            user_id=user.id,
            weight=invite.weight,
        )
        db.add(expert)
        invite.accepted_by_user_id = user.id
        await db.flush()
        await db.refresh(expert)
        await activity_service.log(db, selection.user_id, "selection", selection.id, "invite_accepted", None, user.email)
        await email_service.send_selection_invite_accepted(db, invite.selection_id, user.id)
        return expert

    async def calculate_vikor(self, db: AsyncSession, selection_id: int, user_id: int) -> VIKORResult:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        return await self._calculate_vikor_for_selection(db, selection)

    async def process_selection_deadline(self, db: AsyncSession, selection_id: int) -> Selection:
        selection = await self._get_selection_for_status_check(db, selection_id)
        if selection.status != SelectionStatus.EXPERT_EVALUATION:
            return selection

        experts = (
            await db.execute(select(SelectionExpert).where(SelectionExpert.selection_id == selection_id))
        ).scalars().all()
        candidate_ids = await self._get_selection_candidate_ids(db, selection_id)
        criterion_ids = await self._get_selection_criterion_ids(db, selection_id)

        if experts and candidate_ids and criterion_ids:
            try:
                await self._ensure_selection_scoring_complete(
                    db,
                    selection_id,
                    experts,
                    candidate_ids,
                    criterion_ids,
                )
            except HTTPException:
                selection.status = SelectionStatus.CANCELLED
                await db.flush()
                await activity_service.log(db, selection.user_id, "selection", selection.id, "status_change", "expert_evaluation", "cancelled")
                await db.refresh(selection)
                return selection
            await self._calculate_vikor_for_selection(db, selection)
            await db.refresh(selection)
            return selection

        selection.status = SelectionStatus.CANCELLED
        await db.flush()
        await activity_service.log(db, selection.user_id, "selection", selection.id, "status_change", "expert_evaluation", "cancelled")
        await db.refresh(selection)
        return selection

    async def _calculate_vikor_for_selection(
        self,
        db: AsyncSession,
        selection: Selection,
    ) -> VIKORResult:
        if selection.status != SelectionStatus.EXPERT_EVALUATION:
            raise HTTPException(status_code=400, detail="VIKOR can only run in expert evaluation status")

        selection_id = selection.id
        experts = (
            await db.execute(select(SelectionExpert).where(SelectionExpert.selection_id == selection_id))
        ).scalars().all()
        if not experts:
            raise HTTPException(status_code=400, detail="No accepted experts for this selection")

        candidate_ids = await self._get_selection_candidate_ids(db, selection_id)
        criterion_ids = await self._get_selection_criterion_ids(db, selection_id)
        await self._ensure_selection_scoring_complete(
            db,
            selection_id,
            experts,
            candidate_ids,
            criterion_ids,
        )

        all_scores = (
            await db.execute(
                select(CandidateScore)
                .join(SelectionExpert, SelectionExpert.id == CandidateScore.expert_id)
                .where(SelectionExpert.selection_id == selection_id)
            )
        ).scalars().all()
        criterion_weights = await self._get_selection_criterion_weights(db, selection_id)
        expert_weights = self._normalize_expert_weights(experts)
        aggregated: dict[tuple[int, int], float] = {}
        for score in all_scores:
            key = (score.candidate_id, score.selection_criterion_id)
            aggregated[key] = aggregated.get(key, 0.0) + score.score * expert_weights.get(score.expert_id, 0.0)
        vikor_inputs = [
            VIKORInput(
                candidate_id=candidate_id,
                criterion_id=criterion_id,
                aggregated_score=aggregated[(candidate_id, criterion_id)],
            )
            for candidate_id in candidate_ids
            for criterion_id in criterion_ids
        ]
        vikor_results = run_vikor(vikor_inputs, criterion_weights)
        for result in vikor_results:
            cs = (
                await db.execute(
                    select(CandidateSelection).where(
                        CandidateSelection.candidate_id == result.candidate_id,
                        CandidateSelection.selection_id == selection_id,
                    )
                )
            ).scalar_one_or_none()
            if cs:
                cs.score = result.q_score
                cs.rank = result.rank
        selection.status = SelectionStatus.COMPLETED
        await db.flush()
        await activity_service.log(db, selection.user_id, "selection", selection.id, "status_change", "expert_evaluation", "completed")
        candidates = {
            item.id: item
            for item in (
                await db.execute(
                    select(Candidate).where(Candidate.id.in_([item.candidate_id for item in vikor_results]))
                )
            ).scalars().all()
        }
        return VIKORResult(
            ranked_candidates=[
                CandidateRankOut(
                    candidate_id=item.candidate_id,
                    candidate_name=candidates[item.candidate_id].name if item.candidate_id in candidates else None,
                    score=item.q_score,
                    rank=item.rank,
                )
                for item in sorted(vikor_results, key=lambda result: result.rank)
            ],
            status="success",
        )

    async def get_selection_results(
        self, db: AsyncSession, selection_id: int, user_id: int
    ) -> VIKORResult:
        selection = await self._get_selection_orm(db, selection_id, user_id)
        if selection.status != SelectionStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Results are only available for completed selections")
        rows = (
            await db.execute(
                select(CandidateSelection, Candidate.name)
                .join(Candidate, Candidate.id == CandidateSelection.candidate_id)
                .where(CandidateSelection.selection_id == selection_id)
                .order_by(CandidateSelection.rank)
            )
        ).all()
        return VIKORResult(
            ranked_candidates=[
                CandidateRankOut(
                    candidate_id=row.CandidateSelection.candidate_id,
                    candidate_name=row.name,
                    score=float(row.CandidateSelection.score or 0),
                    rank=row.CandidateSelection.rank or 0,
                )
                for row in rows
            ],
            status="success",
        )

    def _require_status(self, selection: Selection, required: SelectionStatus) -> None:
        if selection.status is None or selection.status != required:
            current = SelectionStatus(selection.status).name if selection.status is not None else "None"
            raise HTTPException(status_code=400, detail=f"Operation is unavailable in status {current}")

    async def _get_selection_orm(
        self, db: AsyncSession, selection_id: int, user_id: int
    ) -> Selection:
        result = await db.execute(
            select(Selection)
            .where(Selection.id == selection_id, Selection.user_id == user_id)
            .options(
                selectinload(Selection.candidates).selectinload(CandidateSelection.candidate),
                selectinload(Selection.experts).selectinload(SelectionExpert.user),
                selectinload(Selection.criteria),
                selectinload(Selection.expert_invites),
            )
        )
        selection = result.scalar_one_or_none()
        if not selection:
            raise HTTPException(status_code=404, detail="Selection not found")
        return selection

    async def _get_candidate_orm(
        self, db: AsyncSession, candidate_id: int, user_id: int
    ) -> Candidate:
        result = await db.execute(
            select(Candidate)
            .where(Candidate.id == candidate_id, Candidate.user_id == user_id)
            .options(
                selectinload(Candidate.competencies).selectinload(CandidateCompetency.competency),
            )
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return candidate

    async def _get_selection_for_status_check(self, db: AsyncSession, selection_id: int) -> Selection:
        result = await db.execute(select(Selection).where(Selection.id == selection_id))
        selection = result.scalar_one_or_none()
        if not selection:
            raise HTTPException(status_code=404, detail="Selection not found")
        return selection

    async def _get_expert(self, db: AsyncSession, expert_id: int, selection_id: int) -> SelectionExpert:
        result = await db.execute(
            select(SelectionExpert).where(
                SelectionExpert.id == expert_id,
                SelectionExpert.selection_id == selection_id,
            )
        )
        expert = result.scalar_one_or_none()
        if not expert:
            raise HTTPException(status_code=404, detail="Expert not found")
        return expert

    async def _get_expert_by_user(
        self, db: AsyncSession, selection_id: int, user_id: int
    ) -> SelectionExpert:
        result = await db.execute(
            select(SelectionExpert).where(
                SelectionExpert.selection_id == selection_id,
                SelectionExpert.user_id == user_id,
            )
        )
        expert = result.scalar_one_or_none()
        if not expert:
            raise HTTPException(status_code=403, detail="Current user is not an expert for this selection")
        return expert

    async def _get_expert_invite(
        self, db: AsyncSession, invite_id: int, selection_id: int
    ) -> SelectionExpertInvite:
        result = await db.execute(
            select(SelectionExpertInvite).where(
                SelectionExpertInvite.id == invite_id,
                SelectionExpertInvite.selection_id == selection_id,
            )
        )
        invite = result.scalar_one_or_none()
        if not invite:
            raise HTTPException(status_code=404, detail="Expert invite not found")
        return invite

    async def _get_expert_invite_by_token(self, db: AsyncSession, token: str) -> SelectionExpertInvite:
        result = await db.execute(select(SelectionExpertInvite).where(SelectionExpertInvite.token == token))
        invite = result.scalar_one_or_none()
        if not invite:
            raise HTTPException(status_code=404, detail="Expert invite not found")
        return invite

    async def _get_selection_candidate_ids(self, db: AsyncSession, selection_id: int) -> list[int]:
        return (
            await db.execute(
                select(CandidateSelection.candidate_id).where(
                    CandidateSelection.selection_id == selection_id
                )
            )
        ).scalars().all()

    async def _get_selection_criterion_ids(self, db: AsyncSession, selection_id: int) -> list[int]:
        return (
            await db.execute(
                select(SelectionCriterion.id).where(
                    SelectionCriterion.selection_id == selection_id
                )
            )
        ).scalars().all()

    async def _get_selection_criterion_weights(
        self, db: AsyncSession, selection_id: int
    ) -> dict[int, float]:
        result = await db.execute(
            select(SelectionCriterion.id, SelectionCriterion.weight).where(
                SelectionCriterion.selection_id == selection_id
            )
        )
        return {
            row.id: float(row.weight) if row.weight is not None else 0.0
            for row in result.all()
        }

    def _normalize_expert_weights(self, experts: list[SelectionExpert]) -> dict[int, float]:
        weights = {item.id: float(item.weight) if item.weight else 1.0 for item in experts}
        total = sum(weights.values())
        if total == 0:
            return {expert_id: 1.0 / len(experts) for expert_id in weights}
        return {expert_id: value / total for expert_id, value in weights.items()}

    async def _ensure_selection_scoring_complete(
        self,
        db: AsyncSession,
        selection_id: int,
        experts: list[SelectionExpert],
        candidate_ids: list[int],
        criterion_ids: list[int],
    ) -> None:
        expected_total = len(experts) * len(candidate_ids) * len(criterion_ids)
        if expected_total == 0:
            raise HTTPException(status_code=400, detail="Selection scoring matrix is empty")
        actual_total = (
            await db.execute(
                select(func.count())
                .select_from(CandidateScore)
                .join(SelectionExpert, SelectionExpert.id == CandidateScore.expert_id)
                .where(SelectionExpert.selection_id == selection_id)
            )
        ).scalar_one()
        if actual_total != expected_total:
            raise HTTPException(status_code=400, detail="Selection scoring is incomplete")

    async def _get_user(self, db: AsyncSession, user_id: int) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    async def _ensure_user_not_already_expert(self, db: AsyncSession, selection_id: int, user_id: int) -> None:
        result = await db.execute(
            select(SelectionExpert).where(
                SelectionExpert.selection_id == selection_id,
                SelectionExpert.user_id == user_id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="User is already an expert in this selection")

    async def _ensure_invite_email_missing(
        self,
        db: AsyncSession,
        selection_id: int,
        email: str,
        exclude_id: int | None = None,
    ) -> None:
        query = select(SelectionExpertInvite).where(
            SelectionExpertInvite.selection_id == selection_id,
            func.lower(SelectionExpertInvite.email) == email,
        )
        if exclude_id is not None:
            query = query.where(SelectionExpertInvite.id != exclude_id)
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Invite for this email already exists")

    async def _ensure_email_not_already_expert(self, db: AsyncSession, selection_id: int, email: str) -> None:
        result = await db.execute(
            select(SelectionExpert)
            .join(User, User.id == SelectionExpert.user_id)
            .where(
                SelectionExpert.selection_id == selection_id,
                func.lower(User.email) == email,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="User with this email is already an expert")

    async def _ensure_no_pending_invite_for_email(self, db: AsyncSession, selection_id: int, email: str) -> None:
        normalized_email = email.strip().lower()
        result = await db.execute(
            select(SelectionExpertInvite).where(
                SelectionExpertInvite.selection_id == selection_id,
                func.lower(SelectionExpertInvite.email) == normalized_email,
                SelectionExpertInvite.accepted_by_user_id.is_(None),
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Pending invite for this email already exists")

    def _serialize_selection_detail(self, selection: Selection) -> SelectionDetail:
        return SelectionDetail(
            id=selection.id,
            user_id=selection.user_id,
            model_id=selection.model_id,
            evaluation_deadline=selection.evaluation_deadline,
            status_code=selection.status,
            created_at=selection.created_at,
            candidates=[
                CandidateSelectionOut(
                    candidate_id=item.candidate_id,
                    selection_id=item.selection_id,
                    score=float(item.score) if item.score is not None else None,
                    rank=item.rank,
                    candidate_name=item.candidate.name if item.candidate else None,
                    candidate_email=item.candidate.email if item.candidate else None,
                )
                for item in selection.candidates
            ],
            experts=[self._serialize_selection_expert(item) for item in selection.experts],
            criteria=[SelectionCriterionOut.model_validate(item) for item in selection.criteria],
            expert_invites=[self._serialize_expert_invite(item) for item in selection.expert_invites],
        )

    def _serialize_candidate(self, candidate: Candidate) -> CandidateWithCompetencies:
        return CandidateWithCompetencies(
            id=candidate.id,
            user_id=candidate.user_id,
            name=candidate.name,
            email=candidate.email,
            profession_id=candidate.profession_id,
            cv_file_path=candidate.cv_file_path,
            cv_original_filename=candidate.cv_original_filename,
            cv_mime_type=candidate.cv_mime_type,
            cv_uploaded_at=candidate.cv_uploaded_at,
            cv_parse_status=self._resolve_candidate_cv_parse_status(candidate),
            cv_parsed_at=candidate.cv_parsed_at,
            cv_parse_error=candidate.cv_parse_error,
            matched_competency_count=len(candidate.competencies),
            created_at=candidate.created_at,
            competencies=[
                CompetencyShort(id=item.competency.id, name=item.competency.name)
                for item in candidate.competencies
                if item.competency is not None
            ],
        )

    def _serialize_candidate_summary(
        self,
        candidate: Candidate,
        matched_competency_count: int | None = None,
    ) -> CandidateOut:
        return CandidateOut(
            id=candidate.id,
            user_id=candidate.user_id,
            name=candidate.name,
            email=candidate.email,
            profession_id=candidate.profession_id,
            cv_file_path=candidate.cv_file_path,
            cv_original_filename=candidate.cv_original_filename,
            cv_mime_type=candidate.cv_mime_type,
            cv_uploaded_at=candidate.cv_uploaded_at,
            cv_parse_status=self._resolve_candidate_cv_parse_status(candidate),
            cv_parsed_at=candidate.cv_parsed_at,
            cv_parse_error=candidate.cv_parse_error,
            matched_competency_count=matched_competency_count or 0,
            created_at=candidate.created_at,
        )
    
    def _serialize_selection_expert(self, expert: SelectionExpert) -> SelectionExpertDetailOut:
        return SelectionExpertDetailOut(
            id=expert.id,
            selection_id=expert.selection_id,
            user_id=expert.user_id,
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

    def _serialize_expert_invite(self, invite: SelectionExpertInvite) -> SelectionExpertInviteOut:
        return SelectionExpertInviteOut(
            id=invite.id,
            selection_id=invite.selection_id,
            email=invite.email,
            weight=float(invite.weight) if invite.weight is not None else None,
            token=invite.token,
            accepted_by_user_id=invite.accepted_by_user_id,
            created_at=invite.created_at,
        )

    def _resolve_selection_criterion_name(self, alternative: Alternative) -> str:
        if alternative.custom_competency is not None:
            return alternative.custom_competency.name
        if alternative.competency is not None:
            return alternative.competency.name
        raise HTTPException(status_code=400, detail="Alternative has no linked competency")

    def _resolve_candidate_cv_parse_status(self, candidate: Candidate) -> CandidateCVParseStatus:
        if candidate.cv_parse_status is not None:
            return CandidateCVParseStatus(candidate.cv_parse_status)
        if candidate.cv_file_path:
            return CandidateCVParseStatus.UPLOADED
        return CandidateCVParseStatus.NOT_UPLOADED

    async def _persist_candidate_parse_failure(
        self,
        db: AsyncSession,
        candidate_id: int,
        user_id: int,
        error_message: str,
    ) -> None:
        await db.rollback()
        candidate = await self._get_candidate_orm(db, candidate_id, user_id)
        candidate.cv_parse_status = CandidateCVParseStatus.FAILED
        candidate.cv_parsed_at = None
        candidate.cv_parse_error = error_message[:1000]
        await db.commit()

    def _extract_text(
        self,
        content: bytes,
        filename: str | None,
        content_type: str | None,
    ) -> str:
        name = (filename or "").lower()
        mime = (content_type or "").lower()
        if name.endswith(".pdf") or "pdf" in mime:
            import PyPDF2

            reader = PyPDF2.PdfReader(io.BytesIO(content))
            return " ".join(page.extract_text() or "" for page in reader.pages)
        if name.endswith(".docx") or "wordprocessingml" in mime:
            document = Document(io.BytesIO(content))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        return content.decode("utf-8", errors="ignore")


candidate_selection_service = CandidateSelectionService()
