"""Rotas de ingestão e leitura de eventos."""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from src.api.auth import conexao, tenant_autenticado
from src.core import chain

router = APIRouter()


class NovoEvento(BaseModel):
    tipo: str = Field(min_length=1)
    origem: str = Field(min_length=1)
    payload: dict[str, Any]
    dedupe_key: str | None = None


@router.post("/events")
def criar_evento(
    corpo: NovoEvento,
    tenant_id: Annotated[UUID, Depends(tenant_autenticado)],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
    response: Response,
) -> dict[str, Any]:
    """Anexa à cadeia do tenant; replay do mesmo dedupe_key devolve 200."""
    try:
        evento, criado = chain.append(
            conn, tenant_id, corpo.tipo, corpo.origem, corpo.payload, corpo.dedupe_key
        )
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
    response.status_code = 201 if criado else 200
    return asdict(evento)


@router.get("/events")
def listar_eventos(
    tenant_id: Annotated[UUID, Depends(tenant_autenticado)],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
    desde_seq: Annotated[int, Query(ge=1)] = 1,
    limite: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> dict[str, Any]:
    """Eventos do tenant em ordem de seq, paginados por desde_seq/limite."""
    eventos = chain.ler_cadeia(conn, tenant_id, desde_seq=desde_seq, limite=limite)
    return {"eventos": [asdict(evento) for evento in eventos]}
