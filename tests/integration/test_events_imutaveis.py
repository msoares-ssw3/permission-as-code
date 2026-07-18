"""Sessão 1(a): adulteração falha no BANCO, não na aplicação.

UPDATE e DELETE em core.events levantam a exceção do trigger para qualquer
role — inclusive superuser, que ignora RLS mas não escapa do trigger.
"""

from uuid import UUID

import psycopg
import pytest

from src.adapters.pg import set_tenant


def test_update_recusado_pelo_banco(
    admin_conn: psycopg.Connection, tenants: dict[str, UUID]
) -> None:
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        admin_conn.execute(
            "update core.events set payload = '{}' where tenant_id = %s",
            (tenants["a"],),
        )


def test_delete_recusado_pelo_banco(
    admin_conn: psycopg.Connection, tenants: dict[str, UUID]
) -> None:
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        admin_conn.execute(
            "delete from core.events where tenant_id = %s", (tenants["a"],)
        )


def test_update_recusado_tambem_para_role_de_app(
    app_conn: psycopg.Connection, tenants: dict[str, UUID]
) -> None:
    set_tenant(app_conn, tenants["a"])
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        app_conn.execute("update core.events set origem = 'x' where seq = 1")
