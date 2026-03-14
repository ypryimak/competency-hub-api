"""
Manual smoke-test script for competency model endpoints.
"""

from pathlib import Path
import sys
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.smoke_common import (
    BASE_URL,
    auth_headers,
    delete,
    ensure_admin,
    expect_status,
    get,
    ok,
    patch,
    post,
    register_user,
    suffix,
)


def create_catalog(admin_token: str, marker: str) -> tuple[dict, dict, list[dict]]:
    group = post(admin_token, "/profession-groups", {"name": f"[TEST {marker}] Model Group"})
    profession = post(
        admin_token,
        "/professions",
        {"name": f"[TEST {marker}] Model Profession", "profession_group_id": group["id"]},
    )
    fallback_profession = post(
        admin_token,
        "/professions",
        {"name": f"[TEST {marker}] Alt Profession", "profession_group_id": group["id"]},
    )
    competencies = [
        post(admin_token, "/competencies", {"name": f"[TEST {marker}] Architecture", "competency_type": "knowledge"}),
        post(admin_token, "/competencies", {"name": f"[TEST {marker}] Python", "competency_type": "skill/competence"}),
        post(admin_token, "/competencies", {"name": f"[TEST {marker}] Docker", "competency_type": "skill/competence"}),
        post(admin_token, "/competencies", {"name": f"[TEST {marker}] Terraform", "competency_type": "skill/competence"}),
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
        {"competency_id": competencies[2]["id"], "link_type": "manual", "weight": 0.6},
    )
    return group, fallback_profession, [profession, *competencies]


def main() -> None:
    print("=" * 60)
    print("Competency Models API smoke test")
    print("=" * 60)

    marker = suffix()
    admin_token = ensure_admin()
    _, hr_token, _ = register_user("hr")
    direct_expert_user, direct_expert_token, _ = register_user("direct-expert")
    _, other_token, _ = register_user("other")
    invited_email = f"invited_{marker}@example.com"

    group, fallback_profession, seeded = create_catalog(admin_token, marker)
    profession = seeded[0]
    competencies = seeded[1:]

    print("\n[1] Model create/list/get/update/delete/cancel")
    get(hr_token, "/competency-models")
    deletable_model = post(
        hr_token,
        "/competency-models",
        {"name": f"[TEST {marker}] Delete Me", "profession_id": profession["id"]},
    )
    delete(hr_token, f"/competency-models/{deletable_model['id']}")

    cancellable_model = post(
        hr_token,
        "/competency-models",
        {"name": f"[TEST {marker}] Cancel Me", "profession_id": profession["id"]},
    )
    post(hr_token, f"/competency-models/{cancellable_model['id']}/cancel", expected=200)

    model = post(
        hr_token,
        "/competency-models",
        {"name": f"[TEST {marker}] Main Model", "profession_id": profession["id"]},
    )
    model_id = model["id"]
    get(hr_token, "/competency-models")
    get(hr_token, f"/competency-models/{model_id}")
    detail = get(hr_token, f"/competency-models/{model_id}")
    assert detail["status"] == "draft", "Expected string workflow status in model detail"
    patch(
        hr_token,
        f"/competency-models/{model_id}",
        {"name": f"[TEST {marker}] Main Model Updated", "profession_id": fallback_profession["id"]},
    )
    patch(
        hr_token,
        f"/competency-models/{model_id}",
        {"profession_id": profession["id"]},
    )

    print("\n[2] Experts and invites")
    direct_expert = post(
        hr_token,
        f"/competency-models/{model_id}/experts",
        {"user_id": direct_expert_user["id"], "rank": 1},
    )
    temp_expert = post(
        hr_token,
        f"/competency-models/{model_id}/experts",
        {"user_id": direct_expert_user["id"], "rank": 3},
        expected=409,
    )
    _ = temp_expert

    owner_user, owner_token, _ = register_user("owner-helper")
    removable_expert = post(
        hr_token,
        f"/competency-models/{model_id}/experts",
        {"user_id": owner_user["id"], "rank": 3},
    )
    patch(
        hr_token,
        f"/competency-models/{model_id}/experts/{removable_expert['id']}",
        {"rank": 4},
    )
    delete(hr_token, f"/competency-models/{model_id}/experts/{removable_expert['id']}")

    invite = post(
        hr_token,
        f"/competency-models/{model_id}/expert-invites",
        {"email": invited_email, "rank": 2},
    )
    temp_invite = post(
        hr_token,
        f"/competency-models/{model_id}/expert-invites",
        {"email": f"temp_invited_{marker}@example.com", "rank": 5},
    )
    get(hr_token, f"/competency-models/{model_id}/expert-invites")
    patch(
        hr_token,
        f"/competency-models/{model_id}/expert-invites/{temp_invite['id']}",
        {"rank": 6},
    )
    delete(hr_token, f"/competency-models/{model_id}/expert-invites/{temp_invite['id']}")

    print("\n[2.1] Reorder experts (BUG-009)")
    ok(
        "Reorder experts atomically",
        requests.post(
            f"{BASE_URL}/competency-models/{model_id}/experts/reorder",
            headers=auth_headers(hr_token),
            json={
                "ranks": [
                    {"kind": "expert", "id": direct_expert["id"], "rank": 2},
                    {"kind": "invite", "id": invite["id"], "rank": 1},
                ]
            },
        ),
        204,
    )
    # Restore original ranks for the rest of the test
    ok(
        "Restore original ranks",
        requests.post(
            f"{BASE_URL}/competency-models/{model_id}/experts/reorder",
            headers=auth_headers(hr_token),
            json={
                "ranks": [
                    {"kind": "expert", "id": direct_expert["id"], "rank": 1},
                    {"kind": "invite", "id": invite["id"], "rank": 2},
                ]
            },
        ),
        204,
    )
    # Duplicate rank must be rejected by Pydantic (422)
    expect_status(
        "Reject duplicate ranks in reorder request",
        requests.post(
            f"{BASE_URL}/competency-models/{model_id}/experts/reorder",
            headers=auth_headers(hr_token),
            json={
                "ranks": [
                    {"kind": "expert", "id": direct_expert["id"], "rank": 1},
                    {"kind": "invite", "id": invite["id"], "rank": 1},
                ]
            },
        ),
        422,
    )
    # Foreign expert ID must be rejected (400)
    expect_status(
        "Reject foreign expert id in reorder request",
        requests.post(
            f"{BASE_URL}/competency-models/{model_id}/experts/reorder",
            headers=auth_headers(hr_token),
            json={
                "ranks": [
                    {"kind": "expert", "id": 999999999, "rank": 1},
                ]
            },
        ),
        400,
    )

    print("\n[3] Criteria and alternatives")
    temp_criterion = post(
        hr_token,
        f"/competency-models/{model_id}/criteria",
        {"name": "Temporary criterion"},
    )
    patch(
        hr_token,
        f"/competency-models/{model_id}/criteria/{temp_criterion['id']}",
        {"name": "Temporary criterion updated"},
    )
    delete(hr_token, f"/competency-models/{model_id}/criteria/{temp_criterion['id']}")

    criterion_1 = post(
        hr_token,
        f"/competency-models/{model_id}/criteria",
        {"name": "Technical depth"},
    )
    criterion_2 = post(
        hr_token,
        f"/competency-models/{model_id}/criteria",
        {"name": "Business relevance"},
    )

    print("\n[3.1] Custom competencies")
    temp_custom = post(
        hr_token,
        f"/competency-models/{model_id}/custom-competencies",
        {"name": f"[TEST {marker}] Temporary custom competency"},
    )
    kept_custom = post(
        hr_token,
        f"/competency-models/{model_id}/custom-competencies",
        {
            "name": f"[TEST {marker}] Domain expertise",
            "description": "Specific domain knowledge not covered by the system catalog",
        },
    )
    get(hr_token, f"/competency-models/{model_id}/custom-competencies")
    patch(
        hr_token,
        f"/competency-models/{model_id}/custom-competencies/{kept_custom['id']}",
        {"name": f"[TEST {marker}] Product domain expertise"},
    )
    delete(
        hr_token,
        f"/competency-models/{model_id}/custom-competencies/{temp_custom['id']}",
    )

    recommendations = get(hr_token, f"/competency-models/{model_id}/recommendations")
    temp_alternative = post(
        hr_token,
        f"/competency-models/{model_id}/alternatives",
        {"competency_id": competencies[3]["id"]},
    )
    delete(hr_token, f"/competency-models/{model_id}/alternatives/{temp_alternative['id']}")

    detail = get(hr_token, f"/competency-models/{model_id}")
    if len(detail["alternatives"]) < 2:
        post(
            hr_token,
            f"/competency-models/{model_id}/alternatives",
            {"competency_id": competencies[3]["id"]},
        )
        detail = get(hr_token, f"/competency-models/{model_id}")
    alternative_ids = [item["id"] for item in detail["alternatives"]]
    custom_alternatives = [item for item in detail["alternatives"] if item["source_type"] == "custom"]
    assert detail["experts"][0]["user"]["id"] == direct_expert_user["id"], "Expected nested expert user in detail"
    assert len(recommendations) >= 2, "Expected recommendations for the model"
    assert len(alternative_ids) >= 2, "Expected default alternatives from profession competencies"
    assert detail["custom_competencies"], "Expected custom competencies in model detail"
    assert custom_alternatives, "Expected custom alternative generated from custom competency"

    print("\n[4] Invite acceptance flow")
    invited_user, invited_token, _ = register_user("invited", email=invited_email)
    invites = get(invited_token, "/expert/competency-model-invites")
    assert any(item["token"] == invite["token"] for item in invites), "Invite token not visible to invited user"
    accepted_expert = ok(
        "Accept expert invite",
        requests.post(
            f"{BASE_URL}/expert/competency-model-invites/{invite['token']}/accept",
            headers=auth_headers(invited_token),
        ),
        200,
    )
    assert accepted_expert["rank"] == 2, "Invite rank was not applied"

    print("\n[5] Submit and expert-side endpoints")
    submitted = post(
        hr_token,
        f"/competency-models/{model_id}/submit",
        {"max_competency_rank": 5, "evaluation_deadline": "2026-12-31T23:59:59"},
        expected=200,
    )
    assert submitted["status"] is not None, "Model status was not updated on submit"
    get(invited_token, "/expert/competency-models")
    get(invited_token, f"/expert/competency-models/{model_id}/evaluation-status")

    print("\n[6] Negative checks for foreign ids")
    foreign_model = post(
        hr_token,
        "/competency-models",
        {"name": f"[TEST {marker}] Foreign Model", "profession_id": profession["id"]},
    )
    foreign_criterion = post(
        hr_token,
        f"/competency-models/{foreign_model['id']}/criteria",
        {"name": "Foreign criterion"},
    )
    foreign_detail = get(hr_token, f"/competency-models/{foreign_model['id']}")
    if not foreign_detail["alternatives"]:
        post(
            hr_token,
            f"/competency-models/{foreign_model['id']}/alternatives",
            {"competency_id": competencies[3]["id"]},
        )
        foreign_detail = get(hr_token, f"/competency-models/{foreign_model['id']}")
    foreign_alternative = foreign_detail["alternatives"][0]

    expect_status(
        "Reject foreign criterion in expert evaluation",
        requests.post(
            f"{BASE_URL}/expert/competency-models/{model_id}/evaluate",
            headers=auth_headers(invited_token),
            json={
                "criterion_ranks": [
                    {"criterion_id": criterion_1["id"], "rank": 1},
                    {"criterion_id": foreign_criterion["id"], "rank": 2},
                ],
                "alternative_ranks": [
                    {
                        "alternative_id": alternative_id,
                        "criterion_id": criterion_1["id"],
                        "rank": index + 1,
                    }
                    for index, alternative_id in enumerate(alternative_ids)
                ]
                + [
                    {
                        "alternative_id": alternative_id,
                        "criterion_id": foreign_criterion["id"],
                        "rank": index + 1,
                    }
                    for index, alternative_id in enumerate(alternative_ids)
                ],
            },
        ),
        400,
    )
    expect_status(
        "Reject foreign alternative in expert evaluation",
        requests.post(
            f"{BASE_URL}/expert/competency-models/{model_id}/evaluate",
            headers=auth_headers(invited_token),
            json={
                "criterion_ranks": [
                    {"criterion_id": criterion_1["id"], "rank": 1},
                    {"criterion_id": criterion_2["id"], "rank": 2},
                ],
                "alternative_ranks": [
                    {
                        "alternative_id": foreign_alternative["id"] if criterion_id == criterion_1["id"] and index == 0 else alternative_id,
                        "criterion_id": criterion_id,
                        "rank": index + 1,
                    }
                    for criterion_id in [criterion_1["id"], criterion_2["id"]]
                    for index, alternative_id in enumerate(alternative_ids)
                ],
            },
        ),
        400,
    )

    print("\n[7] Successful evaluation and OPA")
    ok(
        "Submit invited expert evaluation",
        requests.post(
            f"{BASE_URL}/expert/competency-models/{model_id}/evaluate",
            headers=auth_headers(invited_token),
            json={
                "criterion_ranks": [
                    {"criterion_id": criterion_1["id"], "rank": 1},
                    {"criterion_id": criterion_2["id"], "rank": 2},
                ],
                "alternative_ranks": [
                    {
                        "alternative_id": alternative_id,
                        "criterion_id": criterion_id,
                        "rank": index + 1,
                    }
                    for criterion_id in [criterion_1["id"], criterion_2["id"]]
                    for index, alternative_id in enumerate(alternative_ids)
                ],
            },
        ),
        200,
    )
    ok(
        "Submit direct expert evaluation",
        requests.post(
            f"{BASE_URL}/expert/competency-models/{model_id}/evaluate",
            headers=auth_headers(direct_expert_token),
            json={
                "criterion_ranks": [
                    {"criterion_id": criterion_1["id"], "rank": 2},
                    {"criterion_id": criterion_2["id"], "rank": 1},
                ],
                "alternative_ranks": [
                    {
                        "alternative_id": alternative_id,
                        "criterion_id": criterion_id,
                        "rank": len(alternative_ids) - index,
                    }
                    for criterion_id in [criterion_1["id"], criterion_2["id"]]
                    for index, alternative_id in enumerate(alternative_ids)
                ],
            },
        ),
        200,
    )
    post(hr_token, f"/competency-models/{model_id}/calculate", expected=200)

    print("\n[8] Access check")
    expect_status(
        "Block foreign model access",
        requests.get(
            f"{BASE_URL}/competency-models/{model_id}",
            headers=auth_headers(other_token),
        ),
        404,
    )

    print("\n" + "=" * 60)
    print("Competency models smoke test passed")
    print("=" * 60)


def test_competency_models_api_smoke() -> None:
    main()


if __name__ == "__main__":
    main()
