from __future__ import annotations

from fastapi.testclient import TestClient
from unittest.mock import patch

import app.api.main as main_app
from app.domain.user import User
from app.services.auth_service import AuthResult
from main import app

client = TestClient(app)

ADMIN_USER = User(id="00000000-0000-0000-0000-000000000001", username="admin", role="admin")
PLAIN_USER = User(id="00000000-0000-0000-0000-000000000002", username="alice", role="user")


def _auth_headers(user: User = ADMIN_USER) -> dict[str, str]:
    token = main_app._token_service.create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_token_and_user_payload():
    with patch.object(
        main_app._auth_service,
        "login",
        return_value=AuthResult(
            access_token="token-123",
            token_type="bearer",
            user=ADMIN_USER,
        ),
    ) as login:
        response = client.post(
            "/auth/login",
            json={"username": "admin", "password": "admin"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "token-123",
        "token_type": "bearer",
        "user": {
            "id": ADMIN_USER.id,
            "username": "admin",
            "role": "admin",
        },
    }
    login.assert_called_once_with("admin", "admin")


def test_login_rejects_invalid_credentials():
    with patch.object(
        main_app._auth_service,
        "login",
        side_effect=PermissionError("Invalid username or password"),
    ):
        response = client.post(
            "/auth/login",
            json={"username": "admin", "password": "wrong"},
        )

    assert response.status_code == 401


def test_me_returns_current_user():
    with patch.object(main_app._auth_service, "get_current_user", return_value=ADMIN_USER):
        response = client.get("/auth/me", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_admin_can_create_user():
    with patch.object(main_app._auth_service, "get_current_user", return_value=ADMIN_USER), \
         patch.object(main_app._user_service, "create_user", return_value=PLAIN_USER) as create_user:
        response = client.post(
            "/admin/users",
            json={"username": "alice", "password": "shared", "role": "user"},
            headers=_auth_headers(),
        )

    assert response.status_code == 201
    assert response.json()["username"] == "alice"
    assert response.json()["role"] == "user"
    create_user.assert_called_once_with("alice", "shared", "user")


def test_non_admin_cannot_create_user():
    with patch.object(main_app._auth_service, "get_current_user", return_value=PLAIN_USER):
        response = client.post(
            "/admin/users",
            json={"username": "bob", "password": "shared", "role": "user"},
            headers=_auth_headers(PLAIN_USER),
        )

    assert response.status_code == 403


def test_duplicate_username_returns_conflict():
    with patch.object(main_app._auth_service, "get_current_user", return_value=ADMIN_USER), \
         patch.object(
             main_app._user_service,
             "create_user",
             side_effect=ValueError("Username already exists"),
         ):
        response = client.post(
            "/admin/users",
            json={"username": "admin", "password": "shared", "role": "admin"},
            headers=_auth_headers(),
        )

    assert response.status_code == 409


def test_admin_can_list_users():
    with patch.object(main_app._auth_service, "get_current_user", return_value=ADMIN_USER), \
         patch.object(main_app._user_service, "list_users", return_value=[ADMIN_USER, PLAIN_USER]):
        response = client.get("/admin/users", headers=_auth_headers())

    assert response.status_code == 200
    assert [user["username"] for user in response.json()] == ["admin", "alice"]


def test_admin_can_update_user_role():
    updated_user = User(id=PLAIN_USER.id, username="alice", role="admin")
    with patch.object(main_app._auth_service, "get_current_user", return_value=ADMIN_USER), \
         patch.object(main_app._user_service, "update_user_role", return_value=updated_user) as update_user_role:
        response = client.patch(
            f"/admin/users/{PLAIN_USER.id}",
            json={"role": "admin"},
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert response.json()["role"] == "admin"
    update_user_role.assert_called_once_with(PLAIN_USER.id, "admin")


def test_non_admin_cannot_update_user_role():
    with patch.object(main_app._auth_service, "get_current_user", return_value=PLAIN_USER):
        response = client.patch(
            f"/admin/users/{ADMIN_USER.id}",
            json={"role": "user"},
            headers=_auth_headers(PLAIN_USER),
        )

    assert response.status_code == 403


def test_update_user_role_rejects_invalid_role():
    with patch.object(main_app._auth_service, "get_current_user", return_value=ADMIN_USER), \
         patch.object(
             main_app._user_service,
             "update_user_role",
             side_effect=ValueError("Role must be admin or user"),
         ):
        response = client.patch(
            f"/admin/users/{PLAIN_USER.id}",
            json={"role": "owner"},
            headers=_auth_headers(),
        )

    assert response.status_code == 422


def test_update_user_role_returns_404_for_missing_user():
    with patch.object(main_app._auth_service, "get_current_user", return_value=ADMIN_USER), \
         patch.object(
             main_app._user_service,
             "update_user_role",
             side_effect=LookupError("User not found"),
         ):
        response = client.patch(
            "/admin/users/00000000-0000-0000-0000-000000000099",
            json={"role": "admin"},
            headers=_auth_headers(),
        )

    assert response.status_code == 404


def test_admin_cannot_change_own_role():
    with patch.object(main_app._auth_service, "get_current_user", return_value=ADMIN_USER), \
         patch.object(main_app._user_service, "update_user_role") as update_user_role:
        response = client.patch(
            f"/admin/users/{ADMIN_USER.id}",
            json={"role": "user"},
            headers=_auth_headers(),
        )

    assert response.status_code == 400
    update_user_role.assert_not_called()
