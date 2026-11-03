"""Leitura da revisão de schema aplicada (Alembic) sem expor dados de conexão."""

from __future__ import annotations

from sqlalchemy import text

from app.db.session import get_engine


def current_schema_revision() -> str | None:
    try:
        with get_engine().connect() as connection:
            value = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        return str(value) if value else None
    except Exception:  # noqa: BLE001 - tabela ausente significa banco ainda não migrado
        return None
