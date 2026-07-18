"""Verificador standalone de exports (manifest v1 — spec 1.3/1.4).

Requisito de produto: stdlib pura (json + hashlib, zero deps), executável em
máquina limpa com `python verify.py export.json` — não importa src/ de
propósito, mesmo que isso duplique a serialização canônica e a cadeia de
hash já congeladas em src/core/canonical.py e src/core/chain.py.
"""

import json
import sys
from hashlib import sha256
from typing import Any

GENESIS = "0" * 64
ALGORITMO = "sha256(prev_bytes + sha256(canonical))"
CAMPOS_CANONICOS = ("tenant_id", "seq", "tipo", "origem", "payload", "ts")


class CadeiaInvalida(Exception):
    """A cadeia do export não bate com o recomputado — adulteração ou bug."""


def canonical(evento: dict[str, Any]) -> bytes:
    """Bytes canônicos do evento — mesma spec 1.3 de src/core/canonical.py."""
    recorte = {campo: evento[campo] for campo in CAMPOS_CANONICOS}
    return json.dumps(
        recorte, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def hash_evento(prev_hash: str, corpo: bytes) -> str:
    """Elo da cadeia, exatamente como na spec 1.3."""
    interno = sha256(corpo).digest()
    return sha256(bytes.fromhex(prev_hash) + interno).hexdigest()


def verificar_manifest(manifest: dict[str, Any]) -> None:
    """Recomputa a cadeia do export; levanta CadeiaInvalida apontando o seq."""
    eventos = manifest["eventos"]
    if not eventos:
        raise CadeiaInvalida("export sem eventos")
    tenant_id = manifest["tenant"]
    prev = eventos[0]["prev_hash"]
    esperado = manifest["seq_de"]
    if esperado == 1 and prev != GENESIS:
        raise CadeiaInvalida("export completo (seq_de=1) não começa no genesis")
    for evento in eventos:
        if evento["seq"] != esperado:
            raise CadeiaInvalida(
                f"buraco na cadeia: esperado seq {esperado}, veio {evento['seq']}"
            )
        if evento["prev_hash"] != prev:
            raise CadeiaInvalida(f"prev_hash divergente no seq {evento['seq']}")
        corpo = canonical({"tenant_id": tenant_id, **evento})
        if hash_evento(prev, corpo) != evento["hash"]:
            raise CadeiaInvalida(f"hash divergente no seq {evento['seq']}")
        prev = evento["hash"]
        esperado += 1
    if prev != manifest["hash_final"]:
        raise CadeiaInvalida("hash_final do manifest não bate com o último elo")
    if manifest["seq_ate"] != eventos[-1]["seq"]:
        raise CadeiaInvalida("seq_ate do manifest não bate com o último evento")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("uso: python verify.py export.json", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as arquivo:
        manifest = json.load(arquivo)
    try:
        verificar_manifest(manifest)
    except CadeiaInvalida as erro:
        print(f"INVÁLIDO: {erro}")
        return 1
    print(
        f"OK: seq {manifest['seq_de']}..{manifest['seq_ate']} íntegro, "
        f"hash_final={manifest['hash_final']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
