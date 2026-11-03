"""Testes de unidade da validação de schemas."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.agent import AgentHeartbeatRequest, AgentRegistrationRequest
from app.schemas.server import ServerCreate, ServerUpdate


@pytest.mark.unit
def test_server_create_defaults() -> None:
    server = ServerCreate(name="VPS-01")
    assert server.environment.value == "other"
    assert server.panel.value == "none"
    assert server.collection_interval_seconds == 30
    assert server.heartbeat_timeout_seconds == 90
    assert server.tags == []


@pytest.mark.unit
def test_timeout_must_cover_two_collections() -> None:
    with pytest.raises(ValidationError):
        ServerCreate(
            name="VPS-01",
            collection_interval_seconds=60,
            heartbeat_timeout_seconds=90,
        )


@pytest.mark.unit
def test_invalid_ip_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ServerCreate(name="VPS-01", ip_address="999.999.999.999")


@pytest.mark.unit
def test_ipv6_is_accepted_and_normalized() -> None:
    server = ServerCreate(name="VPS-01", ip_address="2001:0DB8::1")
    assert server.ip_address == "2001:db8::1"


@pytest.mark.unit
def test_tags_are_deduplicated_case_insensitively() -> None:
    server = ServerCreate(name="VPS-01", tags=["Producao", "producao", "web "])
    assert server.tags == ["Producao", "web"]


@pytest.mark.unit
def test_tags_above_limit_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ServerCreate(name="VPS-01", tags=[f"t{i}" for i in range(21)])


@pytest.mark.unit
def test_hostname_is_lowercased_and_validated() -> None:
    server = ServerCreate(name="VPS-01", hostname="VPS-01.Exemplo.COM")
    assert server.hostname == "vps-01.exemplo.com"
    with pytest.raises(ValidationError):
        ServerCreate(name="VPS-01", hostname="-invalido")


@pytest.mark.unit
def test_name_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        ServerCreate(name="VPS\n01")


@pytest.mark.unit
def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ServerCreate(name="VPS-01", status="online")  # status é somente leitura


@pytest.mark.unit
def test_partial_update_accepts_single_field() -> None:
    update = ServerUpdate(notes="manutenção programada")
    assert update.model_dump(exclude_unset=True) == {"notes": "manutenção programada"}


@pytest.mark.unit
def test_heartbeat_requires_timezone() -> None:
    with pytest.raises(ValidationError):
        AgentHeartbeatRequest(
            sent_at=datetime(2026, 11, 3, 12, 0, 0),  # naive
            agent_version="1.0.0",
            uptime_seconds=10,
        )


@pytest.mark.unit
def test_heartbeat_accepts_utc() -> None:
    payload = AgentHeartbeatRequest(
        sent_at=datetime(2026, 11, 3, 12, 0, 0, tzinfo=UTC),
        agent_version="1.0.0",
        uptime_seconds=10,
    )
    assert payload.uptime_seconds == 10


@pytest.mark.unit
def test_agent_version_pattern() -> None:
    with pytest.raises(ValidationError):
        AgentRegistrationRequest(provisioning_token="x" * 40, agent_version="v1")


@pytest.mark.unit
def test_provisioning_token_rejects_whitespace() -> None:
    with pytest.raises(ValidationError):
        AgentRegistrationRequest(
            provisioning_token="token com espaco e tamanho suficiente", agent_version="1.0.0"
        )
