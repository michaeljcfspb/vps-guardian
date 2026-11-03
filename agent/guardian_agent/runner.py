"""Ciclo de vida do agente: registro, coleta, envio e buffer local."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from guardian_agent import __version__
from guardian_agent.collectors.cpu import CpuSample, collect_cpu
from guardian_agent.collectors.disk import DiskSample, collect_disks
from guardian_agent.collectors.memory import MemorySample, collect_memory
from guardian_agent.collectors.network import (
    NetworkSample,
    collect_networks,
    current_counters,
)
from guardian_agent.collectors.system import (
    collect_process_count,
    collect_system_info,
    collect_uptime_seconds,
)
from guardian_agent.config import DEFAULT_CONFIG_PATH, AgentConfig, ConfigError
from guardian_agent.logging_setup import register_secret
from guardian_agent.spool import Spool
from guardian_agent.state import NetworkState, load_state, save_state
from guardian_agent.transport import CentralClient, TransportError

POISON_LIMIT = 5


@dataclass(frozen=True)
class CollectorSet:
    cpu: Callable[[], CpuSample]
    memory: Callable[[], MemorySample]
    disks: Callable[[], list[DiskSample]]
    networks: Callable[..., list[NetworkSample]]
    uptime: Callable[[], int]
    processes: Callable[[], int | None]


def default_collectors() -> CollectorSet:
    return CollectorSet(
        cpu=collect_cpu,
        memory=collect_memory,
        disks=collect_disks,
        networks=collect_networks,
        uptime=collect_uptime_seconds,
        processes=collect_process_count,
    )


@dataclass(frozen=True, slots=True)
class TickResult:
    metrics_sent: bool
    metrics_spooled: bool
    spool_flushed: int
    heartbeat_ok: bool


class AgentRunner:
    def __init__(
        self,
        config: AgentConfig,
        client: CentralClient,
        *,
        collectors: CollectorSet | None = None,
        spool: Spool | None = None,
        config_path: str = DEFAULT_CONFIG_PATH,
        logger: logging.Logger | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._config = config
        self._client = client
        self._collectors = collectors or default_collectors()
        self._spool = spool or Spool(
            config.spool_dir,
            max_items=config.max_spool_items,
            max_age_seconds=config.max_spool_age_seconds,
        )
        self._config_path = config_path
        self._logger = logger or logging.getLogger("guardian_agent")
        self._clock = clock
        self._state = load_state(config.state_file)

    # --- Registro -----------------------------------------------------------

    def ensure_registered(self) -> AgentConfig:
        """Troca o token de provisionamento pela credencial permanente (uma vez)."""
        if self._config.credential:
            register_secret(self._config.credential)
            return self._config
        if not self._config.provisioning_token:
            raise ConfigError("sem credencial e sem token de provisionamento")

        info = collect_system_info()
        response = self._client.register(
            provisioning_token=self._config.provisioning_token,
            agent_version=__version__,
            hostname=info.hostname,
            os_name=info.os_name,
            os_version=info.os_version,
            kernel=info.kernel,
            architecture=info.architecture,
        )
        credential = str(response.get("credential") or "")
        if not credential:
            raise TransportError("central não retornou credencial", transient=False)

        self._config = self._config.with_credential(credential)
        self._config.save(self._config_path)
        register_secret(credential)
        self._logger.info(
            "agente registrado",
            extra={"server_id": self._config.server_id, "config": str(self._config_path)},
        )
        return self._config

    # --- Coleta -------------------------------------------------------------

    def build_payload(self, now: float) -> tuple[dict[str, Any], dict[str, tuple[int, int]]]:
        cpu = self._collectors.cpu()
        memory = self._collectors.memory()
        disks = self._collectors.disks()

        previous = self._state.counters if self._state else None
        elapsed = (now - self._state.timestamp) if self._state else None
        networks = self._collectors.networks(
            previous=previous,
            elapsed_seconds=elapsed,
            exclude=self._config.exclude_interfaces,
        )

        payload: dict[str, Any] = {
            "collected_at": _iso_utc(now),
            "agent_version": __version__,
            "host": {
                "cpu_percent": cpu.percent,
                "cpu_cores": cpu.cores,
                "load_1": cpu.load_1,
                "load_5": cpu.load_5,
                "load_15": cpu.load_15,
                "ram_total_bytes": memory.total_bytes,
                "ram_used_bytes": memory.used_bytes,
                "ram_available_bytes": memory.available_bytes,
                "ram_percent": memory.percent,
                "swap_total_bytes": memory.swap_total_bytes,
                "swap_used_bytes": memory.swap_used_bytes,
                "swap_percent": memory.swap_percent,
                "uptime_seconds": self._collectors.uptime(),
                "process_count": self._collectors.processes(),
            },
            "disks": [
                {
                    "mount_point": sample.mount_point,
                    "filesystem": sample.filesystem,
                    "total_bytes": sample.total_bytes,
                    "used_bytes": sample.used_bytes,
                    "free_bytes": sample.free_bytes,
                    "used_percent": sample.used_percent,
                }
                for sample in disks
            ],
            "networks": [
                {
                    "interface": sample.interface,
                    "rx_bytes": sample.rx_bytes,
                    "tx_bytes": sample.tx_bytes,
                    "rx_rate_bps": sample.rx_rate_bps,
                    "tx_rate_bps": sample.tx_rate_bps,
                }
                for sample in networks
            ],
        }
        return payload, current_counters(networks)

    # --- Ciclo --------------------------------------------------------------

    def tick(self) -> TickResult:
        now = self._clock()
        payload, counters = self.build_payload(now)
        credential = self._config.credential or ""

        sent = False
        spooled = False
        try:
            self._client.send_metrics(credential=credential, payload=payload)
            sent = True
            self._logger.info(
                "métricas enviadas",
                extra={
                    "disks": len(payload["disks"]),
                    "networks": len(payload["networks"]),
                },
            )
        except TransportError as exc:
            if exc.transient:
                self._spool.enqueue(payload)
                spooled = True
                self._logger.warning(
                    "envio falhou; métricas guardadas no buffer local",
                    extra={"status": exc.status, "motivo": str(exc)},
                )
            else:
                # Erro permanente: reenviar o mesmo payload não resolve (ex.: 422).
                self._logger.error(
                    "métricas rejeitadas pela central",
                    extra={"status": exc.status, "motivo": str(exc)},
                )

        save_state(self._config.state_file, timestamp=now, counters=counters)
        self._state = NetworkState(timestamp=now, counters=counters)

        flushed = self.flush_spool()

        heartbeat_ok = False
        try:
            self._client.heartbeat(
                credential=credential,
                sent_at=_iso_utc(now),
                agent_version=__version__,
                uptime_seconds=int(payload["host"]["uptime_seconds"]),
                hostname=None,
            )
            heartbeat_ok = True
        except TransportError as exc:
            self._logger.warning(
                "heartbeat falhou", extra={"status": exc.status, "motivo": str(exc)}
            )

        return TickResult(
            metrics_sent=sent,
            metrics_spooled=spooled,
            spool_flushed=flushed,
            heartbeat_ok=heartbeat_ok,
        )

    def flush_spool(self, limit: int = 10) -> int:
        flushed = 0
        for path in self._spool.pending()[:limit]:
            payload = self._spool.read(path)
            if payload is None:
                continue
            try:
                self._client.send_metrics(
                    credential=self._config.credential or "", payload=payload
                )
            except TransportError as exc:
                if exc.transient:
                    break
                # Payload inválido nunca vai passar: descartar para não travar a fila.
                self._spool.ack(path)
                self._logger.error(
                    "payload do buffer descartado (rejeição permanente)",
                    extra={"status": exc.status},
                )
                continue
            self._spool.ack(path)
            flushed += 1

        if flushed:
            self._logger.info("buffer local esvaziado", extra={"enviados": flushed})
        return flushed

    def run_forever(self, stop_event: threading.Event, *, max_ticks: int | None = None) -> None:
        self._logger.info(
            "agente iniciado",
            extra={
                "interval_seconds": self._config.interval_seconds,
                "server_id": self._config.server_id,
                "versao": __version__,
            },
        )
        next_at = self._clock()
        ticks = 0

        while not stop_event.is_set():
            self._spool.prune()
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - uma falha de coleta não pode parar o agente
                self._logger.exception("falha no ciclo de coleta")

            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break

            next_at += self._config.interval_seconds
            delay = next_at - self._clock()
            if delay < 0:
                # Se o ciclo demorou mais que o intervalo, não acumular atraso.
                next_at = self._clock()
                delay = 0
            stop_event.wait(delay)

        self._logger.info("agente encerrado")


def _iso_utc(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
