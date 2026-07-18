"""Ports (interfaces) da plataforma — core nunca importa SDK de provider.

Adapters concretos vivem em src/adapters/; aqui só o contrato. Valores
monetários/quantidades são SEMPRE int na unidade mínima (guardrail 2).
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TransferenciaOnchain:
    tx: str
    de: str
    para: str
    valor: int  # unidade mínima do token (int, nunca float)
    token: str
    bloco: int


class ProviderOnchain(Protocol):
    """Fonte de transferências on-chain (indexer/webhook provider)."""

    def transferencias(self, desde_bloco: int = 0) -> list[TransferenciaOnchain]:
        """Transferências a partir do bloco dado, em ordem de bloco."""
        ...
