from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.enums import ModelStatus, SelectionStatus
from app.schemas.activity import ActivityLogOut
from app.schemas.auth import UserOut, UserRegister
from app.schemas.candidate_selection import CandidateOut, ExpertCandidateScoreOut, SelectionOut
from app.schemas.competency_model import (
    CompetencyModelOut,
    CompetencyModelUpdate,
    ExpertAlternativeRankOut,
    ExpertCriterionRankOut,
    ExpertInviteCreate,
    ModelSubmitRequest,
)
from app.services.auth_service import AuthService
from app.services.candidate_selection_service import CandidateSelectionService
from app.services.competency_model_service import CompetencyModelService
from app.services.email_service import email_service
from app.services.activity_service import activity_service
from app.services.opa_service import AlternativeInput, CriterionInput, ExpertInput, run_opa


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

    payload = service._serialize_model_expert(expert, is_complete=True).model_dump(mode="json")

    assert payload["weight"] == 0.75
    assert payload["is_complete"] is True
    assert payload["user"] == {
        "id": 5,
        "name": "Expert Name",
        "email": "expert@example.com",
    }


@pytest.mark.asyncio
async def test_model_expert_completion_map_marks_only_fully_submitted_experts() -> None:
    service = CompetencyModelService()
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one=lambda: 2),
                SimpleNamespace(scalar_one=lambda: 3),
                SimpleNamespace(all=lambda: [(7, 2), (8, 1)]),
                SimpleNamespace(all=lambda: [(7, 6), (8, 3)]),
            ]
        )
    )

    payload = await service._get_model_expert_completion_map(db, 10, [7, 8, 9])

    assert payload == {7: True, 8: False, 9: False}


def test_run_opa_normalizes_all_weight_groups_to_one() -> None:
    result = run_opa(
        experts=[ExpertInput(id=1, rank=1), ExpertInput(id=2, rank=2)],
        criteria=[
            CriterionInput(id=11, expert_id=1, rank=1),
            CriterionInput(id=12, expert_id=1, rank=2),
            CriterionInput(id=11, expert_id=2, rank=1),
            CriterionInput(id=12, expert_id=2, rank=2),
        ],
        alternatives=[
            AlternativeInput(id=21, expert_id=1, criterion_id=11, rank=1),
            AlternativeInput(id=22, expert_id=1, criterion_id=11, rank=2),
            AlternativeInput(id=21, expert_id=1, criterion_id=12, rank=1),
            AlternativeInput(id=22, expert_id=1, criterion_id=12, rank=2),
            AlternativeInput(id=21, expert_id=2, criterion_id=11, rank=1),
            AlternativeInput(id=22, expert_id=2, criterion_id=11, rank=2),
            AlternativeInput(id=21, expert_id=2, criterion_id=12, rank=1),
            AlternativeInput(id=22, expert_id=2, criterion_id=12, rank=2),
        ],
    )

    assert result.solved is True
    assert sum(result.expert_weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert sum(result.criterion_weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert sum(result.alternative_weights.values()) == pytest.approx(1.0, abs=1e-6)


def test_final_weight_normalizer_returns_sum_one() -> None:
    service = CompetencyModelService()

    payload = service._normalize_weights_for_sum_one({1: 0.3333333, 2: 0.3333333, 3: 0.3333334})

    assert sum(payload.values()) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.asyncio
async def test_selection_and_candidate_serializers_include_frontend_metadata() -> None:
    service = CandidateSelectionService()
    service._get_selection_expert_completion_map = AsyncMock(return_value={31: True})
    service._get_users_by_emails = AsyncMock(return_value={})
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
    selection_payload = (
        await service._serialize_selection_detail(SimpleNamespace(), selection)
    ).model_dump(mode="json")

    assert candidate_payload["cv_parse_status"] == "parsed"
    assert candidate_payload["matched_competency_count"] == 3
    assert selection_payload["status_code"] == 1
    assert selection_payload["status"] == "draft"
    assert selection_payload["experts"][0]["user"]["email"] == "selection-expert@example.com"


@pytest.mark.asyncio
async def test_build_model_detail_includes_current_expert_ranks() -> None:
    service = CompetencyModelService()
    service._get_users_by_emails = AsyncMock(return_value={})
    service._get_model_expert_completion_map = AsyncMock(return_value={7: True})
    model = SimpleNamespace(
        id=10,
        user_id=2,
        name="Model",
        profession_id=4,
        profession=SimpleNamespace(name="Data Analyst"),
        min_competency_weight=None,
        max_competency_rank=None,
        evaluation_deadline=None,
        status=1,
        created_at=datetime.now(timezone.utc),
        experts=[
            SimpleNamespace(
                id=7,
                model_id=10,
                user_id=5,
                rank=1,
                weight=None,
                user=SimpleNamespace(id=5, name="Expert Name", email="expert@example.com"),
            )
        ],
        expert_invites=[],
        criteria=[],
        custom_competencies=[],
        alternatives=[],
    )

    payload = await service._build_model_detail(
        SimpleNamespace(),
        model,
        current_criterion_ranks=[ExpertCriterionRankOut(criterion_id=5, rank=1)],
        current_alternative_ranks=[ExpertAlternativeRankOut(alternative_id=9, criterion_id=5, rank=2)],
    )

    dumped = payload.model_dump(mode="json")

    assert dumped["profession_name"] == "Data Analyst"
    assert dumped["experts"][0]["is_complete"] is True
    assert dumped["current_criterion_ranks"] == [{"criterion_id": 5, "rank": 1}]
    assert dumped["current_alternative_ranks"] == [
        {"alternative_id": 9, "criterion_id": 5, "rank": 2}
    ]


@pytest.mark.asyncio
async def test_selection_serializer_includes_current_scores() -> None:
    service = CandidateSelectionService()
    service._get_selection_expert_completion_map = AsyncMock(return_value={})
    service._get_users_by_emails = AsyncMock(return_value={})
    selection = SimpleNamespace(
        id=9,
        user_id=2,
        model_id=12,
        evaluation_deadline=None,
        status=1,
        created_at=datetime.now(timezone.utc),
        candidates=[],
        experts=[],
        criteria=[],
        expert_invites=[],
    )

    payload = (
        await service._serialize_selection_detail(
            SimpleNamespace(),
            selection,
            current_scores=[ExpertCandidateScoreOut(candidate_id=21, selection_criterion_id=8, score=4)],
        )
    ).model_dump(mode="json")

    assert payload["current_scores"] == [
        {"candidate_id": 21, "selection_criterion_id": 8, "score": 4}
    ]


@pytest.mark.asyncio
async def test_selection_detail_serialization_marks_completed_experts_and_pending_invites() -> None:
    service = CandidateSelectionService()
    service._get_selection_expert_completion_map = AsyncMock(return_value={31: True, 32: False})
    service._get_users_by_emails = AsyncMock(
        return_value={
            "invite@example.com": SimpleNamespace(
                id=17,
                name="Invited Expert",
                email="invite@example.com",
            )
        }
    )
    selection = SimpleNamespace(
        id=15,
        user_id=3,
        model_id=21,
        evaluation_deadline=None,
        status=1,
        created_at=datetime.now(timezone.utc),
        candidates=[],
        experts=[
            SimpleNamespace(
                id=31,
                selection_id=15,
                user_id=8,
                weight=Decimal("0.70"),
                user=SimpleNamespace(id=8, name="Completed Expert", email="done@example.com"),
            ),
            SimpleNamespace(
                id=32,
                selection_id=15,
                user_id=9,
                weight=None,
                user=SimpleNamespace(id=9, name="Accepted Expert", email="open@example.com"),
            ),
        ],
        criteria=[],
        expert_invites=[
            SimpleNamespace(
                id=41,
                selection_id=15,
                email="invite@example.com",
                weight=Decimal("0.30"),
                token="pending-token",
                accepted_by_user_id=None,
                created_at=datetime.now(timezone.utc),
            ),
            SimpleNamespace(
                id=42,
                selection_id=15,
                email="accepted@example.com",
                weight=None,
                token="accepted-token",
                accepted_by_user_id=99,
                created_at=datetime.now(timezone.utc),
            ),
        ],
    )

    payload = (
        await service._serialize_selection_detail(SimpleNamespace(), selection)
    ).model_dump(mode="json")

    assert payload["experts"][0]["is_complete"] is True
    assert payload["experts"][1]["is_complete"] is False
    assert payload["expert_invites"] == [
        {
            "id": 41,
            "selection_id": 15,
            "email": "invite@example.com",
            "weight": 0.3,
            "token": "pending-token",
            "accepted_by_user_id": None,
            "created_at": payload["expert_invites"][0]["created_at"],
            "status": "added",
            "user": {
                "id": 17,
                "name": "Invited Expert",
                "email": "invite@example.com",
            },
        }
    ]


@pytest.mark.asyncio
async def test_create_selection_expert_invite_returns_added_status_and_matched_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CandidateSelectionService()
    selection = SimpleNamespace(
        id=12,
        status=SelectionStatus.DRAFT,
    )
    captured_invites: list[object] = []

    async def refresh(invite: object) -> None:
        invite.id = 52
        invite.created_at = datetime.now(timezone.utc)

    db = SimpleNamespace(
        add=captured_invites.append,
        flush=AsyncMock(),
        refresh=AsyncMock(side_effect=refresh),
    )
    service._get_selection_orm = AsyncMock(return_value=selection)
    service._ensure_invite_email_missing = AsyncMock()
    service._ensure_email_not_already_expert = AsyncMock()
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
    monkeypatch.setattr(email_service, "send_selection_invite", send_invite)

    payload = await service.create_expert_invite(
        db,
        12,
        3,
        SimpleNamespace(email="Expert@example.com", weight=0.4),
    )

    assert captured_invites
    assert payload.status == "added"
    assert payload.email == "expert@example.com"
    assert payload.user is not None
    assert payload.user.name == "Existing Expert"
    send_invite.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_selection_sends_pending_selection_invites(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CandidateSelectionService()
    pending_invite = SimpleNamespace(id=51, accepted_by_user_id=None)
    selection = SimpleNamespace(
        id=11,
        user_id=7,
        status=SelectionStatus.DRAFT,
        experts=[],
        expert_invites=[pending_invite],
        candidates=[SimpleNamespace(candidate_id=1)],
    )
    db = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock())
    service._get_selection_orm = AsyncMock(return_value=selection)
    log_activity = AsyncMock()
    send_invite = AsyncMock()
    monkeypatch.setattr(activity_service, "log", log_activity)
    monkeypatch.setattr(email_service, "send_selection_invite", send_invite)

    await service.submit_selection(db, 11, 7)

    assert selection.status == SelectionStatus.EXPERT_EVALUATION
    send_invite.assert_awaited_once_with(db, 51)
    log_activity.assert_awaited_once()


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
async def test_update_model_rejects_clearing_all_competency_filters_after_submission() -> None:
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

    with pytest.raises(HTTPException) as exc_info:
        await service.update_model(db, 10, 1, payload)

    assert exc_info.value.detail == "At least one competency filter is required: minimum weight or maximum rank"
    db.flush.assert_not_awaited()
    db.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_model_allows_clearing_one_filter_while_preserving_the_other() -> None:
    service = CompetencyModelService()
    model = SimpleNamespace(
        id=10,
        user_id=1,
        status=ModelStatus.EXPERT_EVALUATION,
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
    )

    await service.update_model(db, 10, 1, payload)

    assert model.min_competency_weight is None
    assert model.max_competency_rank == 5
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(model)


@pytest.mark.asyncio
async def test_update_model_rejects_past_deadline() -> None:
    service = CompetencyModelService()
    model = SimpleNamespace(
        id=10,
        user_id=1,
        status=ModelStatus.EXPERT_EVALUATION,
        name="Model",
        profession_id=3,
        evaluation_deadline=datetime.now(timezone.utc) + timedelta(days=2),
        min_competency_weight=0.6,
        max_competency_rank=5,
    )
    db = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock())
    service._get_model_orm = AsyncMock(return_value=model)
    payload = CompetencyModelUpdate(
        evaluation_deadline=datetime.now(timezone.utc) - timedelta(days=1),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_model(db, 10, 1, payload)

    assert exc_info.value.detail == "Evaluation deadline must be tomorrow or later"
    db.flush.assert_not_awaited()
    db.refresh.assert_not_awaited()


def test_submit_model_requires_tomorrow_or_later_deadline() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ModelSubmitRequest(
            min_competency_weight=0.5,
            evaluation_deadline=datetime.now(timezone.utc) - timedelta(days=1),
        )

    assert "Evaluation deadline must be tomorrow or later" in str(exc_info.value)


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
            evaluation_deadline=datetime.now(timezone.utc) + timedelta(days=1),
        ),
    )

    assert model.status == ModelStatus.EXPERT_EVALUATION
    send_invite.assert_awaited_once_with(db, 51)
    log_activity.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_pending_invites_for_user_excludes_draft_models() -> None:
    service = CompetencyModelService()
    user = SimpleNamespace(id=7, email="Expert@example.com", name="Existing Expert")
    active_model = SimpleNamespace(id=11, name="Active model", profession_id=3)
    draft_model = SimpleNamespace(id=12, name="Draft model", profession_id=4)
    active_invite = SimpleNamespace(
        id=51,
        model_id=11,
        email="expert@example.com",
        rank=2,
        accepted_by_user_id=None,
        token="active-token",
        created_at=datetime.now(timezone.utc),
    )
    draft_invite = SimpleNamespace(
        id=52,
        model_id=12,
        email="expert@example.com",
        rank=3,
        accepted_by_user_id=None,
        token="draft-token",
        created_at=datetime.now(timezone.utc),
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                all=lambda: [
                    (active_invite, active_model),
                ]
            )
        )
    )
    service._get_user = AsyncMock(return_value=user)

    invites = await service.list_pending_invites_for_user(db, 7)

    assert [invite.id for invite in invites] == [51]
    assert all(invite.model_id != 12 for invite in invites)


def test_template_renderer_renders_cancelled_deadline_email_without_reopen_copy() -> None:
    from app.services.email_service import EmailTemplateRenderer
    from app.core.enums import EmailTemplateKey

    renderer = EmailTemplateRenderer()

    rendered = renderer.render(
        EmailTemplateKey.OWNER_DEADLINE_REACHED_CANCELLED,
        {
            "recipient_name": "owner@example.com",
            "resource_kind": "competency model",
            "resource_name": "Backend Engineer Model",
            "action_url": "http://localhost:3000/models/1",
            "app_url": "http://localhost:3000",
        },
    )

    assert "re-opening" not in rendered.html
    assert "re-open" not in rendered.text
    assert "create a new assessment later" in rendered.text


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
