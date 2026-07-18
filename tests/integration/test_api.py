"""Sessão 3: API de ingestão — auth por API key, POST idempotente, GET paginado."""

from collections.abc import Callable
from uuid import UUID

import psycopg
from fastapi.testclient import TestClient

from src.core import chain

FabricaTenant = Callable[[], tuple[UUID, str]]


def _headers(chave: str) -> dict[str, str]:
    return {"X-API-Key": chave}


def test_post_cria_evento(client: TestClient, tenant_api: FabricaTenant) -> None:
    _, chave = tenant_api()
    resposta = client.post(
        "/events",
        json={"tipo": "pix", "origem": "api", "payload": {"n": 1}},
        headers=_headers(chave),
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["seq"] == 1
    assert corpo["prev_hash"] == chain.GENESIS
    assert len(corpo["hash"]) == 64


def test_replay_dedupe_devolve_200_sem_duplicar(
    client: TestClient, tenant_api: FabricaTenant, admin_conn: psycopg.Connection
) -> None:
    tid, chave = tenant_api()
    corpo = {"tipo": "pix", "origem": "api", "payload": {"n": 1}, "dedupe_key": "k"}
    primeira = client.post("/events", json=corpo, headers=_headers(chave))
    replay = client.post("/events", json=corpo, headers=_headers(chave))
    assert primeira.status_code == 201
    assert replay.status_code == 200
    assert primeira.json() == replay.json()
    total = admin_conn.execute(
        "select count(*) from core.events where tenant_id = %s", (tid,)
    ).fetchone()
    assert total is not None and total[0] == 1


def test_get_paginado(client: TestClient, tenant_api: FabricaTenant) -> None:
    _, chave = tenant_api()
    for n in range(1, 6):
        client.post(
            "/events",
            json={"tipo": "t", "origem": "api", "payload": {"n": n}},
            headers=_headers(chave),
        )
    resposta = client.get(
        "/events", params={"desde_seq": 3, "limite": 2}, headers=_headers(chave)
    )
    assert resposta.status_code == 200
    assert [e["seq"] for e in resposta.json()["eventos"]] == [3, 4]


def test_isolamento_entre_tenants_pela_api(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    _, chave_a = tenant_api()
    _, chave_b = tenant_api()
    client.post(
        "/events",
        json={"tipo": "t", "origem": "api", "payload": {"segredo": "do-a"}},
        headers=_headers(chave_a),
    )
    resposta = client.get("/events", headers=_headers(chave_b))
    assert resposta.status_code == 200
    assert resposta.json()["eventos"] == []


def test_chave_invalida_401_e_sem_chave_422(client: TestClient) -> None:
    assert client.get("/events").status_code == 422
    assert client.get("/events", headers=_headers("nao-existe")).status_code == 401


def test_payload_com_float_422(client: TestClient, tenant_api: FabricaTenant) -> None:
    _, chave = tenant_api()
    resposta = client.post(
        "/events",
        json={"tipo": "t", "origem": "api", "payload": {"valor": 1.5}},
        headers=_headers(chave),
    )
    assert resposta.status_code == 422
