"""Sessão 2: genesis, encadeamento, dedupe e formato do ts persistido."""

import re
from uuid import UUID

import psycopg
import pytest

from src.core import chain


def test_genesis_e_encadeamento(
    app_conn: psycopg.Connection, tenant_novo: UUID
) -> None:
    e1, criado1 = chain.append(app_conn, tenant_novo, "t", "s2", {"n": 1})
    e2, criado2 = chain.append(app_conn, tenant_novo, "t", "s2", {"n": 2})
    assert criado1 and criado2
    assert e1.seq == 1 and e1.prev_hash == chain.GENESIS
    assert e2.seq == 2 and e2.prev_hash == e1.hash
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00", e1.ts)


def test_dedupe_replay_nao_duplica(
    app_conn: psycopg.Connection, admin_conn: psycopg.Connection, tenant_novo: UUID
) -> None:
    a, criado_a = chain.append(app_conn, tenant_novo, "t", "s2", {"x": 1}, "k1")
    b, criado_b = chain.append(app_conn, tenant_novo, "t", "s2", {"x": 1}, "k1")
    assert criado_a and not criado_b
    assert (a.seq, a.hash, a.id) == (b.seq, b.hash, b.id)
    total = admin_conn.execute(
        "select count(*) from core.events where tenant_id = %s", (tenant_novo,)
    ).fetchone()
    assert total is not None and total[0] == 1


def test_float_no_payload_e_recusado(
    app_conn: psycopg.Connection, tenant_novo: UUID
) -> None:
    with pytest.raises(ValueError, match="float"):
        chain.append(app_conn, tenant_novo, "t", "s2", {"valor": 1.5})
