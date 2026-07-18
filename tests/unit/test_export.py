"""Sessão 4: geração e verificação do manifest v1 (spec 1.4) — sem banco."""

import pytest

from src.core import chain
from src.core.canonical import canonical
from src.core.events import Evento
from src.core.export import ALGORITMO, VERSAO, gerar_manifest, verificar_manifest

TENANT = "11111111-1111-1111-1111-111111111111"
GERADO_EM = "2026-01-01T00:00:10.000000+00:00"


def _cadeia_fabricada(n: int) -> list[Evento]:
    eventos = []
    prev = chain.GENESIS
    for seq in range(1, n + 1):
        ts = f"2026-01-01T00:00:{seq:02d}.000000+00:00"
        payload = {"n": seq}
        corpo = canonical(
            {
                "tenant_id": TENANT, "seq": seq, "tipo": "t", "origem": "teste",
                "payload": payload, "ts": ts,
            }
        )
        h = chain.hash_evento(prev, corpo)
        eventos.append(
            Evento(
                tenant_id=TENANT, seq=seq, id=f"id-{seq}", tipo="t", origem="teste",
                dedupe_key=None, payload=payload, ts=ts, prev_hash=prev, hash=h,
            )
        )
        prev = h
    return eventos


def test_gerar_manifest_forma_e_hash_final() -> None:
    eventos = _cadeia_fabricada(3)
    manifest = gerar_manifest(TENANT, eventos, GERADO_EM)
    assert manifest["versao"] == VERSAO
    assert manifest["algoritmo"] == ALGORITMO
    assert manifest["tenant"] == TENANT
    assert manifest["seq_de"] == 1
    assert manifest["seq_ate"] == 3
    assert manifest["hash_final"] == eventos[-1].hash
    assert [e["seq"] for e in manifest["eventos"]] == [1, 2, 3]
    verificar_manifest(manifest)


def test_export_vazio_recusado() -> None:
    with pytest.raises(ValueError):
        gerar_manifest(TENANT, [], "2026-01-01T00:00:00.000000+00:00")


def test_1_byte_flipado_no_payload_aponta_o_seq() -> None:
    manifest = gerar_manifest(TENANT, _cadeia_fabricada(3), GERADO_EM)
    manifest["eventos"][1]["payload"] = {"n": 999}
    with pytest.raises(chain.CadeiaInvalida, match="seq 2"):
        verificar_manifest(manifest)


def test_hash_final_adulterado_e_detectado() -> None:
    manifest = gerar_manifest(TENANT, _cadeia_fabricada(2), GERADO_EM)
    manifest["hash_final"] = "f" * 64
    with pytest.raises(chain.CadeiaInvalida, match="hash_final"):
        verificar_manifest(manifest)


def test_export_completo_sem_genesis_e_recusado() -> None:
    manifest = gerar_manifest(TENANT, _cadeia_fabricada(2), GERADO_EM)
    manifest["eventos"][0]["prev_hash"] = "a" * 64
    with pytest.raises(chain.CadeiaInvalida, match="genesis"):
        verificar_manifest(manifest)
