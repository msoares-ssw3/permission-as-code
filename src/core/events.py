"""Modelo do evento imutável (a forma que circula fora do banco)."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Evento:
    tenant_id: str
    seq: int
    id: str
    tipo: str
    origem: str
    dedupe_key: str | None
    payload: dict[str, Any]
    ts: str  # ISO-8601 UTC, forma canônica do valor persistido
    prev_hash: str
    hash: str
