import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.enums import ModelStatus, SelectionStatus
from app.db.session import AsyncSessionLocal
from app.models.models import CompetencyModel, Selection
from app.services.candidate_selection_service import candidate_selection_service
from app.services.competency_model_service import competency_model_service
from app.services.email_service import email_service


logger = logging.getLogger(__name__)


class BackgroundJobRunner:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if not settings.BACKGROUND_JOBS_ENABLED:
            logger.info("Background jobs are disabled")
            return
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop(), name="background-job-runner")
        logger.info(
            "Background jobs started with poll interval %s seconds",
            settings.BACKGROUND_JOBS_POLL_SECONDS,
        )

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("Background jobs stopped")

    async def _run_loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:
                logger.exception("Background job iteration failed")
            await asyncio.sleep(settings.BACKGROUND_JOBS_POLL_SECONDS)

    async def run_once(self) -> None:
        async with AsyncSessionLocal() as session:
            reminded_models = await self._send_due_soon_model_reminders(session)
            reminded_selections = await self._send_due_soon_selection_reminders(session)
            processed_models = await self._process_due_models(session)
            processed_selections = await self._process_due_selections(session)
            await session.commit()
            if reminded_models or reminded_selections or processed_models or processed_selections:
                logger.info(
                    "Background jobs sent %s model reminders, %s selection reminders, processed %s due models and %s due selections",
                    reminded_models,
                    reminded_selections,
                    processed_models,
                    processed_selections,
                )

    async def _send_due_soon_model_reminders(self, session) -> int:
        if settings.EMAIL_DEADLINE_REMINDER_DAYS <= 0:
            return 0
        now = datetime.now(timezone.utc)
        reminder_cutoff = now + timedelta(days=settings.EMAIL_DEADLINE_REMINDER_DAYS)
        result = await session.execute(
            select(CompetencyModel.id)
            .where(
                CompetencyModel.status == ModelStatus.EXPERT_EVALUATION,
                CompetencyModel.evaluation_deadline.isnot(None),
                CompetencyModel.evaluation_deadline > now,
                CompetencyModel.evaluation_deadline <= reminder_cutoff,
            )
            .order_by(CompetencyModel.evaluation_deadline, CompetencyModel.id)
        )
        model_ids = result.scalars().all()
        reminded = 0
        for model_id in model_ids:
            try:
                reminded += await email_service.send_competency_model_deadline_reminders(
                    session,
                    model_id,
                    settings.EMAIL_DEADLINE_REMINDER_DAYS,
                )
                await session.commit()
            except Exception:
                logger.exception("Failed to send reminder emails for competency model %s", model_id)
                await session.rollback()
        return reminded

    async def _send_due_soon_selection_reminders(self, session) -> int:
        if settings.EMAIL_DEADLINE_REMINDER_DAYS <= 0:
            return 0
        now = datetime.now(timezone.utc)
        reminder_cutoff = now + timedelta(days=settings.EMAIL_DEADLINE_REMINDER_DAYS)
        result = await session.execute(
            select(Selection.id)
            .where(
                Selection.status == SelectionStatus.EXPERT_EVALUATION,
                Selection.evaluation_deadline.isnot(None),
                Selection.evaluation_deadline > now,
                Selection.evaluation_deadline <= reminder_cutoff,
            )
            .order_by(Selection.evaluation_deadline, Selection.id)
        )
        selection_ids = result.scalars().all()
        reminded = 0
        for selection_id in selection_ids:
            try:
                reminded += await email_service.send_selection_deadline_reminders(
                    session,
                    selection_id,
                    settings.EMAIL_DEADLINE_REMINDER_DAYS,
                )
                await session.commit()
            except Exception:
                logger.exception("Failed to send reminder emails for selection %s", selection_id)
                await session.rollback()
        return reminded

    async def _process_due_models(self, session) -> int:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(CompetencyModel.id)
            .where(
                CompetencyModel.status == ModelStatus.EXPERT_EVALUATION,
                CompetencyModel.evaluation_deadline.isnot(None),
                CompetencyModel.evaluation_deadline <= now,
            )
            .order_by(CompetencyModel.evaluation_deadline, CompetencyModel.id)
        )
        model_ids = result.scalars().all()
        processed = 0
        for model_id in model_ids:
            try:
                await competency_model_service.calculate_opa_for_deadline(session, model_id)
                await email_service.send_competency_model_deadline_result(session, model_id)
                await session.commit()
                processed += 1
            except Exception:
                logger.exception("Failed to process due competency model %s", model_id)
                await session.rollback()
        return processed

    async def _process_due_selections(self, session) -> int:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Selection.id)
            .where(
                Selection.status == SelectionStatus.EXPERT_EVALUATION,
                Selection.evaluation_deadline.isnot(None),
                Selection.evaluation_deadline <= now,
            )
            .order_by(Selection.evaluation_deadline, Selection.id)
        )
        selection_ids = result.scalars().all()
        processed = 0
        for selection_id in selection_ids:
            try:
                await candidate_selection_service.process_selection_deadline(session, selection_id)
                await email_service.send_selection_deadline_result(session, selection_id)
                await session.commit()
                processed += 1
            except Exception:
                logger.exception("Failed to process due selection %s", selection_id)
                await session.rollback()
        return processed


background_job_runner = BackgroundJobRunner()
