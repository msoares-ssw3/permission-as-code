"""Webhook receiver on-chain: normaliza pra evento e avalia perímetro — Sessão 6."""

from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from src.api.auth import conexao, tenant_autenticado
from src.domain.ports import TransferenciaOnchain
from src.engines import perimeter

router = APIRouter()


class WebhookTransferencia(BaseModel):
    tx: str = Field(min_length=1)
    de: str = Field(min_length=1)
    para: str = Field(min_length=1)
    valor: int = Field(ge=0)
    token: str = Field(min_length=1)
    bloco: int = Field(ge=0)


@router.post("/webhooks/onchain")
def receber_transferencia(
    corpo: WebhookTransferencia,
    tenant_id: Annotated[UUID, Depends(tenant_autenticado)],
    conn: Annotated[psycopg.Connection, Depends(conexao)],
    response: Response,
) -> dict[str, Any]:
    """Transferência do provider vira evento; violação abre case. Idempotente por tx."""
    transf = TransferenciaOnchain(**corpo.model_dump())
    evento, criado, casos = perimeter.ingerir_transferencia(conn, tenant_id, transf)
    response.status_code = 201 if criado else 200
    return {"evento_seq": evento.seq, "criado": criado, "casos_abertos": casos}
