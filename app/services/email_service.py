import logging
from urllib.parse import urlencode
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import (
    EmailDeliveryStatus,
    EmailTemplateKey,
    ModelStatus,
    SelectionStatus,
)
from app.models.models import (
    CompetencyModel,
    Email,
    ExpertInvite,
    ModelExpert,
    Selection,
    SelectionExpert,
    SelectionExpertInvite,
    User,
)


logger = logging.getLogger(__name__)


SUBJECT_TEMPLATES: dict[EmailTemplateKey, str] = {
    EmailTemplateKey.WELCOME: "Welcome to {{ product_name }}",
    EmailTemplateKey.EXPERT_INVITE: "{{ workflow_label }} invitation for {{ resource_name }}",
    EmailTemplateKey.EXPERT_DEADLINE_REMINDER: "Reminder: {{ resource_name }} deadline is in {{ days_before_deadline }} day(s)",
    EmailTemplateKey.OWNER_DEADLINE_REMINDER: "Reminder: {{ resource_name }} deadline is in {{ days_before_deadline }} day(s)",
    EmailTemplateKey.OWNER_DEADLINE_REACHED_COMPLETED: "{{ resource_name }} was completed at deadline",
    EmailTemplateKey.OWNER_DEADLINE_REACHED_CANCELLED: "{{ resource_name }} was cancelled at deadline",
    EmailTemplateKey.OWNER_INVITE_ACCEPTED: "{{ expert_name }} accepted the invite for {{ resource_name }}",
    EmailTemplateKey.OWNER_SUBMISSION_RECEIVED: "{{ expert_name }} submitted for {{ resource_name }}",
    EmailTemplateKey.PASSWORD_RESET: "Reset your CompetencyHub password",
}

@dataclass
class RenderedEmail:
    subject: str
    html: str
    text: str


@dataclass
class EmailProviderResult:
    provider: str
    message_id: str | None


class EmailProviderError(RuntimeError):
    pass


class ResendEmailProvider:
    provider_name = "resend"
    api_url = "https://api.resend.com/emails"

    async def send(
        self,
        *,
        to_email: str,
        subject: str,
        html: str,
        text: str,
    ) -> EmailProviderResult:
        if not settings.RESEND_API_KEY:
            raise EmailProviderError("RESEND_API_KEY is not configured")
        if not settings.EMAIL_FROM:
            raise EmailProviderError("EMAIL_FROM is not configured")

        payload: dict[str, Any] = {
            "from": settings.EMAIL_FROM,
            "to": [to_email],
            "subject": subject,
            "html": html,
            "text": text,
        }
        if settings.EMAIL_REPLY_TO:
            payload["reply_to"] = [settings.EMAIL_REPLY_TO]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            details = ""
            response = getattr(exc, "response", None)
            if response is not None:
                details = response.text[:500]
            raise EmailProviderError(f"Resend request failed: {details or exc}") from exc

        data = response.json()
        return EmailProviderResult(
            provider=self.provider_name,
            message_id=data.get("id"),
        )


class EmailTemplateRenderer:
    def __init__(self) -> None:
        template_dir = Path(__file__).resolve().parents[1] / "templates" / "emails"
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        )

    def render(self, template_key: EmailTemplateKey, context: dict[str, Any]) -> RenderedEmail:
        subject_template = self._env.from_string(SUBJECT_TEMPLATES[template_key])
        subject = subject_template.render(**context).strip()
        html = self._env.get_template(f"{template_key.value}.html.j2").render(**context)
        text = self._env.get_template(f"{template_key.value}.txt.j2").render(**context)
        return RenderedEmail(
            subject=subject,
            html=html,
            text=text.strip(),
        )


class EmailService:
    def __init__(
        self,
        renderer: EmailTemplateRenderer | None = None,
        provider: ResendEmailProvider | None = None,
    ) -> None:
        self._renderer = renderer or EmailTemplateRenderer()
        self._provider = provider or ResendEmailProvider()

    async def send_welcome_email(self, db: AsyncSession, user_id: int) -> Email | None:
        user = await self._get_user(db, user_id)
        if not user:
            return None
        return await self._send_email(
            db,
            template_key=EmailTemplateKey.WELCOME,
            to_email=user.email,
            user_id=user.id,
            entity_type=None,
            entity_id=None,
            dedupe_key=f"user:{user.id}:welcome",
            context={
                "recipient_name": self._display_name(user),
                "product_name": settings.PROJECT_NAME,
                "app_url": settings.frontend_base_url,
            },
        )

    async def send_password_reset_email(
        self,
        db: AsyncSession,
        user_id: int,
        token: str,
    ) -> None:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return

        frontend_url = settings.frontend_base_url
        reset_url: str | None = None
        if frontend_url:
            reset_url = f"{frontend_url.rstrip('/')}/reset-password?token={token}"

        await self._send_email(
            db,
            template_key=EmailTemplateKey.PASSWORD_RESET,
            to_email=user.email,
            user_id=user.id,
            entity_type=None,
            entity_id=None,
            dedupe_key=f"user:{user.id}:password-reset:{token[:16]}",
            context={
                "recipient_name": user.name or user.email,
                "reset_url": reset_url,
                "app_url": frontend_url,
            },
        )

    async def send_competency_model_invite(self, db: AsyncSession, invite_id: int) -> Email | None:
        row = (
            await db.execute(
                select(ExpertInvite, CompetencyModel, User)
                .join(CompetencyModel, CompetencyModel.id == ExpertInvite.model_id)
                .join(User, User.id == CompetencyModel.user_id)
                .where(ExpertInvite.id == invite_id)
            )
        ).first()
        if not row:
            return None
        invite, model, owner = row
        invite_url = await self._invite_landing_url(db, invite.email)
        return await self._send_email(
            db,
            template_key=EmailTemplateKey.EXPERT_INVITE,
            to_email=invite.email,
            user_id=None,
            entity_type="competency_model",
            entity_id=model.id,
            dedupe_key=f"competency-model-invite:{invite.id}",
            context={
                "recipient_name": invite.email,
                "workflow_label": "Competency model expert review",
                "resource_kind": "competency model",
                "resource_name": self._format_model_name(model),
                "resource_url": invite_url,
                "owner_name": self._display_name(owner),
                "deadline": self._format_datetime(model.evaluation_deadline),
                "assignment_details": None,
                "app_url": settings.frontend_base_url,
            },
        )

    async def send_selection_invite(self, db: AsyncSession, invite_id: int) -> Email | None:
        row = (
            await db.execute(
                select(SelectionExpertInvite, Selection, User, CompetencyModel)
                .join(Selection, Selection.id == SelectionExpertInvite.selection_id)
                .join(User, User.id == Selection.user_id)
                .outerjoin(CompetencyModel, CompetencyModel.id == Selection.model_id)
                .where(SelectionExpertInvite.id == invite_id)
            )
        ).first()
        if not row:
            return None
        invite, selection, owner, model = row
        invite_url = await self._invite_landing_url(db, invite.email)
        return await self._send_email(
            db,
            template_key=EmailTemplateKey.EXPERT_INVITE,
            to_email=invite.email,
            user_id=None,
            entity_type="selection",
            entity_id=selection.id,
            dedupe_key=f"selection-invite:{invite.id}",
            context={
                "recipient_name": invite.email,
                "workflow_label": "Candidate selection expert review",
                "resource_kind": "candidate selection",
                "resource_name": self._format_selection_name(selection, model),
                "resource_url": invite_url,
                "owner_name": self._display_name(owner),
                "deadline": self._format_datetime(selection.evaluation_deadline),
                "assignment_details": None,
                "app_url": settings.frontend_base_url,
            },
        )

    async def send_competency_model_invite_accepted(
        self,
        db: AsyncSession,
        model_id: int,
        expert_user_id: int,
    ) -> Email | None:
        row = await self._load_model_owner_and_expert(db, model_id, expert_user_id)
        if not row:
            return None
        model, owner, expert = row
        return await self._send_owner_progress_email(
            db,
            template_key=EmailTemplateKey.OWNER_INVITE_ACCEPTED,
            owner=owner,
            expert=expert,
            resource_name=self._format_model_name(model),
            resource_kind="competency model",
            entity_type="competency_model",
            entity_id=model.id,
            dedupe_key=f"competency-model:{model.id}:invite-accepted:{expert.id}",
        )

    async def send_selection_invite_accepted(
        self,
        db: AsyncSession,
        selection_id: int,
        expert_user_id: int,
    ) -> Email | None:
        row = await self._load_selection_owner_and_expert(db, selection_id, expert_user_id)
        if not row:
            return None
        selection, owner, expert, model = row
        return await self._send_owner_progress_email(
            db,
            template_key=EmailTemplateKey.OWNER_INVITE_ACCEPTED,
            owner=owner,
            expert=expert,
            resource_name=self._format_selection_name(selection, model),
            resource_kind="candidate selection",
            entity_type="selection",
            entity_id=selection.id,
            dedupe_key=f"selection:{selection.id}:invite-accepted:{expert.id}",
        )

    async def send_competency_model_submission_received(
        self,
        db: AsyncSession,
        model_id: int,
        expert_user_id: int,
    ) -> Email | None:
        row = await self._load_model_owner_and_expert(db, model_id, expert_user_id)
        if not row:
            return None
        model, owner, expert = row
        return await self._send_owner_progress_email(
            db,
            template_key=EmailTemplateKey.OWNER_SUBMISSION_RECEIVED,
            owner=owner,
            expert=expert,
            resource_name=self._format_model_name(model),
            resource_kind="competency model",
            entity_type="competency_model",
            entity_id=model.id,
            dedupe_key=f"competency-model:{model.id}:submission:{expert.id}",
        )

    async def send_selection_submission_received(
        self,
        db: AsyncSession,
        selection_id: int,
        expert_user_id: int,
    ) -> Email | None:
        row = await self._load_selection_owner_and_expert(db, selection_id, expert_user_id)
        if not row:
            return None
        selection, owner, expert, model = row
        return await self._send_owner_progress_email(
            db,
            template_key=EmailTemplateKey.OWNER_SUBMISSION_RECEIVED,
            owner=owner,
            expert=expert,
            resource_name=self._format_selection_name(selection, model),
            resource_kind="candidate selection",
            entity_type="selection",
            entity_id=selection.id,
            dedupe_key=f"selection:{selection.id}:submission:{expert.id}",
        )

    async def send_competency_model_deadline_reminders(
        self,
        db: AsyncSession,
        model_id: int,
        days_before_deadline: int,
    ) -> int:
        row = (
            await db.execute(
                select(CompetencyModel, User)
                .join(User, User.id == CompetencyModel.user_id)
                .where(CompetencyModel.id == model_id)
            )
        ).first()
        if not row:
            return 0
        model, owner = row
        sent = 0
        owner_dedupe_key = f"competency-model:{model.id}:owner-reminder:{days_before_deadline}"
        if not await self._has_dedupe_key(db, owner_dedupe_key):
            await self._send_owner_deadline_reminder(
                db,
                owner=owner,
                resource_name=self._format_model_name(model),
                resource_kind="competency model",
                deadline=model.evaluation_deadline,
                entity_type="competency_model",
                entity_id=model.id,
                days_before_deadline=days_before_deadline,
                dedupe_key=owner_dedupe_key,
            )
            sent += 1
        experts = (
            await db.execute(
                select(User)
                .join(ModelExpert, ModelExpert.user_id == User.id)
                .where(ModelExpert.model_id == model.id)
            )
        ).scalars().all()
        for expert in experts:
            expert_dedupe_key = f"competency-model:{model.id}:expert:{expert.id}:reminder:{days_before_deadline}"
            if await self._has_dedupe_key(db, expert_dedupe_key):
                continue
            await self._send_expert_deadline_reminder(
                db,
                expert=expert,
                owner=owner,
                resource_name=self._format_model_name(model),
                resource_kind="competency model",
                deadline=model.evaluation_deadline,
                entity_type="competency_model",
                entity_id=model.id,
                days_before_deadline=days_before_deadline,
                dedupe_key=expert_dedupe_key,
            )
            sent += 1
        return sent

    async def send_selection_deadline_reminders(
        self,
        db: AsyncSession,
        selection_id: int,
        days_before_deadline: int,
    ) -> int:
        row = (
            await db.execute(
                select(Selection, User, CompetencyModel)
                .join(User, User.id == Selection.user_id)
                .outerjoin(CompetencyModel, CompetencyModel.id == Selection.model_id)
                .where(Selection.id == selection_id)
            )
        ).first()
        if not row:
            return 0
        selection, owner, model = row
        resource_name = self._format_selection_name(selection, model)
        sent = 0
        owner_dedupe_key = f"selection:{selection.id}:owner-reminder:{days_before_deadline}"
        if not await self._has_dedupe_key(db, owner_dedupe_key):
            await self._send_owner_deadline_reminder(
                db,
                owner=owner,
                resource_name=resource_name,
                resource_kind="candidate selection",
                deadline=selection.evaluation_deadline,
                entity_type="selection",
                entity_id=selection.id,
                days_before_deadline=days_before_deadline,
                dedupe_key=owner_dedupe_key,
            )
            sent += 1
        experts = (
            await db.execute(
                select(User)
                .join(SelectionExpert, SelectionExpert.user_id == User.id)
                .where(SelectionExpert.selection_id == selection.id)
            )
        ).scalars().all()
        for expert in experts:
            expert_dedupe_key = f"selection:{selection.id}:expert:{expert.id}:reminder:{days_before_deadline}"
            if await self._has_dedupe_key(db, expert_dedupe_key):
                continue
            await self._send_expert_deadline_reminder(
                db,
                expert=expert,
                owner=owner,
                resource_name=resource_name,
                resource_kind="candidate selection",
                deadline=selection.evaluation_deadline,
                entity_type="selection",
                entity_id=selection.id,
                days_before_deadline=days_before_deadline,
                dedupe_key=expert_dedupe_key,
            )
            sent += 1
        return sent

    async def send_competency_model_deadline_result(self, db: AsyncSession, model_id: int) -> Email | None:
        row = (
            await db.execute(
                select(CompetencyModel, User)
                .join(User, User.id == CompetencyModel.user_id)
                .where(CompetencyModel.id == model_id)
            )
        ).first()
        if not row:
            return None
        model, owner = row
        return await self._send_deadline_result(
            db,
            owner=owner,
            resource_name=self._format_model_name(model),
            resource_kind="competency model",
            entity_type="competency_model",
            entity_id=model.id,
            status_label=self._deadline_result_status(model.status),
        )

    async def send_selection_deadline_result(self, db: AsyncSession, selection_id: int) -> Email | None:
        row = (
            await db.execute(
                select(Selection, User, CompetencyModel)
                .join(User, User.id == Selection.user_id)
                .outerjoin(CompetencyModel, CompetencyModel.id == Selection.model_id)
                .where(Selection.id == selection_id)
            )
        ).first()
        if not row:
            return None
        selection, owner, model = row
        return await self._send_deadline_result(
            db,
            owner=owner,
            resource_name=self._format_selection_name(selection, model),
            resource_kind="candidate selection",
            entity_type="selection",
            entity_id=selection.id,
            status_label=self._deadline_result_status(selection.status),
        )

    async def _send_owner_progress_email(
        self,
        db: AsyncSession,
        *,
        template_key: EmailTemplateKey,
        owner: User,
        expert: User,
        resource_name: str,
        resource_kind: str,
        entity_type: str,
        entity_id: int,
        dedupe_key: str,
    ) -> Email:
        return await self._send_email(
            db,
            template_key=template_key,
            to_email=owner.email,
            user_id=owner.id,
            entity_type=entity_type,
            entity_id=entity_id,
            dedupe_key=dedupe_key,
            context={
                "recipient_name": self._display_name(owner),
                "expert_name": self._display_name(expert),
                "expert_email": expert.email,
                "resource_name": resource_name,
                "resource_kind": resource_kind,
                "action_url": self._resource_url(entity_type, entity_id),
                "app_url": settings.frontend_base_url,
            },
        )

    async def _send_owner_deadline_reminder(
        self,
        db: AsyncSession,
        *,
        owner: User,
        resource_name: str,
        resource_kind: str,
        deadline: datetime | None,
        entity_type: str,
        entity_id: int,
        days_before_deadline: int,
        dedupe_key: str,
    ) -> Email:
        return await self._send_email(
            db,
            template_key=EmailTemplateKey.OWNER_DEADLINE_REMINDER,
            to_email=owner.email,
            user_id=owner.id,
            entity_type=entity_type,
            entity_id=entity_id,
            dedupe_key=dedupe_key,
            context={
                "recipient_name": self._display_name(owner),
                "resource_name": resource_name,
                "resource_kind": resource_kind,
                "deadline": self._format_datetime(deadline),
                "days_before_deadline": days_before_deadline,
                "action_url": self._resource_url(entity_type, entity_id),
                "app_url": settings.frontend_base_url,
            },
        )

    async def _send_expert_deadline_reminder(
        self,
        db: AsyncSession,
        *,
        expert: User,
        owner: User,
        resource_name: str,
        resource_kind: str,
        deadline: datetime | None,
        entity_type: str,
        entity_id: int,
        days_before_deadline: int,
        dedupe_key: str,
    ) -> Email:
        return await self._send_email(
            db,
            template_key=EmailTemplateKey.EXPERT_DEADLINE_REMINDER,
            to_email=expert.email,
            user_id=expert.id,
            entity_type=entity_type,
            entity_id=entity_id,
            dedupe_key=dedupe_key,
            context={
                "recipient_name": self._display_name(expert),
                "owner_name": self._display_name(owner),
                "resource_name": resource_name,
                "resource_kind": resource_kind,
                "deadline": self._format_datetime(deadline),
                "days_before_deadline": days_before_deadline,
                "action_url": self._resource_url(entity_type, entity_id),
                "app_url": settings.frontend_base_url,
            },
        )

    async def _send_deadline_result(
        self,
        db: AsyncSession,
        *,
        owner: User,
        resource_name: str,
        resource_kind: str,
        entity_type: str,
        entity_id: int,
        status_label: str,
    ) -> Email:
        template_key = (
            EmailTemplateKey.OWNER_DEADLINE_REACHED_COMPLETED
            if status_label == "completed"
            else EmailTemplateKey.OWNER_DEADLINE_REACHED_CANCELLED
        )
        return await self._send_email(
            db,
            template_key=template_key,
            to_email=owner.email,
            user_id=owner.id,
            entity_type=entity_type,
            entity_id=entity_id,
            dedupe_key=f"{entity_type}:{entity_id}:deadline-result:{status_label}",
            context={
                "recipient_name": self._display_name(owner),
                "resource_name": resource_name,
                "resource_kind": resource_kind,
                "status_label": status_label,
                "action_url": self._resource_url(entity_type, entity_id),
                "app_url": settings.frontend_base_url,
            },
        )

    async def _send_email(
        self,
        db: AsyncSession,
        *,
        template_key: EmailTemplateKey,
        to_email: str,
        user_id: int | None,
        entity_type: str | None,
        entity_id: int | None,
        dedupe_key: str | None,
        context: dict[str, Any],
    ) -> Email:
        if dedupe_key:
            existing = (
                await db.execute(select(Email).where(Email.dedupe_key == dedupe_key))
            ).scalar_one_or_none()
            if existing:
                return existing

        normalized_email = to_email.strip().lower()

        try:
            rendered = self._renderer.render(template_key, context)
        except Exception as exc:
            logger.exception("Failed to render email template %s", template_key.value)
            return await self._create_log_entry(
                db,
                email=normalized_email,
                user_id=user_id,
                template_key=template_key,
                status=EmailDeliveryStatus.FAILED,
                error_message=f"Template rendering failed: {exc}",
                entity_type=entity_type,
                entity_id=entity_id,
                dedupe_key=dedupe_key,
            )

        log_entry = await self._create_log_entry(
            db,
            email=normalized_email,
            user_id=user_id,
            template_key=template_key,
            status=EmailDeliveryStatus.PENDING,
            error_message=None,
            entity_type=entity_type,
            entity_id=entity_id,
            dedupe_key=dedupe_key,
        )

        if not settings.EMAILS_ENABLED:
            log_entry.status = EmailDeliveryStatus.SKIPPED.value
            log_entry.error_message = "EMAILS_ENABLED is false"
            await db.flush()
            return log_entry

        if not settings.EMAIL_FROM:
            log_entry.status = EmailDeliveryStatus.SKIPPED.value
            log_entry.error_message = "EMAIL_FROM is not configured"
            await db.flush()
            return log_entry

        try:
            result = await self._provider.send(
                to_email=normalized_email,
                subject=rendered.subject,
                html=rendered.html,
                text=rendered.text,
            )
        except Exception as exc:
            logger.exception("Failed to send email %s to %s", template_key.value, normalized_email)
            log_entry.status = EmailDeliveryStatus.FAILED.value
            log_entry.error_message = str(exc)
            await db.flush()
            return log_entry

        now = datetime.now(timezone.utc)
        log_entry.status = EmailDeliveryStatus.SENT.value
        log_entry.provider_message_id = result.message_id
        log_entry.sent_at = now
        await db.flush()
        return log_entry

    async def _create_log_entry(
        self,
        db: AsyncSession,
        *,
        email: str,
        user_id: int | None,
        template_key: EmailTemplateKey,
        status: EmailDeliveryStatus,
        error_message: str | None,
        entity_type: str | None,
        entity_id: int | None,
        dedupe_key: str | None,
    ) -> Email:
        entry = Email(
            email=email,
            user_id=user_id,
            template_key=template_key.value,
            status=status.value,
            error_message=error_message,
            dedupe_key=dedupe_key,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        db.add(entry)
        await db.flush()
        return entry

    async def _load_model_owner_and_expert(
        self,
        db: AsyncSession,
        model_id: int,
        expert_user_id: int,
    ) -> tuple[CompetencyModel, User, User] | None:
        model_row = (
            await db.execute(
                select(CompetencyModel, User)
                .join(User, User.id == CompetencyModel.user_id)
                .where(CompetencyModel.id == model_id)
            )
        ).first()
        if not model_row:
            return None
        model, owner = model_row
        expert = await self._get_user(db, expert_user_id)
        if not expert:
            return None
        return model, owner, expert

    async def _load_selection_owner_and_expert(
        self,
        db: AsyncSession,
        selection_id: int,
        expert_user_id: int,
    ) -> tuple[Selection, User, User, CompetencyModel | None] | None:
        row = (
            await db.execute(
                select(Selection, User, CompetencyModel)
                .join(User, User.id == Selection.user_id)
                .outerjoin(CompetencyModel, CompetencyModel.id == Selection.model_id)
                .where(Selection.id == selection_id)
            )
        ).first()
        if not row:
            return None
        selection, owner, model = row
        expert = await self._get_user(db, expert_user_id)
        if not expert:
            return None
        return selection, owner, expert, model

    async def _get_user(self, db: AsyncSession, user_id: int) -> User | None:
        return (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()

    async def _has_dedupe_key(self, db: AsyncSession, dedupe_key: str) -> bool:
        return (
            await db.execute(select(Email.id).where(Email.dedupe_key == dedupe_key))
        ).scalar_one_or_none() is not None

    def _display_name(self, user: User) -> str:
        return user.name.strip() if user.name and user.name.strip() else user.email

    def _format_model_name(self, model: CompetencyModel) -> str:
        if model.name and model.name.strip():
            return model.name.strip()
        return f"Competency model #{model.id}"

    def _format_selection_name(
        self,
        selection: Selection,
        model: CompetencyModel | None,
    ) -> str:
        created_on = self._format_date(selection.created_at)
        if model and model.name and model.name.strip():
            return f"Candidate selection for {model.name.strip()} created on {created_on}"
        return f"Candidate selection #{selection.id} created on {created_on}"

    def _format_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _format_date(self, value: datetime | None) -> str:
        if value is None:
            return "unknown date"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d")

    def _resource_url(self, entity_type: str, entity_id: int) -> str | None:
        base = settings.frontend_base_url
        if not base:
            return None
        if entity_type == "competency_model":
            return f"{base.rstrip('/')}/competency-models/{entity_id}"
        if entity_type == "selection":
            return f"{base.rstrip('/')}/candidate-selections/{entity_id}"
        return None

    async def _invite_landing_url(self, db: AsyncSession, email: str) -> str | None:
        base = settings.frontend_base_url
        if not base:
            return None

        normalized_email = email.strip().lower()
        existing_user = (
            await db.execute(
                select(User.id).where(func.lower(User.email) == normalized_email)
            )
        ).scalar_one_or_none()
        mode = "login" if existing_user is not None else "register"
        query = urlencode(
            {
                "mode": mode,
                "email": normalized_email,
                "next": "/expert-workspace",
            }
        )
        return f"{base.rstrip('/')}/login?{query}"

    def _deadline_result_status(self, status: int | None) -> str:
        if status in (ModelStatus.COMPLETED, SelectionStatus.COMPLETED):
            return "completed"
        return "cancelled"


email_service = EmailService()
