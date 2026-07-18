"""Acesso Postgres (psycopg, SQL direto).

Convenção de acesso: toda conexão de aplicação executa
`set local app.tenant_id = '<uuid>'` no início da transação (via set_tenant);
jobs de sistema usam role própria com bypass explícito e justificado.
"""

from uuid import UUID

import psycopg


def set_tenant(conn: psycopg.Connection, tenant_id: UUID | str) -> None:
    """Fixa o tenant da transação atual (SET LOCAL via set_config)."""
    conn.execute("select set_config('app.tenant_id', %s, true)", (str(tenant_id),))
