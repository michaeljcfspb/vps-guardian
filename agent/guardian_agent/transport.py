"""Cliente HTTPS da central.

Somente stdlib (``urllib``) — reduz superfície de ataque e facilita auditoria.
Classificação de falhas:

- **transiente** (rede, timeout, HTTP 429/5xx): nova tentativa com backoff exponencial;
- **permanente** (HTTP 4xx, exceto 429): não repetir — payload/credencial não vão melhorar.

A credencial nunca é registrada em log. Respostas são limitadas em tamanho.
"""

from __future__ import annotations

import contextlib
import json
import random
import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from guardian_agent import __version__

MAX_RESPONSE_BYTES = 64 * 1024
PERMANENT_STATUS = {400, 401, 403, 404, 409, 413, 415, 422}
TRANSIENT_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: dict[str, Any]


class TransportError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        transient: bool = True,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.transient = transient
        self.retry_after = retry_after


class CentralClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        verify_tls: bool = True,
        opener: Any | None = None,
        max_attempts: int = 3,
        backoff_base: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts deve ser >= 1")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._verify_tls = verify_tls
        self._opener = opener
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._sleep = sleep
        self._random = random_value

    # --- Operações de alto nível -------------------------------------------

    def register(self, *, provisioning_token: str, **agent_info: Any) -> dict[str, Any]:
        payload = {"provisioning_token": provisioning_token, **agent_info}
        return self._request_with_retries("POST", "/api/v1/agent/register", payload)

    def heartbeat(
        self,
        *,
        credential: str,
        sent_at: str,
        agent_version: str,
        uptime_seconds: int,
        hostname: str | None,
    ) -> dict[str, Any]:
        payload = {
            "sent_at": sent_at,
            "agent_version": agent_version,
            "uptime_seconds": uptime_seconds,
            "hostname": hostname,
        }
        return self._request_with_retries(
            "POST", "/api/v1/agent/heartbeat", payload, credential=credential
        )

    def send_metrics(self, *, credential: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_with_retries(
            "POST", "/api/v1/agent/metrics", payload, credential=credential
        )

    def fetch_config(self, *, credential: str) -> dict[str, Any]:
        return self._request_with_retries(
            "GET", "/api/v1/agent/config", None, credential=credential
        )

    # --- Núcleo -------------------------------------------------------------

    def _request_with_retries(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        credential: str | None = None,
    ) -> dict[str, Any]:
        attempt = 0
        while True:
            attempt += 1
            try:
                return self._request_once(
                    method, path, payload, credential=credential
                ).body
            except TransportError as exc:
                if not exc.transient or attempt >= self._max_attempts:
                    raise
                delay = self._backoff(attempt, exc.retry_after)
                self._sleep(delay)

    def _backoff(self, attempt: int, retry_after: float | None) -> float:
        base = self._backoff_base * (2 ** (attempt - 1))
        jitter = self._random() * 0.25 * base
        return max(base + jitter, retry_after or 0.0)

    def _request_once(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        credential: str | None,
    ) -> Response:
        url = f"{self._base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None

        headers = {
            "Accept": "application/json",
            "User-Agent": f"vps-guardian-agent/{__version__}",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        if credential:
            headers["Authorization"] = f"Bearer {credential}"

        # URL composta de base validada (https) + caminho constante; sem entrada do usuário.
        request = urllib.request.Request(  # noqa: S310
            url, data=data, headers=headers, method=method
        )
        opener = self._opener if self._opener is not None else self._build_opener()

        try:
            # URL fixa composta de base validada (https) + caminho constante.
            with opener.open(request, timeout=self._timeout) as response:  # noqa: S310
                raw = response.read(MAX_RESPONSE_BYTES)
                return Response(status=int(response.status), body=_decode(raw))
        except urllib.error.HTTPError as exc:
            # A resposta de erro da central é JSON sanitizado; não propagar o corpo.
            with contextlib.suppress(Exception):
                exc.read(MAX_RESPONSE_BYTES)
            status = int(exc.code)
            raise TransportError(
                f"HTTP {status}",
                status=status,
                transient=status in TRANSIENT_STATUS or status >= 500,
                retry_after=_retry_after(exc.headers),
            ) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise TransportError(
                f"falha de rede: {type(exc).__name__}", transient=True
            ) from exc

    def _build_opener(self) -> urllib.request.OpenerDirector:
        if self._verify_tls:
            return urllib.request.build_opener()
        # Uso restrito a testes locais; a configuração padrão exige TLS válido.
        context = ssl._create_unverified_context()  # noqa: S323
        return urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))


def _decode(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransportError("resposta inválida da central", transient=False) from exc
    if not isinstance(parsed, dict):
        raise TransportError("resposta inesperada da central", transient=False)
    return parsed


def _retry_after(headers: Any) -> float | None:
    if not headers:
        return None
    try:
        value = headers.get("Retry-After")
    except AttributeError:  # pragma: no cover - headers alternativos
        return None
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
