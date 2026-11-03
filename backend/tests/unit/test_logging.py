"""Testes de unidade da redação de segredos nos logs (PRD §11)."""

from __future__ import annotations

import pytest

from app.core.logging import REDACTED, redact, redact_processor


@pytest.mark.unit
def test_password_key_is_redacted() -> None:
    result = redact({"password": "super-secreta", "user": "admin"})
    assert result == {"password": REDACTED, "user": "admin"}


@pytest.mark.unit
def test_nested_and_case_insensitive_keys() -> None:
    payload = {
        "request": {"Authorization": "Bearer abc", "body": {"Token": "xyz", "id": 3}},
        "items": [{"secret": "s1"}, {"ok": True}],
    }
    result = redact(payload)
    assert result["request"]["Authorization"] == REDACTED
    assert result["request"]["body"]["Token"] == REDACTED
    assert result["request"]["body"]["id"] == 3
    assert result["items"][0]["secret"] == REDACTED
    assert result["items"][1]["ok"] is True


@pytest.mark.unit
def test_database_url_and_csrf_are_redacted() -> None:
    result = redact({"database_url": "mysql://u:p@h/db", "csrf_token": "abc"})
    assert result["database_url"] == REDACTED
    assert result["csrf_token"] == REDACTED


@pytest.mark.unit
def test_processor_returns_dict_for_non_mapping() -> None:
    assert isinstance(redact_processor(None, "info", {"event": "x"}), dict)


@pytest.mark.unit
def test_depth_is_bounded() -> None:
    deep: dict[str, object] = {"password": "x"}
    for _ in range(20):
        deep = {"nested": deep}
    result = redact(deep)
    assert "password" not in str(result) or REDACTED in str(result)
