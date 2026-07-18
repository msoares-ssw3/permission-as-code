"""Sessão 5: watchlist — API, eventos na cadeia, rebuild e isolamento RLS."""

from collections.abc import Callable
from uuid import UUID

import psycopg
from fastapi.testclient import TestClient

from src.core import chain
from src.projections import watchlist
from src.shared.config import APP_DATABASE_URL

FabricaTenant = Callable[[], tuple[UUID, str]]


def _headers(chave: str) -> dict[str, str]:
    return {"X-API-Key": chave}


def test_adicionar_listar_remover_via_api(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    _, chave = tenant_api()
    criada = client.post(
        "/watchlist",
        json={"endereco": "0xdead", "motivo": "sanção"},
        headers=_headers(chave),
    )
    assert criada.status_code == 201
    lista = client.get("/watchlist", headers=_headers(chave)).json()
    assert lista["entradas"] == [{"endereco": "0xdead", "motivo": "sanção"}]
    removida = client.delete("/watchlist/0xdead", headers=_headers(chave))
    assert removida.status_code == 200
    assert client.get("/watchlist", headers=_headers(chave)).json()["entradas"] == []


def test_mutacoes_viram_eventos_na_cadeia(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    tid, chave = tenant_api()
    client.post(
        "/watchlist", json={"endereco": "0xa", "motivo": "m"}, headers=_headers(chave)
    )
    client.delete("/watchlist/0xa", headers=_headers(chave))
    with psycopg.connect(APP_DATABASE_URL) as conn:
        eventos = chain.ler_cadeia(conn, tid)
    assert [e.tipo for e in eventos] == ["watchlist.adicionado", "watchlist.removido"]
    assert eventos[0].payload == {"endereco": "0xa", "motivo": "m"}
    chain.verificar(eventos)


def test_rls_tenant_b_nao_ve_watchlist_do_a(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    _, chave_a = tenant_api()
    _, chave_b = tenant_api()
    client.post(
        "/watchlist",
        json={"endereco": "0xsegredo", "motivo": "do-a"},
        headers=_headers(chave_a),
    )
    assert client.get("/watchlist", headers=_headers(chave_b)).json()["entradas"] == []


def test_rebuild_reproduz_o_estado_atual(tenant_novo: UUID) -> None:
    with psycopg.connect(APP_DATABASE_URL) as conn:
        watchlist.adicionar(conn, tenant_novo, "0xa", "m1")
        watchlist.adicionar(conn, tenant_novo, "0xb", "m2")
        watchlist.remover(conn, tenant_novo, "0xa")
        watchlist.adicionar(conn, tenant_novo, "0xc", "m3")
        antes = watchlist.listar(conn, tenant_novo)
        watchlist.rebuild(conn, tenant_novo)
        depois = watchlist.listar(conn, tenant_novo)
    assert antes == depois
    assert {item["endereco"] for item in depois} == {"0xb", "0xc"}
