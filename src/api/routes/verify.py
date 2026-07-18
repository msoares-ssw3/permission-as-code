"""Rota pública de verificação de exports (manifest v1) — Sessão 4.

Roda a mesma verificação do verifier/verify.py standalone, server-side;
não exige API key — quem recebe um export de terceiro pode conferir aqui.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core import chain
from src.core.export import verificar_manifest

router = APIRouter()


class EventoManifest(BaseModel):
    seq: int
    tipo: str
    origem: str
    payload: dict[str, Any]
    ts: str
    prev_hash: str
    hash: str


class Manifest(BaseModel):
    versao: int
    tenant: str
    gerado_em: str
    seq_de: int
    seq_ate: int
    algoritmo: str
    hash_final: str
    eventos: list[EventoManifest]


@router.post("/verify")
def verificar(manifest: Manifest) -> dict[str, Any]:
    """200 com o veredito se a cadeia do export é íntegra; 422 apontando o seq."""
    try:
        verificar_manifest(manifest.model_dump())
    except chain.CadeiaInvalida as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
    return {"valido": True, "seq_de": manifest.seq_de, "seq_ate": manifest.seq_ate}
