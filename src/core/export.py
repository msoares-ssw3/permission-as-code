"""Geração e verificação do manifest de export (manifest v1 — spec 1.4).

Reaproveita a cadeia de hash congelada (core.chain / core.canonical); a
verificação aqui é a mesma que a rota pública POST /verify expõe. O
verificador standalone (verifier/verify.py) reimplementa esta lógica em
stdlib pura porque não pode importar src/ — requisito de produto.
"""

from collections.abc import Sequence
from typing import Any

from src.core import chain
from src.core.canonical import canonical
from src.core.events import Evento

VERSAO = 1
ALGORITMO = "sha256(prev_bytes + sha256(canonical))"


def gerar_manifest(
    tenant_id: str, eventos: Sequence[Evento], gerado_em: str
) -> dict[str, Any]:
    """Manifest v1 (spec 1.4) da faixa de eventos fornecida."""
    if not eventos:
        raise ValueError("export vazio: não há eventos para exportar")
    return {
        "versao": VERSAO,
        "tenant": tenant_id,
        "gerado_em": gerado_em,
        "seq_de": eventos[0].seq,
        "seq_ate": eventos[-1].seq,
        "algoritmo": ALGORITMO,
        "hash_final": eventos[-1].hash,
        "eventos": [_evento_no_manifest(evento) for evento in eventos],
    }


def _evento_no_manifest(evento: Evento) -> dict[str, Any]:
    return {
        "seq": evento.seq,
        "tipo": evento.tipo,
        "origem": evento.origem,
        "payload": evento.payload,
        "ts": evento.ts,
        "prev_hash": evento.prev_hash,
        "hash": evento.hash,
    }


def verificar_manifest(manifest: dict[str, Any]) -> None:
    """Recomputa a cadeia do export; levanta CadeiaInvalida apontando o seq.

    Ao contrário de chain.verificar (que assume recompute a partir do
    genesis), aqui a faixa pode começar em qualquer seq_de — o prev_hash
    do primeiro evento do export é aceito como dado, não recalculado.
    """
    if manifest["versao"] != VERSAO:
        raise chain.CadeiaInvalida(
            f"versão de manifest não suportada: {manifest['versao']}"
        )
    eventos = manifest["eventos"]
    if not eventos:
        raise chain.CadeiaInvalida("export sem eventos")
    tenant_id = manifest["tenant"]
    prev = eventos[0]["prev_hash"]
    esperado = manifest["seq_de"]
    if esperado == 1 and prev != chain.GENESIS:
        raise chain.CadeiaInvalida("export completo (seq_de=1) não começa no genesis")
    for evento in eventos:
        if evento["seq"] != esperado:
            raise chain.CadeiaInvalida(
                f"buraco na cadeia: esperado seq {esperado}, veio {evento['seq']}"
            )
        if evento["prev_hash"] != prev:
            raise chain.CadeiaInvalida(f"prev_hash divergente no seq {evento['seq']}")
        corpo = canonical({"tenant_id": tenant_id, **evento})
        if chain.hash_evento(prev, corpo) != evento["hash"]:
            raise chain.CadeiaInvalida(f"hash divergente no seq {evento['seq']}")
        prev = evento["hash"]
        esperado += 1
    if prev != manifest["hash_final"]:
        raise chain.CadeiaInvalida("hash_final do manifest não bate com o último elo")
    if manifest["seq_ate"] != eventos[-1]["seq"]:
        raise chain.CadeiaInvalida("seq_ate do manifest não bate com o último evento")
