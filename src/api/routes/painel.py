"""Painel read-only de casos e trilha — Sessão 7 (FastAPI + HTML de stdlib).

HTML gerado com html.escape + f-strings (sem jinja2 — dep nova exigiria
aprovação, CLAUDE.md). Auth por `?chave=` (a API key do tenant) porque é
painel de demo local navegável; produção troca por auth de sessão de verdade.
"""

import hashlib
import html
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from src.api.auth import conexao
from src.core import chain
from src.engines import cases_flow

router = APIRouter()

_ESTILO = (
    "body{font-family:sans-serif;margin:2rem;max-width:70rem}"
    "table{border-collapse:collapse;width:100%;margin-bottom:2rem}"
    "th,td{border:1px solid #ccc;padding:.4rem .6rem;text-align:left;"
    "font-size:.9rem}th{background:#f2f2f2}"
    "code{font-size:.8rem}"
)


@router.get("/painel", response_class=HTMLResponse)
def painel(
    chave: Annotated[str, Query(min_length=1)],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
) -> str:
    tenant_id = _tenant_da_chave(conn, chave)
    cases = cases_flow.listar(conn, tenant_id)
    eventos = chain.ler_cadeia(conn, tenant_id)
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>simbios3 · painel</title><style>{_ESTILO}</style></head><body>"
        f"<h1>Guard — casos do tenant</h1>"
        f"{_tabela_cases(cases)}"
        f"<h2>Trilha (cadeia de eventos)</h2>"
        f"{_tabela_eventos(eventos)}"
        f"</body></html>"
    )


def _tenant_da_chave(conn: psycopg.Connection, chave: str) -> Any:
    chave_hash = hashlib.sha256(chave.encode()).hexdigest()
    linha = conn.execute(
        "select id from core.tenants where api_key_hash = %s", (chave_hash,)
    ).fetchone()
    if linha is None:
        raise HTTPException(status_code=401, detail="chave inválida")
    return linha[0]


def _tabela_cases(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return "<p>Nenhum case.</p>"
    linhas = "".join(
        "<tr>"
        f"<td><code>{html.escape(c['id'])}</code></td>"
        f"<td>{html.escape(c['status'])}</td>"
        f"<td>{html.escape(c['regra_id'])} v{c['regra_versao']}</td>"
        f"<td>{c['evento_origem_seq']}</td>"
        f"<td>{html.escape(c['decidido_por'] or '—')}</td>"
        f"<td>{html.escape(c['decisao'] or '—')}</td>"
        f"<td>{html.escape(c['justificativa'] or '—')}</td>"
        "</tr>"
        for c in cases
    )
    return (
        "<table><tr><th>case</th><th>status</th><th>regra</th><th>evento origem</th>"
        "<th>decidido por</th><th>decisão</th><th>justificativa</th></tr>"
        f"{linhas}</table>"
    )


def _tabela_eventos(eventos: list[Any]) -> str:
    linhas = "".join(
        "<tr>"
        f"<td>{evento.seq}</td>"
        f"<td>{html.escape(evento.tipo)}</td>"
        f"<td>{html.escape(evento.origem)}</td>"
        f"<td>{html.escape(evento.ts)}</td>"
        f"<td><code>{html.escape(evento.hash[:16])}…</code></td>"
        "</tr>"
        for evento in eventos
    )
    return (
        "<table><tr><th>seq</th><th>tipo</th><th>origem</th><th>ts</th>"
        f"<th>hash</th></tr>{linhas}</table>"
    )
