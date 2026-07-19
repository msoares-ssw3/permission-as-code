"""Rotas de casos: listagem, trilha e transições com decisão humana — Sessão 7."""

from dataclasses import asdict
from typing import Annotated, Any, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import conexao, tenant_autenticado
from src.engines import cases_flow

router = APIRouter()


class Decisao(BaseModel):
    decisao: Literal["procedente", "improcedente"]
    justificativa: str = Field(min_length=1)
    decidido_por: str = Field(min_length=1)


@router.get("/cases")
def listar(
    tenant_id: Annotated[UUID, Depends(tenant_autenticado)],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
    status: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    return {"cases": cases_flow.listar(conn, tenant_id, status)}


@router.get("/cases/{case_id}")
def detalhar(
    case_id: str,
    tenant_id: Annotated[UUID, Depends(tenant_autenticado)],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
) -> dict[str, Any]:
    case = _ou_404(lambda: cases_flow.carregar(conn, tenant_id, case_id))
    eventos = cases_flow.trilha(conn, tenant_id, case)
    return {"case": case, "trilha": [asdict(evento) for evento in eventos]}


@router.post("/cases/{case_id}/analisar")
def analisar(
    case_id: str,
    tenant_id: Annotated[UUID, Depends(tenant_autenticado)],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
) -> dict[str, Any]:
    _ou_404(lambda: cases_flow.iniciar_analise(conn, tenant_id, case_id))
    return {"case_id": case_id, "status": "em_analise"}


@router.post("/cases/{case_id}/decidir")
def decidir(
    case_id: str,
    corpo: Decisao,
    tenant_id: Annotated[UUID, Depends(tenant_autenticado)],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
) -> dict[str, Any]:
    try:
        _ou_404(
            lambda: cases_flow.decidir(
                conn, tenant_id, case_id,
                corpo.decisao, corpo.justificativa, corpo.decidido_por,
            )
        )
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
    return {"case_id": case_id, "status": "decidido"}


def _ou_404(acao: Any) -> Any:
    try:
        return acao()
    except cases_flow.CaseNaoEncontrado as erro:
        detalhe = f"case não encontrado: {erro}"
        raise HTTPException(status_code=404, detail=detalhe) from erro
    except cases_flow.TransicaoInvalida as erro:
        raise HTTPException(status_code=409, detail=str(erro)) from erro
