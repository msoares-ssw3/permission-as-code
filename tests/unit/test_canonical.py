"""Sessão 2: vetores CONGELADOS da spec 1.3 — se algum destes testes quebrar,
a serialização/hash mudou, e isso exige migração de cadeia (ou seja: não muda).
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.core.canonical import canonical, iso_utc, validar_payload
from src.core.chain import GENESIS, hash_evento

EVENTO = {
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "seq": 1,
    "tipo": "teste",
    "origem": "unit",
    "payload": {"b": 2, "a": 1, "texto": "ação"},
    "ts": "2026-01-01T00:00:00.000000+00:00",
}
CANONICO_ESPERADO = (
    '{"origem":"unit","payload":{"a":1,"b":2,"texto":"ação"},"seq":1,'
    '"tenant_id":"11111111-1111-1111-1111-111111111111","tipo":"teste",'
    '"ts":"2026-01-01T00:00:00.000000+00:00"}'
).encode()
HASH_ESPERADO = "9f97ce12238d298c7705a7d2ee582b2295218a222a4b3939329e81be8acc4bb8"


def test_vetor_congelado_canonical() -> None:
    assert canonical(EVENTO) == CANONICO_ESPERADO


def test_vetor_congelado_hash() -> None:
    assert hash_evento(GENESIS, canonical(EVENTO)) == HASH_ESPERADO


def test_canonical_ignora_campos_extras() -> None:
    com_extras = {**EVENTO, "id": "x", "prev_hash": "y", "hash": "z"}
    assert canonical(com_extras) == CANONICO_ESPERADO


def test_iso_utc_formato_fixo_e_conversao() -> None:
    em_utc = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    assert iso_utc(em_utc) == "2026-01-02T03:04:05.123456+00:00"
    em_sp = em_utc.astimezone(timezone(timedelta(hours=-3)))
    assert iso_utc(em_sp) == iso_utc(em_utc)
    with pytest.raises(ValueError, match="timezone-aware"):
        iso_utc(datetime(2026, 1, 1))


def test_validar_payload_recusa_float_em_qualquer_nivel() -> None:
    with pytest.raises(ValueError, match="float"):
        validar_payload({"valor": 1.5})
    with pytest.raises(ValueError, match="float"):
        validar_payload({"a": [{"b": [0.1]}]})


def test_validar_payload_aceita_json_sem_float() -> None:
    validar_payload({"i": 1, "s": "x", "b": True, "n": None, "l": [1, "2", {"k": 3}]})


def test_validar_payload_recusa_chave_nao_str_e_tipos_estranhos() -> None:
    with pytest.raises(ValueError, match="chaves"):
        validar_payload({1: "a"})
    with pytest.raises(ValueError, match="não serializável"):
        validar_payload({"s": {1, 2}})
