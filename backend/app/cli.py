"""CLI operacional da central.

Comandos:
    python -m app.cli check
    python -m app.cli wait-db --timeout 180
    python -m app.cli create-admin --email admin@exemplo.com --name "Administrador"

A senha do administrador **nunca** é aceita como argumento de linha de comando
(ficaria no histórico do shell). Ela é lida de ``GUARDIAN_ADMIN_PASSWORD`` (uso em
automação) ou digitada interativamente.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import time

from sqlalchemy import text

from app.core.config import ConfigurationError, get_settings
from app.core.enums import UserRole
from app.core.errors import APIError
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password, utc_now
from app.db.session import dispose_engine, ping_database, session_scope
from app.models.user import User
from app.services.auth import find_user_by_email
from app.services.schema import current_schema_revision

logger = get_logger("app.cli")
MIN_PASSWORD_LENGTH = 12


def _read_password() -> str:
    password = os.environ.get("GUARDIAN_ADMIN_PASSWORD")
    if password:
        return password
    if not sys.stdin.isatty():
        raise SystemExit(
            "Senha não fornecida: defina GUARDIAN_ADMIN_PASSWORD ou execute em um terminal."
        )
    first = getpass.getpass("Senha do administrador: ")
    second = getpass.getpass("Confirme a senha: ")
    if first != second:
        raise SystemExit("As senhas não conferem.")
    return first


def command_wait_db(timeout_seconds: int) -> int:
    """Aguarda o MySQL aceitar conexões (usado no boot dos containers)."""
    deadline = time.monotonic() + timeout_seconds
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        if ping_database():
            print(f"MySQL disponível após {attempt} tentativa(s).")
            return 0
        time.sleep(2)
    print(f"MySQL indisponível após {timeout_seconds}s.")
    return 1


def command_check() -> int:
    settings = get_settings()
    print(f"ambiente: {settings.app_env}")
    print(f"versão: {settings.deployment_version}")
    print(f"banco (host): {settings.database_url.split('@')[-1]}")
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
        print("conectividade MySQL: ok")
    except Exception as exc:  # noqa: BLE001
        print(f"conectividade MySQL: FALHA ({type(exc).__name__})")
        return 1
    revision = current_schema_revision()
    print(f"schema (alembic): {revision or 'não migrado'}")
    if revision is None:
        return 2
    return 0


def command_create_admin(email: str, name: str) -> int:
    password = _read_password()
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"A senha deve ter ao menos {MIN_PASSWORD_LENGTH} caracteres.")
    normalized = email.strip().lower()

    with session_scope() as session:
        if find_user_by_email(session, normalized) is not None:
            raise SystemExit("Já existe um usuário com este e-mail.")
        user = User(
            email=normalized,
            name=name.strip(),
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            is_active=True,
            created_at=utc_now(),
        )
        session.add(user)
        session.flush()
        user_id = user.id

    print(f"administrador criado: {normalized} (id={user_id})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="CLI do VPS Guardian")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Valida configuração e conectividade com o MySQL")

    wait_db = sub.add_parser("wait-db", help="Aguarda o MySQL ficar disponível")
    wait_db.add_argument("--timeout", type=int, default=180)

    admin = sub.add_parser("create-admin", help="Cria o administrador inicial")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        settings = get_settings()
    except ConfigurationError as exc:
        # Mensagem limpa: apenas nomes de variáveis, nunca valores (PRD §11).
        print(f"guardian: {exc.report()}", file=sys.stderr)
        return 2

    configure_logging(settings)

    try:
        if args.command == "check":
            return command_check()
        if args.command == "wait-db":
            return command_wait_db(args.timeout)
        if args.command == "create-admin":
            return command_create_admin(args.email, args.name)
    except APIError as exc:  # pragma: no cover - defensivo
        logger.error("cli_error", code=exc.code, detail=exc.message)
        return 1
    finally:
        dispose_engine()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
