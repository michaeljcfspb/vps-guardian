"""Ponto de entrada do agente VPS Guardian.

O agente **não** executa comandos recebidos da central e não escreve em nada fora de
seus próprios diretórios (spool, estado e log). Todas as conexões são de saída.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import signal
import sys
import threading
import time
from dataclasses import replace

from guardian_agent import __version__
from guardian_agent.config import DEFAULT_CONFIG_PATH, AgentConfig, ConfigError
from guardian_agent.logging_setup import register_secret, setup_logging
from guardian_agent.runner import AgentRunner
from guardian_agent.transport import CentralClient, TransportError


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="guardian-agent",
        description="Agente de coleta do VPS Guardian (somente leitura e envio de saída).",
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="caminho do agent.json")
    parser.add_argument("--once", action="store_true", help="executa um único ciclo e sai")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="coleta e imprime o payload sem enviar nada (diagnóstico)",
    )
    parser.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING, ERROR")
    parser.add_argument("--version", action="store_true", help="mostra a versão e sai")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.version:
        print(f"guardian-agent {__version__}")
        return 0

    try:
        config = AgentConfig.load(args.config)
    except ConfigError as exc:
        print(f"configuração inválida: {exc}", file=sys.stderr)
        return 2

    if args.log_level:
        config = replace(config, log_level=args.log_level.upper())

    logger = setup_logging(config.log_level, config.log_file)
    register_secret(config.credential)
    register_secret(config.provisioning_token)

    client = CentralClient(
        config.api_url,
        timeout=float(config.request_timeout_seconds),
        verify_tls=config.verify_tls,
    )
    runner = AgentRunner(
        config,
        client,
        config_path=args.config,
        logger=logger,
    )

    if args.dry_run:
        payload, _counters = runner.build_payload(time.time())
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    try:
        runner.ensure_registered()
    except (ConfigError, TransportError) as exc:
        logger.error(
            "registro do agente falhou",
            extra={"status": getattr(exc, "status", None), "motivo": str(exc)},
        )
        return 1

    if args.once:
        result = runner.tick()
        logger.info(
            "ciclo único concluído",
            extra={
                "metrics_sent": result.metrics_sent,
                "metrics_spooled": result.metrics_spooled,
                "heartbeat_ok": result.heartbeat_ok,
            },
        )
        return 0 if (result.metrics_sent or result.metrics_spooled) else 1

    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("sinal recebido; encerrando", extra={"signal": signum})
        stop_event.set()

    for signum in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(ValueError, OSError):
            signal.signal(signum, _handle_signal)

    runner.run_forever(stop_event)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
