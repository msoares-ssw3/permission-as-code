"""Rotas da watchlist de endereços por tenant — Sessão 5."""

from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.auth import conexao, tenant_autenticado
from src.projections import watchlist

router = APIRouter()


class NovaEntrada(BaseModel):
    endereco: str = Field(min_length=1)
    motivo: str = Field(min_length=1)


@router.post("/watchlist", status_code=201)
def adicionar(
    corpo: NovaEntrada,
    tenant_id: Annotated[UUID, Depends(tenant_autenticado)],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
) -> dict[str, Any]:
    evento = watchlist.adicionar(conn, tenant_id, corpo.endereco, corpo.motivo)
    return {"endereco": corpo.endereco, "evento_seq": evento.seq}


@router.get("/watchlist")
def listar(
    tenant_id: Annotated[UUID, Depends(tenant_autenticado)],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
) -> dict[str, Any]:
    return {"entradas": watchlist.listar(conn, tenant_id)}


@router.delete("/watchlist/{endereco}")
def remover(
    endereco: str,
    tenant_id: Annotated[UUID, Depends(tenant_autenticado)],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
) -> dict[str, Any]:
    evento = watchlist.remover(conn, tenant_id, endereco)
    return {"endereco": endereco, "evento_seq": evento.seq}
