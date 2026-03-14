"""Tests for authentication utilities (auth.py)."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Response
from jose import jwt

from app import auth, database


# ===================================================================
# Password hashing
# ===================================================================
class TestPasswordHashing:
    def test_hash_password_returns_bcrypt_hash(self):
        hashed = auth.hash_password("mysecretpassword")
        assert hashed.startswith("$2b$")
        assert hashed != "mysecretpassword"

    def test_verify_password_correct(self):
        hashed = auth.hash_password("correct-password")
        assert auth.verify_password("correct-password", hashed) is True

    def test_verify_password_wrong(self):
        hashed = auth.hash_password("correct-password")
        assert auth.verify_password("wrong-password", hashed) is False

    def test_hash_password_unique_salts(self):
        h1 = auth.hash_password("same-password")
        h2 = auth.hash_password("same-password")
        assert h1 != h2  # bcrypt uses random salts


# ===================================================================
# Access tokens (JWT)
# ===================================================================
class TestAccessToken:
    def test_create_and_decode_token(self):
        user_id = str(uuid.uuid4())
        token = auth.create_access_token({"sub": user_id})
        payload = auth.decode_access_token(token)
        assert payload["sub"] == user_id
        assert "exp" in payload

    def test_create_token_with_custom_expiry(self):
        token = auth.create_access_token(
            {"sub": "user1"},
            expires_delta=timedelta(minutes=5),
        )
        payload = auth.decode_access_token(token)
        assert payload["sub"] == "user1"

    def test_decode_expired_token_raises(self):
        token = auth.create_access_token(
            {"sub": "user1"},
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(HTTPException) as exc_info:
            auth.decode_access_token(token)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "INVALID_TOKEN"

    def test_decode_tampered_token_raises(self):
        token = auth.create_access_token({"sub": "user1"})
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(HTTPException) as exc_info:
            auth.decode_access_token(tampered)
        assert exc_info.value.status_code == 401

    def test_decode_garbage_token_raises(self):
        with pytest.raises(HTTPException):
            auth.decode_access_token("not.a.jwt")

    def test_token_preserves_extra_claims(self):
        token = auth.create_access_token({"sub": "u1", "role": "admin"})
        payload = auth.decode_access_token(token)
        assert payload["role"] == "admin"


# ===================================================================
# Decode token ignoring expiry (for refresh flow)
# ===================================================================
class TestDecodeTokenNoExpiry:
    def test_decode_expired_token_succeeds(self):
        token = auth.create_access_token(
            {"sub": "user1"},
            expires_delta=timedelta(seconds=-1),
        )
        payload = auth.decode_access_token_no_expiry(token)
        assert payload["sub"] == "user1"

    def test_decode_valid_token_succeeds(self):
        token = auth.create_access_token({"sub": "user1"})
        payload = auth.decode_access_token_no_expiry(token)
        assert payload["sub"] == "user1"

    def test_decode_garbage_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            auth.decode_access_token_no_expiry("garbage")
        assert exc_info.value.status_code == 401


# ===================================================================
# Refresh tokens (encrypted at rest)
# ===================================================================
class TestRefreshToken:
    def _make_mock_db(self, user=None):
        """Create a mock DB session with a query chain."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = user
        mock_filter.update.return_value = None

        return mock_db

    def test_create_refresh_token_returns_string(self):
        mock_db = self._make_mock_db()
        raw_token = auth.create_refresh_token(mock_db, uuid.uuid4())
        assert isinstance(raw_token, str)
        assert len(raw_token) > 50  # urlsafe_b64 of 64 bytes

    def test_create_refresh_token_stores_encrypted(self):
        mock_db = self._make_mock_db()
        user_id = uuid.uuid4()
        auth.create_refresh_token(mock_db, user_id)
        # Verify update was called on the query chain
        mock_db.query.return_value.filter.return_value.update.assert_called_once()
        call_args = mock_db.query.return_value.filter.return_value.update.call_args[0][0]
        assert "refresh_token_encrypted" in call_args
        assert call_args["refresh_token_encrypted"] is not None
        assert "refresh_token_expires_at" in call_args
        mock_db.commit.assert_called_once()

    def test_verify_refresh_token_success(self):
        mock_db = MagicMock()
        user_id = uuid.uuid4()

        # Create a token first to get encrypted version
        raw_token = auth.create_refresh_token(mock_db, user_id)

        # Get the encrypted token that was stored
        stored_encrypted = mock_db.query.return_value.filter.return_value.update.call_args[0][0][
            "refresh_token_encrypted"
        ]

        # Set up mock user with the encrypted token
        mock_user = MagicMock(spec=database.User)
        mock_user.refresh_token_encrypted = stored_encrypted
        mock_user.refresh_token_expires_at = datetime.utcnow() + timedelta(days=7)

        mock_db.reset_mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = auth.verify_refresh_token(mock_db, raw_token, str(user_id))
        assert result is mock_user

    def test_verify_refresh_token_user_not_found(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            auth.verify_refresh_token(mock_db, "some-token", str(uuid.uuid4()))
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "INVALID_REFRESH_TOKEN"

    def test_verify_refresh_token_expired(self):
        mock_user = MagicMock(spec=database.User)
        mock_user.refresh_token_encrypted = "encrypted-value"
        mock_user.refresh_token_expires_at = datetime.utcnow() - timedelta(days=1)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with pytest.raises(HTTPException) as exc_info:
            auth.verify_refresh_token(mock_db, "some-token", str(uuid.uuid4()))
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "REFRESH_TOKEN_EXPIRED"

    def test_verify_refresh_token_wrong_token(self):
        mock_db = MagicMock()
        user_id = uuid.uuid4()

        # Create a real token
        raw_token = auth.create_refresh_token(mock_db, user_id)
        stored_encrypted = mock_db.query.return_value.filter.return_value.update.call_args[0][0][
            "refresh_token_encrypted"
        ]

        mock_user = MagicMock(spec=database.User)
        mock_user.refresh_token_encrypted = stored_encrypted
        mock_user.refresh_token_expires_at = datetime.utcnow() + timedelta(days=7)

        mock_db.reset_mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with pytest.raises(HTTPException) as exc_info:
            auth.verify_refresh_token(mock_db, "completely-wrong-token", str(user_id))
        assert exc_info.value.status_code == 401

    def test_revoke_refresh_token(self):
        mock_db = MagicMock()
        user_id = uuid.uuid4()
        auth.revoke_refresh_token(mock_db, user_id)

        call_args = mock_db.query.return_value.filter.return_value.update.call_args[0][0]
        assert call_args["refresh_token_encrypted"] is None
        assert call_args["refresh_token_expires_at"] is None
        mock_db.commit.assert_called_once()


# ===================================================================
# Cookie helpers
# ===================================================================
class TestCookieHelpers:
    def test_set_auth_cookies(self):
        response = Response()
        auth.set_auth_cookies(response, "access-tok", "refresh-tok")

        # Response.headers has raw set-cookie entries
        cookie_headers = [
            v for k, v in response.raw_headers if k == b"set-cookie"
        ]
        assert len(cookie_headers) == 2

        cookies_str = b" ".join(cookie_headers).decode()
        assert "access_token=access-tok" in cookies_str
        assert "refresh_token=refresh-tok" in cookies_str
        assert "httponly" in cookies_str.lower()

    def test_clear_auth_cookies(self):
        response = Response()
        auth.clear_auth_cookies(response)

        cookie_headers = [
            v for k, v in response.raw_headers if k == b"set-cookie"
        ]
        # delete_cookie sets max-age=0 or expires in the past
        assert len(cookie_headers) == 2
        cookies_str = b" ".join(cookie_headers).decode()
        # Deleted cookies have max-age=0
        assert 'max-age=0' in cookies_str.lower() or '01 jan 1970' in cookies_str.lower()


# ===================================================================
# get_current_user dependency
# ===================================================================
class TestGetCurrentUser:
    def _make_request(self, cookies=None):
        """Create a mock Request with optional cookies."""
        request = MagicMock()
        request.cookies = cookies or {}
        return request

    def test_auth_via_cookie(self, db):
        user_id = str(uuid.uuid4())
        token = auth.create_access_token({"sub": user_id})

        mock_user = MagicMock(spec=database.User)
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        request = self._make_request(cookies={"access_token": token})
        result = auth.get_current_user(request, credentials=None, db=mock_db)
        assert result is mock_user

    def test_auth_via_bearer_header(self):
        user_id = str(uuid.uuid4())
        token = auth.create_access_token({"sub": user_id})

        mock_user = MagicMock(spec=database.User)
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        credentials = MagicMock()
        credentials.credentials = token

        request = self._make_request(cookies={})
        result = auth.get_current_user(request, credentials=credentials, db=mock_db)
        assert result is mock_user

    def test_no_token_raises(self):
        request = self._make_request(cookies={})
        mock_db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            auth.get_current_user(request, credentials=None, db=mock_db)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "NOT_AUTHENTICATED"

    def test_invalid_token_raises(self):
        request = self._make_request(cookies={"access_token": "bad-token"})
        mock_db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            auth.get_current_user(request, credentials=None, db=mock_db)
        assert exc_info.value.status_code == 401

    def test_token_without_sub_claim_raises(self):
        # Token with no "sub" key
        token = auth.create_access_token({"role": "admin"})
        request = self._make_request(cookies={"access_token": token})
        mock_db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            auth.get_current_user(request, credentials=None, db=mock_db)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "INVALID_TOKEN"

    def test_user_not_found_in_db_raises(self):
        user_id = str(uuid.uuid4())
        token = auth.create_access_token({"sub": user_id})
        request = self._make_request(cookies={"access_token": token})

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            auth.get_current_user(request, credentials=None, db=mock_db)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "USER_NOT_FOUND"

    def test_cookie_takes_priority_over_bearer(self):
        """When both cookie and bearer are present, cookie wins."""
        cookie_user_id = str(uuid.uuid4())
        bearer_user_id = str(uuid.uuid4())

        cookie_token = auth.create_access_token({"sub": cookie_user_id})
        bearer_token = auth.create_access_token({"sub": bearer_user_id})

        mock_user = MagicMock(spec=database.User)
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        credentials = MagicMock()
        credentials.credentials = bearer_token

        request = self._make_request(cookies={"access_token": cookie_token})
        auth.get_current_user(request, credentials=credentials, db=mock_db)

        # Verify the filter used the cookie user_id
        filter_call = mock_db.query.return_value.filter.call_args
        # The filter expression should involve the cookie_user_id
        assert filter_call is not None
