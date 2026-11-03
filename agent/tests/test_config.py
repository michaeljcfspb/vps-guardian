"""Configuração local do agente."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from guardian_agent.config import AgentConfig, ConfigError, write_private_file

BASE = {
    "api_url": "https://guardian.exemplo.com",
    "server_id": "11111111-1111-4111-8111-111111111111",
    "provisioning_token": "t" * 40,
}


@pytest.mark.unit
def test_valid_config_is_accepted() -> None:
    config = AgentConfig.from_dict(BASE)
    assert config.interval_seconds == 30
    assert config.verify_tls is True
    assert config.credential is None


@pytest.mark.unit
def test_http_is_rejected_outside_localhost() -> None:
    with pytest.raises(ConfigError):
        AgentConfig.from_dict({**BASE, "api_url": "http://guardian.exemplo.com"})


@pytest.mark.unit
def test_http_is_allowed_for_localhost() -> None:
    config = AgentConfig.from_dict({**BASE, "api_url": "http://127.0.0.1:8000"})
    assert config.api_url == "http://127.0.0.1:8000"


@pytest.mark.unit
def test_missing_api_url_is_rejected() -> None:
    with pytest.raises(ConfigError):
        AgentConfig.from_dict({**BASE, "api_url": ""})


@pytest.mark.unit
def test_interval_bounds() -> None:
    with pytest.raises(ConfigError):
        AgentConfig.from_dict({**BASE, "interval_seconds": 5})
    with pytest.raises(ConfigError):
        AgentConfig.from_dict({**BASE, "interval_seconds": 7200})


@pytest.mark.unit
def test_requires_credential_or_provisioning_token() -> None:
    with pytest.raises(ConfigError):
        AgentConfig.from_dict({"api_url": BASE["api_url"], "server_id": BASE["server_id"]})


@pytest.mark.unit
def test_with_credential_removes_provisioning_token() -> None:
    config = AgentConfig.from_dict(BASE).with_credential("credencial-permanente")
    assert config.credential == "credencial-permanente"
    assert config.provisioning_token is None


@pytest.mark.unit
def test_save_is_atomic_and_private(tmp_path: Path) -> None:
    target = tmp_path / "agent.json"
    config = AgentConfig.from_dict(BASE).with_credential("c" * 40)
    config.save(target)

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["credential"] == "c" * 40
    assert saved["provisioning_token"] is None
    assert not list(tmp_path.glob(".tmp-*"))

    if sys.platform != "win32":
        assert os.stat(target).st_mode & 0o777 == 0o600


@pytest.mark.unit
def test_null_log_file_disables_file_logging() -> None:
    config = AgentConfig.from_dict({**BASE, "log_file": None})
    assert config.log_file is None
    assert config.to_dict()["log_file"] is None


@pytest.mark.unit
def test_default_log_file_is_used_when_absent() -> None:
    config = AgentConfig.from_dict(BASE)
    assert config.log_file == "/var/log/vps-guardian/agent.log"


@pytest.mark.unit
def test_load_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        AgentConfig.load(tmp_path / "nope.json")


@pytest.mark.unit
def test_load_reports_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "agent.json"
    path.write_text("{nao-e-json", encoding="utf-8")
    with pytest.raises(ConfigError):
        AgentConfig.load(path)


@pytest.mark.unit
def test_write_private_file_creates_parents(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "file.txt"
    write_private_file(target, "conteudo")
    assert target.read_text(encoding="utf-8") == "conteudo"
