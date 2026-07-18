"""Auth por API key: sha256 da chave casa com api_key_hash em core.tenants.

A conexão de aplicação (role sem bypass de RLS) é compartilhada entre a
autenticação e a rota via cache de dependências do FastAPI; o tenant é
fixado por transação dentro de chain.append/ler_cadeia (set_tenant).
"""

import hashlib
from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import Depends, Header, HTTPException

from src.shared.config import APP_DATABASE_URL


def conexao() -> Iterator[psycopg.Connection]:
    """Uma conexão de aplicação por requisição (fechada ao final)."""
    with psycopg.connect(APP_DATABASE_URL) as conn:
        yield conn


def tenant_autenticado(
    x_api_key: Annotated[str, Header()],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
) -> UUID:
    """Resolve a API key para o tenant dela; 401 se não existir."""
    chave_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    linha = conn.execute(
        "select id from core.tenants where api_key_hash = %s", (chave_hash,)
    ).fetchone()
    if linha is None:
        raise HTTPException(status_code=401, detail="API key inválida")
    return linha[0]
