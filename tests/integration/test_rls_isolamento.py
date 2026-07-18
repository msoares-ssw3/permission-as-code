"""Sessão 1(b,c): isolamento por tenant via RLS, valendo até para o owner."""

from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from src.adapters.pg import set_tenant


def test_tenant_a_nao_ve_eventos_do_b(
    app_conn: psycopg.Connection, tenants: dict[str, UUID]
) -> None:
    set_tenant(app_conn, tenants["a"])
    linhas = app_conn.execute("select tenant_id from core.events").fetchall()
    vistos = {linha[0] for linha in linhas}
    assert vistos == {tenants["a"]}
    assert tenants["b"] not in vistos


def test_insert_para_outro_tenant_recusado(
    app_conn: psycopg.Connection, tenants: dict[str, UUID]
) -> None:
    set_tenant(app_conn, tenants["a"])
    with pytest.raises(
        psycopg.errors.InsufficientPrivilege, match="row-level security"
    ):
        app_conn.execute(
            "insert into core.events"
            " (tenant_id, seq, tipo, origem, payload, prev_hash, hash)"
            " values (%s, 2, 'x', 'x', %s, %s, %s)",
            (tenants["b"], Jsonb({}), "0" * 64, "1" * 64),
        )


def test_force_rls_vale_para_o_owner(
    app_conn: psycopg.Connection, tenants: dict[str, UUID]
) -> None:
    dono = app_conn.execute(
        "select relowner::regrole::text from pg_class"
        " where oid = 'core.events'::regclass"
    ).fetchone()
    usuario = app_conn.execute("select current_user").fetchone()
    assert dono is not None and usuario is not None
    assert dono[0] == usuario[0] == "simbios3_app"
    set_tenant(app_conn, tenants["a"])
    linhas = app_conn.execute("select tenant_id from core.events").fetchall()
    assert {linha[0] for linha in linhas} == {tenants["a"]}
