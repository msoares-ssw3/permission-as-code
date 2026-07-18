"""Watchlist como projeção do log — Sessão 5.

Toda mutação vira evento na cadeia (watchlist.adicionado / watchlist.removido)
e a tabela core.watchlist é atualizada NA MESMA transação; o estado atual é
sempre reconstruível do zero a partir dos eventos (rebuild). Remover apaga a
linha da projeção, mas o log imutável guarda a história completa.
"""

from uuid import UUID

import psycopg

from src.adapters.pg import set_tenant
from src.core import chain
from src.core.events import Evento

TIPO_ADICIONADO = "watchlist.adicionado"
TIPO_REMOVIDO = "watchlist.removido"
ORIGEM = "api.watchlist"


def adicionar(
    conn: psycopg.Connection, tenant_id: UUID | str, endereco: str, motivo: str
) -> Evento:
    """Evento watchlist.adicionado + upsert na projeção, mesma transação."""
    with conn.transaction():
        evento, _ = chain.append(
            conn, tenant_id, TIPO_ADICIONADO, ORIGEM,
            {"endereco": endereco, "motivo": motivo},
        )
        conn.execute(
            "insert into core.watchlist (tenant_id, endereco, motivo)"
            " values (%s, %s, %s)"
            " on conflict (tenant_id, endereco) do update set motivo = excluded.motivo",
            (str(tenant_id), endereco, motivo),
        )
    return evento


def remover(conn: psycopg.Connection, tenant_id: UUID | str, endereco: str) -> Evento:
    """Evento watchlist.removido + delete na projeção, mesma transação."""
    with conn.transaction():
        evento, _ = chain.append(
            conn, tenant_id, TIPO_REMOVIDO, ORIGEM, {"endereco": endereco}
        )
        conn.execute(
            "delete from core.watchlist where tenant_id = %s and endereco = %s",
            (str(tenant_id), endereco),
        )
    return evento


def listar(conn: psycopg.Connection, tenant_id: UUID | str) -> list[dict[str, str]]:
    """Entradas atuais da watchlist do tenant (visão RLS), ordem estável."""
    with conn.transaction():
        set_tenant(conn, tenant_id)
        linhas = conn.execute(
            "select endereco, motivo from core.watchlist"
            " where tenant_id = %s order by endereco",
            (str(tenant_id),),
        ).fetchall()
    return [{"endereco": linha[0], "motivo": linha[1]} for linha in linhas]


def enderecos(conn: psycopg.Connection, tenant_id: UUID | str) -> set[str]:
    """Só os endereços — o que o avaliador de perímetro consome."""
    return {item["endereco"] for item in listar(conn, tenant_id)}


def rebuild(conn: psycopg.Connection, tenant_id: UUID | str) -> None:
    """Apaga a projeção e reaplica os eventos watchlist.* do log, em ordem."""
    with conn.transaction():
        set_tenant(conn, tenant_id)
        conn.execute(
            "delete from core.watchlist where tenant_id = %s", (str(tenant_id),)
        )
        for evento in chain.ler_cadeia(conn, tenant_id):
            _aplicar(conn, str(tenant_id), evento)


def _aplicar(conn: psycopg.Connection, tid: str, evento: Evento) -> None:
    if evento.tipo == TIPO_ADICIONADO:
        conn.execute(
            "insert into core.watchlist (tenant_id, endereco, motivo)"
            " values (%s, %s, %s)"
            " on conflict (tenant_id, endereco) do update set motivo = excluded.motivo",
            (tid, evento.payload["endereco"], evento.payload["motivo"]),
        )
    elif evento.tipo == TIPO_REMOVIDO:
        conn.execute(
            "delete from core.watchlist where tenant_id = %s and endereco = %s",
            (tid, evento.payload["endereco"]),
        )
