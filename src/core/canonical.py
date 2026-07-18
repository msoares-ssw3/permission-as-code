"""Serialização canônica de eventos — spec 1.3, CONGELADA após a Sessão 2.

canonical(e) = json.dumps({6 campos}, sort_keys=True, separators=(",", ":"),
ensure_ascii=False).encode("utf-8"). Mesmo evento, mesmo byte, sempre.
"""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

CAMPOS_CANONICOS = ("tenant_id", "seq", "tipo", "origem", "payload", "ts")


def canonical(evento: Mapping[str, Any]) -> bytes:
    """Bytes canônicos do evento (só os 6 campos da spec; extras são ignorados)."""
    recorte = {campo: evento[campo] for campo in CAMPOS_CANONICOS}
    return json.dumps(
        recorte, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def iso_utc(instante: datetime) -> str:
    """Formata o ts persistido: ISO-8601 UTC com microssegundos fixos."""
    if instante.tzinfo is None:
        raise ValueError("ts precisa ser timezone-aware")
    return instante.astimezone(UTC).isoformat(timespec="microseconds")


def validar_payload(payload: object) -> None:
    """Recusa o que quebraria o recomputo byte a byte a partir do jsonb.

    Float é proibido (o banco re-renderiza números não-inteiros); chaves
    precisam ser str; qualquer tipo fora de JSON é recusado na entrada.
    """
    if isinstance(payload, bool) or payload is None:
        return
    if isinstance(payload, float):
        raise ValueError(
            "float é proibido em payload (determinismo; dinheiro é int centavos)"
        )
    if isinstance(payload, int | str):
        return
    if isinstance(payload, list):
        for item in payload:
            validar_payload(item)
        return
    if isinstance(payload, dict):
        for chave, valor in payload.items():
            if not isinstance(chave, str):
                raise ValueError("chaves de payload precisam ser str")
            validar_payload(valor)
        return
    raise ValueError(f"tipo não serializável em payload: {type(payload).__name__}")
