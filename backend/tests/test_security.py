from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    decode_access_token,
    generate_temp_password,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verifies():
    hashed = hash_password("my-secret-pass")
    assert hashed != "my-secret-pass"
    assert verify_password("my-secret-pass", hashed)
    assert not verify_password("wrong-pass", hashed)


def test_two_hashes_of_same_password_differ():
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_handles_broken_hash():
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_token_round_trip():
    assert decode_access_token(create_access_token(42)) == 42


def test_bad_and_expired_tokens_are_rejected():
    assert decode_access_token("garbage") is None
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        get_settings().secret_key,
        algorithm=ALGORITHM,
    )
    assert decode_access_token(expired) is None
    wrong_key = jwt.encode({"sub": "1"}, "some-other-key-that-is-long-enough-123", algorithm=ALGORITHM)
    assert decode_access_token(wrong_key) is None


def test_temp_password_has_expected_shape():
    pw = generate_temp_password()
    assert len(pw) == 10
    assert generate_temp_password() != pw
