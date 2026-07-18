"""Fixtures de integração: Postgres real, tenants novos por rodada, sem mocks.

Eventos são append-only — em vez de limpar tabelas, cada rodada cria tenants
próprios (uuid novo) e os testes só enxergam o que a RLS permite.
"""

import hashlib
from collections.abc import Iterator
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from src.shared.config import APP_DATABASE_URL, DATABASE_URL

GENESIS = "0" * 64


@pytest.fixture(scope="session")
def tenants() -> dict[str, UUID]:
    """Cria os tenants A e B, cada um com um evento seq=1 (hashes dummy — S2)."""
    with psycopg.connect(DATABASE_URL) as conn:
        ids: dict[str, UUID] = {}
        for nome in ("a", "b"):
            api_key_hash = hashlib.sha256(f"chave-{nome}".encode()).hexdigest()
            linha = conn.execute(
                "insert into core.tenants (nome, api_key_hash)"
                " values (%s, %s) returning id",
                (f"tenant-{nome}", api_key_hash),
            ).fetchone()
            assert linha is not None
            ids[nome] = linha[0]
            conn.execute(
                "insert into core.events"
                " (tenant_id, seq, tipo, origem, payload, prev_hash, hash)"
                " values (%s, 1, 'teste', 'fixture', %s, %s, %s)",
                (ids[nome], Jsonb({"fixture": nome}), GENESIS, "f" * 64),
            )
        conn.commit()
    return ids


@pytest.fixture
def tenant_novo() -> UUID:
    """Tenant limpo, sem eventos — para testes de cadeia (genesis, dedupe, carga)."""
    with psycopg.connect(DATABASE_URL) as conn:
        linha = conn.execute(
            "insert into core.tenants (nome, api_key_hash)"
            " values ('tenant-s2', 'x') returning id"
        ).fetchone()
        assert linha is not None
        conn.commit()
    return linha[0]


@pytest.fixture
def admin_conn() -> Iterator[psycopg.Connection]:
    """Conexão de sistema (superuser): bypass de RLS explícito e justificado."""
    with psycopg.connect(DATABASE_URL) as conn:
        yield conn
        conn.rollback()


@pytest.fixture
def app_conn() -> Iterator[psycopg.Connection]:
    """Conexão de aplicação: role não-superuser, dono de core.events."""
    with psycopg.connect(APP_DATABASE_URL) as conn:
        yield conn
        conn.rollback()
