"""Sessão 4: POST /verify — export íntegro passa; 1 byte flipado aponta o seq."""

import copy
from uuid import UUID

import psycopg
from fastapi.testclient import TestClient

from src.core import chain
from src.core.canonical import iso_utc
from src.core.export import gerar_manifest
from src.shared.config import APP_DATABASE_URL


def _manifest_da_cadeia(tenant_id: UUID) -> dict:
    with psycopg.connect(APP_DATABASE_URL) as conn:
        for i in range(3):
            chain.append(conn, tenant_id, "t", "teste", {"i": i})
        eventos = chain.ler_cadeia(conn, tenant_id)
        agora = conn.execute("select now()").fetchone()
    assert agora is not None
    return gerar_manifest(str(tenant_id), eventos, iso_utc(agora[0]))


def test_export_integro_passa_no_verify(client: TestClient, tenant_novo: UUID) -> None:
    manifest = _manifest_da_cadeia(tenant_novo)
    resposta = client.post("/verify", json=manifest)
    assert resposta.status_code == 200
    assert resposta.json() == {"valido": True, "seq_de": 1, "seq_ate": 3}


def test_1_byte_flipado_falha_apontando_o_seq(
    client: TestClient, tenant_novo: UUID
) -> None:
    manifest = _manifest_da_cadeia(tenant_novo)
    adulterado = copy.deepcopy(manifest)
    adulterado["eventos"][1]["payload"] = {"i": 999}
    resposta = client.post("/verify", json=adulterado)
    assert resposta.status_code == 422
    assert "seq 2" in resposta.json()["detail"]


def test_export_publico_nao_exige_api_key(
    client: TestClient, tenant_novo: UUID
) -> None:
    manifest = _manifest_da_cadeia(tenant_novo)
    resposta = client.post("/verify", json=manifest)
    assert resposta.status_code == 200
