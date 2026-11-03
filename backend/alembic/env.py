"""Ambiente de migrations do Alembic (MySQL, URL via variável de ambiente)."""

from __future__ import annotations

import logging
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Garante que o pacote `app` seja importável quando o Alembic roda do diretório backend/.
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.config import get_settings  # noqa: E402
from app.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

logger = logging.getLogger("alembic.env")

settings = get_settings()
# O ConfigParser do Alembic interpola '%': escapar para URLs com senha codificada.
config.set_main_option("sqlalchemy.url", settings.effective_database_url.replace("%", "%%"))

target_metadata = Base.metadata


def _include_object(object_, name, type_, reflected, compare_to) -> bool:  # noqa: ANN001
    """Nunca gerar diff para tabelas internas do Alembic/MySQL."""
    return not (type_ == "table" and name in {"alembic_version"})


def run_migrations_offline() -> None:
    context.configure(
        url=settings.effective_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=_include_object,
            render_as_batch=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
