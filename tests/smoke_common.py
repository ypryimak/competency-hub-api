import json
import os
import random
import string
import sys
from typing import Any

import requests


BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
ADMIN_EMAIL = "test_admin@competencyhub.dev"
ADMIN_PASSWORD = "testpass123"


def suffix(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def ok(label: str, resp: requests.Response, expected: int = 200) -> Any:
    if resp.status_code != expected:
        print(f"  [FAIL] {label}")
        print(f"         Status: {resp.status_code} (expected {expected})")
        try:
            print(f"         Body:   {json.dumps(resp.json(), ensure_ascii=False, indent=2)}")
        except Exception:
            print(f"         Body:   {resp.text[:500]}")
        sys.exit(1)
    data = resp.json() if resp.text else {}
    print(f"  [OK]   {label}")
    return data


def expect_status(label: str, resp: requests.Response, expected: int) -> Any:
    return ok(label, resp, expected)


def login(email: str, password: str) -> str:
    tokens = ok(
        f"Login {email}",
        requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
        ),
        200,
    )
    return tokens["access_token"]


def register_user(role_label: str, email: str | None = None, password: str | None = None) -> tuple[dict, str, str]:
    marker = suffix()
    payload = {
        "name": f"Test {role_label.upper()} {marker}",
        "email": email or f"test_{role_label}_{marker}@example.com",
        "password": password or f"Passw0rd_{marker}",
    }
    user = ok(
        f"Register {role_label} ({payload['email']})",
        requests.post(f"{BASE_URL}/auth/register", json=payload),
        201,
    )
    tokens = ok(
        f"Login {role_label}",
        requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        ),
        200,
    )
    return user, tokens["access_token"], payload["password"]


def ensure_admin() -> str:
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={"name": "Test Admin", "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if response.status_code not in (201, 409):
        response.raise_for_status()
    return login(ADMIN_EMAIL, ADMIN_PASSWORD)


def get(token: str, path: str) -> Any:
    return ok(path, requests.get(f"{BASE_URL}{path}", headers=auth_headers(token)), 200)


def post(token: str, path: str, payload: dict | None = None, expected: int = 201) -> Any:
    return ok(
        path,
        requests.post(
            f"{BASE_URL}{path}",
            json=payload if payload is not None else None,
            headers=auth_headers(token),
        ),
        expected,
    )


def patch(token: str, path: str, payload: dict) -> Any:
    return ok(
        path,
        requests.patch(f"{BASE_URL}{path}", json=payload, headers=auth_headers(token)),
        200,
    )


def delete(token: str, path: str) -> None:
    response = requests.delete(f"{BASE_URL}{path}", headers=auth_headers(token))
    if response.status_code != 204:
        ok(path, response, 204)
    print(f"  [OK]   DELETE {path}")


def post_file(
    token: str,
    path: str,
    filename: str,
    content: bytes,
    content_type: str = "text/plain",
    expected: int = 200,
) -> Any:
    return ok(
        path,
        requests.post(
            f"{BASE_URL}{path}",
            headers=auth_headers(token),
            files={"file": (filename, content, content_type)},
        ),
        expected,
    )
