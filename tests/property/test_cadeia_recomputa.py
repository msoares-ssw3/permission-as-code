"""Propriedade: recomputar a cadeia inteira a partir do banco bate byte a byte."""

import dataclasses
from typing import Any
from uuid import UUID

import psycopg
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.core import chain
from src.shared.config import APP_DATABASE_URL, DATABASE_URL

texto = st.text(st.characters(codec="utf-8", exclude_characters="\x00"), max_size=8)
payload_simples = st.dictionaries(
    texto,
    st.one_of(st.none(), st.booleans(), st.integers(-(10**9), 10**9), texto),
    max_size=4,
)
lote = st.lists(
    st.tuples(st.sampled_from(["pix", "kyc", "onchain"]), payload_simples),
    min_size=1,
    max_size=5,
)


def _tenant_novo() -> UUID:
    with psycopg.connect(DATABASE_URL) as conn:
        linha = conn.execute(
            "insert into core.tenants (nome, api_key_hash)"
            " values ('prop', 'x') returning id"
        ).fetchone()
        assert linha is not None
        conn.commit()
    return linha[0]


@settings(max_examples=20, deadline=None)
@given(lote)
def test_recomputo_da_cadeia_bate(entrada: list[tuple[str, dict[str, Any]]]) -> None:
    tid = _tenant_novo()
    with psycopg.connect(APP_DATABASE_URL) as conn:
        anexados = [
            chain.append(conn, tid, tipo, "prop", payload)[0]
            for tipo, payload in entrada
        ]
        do_banco = chain.ler_cadeia(conn, tid)
    assert [e.seq for e in do_banco] == list(range(1, len(entrada) + 1))
    assert [e.hash for e in do_banco] == [e.hash for e in anexados]
    chain.verificar(do_banco)


def test_adulteracao_em_memoria_e_detectada() -> None:
    tid = _tenant_novo()
    with psycopg.connect(APP_DATABASE_URL) as conn:
        for i in range(3):
            chain.append(conn, tid, "t", "prop", {"i": i})
        eventos = chain.ler_cadeia(conn, tid)
    adulterados = list(eventos)
    adulterados[1] = dataclasses.replace(adulterados[1], payload={"i": 999})
    with pytest.raises(chain.CadeiaInvalida, match="seq 2"):
        chain.verificar(adulterados)
