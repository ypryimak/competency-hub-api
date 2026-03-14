from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.core.enums import ModelStatus
from app.schemas.activity import ActivityLogOut
from app.schemas.auth import UserOut, UserRegister
from app.schemas.candidate_selection import CandidateOut, SelectionOut
from app.schemas.competency_model import (
    CompetencyModelOut,
    CompetencyModelUpdate,
    ExpertInviteCreate,
    ModelSubmitRequest,
)
from app.services.auth_service import AuthService
from app.services.candidate_selection_service import CandidateSelectionService
from app.services.competency_model_service import CompetencyModelService
from app.services.email_service import email_service
from app.services.activity_service import activity_service


def test_user_out_exposes_role_code_and_string_role() -> None:
    user = SimpleNamespace(
        id=1,
        name="HR User",
        email="hr@example.com",
        role=2,
        created_at=datetime.now(timezone.utc),
    )

    payload = UserOut.model_validate(user).model_dump(mode="json")

    assert payload["role_code"] == 2
    assert payload["role"] == "hr"


def test_workflow_outputs_expose_status_code_and_string_status() -> None:
    created_at = datetime.now(timezone.utc)

    model_payload = CompetencyModelOut.model_validate(
        SimpleNamespace(
            id=10,
            user_id=1,
            name="Model",
            profession_id=3,
            min_competency_weight=None,
            max_competency_rank=None,
            evaluation_deadline=None,
            status=2,
            created_at=created_at,
        )
    ).model_dump(mode="json")
    selection_payload = SelectionOut.model_validate(
        SimpleNamespace(
            id=11,
            user_id=1,
            model_id=10,
            evaluation_deadline=None,
            status=3,
            created_at=created_at,
        )
    ).model_dump(mode="json")

    assert model_payload["status_code"] == 2
    assert model_payload["status"] == "expert_evaluation"
    assert selection_payload["status_code"] == 3
    assert selection_payload["status"] == "completed"


def test_model_expert_serializer_includes_nested_user() -> None:
    service = CompetencyModelService()
    expert = SimpleNamespace(
        id=7,
        model_id=12,
        user_id=5,
        rank=1,
        weight=Decimal("0.75"),
        user=SimpleNamespace(id=5, name="Expert Name", email="expert@example.com"),
    )

    payload = service._serialize_model_expert(expert).model_dump(mode="json")

    assert payload["weight"] == 0.75
    assert payload["user"] == {
        "id": 5,
        "name": "Expert Name",
        "email": "expert@example.com",
    }


def test_selection_and_candidate_serializers_include_frontend_metadata() -> None:
    service = CandidateSelectionService()
    candidate = SimpleNamespace(
        id=21,
        user_id=2,
        name="Candidate",
        email="candidate@example.com",
        profession_id=4,
        cv_file_path="candidate-cv.pdf",
        cv_original_filename="candidate-cv.pdf",
        cv_mime_type="application/pdf",
        cv_uploaded_at=datetime.now(timezone.utc),
        cv_parse_status="parsed",
        cv_parsed_at=datetime.now(timezone.utc),
        cv_parse_error=None,
        created_at=datetime.now(timezone.utc),
        competencies=[],
    )
    expert = SimpleNamespace(
        id=31,
        selection_id=9,
        user_id=5,
        weight=Decimal("0.40"),
        user=SimpleNamespace(id=5, name="Selection Expert", email="selection-expert@example.com"),
    )
    selection = SimpleNamespace(
        id=9,
        user_id=2,
        model_id=12,
        evaluation_deadline=None,
        status=1,
        created_at=datetime.now(timezone.utc),
        candidates=[
            SimpleNamespace(
                candidate_id=21,
                selection_id=9,
                score=Decimal("0.88"),
                rank=1,
                candidate=SimpleNamespace(name="Candidate", email="candidate@example.com"),
            )
        ],
        experts=[expert],
        criteria=[],
        expert_invites=[],
    )

    candidate_payload = service._serialize_candidate_summary(candidate, 3).model_dump(mode="json")
    selection_payload = service._serialize_selection_detail(selection).model_dump(mode="json")

    assert candidate_payload["cv_parse_status"] == "parsed"
    assert candidate_payload["matched_competency_count"] == 3
    assert selection_payload["status_code"] == 1
    assert selection_payload["status"] == "draft"
    assert selection_payload["experts"][0]["user"]["email"] == "selection-expert@example.com"


def test_user_out_exposes_position_and_company() -> None:
    user = SimpleNamespace(
        id=1,
        name="HR User",
        email="hr@example.com",
        role=2,
        position="Senior HR Manager",
        company="Acme Corp",
        created_at=datetime.now(timezone.utc),
    )

    payload = UserOut.model_validate(user).model_dump(mode="json")

    assert payload["position"] == "Senior HR Manager"
    assert payload["company"] == "Acme Corp"


def test_user_out_position_and_company_default_to_none() -> None:
    user = SimpleNamespace(
        id=2,
        name="No Profile",
        email="noprofile@example.com",
        role=2,
        created_at=datetime.now(timezone.utc),
    )

    payload = UserOut.model_validate(user).model_dump(mode="json")

    assert payload["position"] is None
    assert payload["company"] is None


def test_activity_log_out_schema() -> None:
    log = SimpleNamespace(
        id=1,
        user_id=5,
        entity_type="competency_model",
        entity_id=10,
        event_type="status_changed",
        old_value="draft",
        new_value="expert_evaluation",
        created_at=datetime.now(timezone.utc),
    )

    payload = ActivityLogOut.model_validate(log).model_dump(mode="json")

    assert payload["entity_type"] == "competency_model"
    assert payload["entity_id"] == 10
    assert payload["event_type"] == "status_changed"
    assert payload["old_value"] == "draft"
    assert payload["new_value"] == "expert_evaluation"
    assert payload["user_id"] == 5


def test_activity_log_out_nullable_values() -> None:
    log = SimpleNamespace(
        id=2,
        user_id=3,
        entity_type="candidate_selection",
        entity_id=7,
        event_type="invite_accepted",
        old_value=None,
        new_value=None,
        created_at=datetime.now(timezone.utc),
    )

    payload = ActivityLogOut.model_validate(log).model_dump(mode="json")

    assert payload["old_value"] is None
    assert payload["new_value"] is None


@pytest.mark.asyncio
async def test_update_model_allows_clearing_competency_filters() -> None:
    service = CompetencyModelService()
    model = SimpleNamespace(
        id=10,
        user_id=1,
        status=ModelStatus.COMPLETED,
        name="Model",
        profession_id=3,
        evaluation_deadline=None,
        min_competency_weight=0.6,
        max_competency_rank=5,
    )
    db = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock())
    service._get_model_orm = AsyncMock(return_value=model)
    payload = CompetencyModelUpdate(
        min_competency_weight=None,
        max_competency_rank=None,
    )

    await service.update_model(db, 10, 1, payload)

    assert model.min_competency_weight is None
    assert model.max_competency_rank is None
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(model)


@pytest.mark.asyncio
async def test_auth_register_persists_company_and_position(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AuthService()
    added: list[object] = []
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        add=added.append,
        flush=AsyncMock(),
        refresh=AsyncMock(),
    )
    send_welcome_email = AsyncMock()
    monkeypatch.setattr(email_service, "send_welcome_email", send_welcome_email)

    user = await service.register(
        db,
        UserRegister(
            name="Jane Recruiter",
            email="jane@example.com",
            password="Password1",
            company="Acme Corp",
            position="HR Lead",
        ),
    )

    assert added
    assert user.company == "Acme Corp"
    assert user.position == "HR Lead"
    send_welcome_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_expert_invite_stays_added_until_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CompetencyModelService()
    model = SimpleNamespace(
        id=12,
        name="Backend Engineer",
        profession_id=4,
        status=ModelStatus.DRAFT,
    )
    captured_invites: list[object] = []

    async def refresh(invite: object) -> None:
        invite.id = 42
        invite.created_at = datetime.now(timezone.utc)

    db = SimpleNamespace(
        add=captured_invites.append,
        flush=AsyncMock(),
        refresh=AsyncMock(side_effect=refresh),
    )
    service._get_model_orm = AsyncMock(return_value=model)
    service._ensure_invite_email_missing = AsyncMock()
    service._ensure_email_not_already_expert = AsyncMock()
    service._check_expert_rank_unique = AsyncMock()
    service._get_users_by_emails = AsyncMock(
        return_value={
            "expert@example.com": SimpleNamespace(
                id=9,
                name="Existing Expert",
                email="expert@example.com",
            )
        }
    )
    send_invite = AsyncMock()
    monkeypatch.setattr(email_service, "send_competency_model_invite", send_invite)

    payload = await service.create_expert_invite(
        db,
        12,
        3,
        ExpertInviteCreate(email="Expert@example.com", rank=2),
    )

    assert captured_invites
    assert payload.status == "added"
    assert payload.email == "expert@example.com"
    assert payload.user is not None
    assert payload.user.name == "Existing Expert"
    send_invite.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_model_sends_pending_invites(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CompetencyModelService()
    pending_invite = SimpleNamespace(id=51, accepted_by_user_id=None)
    model = SimpleNamespace(
        id=11,
        user_id=7,
        status=ModelStatus.DRAFT,
        experts=[],
        expert_invites=[pending_invite],
        criteria=[SimpleNamespace(id=1)],
        alternatives=[SimpleNamespace(id=1), SimpleNamespace(id=2)],
        min_competency_weight=None,
        max_competency_rank=None,
        evaluation_deadline=None,
    )
    db = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock())
    service._get_model_orm = AsyncMock(return_value=model)
    log_activity = AsyncMock()
    send_invite = AsyncMock()
    monkeypatch.setattr(activity_service, "log", log_activity)
    monkeypatch.setattr(email_service, "send_competency_model_invite", send_invite)

    await service.submit_model(
        db,
        11,
        7,
        ModelSubmitRequest(
            min_competency_weight=0.5,
            evaluation_deadline=datetime.now(timezone.utc),
        ),
    )

    assert model.status == ModelStatus.EXPERT_EVALUATION
    send_invite.assert_awaited_once_with(db, 51)
    log_activity.assert_awaited_once()


@pytest.mark.asyncio
async def test_accept_expert_invite_rejects_inactive_model() -> None:
    service = CompetencyModelService()
    user = SimpleNamespace(id=7, email="expert@example.com")
    invite = SimpleNamespace(
        id=3,
        model_id=10,
        email="expert@example.com",
        accepted_by_user_id=None,
        rank=1,
    )
    service._get_user = AsyncMock(return_value=user)
    service._get_expert_invite_by_token = AsyncMock(return_value=invite)
    service._get_model_for_status_check = AsyncMock(
        return_value=SimpleNamespace(id=10, user_id=2, status=ModelStatus.DRAFT)
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.accept_expert_invite(SimpleNamespace(), "token", 7)

    assert exc_info.value.detail == "Invite is not active yet"
