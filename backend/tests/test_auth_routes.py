"""Tests for auth API endpoints (routers/auth.py)."""

import pytest

from app import crud


# ===================================================================
# POST /api/v1/auth/register
# ===================================================================
class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "phone": "1234567890",
            "password": "securepass123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["phone"] == "1234567890"
        assert "id" in data

    def test_register_duplicate_phone(self, client, db):
        crud.create_user(db, phone="1111111111", password="pass123")
        db.flush()

        resp = client.post("/api/v1/auth/register", json={
            "phone": "1111111111",
            "password": "anotherpass",
        })
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "PHONE_ALREADY_REGISTERED"

    def test_register_missing_phone(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "password": "securepass123",
        })
        assert resp.status_code == 422

    def test_register_password_too_short(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "phone": "1234567890",
            "password": "abc",
        })
        assert resp.status_code == 422

    def test_register_phone_too_short(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "phone": "123",
            "password": "securepass123",
        })
        assert resp.status_code == 422


# ===================================================================
# POST /api/v1/auth/login
# ===================================================================
class TestLogin:
    def test_login_success(self, client, db):
        crud.create_user(db, phone="2222222222", password="correct_pass")
        db.flush()

        resp = client.post("/api/v1/auth/login", json={
            "phone": "2222222222",
            "password": "correct_pass",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600
        assert data["user"]["phone"] == "2222222222"

        # Cookies should be set
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

    def test_login_wrong_password(self, client, db):
        crud.create_user(db, phone="3333333333", password="real_pass")
        db.flush()

        resp = client.post("/api/v1/auth/login", json={
            "phone": "3333333333",
            "password": "wrong_pass",
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "phone": "0000000000",
            "password": "anything",
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_missing_fields(self, client):
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422


# ===================================================================
# GET /api/v1/auth/me
# ===================================================================
class TestMe:
    def test_me_authenticated(self, authenticated_client):
        client, user = authenticated_client
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phone"] == "9999999999"
        assert data["id"] == str(user.id)

    def test_me_unauthenticated(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401


# ===================================================================
# POST /api/v1/auth/refresh
# ===================================================================
class TestRefresh:
    def test_refresh_success(self, authenticated_client):
        client, _ = authenticated_client
        resp = client.post("/api/v1/auth/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600

        # New cookies should be set (token rotation)
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

    def test_refresh_no_cookies(self, client):
        resp = client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "MISSING_AUTH_COOKIES"


# ===================================================================
# POST /api/v1/auth/logout
# ===================================================================
class TestLogout:
    def test_logout_authenticated(self, authenticated_client):
        client, _ = authenticated_client
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["status"] == "logged out"

        # After logout, /me should fail
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_logout_unauthenticated(self, client):
        # Logout without cookies should still return 200 (best-effort)
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
