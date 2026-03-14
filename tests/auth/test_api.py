"""Smoke tests for new auth endpoints (FEAT-001, FEAT-002/003)."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import requests
from tests.smoke_common import BASE_URL, ok, expect_status, register_user


def test_register_and_login_flow():
    marker = "authflow"
    email = f"test_{marker}_{os.getpid()}_{id(marker)}@example.com"
    password = "Passw0rd_authflow"
    register_resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={"name": "Auth Flow User", "email": email, "password": password},
    )
    user = ok("POST /auth/register", register_resp, 201)
    assert user["email"] == email

    login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
    )
    tokens = ok("POST /auth/login", login_resp, 200)
    assert tokens["access_token"]
    assert tokens["refresh_token"]


def test_forgot_password_returns_200_for_unknown_email():
    """Should always return 200 regardless of email existence (prevents enumeration)."""
    resp = requests.post(
        f"{BASE_URL}/auth/forgot-password",
        json={"email": "definitely_does_not_exist_xyz123@example.com"},
    )
    ok("forgot-password unknown email", resp, 200)


def test_forgot_password_returns_200_for_registered_email():
    user, _, _ = register_user("user")
    resp = requests.post(
        f"{BASE_URL}/auth/forgot-password",
        json={"email": user["email"]},
    )
    ok("forgot-password registered email", resp, 200)


def test_reset_password_rejects_invalid_token():
    resp = requests.post(
        f"{BASE_URL}/auth/reset-password",
        json={"token": "invalid_token_xyz_does_not_exist", "password": "NewPass123"},
    )
    expect_status("reset-password invalid token", resp, 400)


def test_update_me_adds_position_and_company():
    _, token, _ = register_user("user")
    resp = requests.patch(
        f"{BASE_URL}/auth/me",
        json={"position": "Senior Engineer", "company": "Acme Corp"},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = ok("PATCH /auth/me position+company", resp, 200)
    assert data.get("position") == "Senior Engineer"
    assert data.get("company") == "Acme Corp"


def test_update_me_rejects_wrong_current_password():
    _, token, _ = register_user("user")
    resp = requests.patch(
        f"{BASE_URL}/auth/me",
        json={"current_password": "WrongPass999", "password": "NewPass123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    expect_status("PATCH /auth/me wrong current_password", resp, 400)


def test_get_me_returns_current_user():
    user, token, _ = register_user("user")
    resp = requests.get(
        f"{BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = ok("GET /auth/me", resp, 200)
    assert data["id"] == user["id"]
    assert data["email"] == user["email"]


def test_refresh_returns_new_tokens():
    user, _, password = register_user("refresh-user")
    tokens = ok(
        "Login refresh-user",
        requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": user["email"], "password": password},
        ),
        200,
    )
    resp = requests.post(
        f"{BASE_URL}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    data = ok("POST /auth/refresh", resp, 200)
    assert data["access_token"]
    assert data["refresh_token"]


def test_activity_endpoint_returns_list():
    _, token, _ = register_user("user")
    resp = requests.get(
        f"{BASE_URL}/activity",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = ok("GET /activity", resp, 200)
    assert isinstance(data, list)


def test_health_endpoint_returns_ok():
    root_url = BASE_URL.removesuffix("/api/v1")
    resp = requests.get(f"{root_url}/health")
    data = ok("GET /health", resp, 200)
    assert data == {"status": "ok"}


if __name__ == "__main__":
    print("Running auth smoke tests...")
    test_register_and_login_flow()
    test_forgot_password_returns_200_for_unknown_email()
    test_forgot_password_returns_200_for_registered_email()
    test_reset_password_rejects_invalid_token()
    test_update_me_adds_position_and_company()
    test_update_me_rejects_wrong_current_password()
    test_get_me_returns_current_user()
    test_refresh_returns_new_tokens()
    test_activity_endpoint_returns_list()
    test_health_endpoint_returns_ok()
    print("All auth smoke tests passed!")
