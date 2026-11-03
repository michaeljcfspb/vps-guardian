"""Testes de unidade de segurança (hash, tokens, IDs)."""

from __future__ import annotations

import pytest

from app.core.security import (
    TOKEN_PREFIX_LENGTH,
    generate_token,
    hash_password,
    hash_token,
    new_id,
    token_prefix,
    utc_now,
    verify_password,
)


@pytest.mark.unit
def test_password_hash_is_not_plaintext() -> None:
    password = "SenhaMuitoForte!2026"
    hashed = hash_password(password)
    assert hashed != password
    assert hashed.startswith("$argon2id$")


@pytest.mark.unit
def test_password_verify_roundtrip() -> None:
    hashed = hash_password("SenhaMuitoForte!2026")
    assert verify_password(hashed, "SenhaMuitoForte!2026") is True


@pytest.mark.unit
def test_password_verify_rejects_wrong_password() -> None:
    hashed = hash_password("SenhaMuitoForte!2026")
    assert verify_password(hashed, "SenhaMuitoForte!2027") is False


@pytest.mark.unit
def test_password_verify_rejects_garbage_hash() -> None:
    assert verify_password("not-a-hash", "qualquer") is False


@pytest.mark.unit
def test_same_password_produces_different_hashes() -> None:
    assert hash_password("mesma-senha") != hash_password("mesma-senha")


@pytest.mark.unit
def test_tokens_are_unique_and_long_enough() -> None:
    tokens = {generate_token() for _ in range(200)}
    assert len(tokens) == 200
    assert all(len(token) >= 40 for token in tokens)


@pytest.mark.unit
def test_token_hash_is_deterministic_and_hex() -> None:
    token = generate_token()
    digest = hash_token(token)
    assert digest == hash_token(token)
    assert len(digest) == 64
    int(digest, 16)  # levanta se não for hexadecimal


@pytest.mark.unit
def test_token_prefix_length() -> None:
    token = generate_token()
    assert len(token_prefix(token)) == TOKEN_PREFIX_LENGTH
    assert token.startswith(token_prefix(token))


@pytest.mark.unit
def test_new_id_is_unique() -> None:
    assert len({new_id() for _ in range(100)}) == 100


@pytest.mark.unit
def test_utc_now_is_naive() -> None:
    assert utc_now().tzinfo is None
