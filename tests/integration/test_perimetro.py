"""Sessão 6: do webhook ao case em uma transação rastreável (aceite literal)."""

import dataclasses
from collections.abc import Callable
from uuid import UUID

import psycopg
from fastapi.testclient import TestClient

from src.adapters.pg import set_tenant
from src.adapters.provider_onchain import MockProviderOnchain
from src.core import chain
from src.shared.config import APP_DATABASE_URL

FabricaTenant = Callable[[], tuple[UUID, str]]


def _headers(chave: str) -> dict[str, str]:
    return {"X-API-Key": chave}


def _transferencia(**ajustes: object) -> dict[str, object]:
    """Transferência simulada do mock (determinística), com ajustes por teste."""
    base = MockProviderOnchain("teste-perimetro").transferencias()[0]
    return dataclasses.asdict(dataclasses.replace(base, **ajustes))  # type: ignore[arg-type]


def _cases_no_banco(tenant_id: UUID) -> list[tuple]:
    with psycopg.connect(APP_DATABASE_URL) as conn, conn.transaction():
        set_tenant(conn, tenant_id)
        return conn.execute(
            "select regra_id, regra_versao, evento_origem_seq, status"
            " from core.cases where tenant_id = %s order by aberto_em",
            (tenant_id,),
        ).fetchall()


def test_transferencia_para_watchlist_abre_case_linkado(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    tid, chave = tenant_api()
    corpo = _transferencia(valor=1000)
    client.post(
        "/watchlist",
        json={"endereco": corpo["para"], "motivo": "sanção"},
        headers=_headers(chave),
    )
    resposta = client.post("/webhooks/onchain", json=corpo, headers=_headers(chave))
    assert resposta.status_code == 201
    dados = resposta.json()
    assert [c["regra_id"] for c in dados["casos_abertos"]] == ["destino-watchlist"]
    cases = _cases_no_banco(tid)
    assert cases == [("destino-watchlist", 1, dados["evento_seq"], "aberto")]
    with psycopg.connect(APP_DATABASE_URL) as conn:
        eventos = chain.ler_cadeia(conn, tid)
    aberto = eventos[-1]
    assert aberto.tipo == "case.aberto"
    assert aberto.payload["evento_origem_seq"] == dados["evento_seq"]
    assert aberto.payload["case_id"] == dados["casos_abertos"][0]["case_id"]
    chain.verificar(eventos)


def test_replay_do_webhook_nao_duplica_case(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    tid, chave = tenant_api()
    corpo = _transferencia(valor=1000)
    client.post(
        "/watchlist",
        json={"endereco": corpo["para"], "motivo": "sanção"},
        headers=_headers(chave),
    )
    primeira = client.post("/webhooks/onchain", json=corpo, headers=_headers(chave))
    replay = client.post("/webhooks/onchain", json=corpo, headers=_headers(chave))
    assert primeira.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["criado"] is False
    assert len(_cases_no_banco(tid)) == 1


def test_transferencia_limpa_nao_abre_case(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    tid, chave = tenant_api()
    resposta = client.post(
        "/webhooks/onchain", json=_transferencia(valor=1000), headers=_headers(chave)
    )
    assert resposta.status_code == 201
    assert resposta.json()["casos_abertos"] == []
    assert _cases_no_banco(tid) == []


def test_valor_acima_do_limite_usa_versao_vigente_da_regra(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    # Hoje (>= 2026-07-01) vige a v2 de valor-maximo, limite 5_000_000.
    tid, chave = tenant_api()
    resposta = client.post(
        "/webhooks/onchain",
        json=_transferencia(valor=5_000_001),
        headers=_headers(chave),
    )
    casos = resposta.json()["casos_abertos"]
    assert [(c["regra_id"], c["regra_versao"]) for c in casos] == [("valor-maximo", 2)]
    assert _cases_no_banco(tid)[0][:2] == ("valor-maximo", 2)


def test_rls_tenant_b_nao_ve_cases_do_a(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    tid_a, chave_a = tenant_api()
    tid_b, _ = tenant_api()
    corpo = _transferencia(valor=1000)
    client.post(
        "/watchlist",
        json={"endereco": corpo["para"], "motivo": "sanção"},
        headers=_headers(chave_a),
    )
    client.post("/webhooks/onchain", json=corpo, headers=_headers(chave_a))
    assert len(_cases_no_banco(tid_a)) == 1
    with psycopg.connect(APP_DATABASE_URL) as conn, conn.transaction():
        set_tenant(conn, tid_b)
        vistos = conn.execute("select count(*) from core.cases").fetchone()
    assert vistos is not None and vistos[0] == 0
