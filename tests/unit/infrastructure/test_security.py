"""Технічні адаптери: bcrypt і JWT. Не потребують БД."""
import pytest

from app.infrastructure.security import (
    BcryptPasswordHasher,
    InvalidToken,
    JwtTokenService,
)


def test_bcrypt_hash_and_verify():
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash("secret123")

    assert hashed != "secret123"
    assert hasher.verify("secret123", hashed)
    assert not hasher.verify("wrong-pass", hashed)


def test_same_password_gives_different_hashes():
    hasher = BcryptPasswordHasher()
    assert hasher.hash("secret123") != hasher.hash("secret123")  # випадкова «сіль»


def test_token_round_trip():
    tokens = JwtTokenService(secret="test-secret-that-is-long-enough-32b", expire_minutes=5)
    assert tokens.read_client_id(tokens.create(42)) == 42


def test_expired_token_rejected():
    tokens = JwtTokenService(secret="test-secret-that-is-long-enough-32b", expire_minutes=-1)
    with pytest.raises(InvalidToken, match="минув"):
        tokens.read_client_id(tokens.create(42))


def test_token_with_wrong_signature_rejected():
    token = JwtTokenService(secret="first-secret-that-is-long-enough-32b").create(42)
    with pytest.raises(InvalidToken):
        JwtTokenService(secret="other-secret-that-is-long-enough-32b").read_client_id(token)
