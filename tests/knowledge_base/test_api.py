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
    profession_label = patch(
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
    competency_group_child = post(
        token,
        "/competency-groups",
        {
            "name": f"[TEST {marker}] Backend",
            "parent_group_id": competency_group["id"],
        },
    )
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
        {"group_id": competency_group_child["id"]},
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

    # FEAT-024: group_id and collection_id filter params on GET /competencies
    filtered_by_group = ok(
        f"GET /competencies?group_id={competency_group['id']}",
        requests.get(
            f"{BASE_URL}/competencies?group_id={competency_group['id']}",
            headers=auth_headers(token),
        ),
        200,
    )
    assert any(item["id"] == competencies[0]["id"] for item in filtered_by_group["items"]), (
        "Competency in a descendant group must appear in ancestor group filter results"
    )
    filtered_by_collection = ok(
        f"GET /competencies?collection_id={competency_collection['id']}",
        requests.get(
            f"{BASE_URL}/competencies?collection_id={competency_collection['id']}",
            headers=auth_headers(token),
        ),
        200,
    )
    assert any(item["id"] == competencies[0]["id"] for item in filtered_by_collection["items"]), (
        "Competency in collection must appear in collection_id filter results"
    )

    # FEAT-024: aliases field in competencies list (after label is created)
    comp_list_with_aliases = ok(
        "GET /competencies (aliases check)",
        requests.get(
            f"{BASE_URL}/competencies?search={requests.utils.quote(f'[TEST {marker}] Python Updated')}",
            headers=auth_headers(token),
        ),
        200,
    )
    test_comp_item = next(
        (c for c in comp_list_with_aliases["items"] if c["id"] == competencies[0]["id"]), None
    )
    assert test_comp_item is not None, "Seeded competency must appear in GET /competencies"
    assert "aliases" in test_comp_item, "GET /competencies items must include 'aliases' field"
    assert isinstance(test_comp_item["aliases"], list)

    # FEAT-025: GET /competencies/{id} includes collections array
    comp_detail = get(token, f"/competencies/{competencies[0]['id']}")
    assert "collections" in comp_detail, "GET /competencies/{id} must include 'collections' field"
    assert isinstance(comp_detail["collections"], list)
    assert any(c["id"] == competency_collection["id"] for c in comp_detail["collections"]), (
        "Competency detail must list collections the competency belongs to"
    )

    # FEAT-026: aliases field in professions list (after profession label is created)
    prof_list_with_aliases = ok(
        "GET /professions (aliases check)",
        requests.get(
            f"{BASE_URL}/professions?search={requests.utils.quote(f'[TEST {marker}] Platform Engineer Updated')}",
            headers=auth_headers(token),
        ),
        200,
    )
    test_prof_item = next(
        (p for p in prof_list_with_aliases["items"] if p["id"] == profession["id"]), None
    )
    assert test_prof_item is not None, "Seeded profession must appear in GET /professions"
    assert "aliases" in test_prof_item, "GET /professions items must include 'aliases' field"
    assert isinstance(test_prof_item["aliases"], list)
    assert any(a == profession_label["label"] for a in test_prof_item["aliases"]), (
        "Profession alias label must appear in 'aliases' list"
    )

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
    # FEAT-027: GET /professions/{id}/competencies returns detail format
    prof_competencies = get(token, f"/professions/{profession['id']}/competencies")
    assert isinstance(prof_competencies, list), "Expected list from profession competencies endpoint"
    if prof_competencies:
        pc = prof_competencies[0]
        assert "link_types" in pc, "Profession competency item must include 'link_types' list"
        assert isinstance(pc["link_types"], list), "'link_types' must be a list"
        assert "weight" in pc, "Profession competency item must include 'weight'"
        assert "aliases" in pc, "Profession competency item must include 'aliases'"
        assert "group_names" in pc, "Profession competency item must include 'group_names'"

    linked_professions = get(token, f"/competencies/{competencies[0]['id']}/professions")
    assert any(item["profession_id"] == profession["id"] for item in linked_professions), (
        "Expected profession link in competency professions endpoint"
    )
    # FEAT-025: GET /competencies/{id}/professions returns detail format
    if linked_professions:
        lp = linked_professions[0]
        assert "link_types" in lp, "Linked profession item must include 'link_types' list"
        assert isinstance(lp["link_types"], list), "'link_types' must be a list"
        assert "weight" in lp, "Linked profession item must include 'weight'"
        assert "aliases" in lp, "Linked profession item must include 'aliases'"
        assert "profession_group_name" in lp, "Linked profession item must include 'profession_group_name'"
    similar = get(token, f"/professions/{profession['id']}/similar")
    assert similar, "Expected similar professions for the seeded profession"
    assert any(item["id"] == similar_profession["id"] for item in similar), "Expected related profession in similar list"
    first_similar = similar[0]
    assert "overlap_ratio" in first_similar, "Similar profession item must include 'overlap_ratio'"
    assert "same_group" in first_similar, "Similar profession item must include 'same_group'"
    assert "same_parent" in first_similar, "Similar profession item must include 'same_parent'"
    assert "direct_hierarchy_match" in first_similar, "Similar profession item must include 'direct_hierarchy_match'"

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
    delete(token, f"/competencies/{competencies[0]['id']}/groups/{competency_group_child['id']}")
    delete(token, f"/competencies/{competencies[0]['id']}/labels/{competency_label['id']}")
    delete(token, f"/professions/{profession['id']}/labels/{profession_label['id']}")
    delete(token, f"/professions/{similar_profession['id']}")
    for competency in competencies:
        delete(token, f"/competencies/{competency['id']}")
    delete(token, f"/competency-groups/{competency_group_child['id']}")
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
