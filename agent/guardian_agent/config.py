"""Configuração local do agente.

O arquivo padrão é ``/etc/vps-guardian/agent.json`` (JSON puro, sem dependências além
da stdlib — ``tomllib`` só existe a partir do Python 3.11 e o alvo inclui o 3.10 do
Ubuntu 22.04).

Contém a credencial individual do servidor: é gravado com permissão ``0600`` e
substituído de forma atômica. A credencial nunca é escrita em log.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_CONFIG_PATH = "/etc/vps-guardian/agent.json"
MIN_INTERVAL = 10
MAX_INTERVAL = 3600
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ConfigError(Exception):
    """Configuração ausente, inválida ou insegura."""


@dataclass(frozen=True, slots=True)
class AgentConfig:
    api_url: str
    server_id: str
    credential: str | None = None
    provisioning_token: str | None = None
    interval_seconds: int = 30
    request_timeout_seconds: int = 10
    verify_tls: bool = True
    spool_dir: str = "/var/lib/vps-guardian/spool"
    state_file: str = "/var/lib/vps-guardian/state.json"
    log_file: str = "/var/log/vps-guardian/agent.log"
    log_level: str = "INFO"
    max_spool_items: int = 120
    max_spool_age_seconds: int = 21600
    exclude_interfaces: tuple[str, ...] = ("lo",)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentConfig:
        if not isinstance(data, dict):
            raise ConfigError("configuração deve ser um objeto JSON")

        api_url = str(data.get("api_url", "")).strip().rstrip("/")
        if not api_url:
            raise ConfigError("api_url é obrigatória")
        _validate_api_url(api_url, allow_http=bool(data.get("allow_insecure_http", False)))

        server_id = str(data.get("server_id", "")).strip()
        if not server_id:
            raise ConfigError("server_id é obrigatório")

        credential = _optional_str(data.get("credential"))
        provisioning_token = _optional_str(data.get("provisioning_token"))
        if credential is None and provisioning_token is None:
            raise ConfigError("informe credential (já registrado) ou provisioning_token")

        interval = int(data.get("interval_seconds", 30))
        if not MIN_INTERVAL <= interval <= MAX_INTERVAL:
            raise ConfigError(f"interval_seconds deve estar entre {MIN_INTERVAL} e {MAX_INTERVAL}")

        timeout = int(data.get("request_timeout_seconds", 10))
        if not 1 <= timeout <= 120:
            raise ConfigError("request_timeout_seconds deve estar entre 1 e 120")

        exclude = data.get("exclude_interfaces", ["lo"])
        if not isinstance(exclude, (list, tuple)) or not all(isinstance(i, str) for i in exclude):
            raise ConfigError("exclude_interfaces deve ser uma lista de textos")

        # log_file nulo desabilita o arquivo de log (útil em container/journald).
        log_file_raw = data.get("log_file", "/var/log/vps-guardian/agent.log")
        log_file = None if log_file_raw is None else str(log_file_raw)

        return cls(
            api_url=api_url,
            server_id=server_id,
            credential=credential,
            provisioning_token=provisioning_token,
            interval_seconds=interval,
            request_timeout_seconds=timeout,
            verify_tls=bool(data.get("verify_tls", True)),
            spool_dir=str(data.get("spool_dir", "/var/lib/vps-guardian/spool")),
            state_file=str(data.get("state_file", "/var/lib/vps-guardian/state.json")),
            log_file=log_file,
            log_level=str(data.get("log_level", "INFO")).upper(),
            max_spool_items=int(data.get("max_spool_items", 120)),
            max_spool_age_seconds=int(data.get("max_spool_age_seconds", 21600)),
            exclude_interfaces=tuple(exclude),
        )

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> AgentConfig:
        config_path = Path(path)
        try:
            # utf-8-sig tolera BOM (arquivo editado no Windows ou por painel).
            raw = config_path.read_text(encoding="utf-8-sig")
        except FileNotFoundError as exc:
            raise ConfigError(f"arquivo de configuração não encontrado: {config_path}") from exc
        except OSError as exc:
            raise ConfigError(f"não foi possível ler {config_path}: {exc.strerror}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"JSON inválido em {config_path}: linha {exc.lineno}") from exc
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_url": self.api_url,
            "server_id": self.server_id,
            "credential": self.credential,
            "provisioning_token": self.provisioning_token,
            "interval_seconds": self.interval_seconds,
            "request_timeout_seconds": self.request_timeout_seconds,
            "verify_tls": self.verify_tls,
            "spool_dir": self.spool_dir,
            "state_file": self.state_file,
            "log_file": self.log_file,
            "log_level": self.log_level,
            "max_spool_items": self.max_spool_items,
            "max_spool_age_seconds": self.max_spool_age_seconds,
            "exclude_interfaces": list(self.exclude_interfaces),
        }

    def with_credential(self, credential: str) -> AgentConfig:
        """Após o registro, remove o token de provisionamento e guarda a credencial."""
        return replace(self, credential=credential, provisioning_token=None)

    def save(self, path: str | Path = DEFAULT_CONFIG_PATH) -> None:
        write_private_file(Path(path), json.dumps(self.to_dict(), indent=2) + "\n")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _validate_api_url(api_url: str, *, allow_http: bool) -> None:
    parts = urlsplit(api_url)
    if parts.scheme not in {"https", "http"} or not parts.netloc:
        raise ConfigError("api_url deve ser uma URL absoluta https://")
    if parts.scheme == "http":
        host = (parts.hostname or "").lower()
        if not (allow_http or host in _LOCAL_HOSTS):
            raise ConfigError(
                "api_url deve usar https:// — HTTP só é aceito em localhost "
                "(defina allow_insecure_http=true apenas em teste local)"
            )


def write_private_file(path: Path, content: str) -> None:
    """Escrita atômica com permissão 0600 (nunca deixa arquivo parcial)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    with contextlib.suppress(OSError):  # pragma: no cover - plataformas sem chmod completo
        os.chmod(path, 0o600)
