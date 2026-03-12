from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.schemas.auth import UserOut
from app.schemas.candidate_selection import CandidateOut, SelectionOut
from app.schemas.competency_model import CompetencyModelOut
from app.services.candidate_selection_service import CandidateSelectionService
from app.services.competency_model_service import CompetencyModelService


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
