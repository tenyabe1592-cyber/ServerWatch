from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

SCHEME = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000


def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS, salt: bytes | None = None) -> str:
    if len(password) < 14:
        raise ValueError("password must contain at least 14 characters")
    salt = salt or secrets.token_bytes(18)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "$".join(
        (SCHEME, str(iterations), base64.urlsafe_b64encode(salt).decode(), base64.urlsafe_b64encode(digest).decode())
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, rounds, salt_text, expected_text = encoded.split("$", 3)
        if scheme != SCHEME:
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(expected_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

