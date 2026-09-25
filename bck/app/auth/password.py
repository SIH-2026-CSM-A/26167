"""Password hashing — argon2 directly (argon2-cffi), no passlib indirection."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# OWASP Argon2id minimum (19 MiB, t=2, p=1). The defaults (64 MiB per op) OOM a 512 MB instance.
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
