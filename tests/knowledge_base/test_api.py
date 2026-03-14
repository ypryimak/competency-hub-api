"""
Manual smoke-test script for knowledge base endpoints.
"""

from pathlib import Path
import sys
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.smoke_common import BASE_URL, auth_headers, delete, ensure_admin, get, ok, patch, post, suffix


def main() -> None:
    print("=" * 60)
    print("Knowledge Base API smoke test")
    print("=" * 60)

    token = ensure_admin()
    marker = suffix()

    print("\n[1] Profession groups and professions")
    profession_group = post(token, "/profession-groups", {"name": f"[TEST {marker}] Profession Group"})
    get(token, f"/profession-groups/{profession_group['id']}")
    get(token, "/profession-groups")
    profession_group = patch(
        token,
        f"/profession-groups/{profession_group['id']}",
        {"name": f"[TEST {marker}] Profession Group Updated"},
    )

    profession = post(
        token,
        "/professions",
        {
            "name": f"[TEST {marker}] Platform Engineer",
            "profession_group_id": profession_group["id"],
        },
    )
    similar_profession = post(
        token,
        "/professions",
        {
            "name": f"[TEST {marker}] DevOps Engineer",
            "profession_group_id": profession_group["id"],
        },
    )
    professions_page = get(token, "/professions")
    assert "items" in professions_page and "total" in professions_page, (
        "GET /professions must return {items, total}"
    )
    assert isinstance(professions_page["items"], list)
    assert isinstance(professions_page["total"], int)

    # pagination params
    paged = ok(
        "GET /professions?limit=1&offset=0",
        requests.get(f"{BASE_URL}/professions?limit=1&offset=0", headers=auth_headers(token)),
        200,
    )
    assert len(paged["items"]) <= 1, "limit=1 must return at most 1 item"
    assert paged["total"] >= 1, "total must include all items regardless of limit"

    get(token, f"/professions/{profession['id']}")
    profession = patch(
        token,
        f"/professions/{profession['id']}",
        {"name": f"[TEST {marker}] Platform Engineer Updated"},
    )

    print("\n[2] Profession labels and profession collections")
    profession_label = post(
        token,
        f"/professions/{profession['id']}/labels",
        {"label": f"[TEST {marker}] Platform DevOps", "label_type": "alternative", "lang": "en"},
    )
    get(token, f"/professions/{profession['id']}/labels")
    patch(
        token,
        f"/professions/{profession['id']}/labels/{profession_label['id']}",
        {"label": f"[TEST {marker}] Platform DevOps Updated"},
    )

    profession_collection = post(
        token,
        "/profession-collections",
        {"code": f"pcol-{marker}", "name": f"[TEST {marker}] Profession Collection"},
    )
    get(token, "/profession-collections")
    get(token, f"/profession-collections/{profession_collection['id']}")
    patch(
        token,
        f"/profession-collections/{profession_collection['id']}",
        {"description": "updated"},
    )
    post(
        token,
        f"/profession-collections/{profession_collection['id']}/members",
        {"profession_id": profession["id"]},
    )
    get(token, f"/profession-collections/{profession_collection['id']}/members")

    print("\n[3] Competency groups and competencies")
    competency_group = post(token, "/competency-groups", {"name": f"[TEST {marker}] Engineering"})
    get(token, "/competency-groups")
    get(token, f"/competency-groups/{competency_group['id']}")
    competency_group = patch(
        token,
        f"/competency-groups/{competency_group['id']}",
        {"name": f"[TEST {marker}] Engineering Updated"},
    )

    competencies = [
        post(token, "/competencies", {"name": f"[TEST {marker}] Python", "competency_type": "knowledge"}),
        post(token, "/competencies", {"name": f"[TEST {marker}] Docker", "competency_type": "skill/competence"}),
        post(token, "/competencies", {"name": f"[TEST {marker}] Kubernetes", "competency_type": "skill/competence"}),
    ]
    competencies_page = get(token, "/competencies")
    assert "items" in competencies_page and "total" in competencies_page, (
        "GET /competencies must return {items, total}"
    )
    assert isinstance(competencies_page["items"], list)
    assert isinstance(competencies_page["total"], int)

    paged_comp = ok(
        "GET /competencies?limit=1&offset=0",
        requests.get(f"{BASE_URL}/competencies?limit=1&offset=0", headers=auth_headers(token)),
        200,
    )
    assert len(paged_comp["items"]) <= 1, "limit=1 must return at most 1 item"
    assert paged_comp["total"] >= 1, "total must include all items regardless of limit"

    get(token, f"/competencies/{competencies[0]['id']}")
    patch(
        token,
        f"/competencies/{competencies[0]['id']}",
        {"name": f"[TEST {marker}] Python Updated"},
    )

    print("\n[4] Competency labels, memberships, relations, collections")
    competency_label = post(
        token,
        f"/competencies/{competencies[0]['id']}/labels",
        {"label": f"[TEST {marker}] Python Alias", "label_type": "alternative", "lang": "en"},
    )
    get(token, f"/competencies/{competencies[0]['id']}/labels")
    patch(
        token,
        f"/competencies/{competencies[0]['id']}/labels/{competency_label['id']}",
        {"label": f"[TEST {marker}] Python Alias Updated"},
    )

    post(
        token,
        f"/competencies/{competencies[0]['id']}/groups",
        {"group_id": competency_group["id"]},
    )
    get(token, f"/competencies/{competencies[0]['id']}/groups")

    relation = post(
        token,
        "/competency-relations",
        {
            "source_competency_id": competencies[0]["id"],
            "target_competency_id": competencies[1]["id"],
            "relation_type": "related",
        },
    )
    get(token, f"/competency-relations?competency_id={competencies[0]['id']}")

    competency_collection = post(
        token,
        "/competency-collections",
        {"code": f"ccol-{marker}", "name": f"[TEST {marker}] Competency Collection"},
    )
    get(token, "/competency-collections")
    get(token, f"/competency-collections/{competency_collection['id']}")
    patch(
        token,
        f"/competency-collections/{competency_collection['id']}",
        {"description": "updated"},
    )
    post(
        token,
        f"/competency-collections/{competency_collection['id']}/members",
        {"competency_id": competencies[0]["id"]},
    )
    get(token, f"/competency-collections/{competency_collection['id']}/members")

    print("\n[5] Profession competency links and jobs")
    post(
        token,
        f"/professions/{profession['id']}/competencies",
        {
            "competency_id": competencies[0]["id"],
            "link_type": "manual",
            "weight": 0.9,
        },
    )
    patch(
        token,
        f"/professions/{profession['id']}/competencies/{competencies[0]['id']}/manual",
        {"weight": 1.0},
    )
    post(
        token,
        f"/professions/{similar_profession['id']}/competencies",
        {
            "competency_id": competencies[0]["id"],
            "link_type": "manual",
            "weight": 0.7,
        },
    )
    post(
        token,
        f"/professions/{similar_profession['id']}/competencies",
        {
            "competency_id": competencies[1]["id"],
            "link_type": "manual",
            "weight": 0.6,
        },
    )
    get(token, f"/professions/{profession['id']}/competencies")
    linked_professions = get(token, f"/competencies/{competencies[0]['id']}/professions")
    assert any(item["profession_id"] == profession["id"] for item in linked_professions), (
        "Expected profession link in competency professions endpoint"
    )
    similar = get(token, f"/professions/{profession['id']}/similar")
    assert similar, "Expected similar professions for the seeded profession"
    assert any(item["id"] == similar_profession["id"] for item in similar), "Expected related profession in similar list"

    jobs = [
        post(
            token,
            "/jobs",
            {
                "title": f"[TEST {marker}] Backend Vacancy",
                "description": f"Need {competencies[0]['name']} and {competencies[1]['name']}",
                "profession_id": profession["id"],
            },
        ),
        post(
            token,
            "/jobs",
            {
                "title": f"[TEST {marker}] Platform Vacancy",
                "description": f"Need {competencies[0]['name']} and {competencies[2]['name']}",
                "profession_id": profession["id"],
            },
        ),
    ]
    get(token, f"/jobs?profession_id={profession['id']}")
    get(token, f"/jobs/{jobs[0]['id']}")
    patch(
        token,
        f"/jobs/{jobs[0]['id']}",
        {"title": f"[TEST {marker}] Backend Vacancy Updated"},
    )

    post(
        token,
        f"/jobs/{jobs[0]['id']}/competencies",
        {"competency_id": competencies[0]["id"]},
    )
    get(token, f"/jobs/{jobs[0]['id']}/competencies")
    delete(token, f"/jobs/{jobs[0]['id']}/competencies/{competencies[0]['id']}")
    post(
        token,
        f"/jobs/{jobs[0]['id']}/competencies",
        {"competency_id": competencies[0]["id"]},
    )

    post(token, f"/jobs/{jobs[0]['id']}/parse-competencies", expected=200)
    post(token, f"/professions/{profession['id']}/parse-all-jobs", expected=200)
    post(token, f"/professions/{profession['id']}/recalculate-competencies", expected=200)

    print("\n[6] Cleanup")
    response = requests.delete(
        f"{BASE_URL}/jobs/{jobs[0]['id']}/competencies/{competencies[0]['id']}",
        headers=auth_headers(token),
    )
    if response.status_code not in (204, 404):
        raise AssertionError(
            f"Unexpected status during cleanup delete: {response.status_code} {response.text}"
        )
    print(f"  [OK]   DELETE /jobs/{jobs[0]['id']}/competencies/{competencies[0]['id']}")
    for job in jobs:
        delete(token, f"/jobs/{job['id']}")
    delete(token, f"/profession-collections/{profession_collection['id']}/members/{profession['id']}")
    delete(token, f"/profession-collections/{profession_collection['id']}")
    delete(token, f"/competency-collections/{competency_collection['id']}/members/{competencies[0]['id']}")
    delete(token, f"/competency-collections/{competency_collection['id']}")
    delete(
        token,
        f"/competency-relations/{relation['source_competency_id']}/{relation['target_competency_id']}/{relation['relation_type']}",
    )
    delete(token, f"/professions/{similar_profession['id']}/competencies/{competencies[0]['id']}/manual")
    delete(token, f"/professions/{similar_profession['id']}/competencies/{competencies[1]['id']}/manual")
    delete(token, f"/professions/{profession['id']}/competencies/{competencies[0]['id']}/manual")
    delete(token, f"/competencies/{competencies[0]['id']}/groups/{competency_group['id']}")
    delete(token, f"/competencies/{competencies[0]['id']}/labels/{competency_label['id']}")
    delete(token, f"/professions/{profession['id']}/labels/{profession_label['id']}")
    delete(token, f"/professions/{similar_profession['id']}")
    for competency in competencies:
        delete(token, f"/competencies/{competency['id']}")
    delete(token, f"/competency-groups/{competency_group['id']}")
    delete(token, f"/professions/{profession['id']}")
    delete(token, f"/profession-groups/{profession_group['id']}")

    print("\n" + "=" * 60)
    print("Knowledge base smoke test passed")
    print("=" * 60)


def test_knowledge_base_api_smoke() -> None:
    main()


if __name__ == "__main__":
    main()
