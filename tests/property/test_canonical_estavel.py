"""Propriedade: qualquer payload válido (JSON sem float) serializa canônico estável."""

import json
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from src.core.canonical import canonical

texto = st.text(st.characters(codec="utf-8", exclude_characters="\x00"), max_size=20)
escalar = st.one_of(
    st.none(), st.booleans(), st.integers(min_value=-(2**53), max_value=2**53), texto
)
payloads = st.dictionaries(
    texto,
    st.recursive(
        escalar,
        lambda filhos: st.lists(filhos, max_size=4)
        | st.dictionaries(texto, filhos, max_size=4),
        max_leaves=12,
    ),
    max_size=6,
)


def _evento(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "seq": 1,
        "tipo": "t",
        "origem": "o",
        "payload": payload,
        "ts": "2026-01-01T00:00:00.000000+00:00",
    }


@given(payloads)
def test_canonical_repetivel(payload: dict[str, Any]) -> None:
    assert canonical(_evento(payload)) == canonical(_evento(payload))


@given(payloads)
def test_canonical_sobrevive_round_trip_json(payload: dict[str, Any]) -> None:
    corpo = canonical(_evento(payload))
    reparsado = json.loads(corpo.decode("utf-8"))
    assert canonical(reparsado) == corpo


@given(payloads)
def test_canonical_ignora_ordem_de_insercao(payload: dict[str, Any]) -> None:
    invertido = dict(reversed(list(payload.items())))
    assert canonical(_evento(invertido)) == canonical(_evento(payload))
