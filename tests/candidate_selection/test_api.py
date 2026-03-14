"""
Manual smoke-test script for candidate selection endpoints.
"""

from pathlib import Path
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.smoke_common import (  # noqa: E402
    BASE_URL,
    auth_headers,
    delete,
    ensure_admin,
    expect_status,
    get,
    ok,
    patch,
    post,
    post_file,
    register_user,
    suffix,
)


def create_catalog(admin_token: str, marker: str) -> tuple[dict, dict, list[dict]]:
    group = post(admin_token, "/profession-groups", {"name": f"[TEST {marker}] Selection Group"})
    profession = post(
        admin_token,
        "/professions",
        {"name": f"[TEST {marker}] Selection Profession", "profession_group_id": group["id"]},
    )
    competencies = [
        post(admin_token, "/competencies", {"name": f"[TEST {marker}] Python", "competency_type": "skill/competence"}),
        post(admin_token, "/competencies", {"name": f"[TEST {marker}] FastAPI", "competency_type": "skill/competence"}),
        post(admin_token, "/competencies", {"name": f"[TEST {marker}] Kubernetes", "competency_type": "skill/competence"}),
    ]
    post(
        admin_token,
        f"/professions/{profession['id']}/competencies",
        {"competency_id": competencies[0]["id"], "link_type": "manual", "weight": 0.9},
    )
    post(
        admin_token,
        f"/professions/{profession['id']}/competencies",
        {"competency_id": competencies[1]["id"], "link_type": "manual", "weight": 0.8},
    )
    post(
        admin_token,
        f"/professions/{profession['id']}/competencies",
        {"competency_id": competencies[2]["id"], "link_type": "manual", "weight": 0.2},
    )
    return group, profession, competencies


def create_completed_model(
    hr_token: str,
    expert_token: str,
    expert_user: dict,
    profession: dict,
    marker: str,
) -> tuple[dict, list[int]]:
    model = post(
        hr_token,
        "/competency-models",
        {"name": f"[TEST {marker}] Selection Model", "profession_id": profession["id"]},
    )
    model_id = model["id"]
    post(
        hr_token,
        f"/competency-models/{model_id}/experts",
        {"user_id": expert_user["id"], "rank": 1},
    )
    criterion_1 = post(
        hr_token,
        f"/competency-models/{model_id}/criteria",
        {"name": "Technical fit"},
    )
    criterion_2 = post(
        hr_token,
        f"/competency-models/{model_id}/criteria",
        {"name": "Delivery fit"},
    )
    custom = post(
        hr_token,
        f"/competency-models/{model_id}/custom-competencies",
        {"name": f"[TEST {marker}] Product domain expertise"},
    )
    _ = custom
    post(
        hr_token,
        f"/competency-models/{model_id}/submit",
        {"max_competency_rank": 3, "evaluation_deadline": "2026-12-31T23:59:59"},
        expected=200,
    )
    detail = get(hr_token, f"/competency-models/{model_id}")
    alternative_ids = [item["id"] for item in detail["alternatives"]]
    custom_alternative_ids = [item["id"] for item in detail["alternatives"] if item["source_type"] == "custom"]
    ok(
        "Submit expert evaluation for model",
        requests.post(
            f"{BASE_URL}/expert/competency-models/{model_id}/evaluate",
            headers=auth_headers(expert_token),
            json={
                "criterion_ranks": [
                    {"criterion_id": criterion_1["id"], "rank": 1},
                    {"criterion_id": criterion_2["id"], "rank": 2},
                ],
                "alternative_ranks": [
                    {
                        "alternative_id": alternative_id,
                        "criterion_id": criterion_id,
                        "rank": 1 if alternative_id in custom_alternative_ids else index + 2,
                    }
                    for criterion_id in [criterion_1["id"], criterion_2["id"]]
                    for index, alternative_id in enumerate(alternative_ids)
                ],
            },
        ),
        200,
    )
    post(hr_token, f"/competency-models/{model_id}/calculate", expected=200)
    completed_detail = get(hr_token, f"/competency-models/{model_id}")
    final_alternatives = [item for item in completed_detail["alternatives"] if item["final_weight"] is not None]
    assert len(final_alternatives) == 3, "Expected three final criteria for selection model"
    assert any(item["source_type"] == "custom" for item in final_alternatives), "Expected custom criterion in final model"
    return model, final_alternatives


def score_payload(candidate_ids: list[int], criterion_ids: list[int], reverse: bool = False) -> dict:
    scores = []
    for cand_index, candidate_id in enumerate(candidate_ids):
        for crit_index, criterion_id in enumerate(criterion_ids):
            value = 5 - ((cand_index + crit_index) % 3)
            if reverse:
                value = 2 + ((cand_index + crit_index) % 3)
            scores.append(
                {
                    "candidate_id": candidate_id,
                    "selection_criterion_id": criterion_id,
                    "score": value,
                }
            )
    return {"scores": scores}


def main() -> None:
    print("=" * 60)
    print("Candidate Selection API smoke test")
    print("=" * 60)

    marker = suffix()
    admin_token = ensure_admin()
    _, hr_token, _ = register_user("selection-hr")
    direct_expert_user, direct_expert_token, _ = register_user("selection-expert")
    removable_expert_user, _, _ = register_user("selection-removable")
    _, other_token, _ = register_user("selection-other")
    invited_email = f"selection_invited_{marker}@example.com"

    group, profession, competencies = create_catalog(admin_token, marker)
    model, final_alternatives = create_completed_model(
        hr_token,
        direct_expert_token,
        direct_expert_user,
        profession,
        marker,
    )

    print("\n[1] Selection CRUD")
    get(hr_token, "/selections")
    deletable_selection = post(
        hr_token,
        "/selections",
        {"model_id": model["id"]},
    )
    delete(hr_token, f"/selections/{deletable_selection['id']}")

    cancellable_selection = post(
        hr_token,
        "/selections",
        {"model_id": model["id"]},
    )
    post(hr_token, f"/selections/{cancellable_selection['id']}/cancel", expected=200)

    selection = post(
        hr_token,
        "/selections",
        {"model_id": model["id"]},
    )
    selection_id = selection["id"]
    patch(
        hr_token,
        f"/selections/{selection_id}",
        {"evaluation_deadline": "2026-12-31T23:59:59"},
    )
    get(hr_token, f"/selections/{selection_id}")

    print("\n[2] Candidates and CV flow")
    candidate_1 = post(
        hr_token,
        "/candidates",
        {"name": f"[TEST {marker}] Alice", "email": f"alice_{marker}@example.com", "profession_id": profession["id"]},
    )
    assert candidate_1["cv_parse_status"] == "not_uploaded", "Expected initial CV parse status"
    candidate_2 = post(
        hr_token,
        "/candidates",
        {"name": f"[TEST {marker}] Bob", "email": f"bob_{marker}@example.com", "profession_id": profession["id"]},
    )
    candidate_3 = post(
        hr_token,
        "/candidates",
        {"name": f"[TEST {marker}] Carol", "email": f"carol_{marker}@example.com", "profession_id": profession["id"]},
    )
    get(hr_token, "/candidates")
    candidate_detail = get(hr_token, f"/candidates/{candidate_1['id']}")
    assert candidate_detail["matched_competency_count"] == 0, "Expected no parsed competencies before CV parsing"
    post_file(
        hr_token,
        f"/candidates/{candidate_1['id']}/cv",
        "candidate.txt",
        f"{competencies[0]['name']} {competencies[1]['name']} experience for {profession['name']}".encode("utf-8"),
        expected=200,
    )
    get(hr_token, f"/candidates/{candidate_1['id']}/cv-url")
    parse_result = post(hr_token, f"/candidates/{candidate_1['id']}/parse-cv", expected=200)
    assert parse_result["matched_competency_ids"], "Expected parsed competencies from CV"
    expect_status(
        "Block foreign candidate access",
        requests.get(
            f"{BASE_URL}/candidates/{candidate_1['id']}",
            headers=auth_headers(other_token),
        ),
        404,
    )
    ok(
        "Delete candidate CV",
        requests.delete(
            f"{BASE_URL}/candidates/{candidate_1['id']}/cv",
            headers=auth_headers(hr_token),
        ),
        200,
    )
    post_file(
        hr_token,
        f"/candidates/{candidate_1['id']}/cv",
        "candidate.txt",
        f"{competencies[0]['name']} {competencies[1]['name']} experience for {profession['name']}".encode("utf-8"),
        expected=200,
    )

    print("\n[3] Selection composition and invites")
    post(
        hr_token,
        f"/selections/{selection_id}/candidates",
        {"candidate_id": candidate_1["id"]},
    )
    post(
        hr_token,
        f"/selections/{selection_id}/candidates",
        {"candidate_id": candidate_2["id"]},
    )
    post(
        hr_token,
        f"/selections/{selection_id}/candidates",
        {"candidate_id": candidate_3["id"]},
    )
    delete(hr_token, f"/selections/{selection_id}/candidates/{candidate_3['id']}")

    removable_expert = post(
        hr_token,
        f"/selections/{selection_id}/experts",
        {"user_id": removable_expert_user["id"], "weight": 0.2},
    )
    delete(hr_token, f"/selections/{selection_id}/experts/{removable_expert['id']}")

    post(
        hr_token,
        f"/selections/{selection_id}/experts",
        {"user_id": direct_expert_user["id"], "weight": 0.7},
    )

    temp_invite = post(
        hr_token,
        f"/selections/{selection_id}/expert-invites",
        {"email": f"selection_temp_{marker}@example.com", "weight": 0.4},
    )
    get(hr_token, f"/selections/{selection_id}/expert-invites")
    patch(
        hr_token,
        f"/selections/{selection_id}/expert-invites/{temp_invite['id']}",
        {"weight": 0.5},
    )
    delete(hr_token, f"/selections/{selection_id}/expert-invites/{temp_invite['id']}")

    invite = post(
        hr_token,
        f"/selections/{selection_id}/expert-invites",
        {"email": invited_email, "weight": 0.3},
    )
    selection_detail = get(hr_token, f"/selections/{selection_id}")
    assert selection_detail["experts"][0]["user"]["id"] == direct_expert_user["id"], (
        "Expected nested expert user in selection detail"
    )

    print("\n[4] Submit selection and accept invite")
    post(hr_token, f"/selections/{selection_id}/submit", expected=200)
    invited_user, invited_token, _ = register_user("selection-invited", email=invited_email)
    invites = get(invited_token, "/expert/selection-invites")
    assert any(item["token"] == invite["token"] for item in invites), "Expected pending selection invite"
    ok(
        "Accept selection invite",
        requests.post(
            f"{BASE_URL}/expert/selection-invites/{invite['token']}/accept",
            headers=auth_headers(invited_token),
        ),
        200,
    )
    get(invited_token, "/expert/selections")
    get(invited_token, f"/expert/selections/{selection_id}/scoring-status")

    print("\n[5] Negative checks for scoring invariants")
    selection_detail = get(hr_token, f"/selections/{selection_id}")
    selected_candidate_ids = [item["candidate_id"] for item in selection_detail["candidates"]]
    selection_criterion_ids = [item["id"] for item in selection_detail["criteria"]]
    assert set(selected_candidate_ids) == {candidate_1["id"], candidate_2["id"]}, "Unexpected selection candidates"
    assert len(selection_criterion_ids) == len(final_alternatives), "Expected frozen selection criteria snapshot"

    invalid_candidate_payload = score_payload(selected_candidate_ids, selection_criterion_ids)
    invalid_candidate_payload["scores"][0]["candidate_id"] = candidate_3["id"]
    expect_status(
        "Reject foreign candidate in expert scoring",
        requests.post(
            f"{BASE_URL}/expert/selections/{selection_id}/score",
            headers=auth_headers(direct_expert_token),
            json=invalid_candidate_payload,
        ),
        400,
    )

    invalid_criterion_payload = score_payload(selected_candidate_ids, selection_criterion_ids)
    invalid_criterion_payload["scores"][0]["selection_criterion_id"] = 999999
    expect_status(
        "Reject foreign criterion in expert scoring",
        requests.post(
            f"{BASE_URL}/expert/selections/{selection_id}/score",
            headers=auth_headers(direct_expert_token),
            json=invalid_criterion_payload,
        ),
        400,
    )

    print("\n[6] Successful scoring and VIKOR")
    ok(
        "Submit direct expert scores",
        requests.post(
            f"{BASE_URL}/expert/selections/{selection_id}/score",
            headers=auth_headers(direct_expert_token),
            json=score_payload(selected_candidate_ids, selection_criterion_ids),
        ),
        200,
    )
    expect_status(
        "Reject premature VIKOR",
        requests.post(
            f"{BASE_URL}/selections/{selection_id}/calculate",
            headers=auth_headers(hr_token),
        ),
        400,
    )
    ok(
        "Submit invited expert scores",
        requests.post(
            f"{BASE_URL}/expert/selections/{selection_id}/score",
            headers=auth_headers(invited_token),
            json=score_payload(selected_candidate_ids, selection_criterion_ids, reverse=True),
        ),
        200,
    )
    get(direct_expert_token, f"/expert/selections/{selection_id}/scoring-status")
    post(hr_token, f"/selections/{selection_id}/calculate", expected=200)
    get(hr_token, f"/selections/{selection_id}/results")

    print("\n" + "=" * 60)
    print("Candidate selection smoke test passed")
    print("=" * 60)


def test_candidate_selection_api_smoke() -> None:
    main()


if __name__ == "__main__":
    main()
