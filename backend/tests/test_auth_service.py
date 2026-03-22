"""Tests for auth service — password hashing and JWT tokens."""

from app.services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_password_returns_bcrypt_hash(self):
        hashed = hash_password("testpassword123")
        assert hashed.startswith("$2b$")
        assert hashed != "testpassword123"

    def test_hash_password_different_each_time(self):
        h1 = hash_password("testpassword123")
        h2 = hash_password("testpassword123")
        assert h1 != h2

    def test_verify_password_correct(self):
        hashed = hash_password("testpassword123")
        assert verify_password("testpassword123", hashed) is True

    def test_verify_password_wrong(self):
        hashed = hash_password("testpassword123")
        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_empty(self):
        hashed = hash_password("testpassword123")
        assert verify_password("", hashed) is False


class TestJWTTokens:
    def test_create_and_decode_token(self):
        token = create_access_token({"sub": "test-user-id"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "test-user-id"
        assert "exp" in payload

    def test_decode_invalid_token(self):
        result = decode_access_token("not.a.valid.token")
        assert result is None

    def test_decode_empty_token(self):
        result = decode_access_token("")
        assert result is None

    def test_token_contains_custom_data(self):
        token = create_access_token({"sub": "user-123", "extra": "data"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["extra"] == "data"
