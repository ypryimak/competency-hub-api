from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import settings
from app.core.enums import EmailTemplateKey
from app.models.models import CompetencyModel, Selection
from app.services.email_service import (
    EmailProviderResult,
    EmailService,
    EmailTemplateRenderer,
    RenderedEmail,
    ResendEmailProvider,
)


class FakeResult:
    def __init__(self, *, scalar=None):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class FakeDbSession:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.flush_calls = 0
        self.execute_calls = 0

    async def execute(self, query):
        self.execute_calls += 1
        return FakeResult(scalar=self.existing)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flush_calls += 1


class FakeRenderer:
    def render(self, template_key, context):
        return RenderedEmail(
            subject="Rendered subject",
            html="<p>Rendered</p>",
            text="Rendered",
        )


class FakeProvider:
    def __init__(self):
        self.calls = []

    async def send(self, *, to_email: str, subject: str, html: str, text: str) -> EmailProviderResult:
        self.calls.append(
            {
                "to_email": to_email,
                "subject": subject,
                "html": html,
                "text": text,
            }
        )
        return EmailProviderResult(provider="resend", message_id="msg_123")


def test_template_renderer_renders_expert_invite() -> None:
    renderer = EmailTemplateRenderer()

    rendered = renderer.render(
        EmailTemplateKey.EXPERT_INVITE,
        {
            "recipient_name": "expert@example.com",
            "workflow_label": "Competency model expert review",
            "resource_kind": "competency model",
            "resource_name": "Backend Engineer Model",
            "resource_url": "http://localhost:3000",
            "owner_name": "Jane Owner",
            "deadline": "2026-03-20 10:00 UTC",
            "assignment_details": None,
            "app_url": "http://localhost:3000",
        },
    )

    assert rendered.subject == "Competency model expert review invitation for Backend Engineer Model"
    assert "Jane Owner invited you" in rendered.text
    assert "Assigned rank" not in rendered.html


@pytest.mark.asyncio
async def test_resend_provider_builds_expected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"id": "re_test_123"}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(settings, "EMAIL_FROM", "CompetencyHub <noreply@example.com>")
    monkeypatch.setattr(settings, "EMAIL_REPLY_TO", "support@example.com")
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    provider = ResendEmailProvider()
    result = await provider.send(
        to_email="expert@example.com",
        subject="Subject",
        html="<p>Hello</p>",
        text="Hello",
    )

    assert result == EmailProviderResult(provider="resend", message_id="re_test_123")
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_test_key"
    assert captured["json"]["from"] == "CompetencyHub <noreply@example.com>"
    assert captured["json"]["reply_to"] == ["support@example.com"]
    assert captured["json"]["to"] == ["expert@example.com"]


@pytest.mark.asyncio
async def test_send_email_skips_delivery_when_emails_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FakeProvider()
    service = EmailService(renderer=FakeRenderer(), provider=provider)
    db = FakeDbSession(existing=None)

    monkeypatch.setattr(settings, "EMAILS_ENABLED", False)
    monkeypatch.setattr(settings, "EMAIL_FROM", "CompetencyHub <noreply@example.com>")

    entry = await service._send_email(
        db,
        template_key=EmailTemplateKey.WELCOME,
        to_email=" User@Example.com ",
        user_id=1,
        entity_type="user",
        entity_id=1,
        dedupe_key="user:1:welcome",
        context={"recipient_name": "User", "product_name": "CompetencyHub", "app_url": None},
    )

    assert entry.email == "user@example.com"
    assert entry.status == "skipped"
    assert entry.error_message == "EMAILS_ENABLED is false"
    assert len(db.added) == 1
    assert provider.calls == []


@pytest.mark.asyncio
async def test_send_email_returns_existing_entry_for_same_dedupe_key() -> None:
    provider = FakeProvider()
    service = EmailService(renderer=FakeRenderer(), provider=provider)
    existing = object()
    db = FakeDbSession(existing=existing)

    result = await service._send_email(
        db,
        template_key=EmailTemplateKey.WELCOME,
        to_email="user@example.com",
        user_id=1,
        entity_type="user",
        entity_id=1,
        dedupe_key="user:1:welcome",
        context={"recipient_name": "User", "product_name": "CompetencyHub", "app_url": None},
    )

    assert result is existing
    assert db.added == []
    assert db.flush_calls == 0
    assert provider.calls == []


def test_format_selection_name_uses_model_name_and_created_date() -> None:
    service = EmailService(renderer=FakeRenderer(), provider=FakeProvider())
    selection = Selection(id=42, created_at=datetime(2026, 3, 12, 14, 30, tzinfo=timezone.utc))
    model = CompetencyModel(name="Senior Backend Engineer Model")

    value = service._format_selection_name(selection, model)

    assert value == "Candidate selection for Senior Backend Engineer Model created on 2026-03-12"


def test_template_renderer_renders_password_reset() -> None:
    renderer = EmailTemplateRenderer()

    rendered = renderer.render(
        EmailTemplateKey.PASSWORD_RESET,
        {
            "recipient_name": "user@example.com",
            "reset_url": "http://localhost:3000/reset-password?token=abc123",
            "app_url": "http://localhost:3000",
        },
    )

    assert "Reset" in rendered.subject or "reset" in rendered.subject.lower()
    assert "reset-password" in rendered.text or "reset" in rendered.text.lower()


@pytest.mark.asyncio
async def test_invite_landing_url_uses_register_for_new_user() -> None:
    service = EmailService(renderer=FakeRenderer(), provider=FakeProvider())
    db = SimpleNamespace(execute=AsyncMock(return_value=FakeResult(scalar=None)))

    url = await service._invite_landing_url(db, "New.Expert@example.com")

    assert url == (
        f"{settings.frontend_base_url.rstrip('/')}"
        "/login?mode=register&email=new.expert%40example.com&next=%2Fexpert-workspace"
    )


@pytest.mark.asyncio
async def test_invite_landing_url_uses_login_for_existing_user() -> None:
    service = EmailService(renderer=FakeRenderer(), provider=FakeProvider())
    db = SimpleNamespace(execute=AsyncMock(return_value=FakeResult(scalar=123)))

    url = await service._invite_landing_url(db, "expert@example.com")

    assert url == (
        f"{settings.frontend_base_url.rstrip('/')}"
        "/login?mode=login&email=expert%40example.com&next=%2Fexpert-workspace"
    )
