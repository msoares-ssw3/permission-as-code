"""Fluxo de casos com decisão humana obrigatória — Sessão 7.

Máquina de estados estrita: aberto → em_analise → decidido. Cada transição
atualiza core.cases E anexa evento case.* na cadeia, na mesma transação.
Decidir exige justificativa, decisão e autor humano (guardrail 6: IA nunca
decide) — e o check constraint da migration 004 garante isso também para
quem falar SQL direto com o banco.
"""

from typing import Any
from uuid import UUID

import psycopg

from src.adapters.pg import set_tenant
from src.core import chain
from src.core.events import Evento

DECISOES = ("procedente", "improcedente")

_CAMPOS = (
    "id, status, regra_id, regra_versao, evento_origem_seq,"
    " aberto_em, decidido_em, decidido_por, decisao, justificativa"
)


class CaseNaoEncontrado(Exception):
    """Case inexistente (ou de outro tenant — RLS não deixa ver)."""


class TransicaoInvalida(Exception):
    """Transição fora de aberto → em_analise → decidido."""


def iniciar_analise(
    conn: psycopg.Connection, tenant_id: UUID | str, case_id: str
) -> None:
    """aberto → em_analise, com evento case.em_analise na cadeia."""
    with conn.transaction():
        set_tenant(conn, tenant_id)
        linha = conn.execute(
            "update core.cases set status = 'em_analise'"
            " where id = %s and status = 'aberto' returning id",
            (case_id,),
        ).fetchone()
        if linha is None:
            _falhar_transicao(conn, case_id, esperado="aberto")
        chain.append(
            conn, tenant_id, "case.em_analise", "engine.cases", {"case_id": case_id}
        )


def decidir(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    case_id: str,
    decisao: str,
    justificativa: str,
    decidido_por: str,
) -> None:
    """em_analise → decidido; justificativa e autor humano são inegociáveis."""
    if decisao not in DECISOES:
        raise ValueError(f"decisão inválida: {decisao} (use {'/'.join(DECISOES)})")
    if not justificativa.strip():
        raise ValueError("decidir sem justificativa é impossível")
    if not decidido_por.strip():
        raise ValueError("decisão exige autor humano (decidido_por)")
    with conn.transaction():
        set_tenant(conn, tenant_id)
        linha = conn.execute(
            "update core.cases set status = 'decidido', decisao = %s,"
            " justificativa = %s, decidido_por = %s, decidido_em = now()"
            " where id = %s and status = 'em_analise' returning id",
            (decisao, justificativa, decidido_por, case_id),
        ).fetchone()
        if linha is None:
            _falhar_transicao(conn, case_id, esperado="em_analise")
        chain.append(
            conn, tenant_id, "case.decidido", "engine.cases",
            {
                "case_id": case_id, "decisao": decisao,
                "justificativa": justificativa, "decidido_por": decidido_por,
            },
        )


def _falhar_transicao(conn: psycopg.Connection, case_id: str, esperado: str) -> None:
    atual = conn.execute(
        "select status from core.cases where id = %s", (case_id,)
    ).fetchone()
    if atual is None:
        raise CaseNaoEncontrado(case_id)
    raise TransicaoInvalida(
        f"case {case_id} está '{atual[0]}', transição exige '{esperado}'"
    )


def listar(
    conn: psycopg.Connection, tenant_id: UUID | str, status: str | None = None
) -> list[dict[str, Any]]:
    """Cases do tenant (visão RLS), mais recentes primeiro."""
    with conn.transaction():
        set_tenant(conn, tenant_id)
        linhas = conn.execute(
            f"select {_CAMPOS} from core.cases"
            " where (%s::text is null or status = %s) order by aberto_em desc, id",
            (status, status),
        ).fetchall()
    return [_case_da_linha(linha) for linha in linhas]


def carregar(
    conn: psycopg.Connection, tenant_id: UUID | str, case_id: str
) -> dict[str, Any]:
    with conn.transaction():
        set_tenant(conn, tenant_id)
        linha = conn.execute(
            f"select {_CAMPOS} from core.cases where id = %s", (case_id,)
        ).fetchone()
    if linha is None:
        raise CaseNaoEncontrado(case_id)
    return _case_da_linha(linha)


def _case_da_linha(linha: tuple) -> dict[str, Any]:
    return {
        "id": str(linha[0]), "status": linha[1], "regra_id": linha[2],
        "regra_versao": linha[3], "evento_origem_seq": linha[4],
        "aberto_em": linha[5].isoformat(),
        "decidido_em": linha[6].isoformat() if linha[6] else None,
        "decidido_por": linha[7], "decisao": linha[8], "justificativa": linha[9],
    }


def trilha(
    conn: psycopg.Connection, tenant_id: UUID | str, case: dict[str, Any]
) -> list[Evento]:
    """Evento de origem + eventos case.* do case, em ordem de seq."""
    eventos = chain.ler_cadeia(conn, tenant_id)
    return [
        evento for evento in eventos
        if evento.seq == case["evento_origem_seq"]
        or evento.payload.get("case_id") == case["id"]
    ]
