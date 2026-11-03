"""Cliente HTTPS: classificação de falhas, retries e cabeçalhos."""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

from guardian_agent.transport import CentralClient, TransportError


class FakeResponse:
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def read(self, _size: int = -1) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class FakeOpener:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.calls: list[Any] = []

    def open(self, request: Any, timeout: float | None = None) -> Any:
        del timeout
        self.calls.append(request)
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://guardian.exemplo.com/api/v1/agent/metrics",
        code=code,
        msg="erro",
        hdrs=None,
        fp=io.BytesIO(b'{"error":{"code":"x"}}'),
    )


def build_client(opener: FakeOpener, **kwargs: Any) -> CentralClient:
    defaults: dict[str, Any] = {
        "timeout": 5.0,
        "opener": opener,
        "max_attempts": 3,
        "backoff_base": 0.01,
        "sleep": lambda _seconds: None,
        "random_value": lambda: 0.0,
    }
    defaults.update(kwargs)
    return CentralClient("https://guardian.exemplo.com", **defaults)


@pytest.mark.unit
def test_successful_send_returns_body() -> None:
    opener = FakeOpener([FakeResponse(200, {"recorded": True})])
    client = build_client(opener)

    result = client.send_metrics(credential="segredo", payload={"a": 1})

    assert result == {"recorded": True}
    assert len(opener.calls) == 1
    request = opener.calls[0]
    assert request.full_url.endswith("/api/v1/agent/metrics")
    assert request.get_header("Authorization") == "Bearer segredo"
    assert request.get_header("Content-type") == "application/json"


@pytest.mark.unit
def test_server_error_is_retried_then_succeeds() -> None:
    opener = FakeOpener([http_error(503), FakeResponse(200, {"ok": True})])
    client = build_client(opener)

    assert client.send_metrics(credential="c", payload={}) == {"ok": True}
    assert len(opener.calls) == 2


@pytest.mark.unit
def test_permanent_error_is_not_retried() -> None:
    opener = FakeOpener([http_error(422)])
    client = build_client(opener)

    with pytest.raises(TransportError) as excinfo:
        client.send_metrics(credential="c", payload={})

    assert excinfo.value.transient is False
    assert excinfo.value.status == 422
    assert len(opener.calls) == 1


@pytest.mark.unit
def test_network_failure_exhausts_attempts() -> None:
    failure = urllib.error.URLError("sem rede")
    opener = FakeOpener([failure, failure, failure])
    client = build_client(opener)

    with pytest.raises(TransportError) as excinfo:
        client.heartbeat(
            credential="c",
            sent_at="2026-11-03T12:00:00Z",
            agent_version="0.2.0",
            uptime_seconds=1,
            hostname=None,
        )

    assert excinfo.value.transient is True
    assert len(opener.calls) == 3


@pytest.mark.unit
def test_invalid_json_is_permanent_failure() -> None:
    class BadResponse(FakeResponse):
        def read(self, _size: int = -1) -> bytes:
            return b"nao-e-json"

    opener = FakeOpener([BadResponse(200, {})])
    client = build_client(opener)

    with pytest.raises(TransportError) as excinfo:
        client.fetch_config(credential="c")
    assert excinfo.value.transient is False


@pytest.mark.unit
def test_register_sends_provisioning_token() -> None:
    opener = FakeOpener([FakeResponse(201, {"credential": "nova"})])
    client = build_client(opener)

    result = client.register(provisioning_token="t" * 40, agent_version="0.2.0")

    assert result["credential"] == "nova"
    body = json.loads(opener.calls[0].data.decode("utf-8"))
    assert body["provisioning_token"] == "t" * 40
