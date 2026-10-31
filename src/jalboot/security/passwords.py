"""Password hashing with scrypt from the standard library."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

N, R, P = 2**14, 8, 1


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _derive(password, salt, N, R, P)
    encoded = base64.b64encode(salt).decode(), base64.b64encode(digest).decode()
    return f"scrypt${N}${R}${P}${encoded[0]}${encoded[1]}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        cost = int(n), int(r), int(p)
        salt_bytes, expected = base64.b64decode(salt), base64.b64decode(digest)
    except (ValueError, TypeError):
        return False
    if scheme != "scrypt":
        return False
    # Outside the try: scrypt running out of memory is a fault, not a wrong password.
    return hmac.compare_digest(_derive(password, salt_bytes, *cost), expected)


# Checked when the email is unknown, so that a wrong email and a wrong password
# take the same time and an attacker cannot list staff accounts by timing.
DUMMY_HASH = hash_password(secrets.token_hex(16))
