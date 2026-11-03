"""Primitivas de segurança: hash de senha, tokens opacos e comparação constante.

Decisões:
- Senhas com Argon2id (OWASP) via ``argon2-cffi`` — ver ADR-0003.
- Tokens de agente/provisionamento com 256 bits de entropia, persistidos apenas como
  SHA-256 + prefixo de identificação — ver ADR-0004.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

TOKEN_BYTES = 32
TOKEN_PREFIX_LENGTH = 12

# Parâmetros alinhados à recomendação OWASP (Argon2id: 19 MiB, t=2, p=1) com margem de
# segurança em memória para hardware de VPS.
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Gera o hash Argon2id da senha em texto claro."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verifica a senha sem lançar exceções e sem vazar a causa da falha."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def generate_token() -> str:
    """Token opaco com 256 bits de entropia, seguro para URL."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 hexadecimal do token. determinístico para permitir lookup indexado."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_prefix(token: str) -> str:
    """Prefixo exibível para identificar o token em auditoria sem revelar o segredo."""
    return token[:TOKEN_PREFIX_LENGTH]


def tokens_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


def new_id() -> str:
    """Identificador público de entidade (UUIDv4 em texto)."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Agora em UTC, *naive*, compatível com as colunas ``DATETIME`` do MySQL.

    O banco armazena sempre UTC (PRD §8.3); a conversão para America/Sao_Paulo é feita
    na camada de apresentação.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def utc_from_now(**delta: float) -> datetime:
    return utc_now() + timedelta(**delta)
