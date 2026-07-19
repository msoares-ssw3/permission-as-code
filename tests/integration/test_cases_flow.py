"""Sessão 7: fluxo de casos — decidir sem justificativa é impossível (2 camadas)."""

import dataclasses
from collections.abc import Callable
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import errors

from src.adapters.provider_onchain import MockProviderOnchain
from src.core import chain
from src.shared.config import APP_DATABASE_URL

FabricaTenant = Callable[[], tuple[UUID, str]]

DECISAO_OK = {
    "decisao": "procedente",
    "justificativa": "endereço sancionado confirmado na lista oficial",
    "decidido_por": "analista@simbios3",
}


def _headers(chave: str) -> dict[str, str]:
    return {"X-API-Key": chave}


def _abrir_case_por_violacao(client: TestClient, chave: str) -> str:
    """Transferência simulada pra watchlist → devolve o case_id aberto."""
    transf = dataclasses.asdict(
        dataclasses.replace(
            MockProviderOnchain("teste-cases").transferencias()[0], valor=1000
        )
    )
    client.post(
        "/watchlist",
        json={"endereco": transf["para"], "motivo": "sanção"},
        headers=_headers(chave),
    )
    resposta = client.post("/webhooks/onchain", json=transf, headers=_headers(chave))
    return resposta.json()["casos_abertos"][0]["case_id"]


def test_fluxo_completo_com_evento_de_decisao_na_cadeia(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    tid, chave = tenant_api()
    case_id = _abrir_case_por_violacao(client, chave)
    assert (
        client.post(f"/cases/{case_id}/analisar", headers=_headers(chave)).status_code
        == 200
    )
    decidido = client.post(
        f"/cases/{case_id}/decidir", json=DECISAO_OK, headers=_headers(chave)
    )
    assert decidido.status_code == 200
    detalhe = client.get(f"/cases/{case_id}", headers=_headers(chave)).json()
    assert detalhe["case"]["status"] == "decidido"
    assert detalhe["case"]["justificativa"] == DECISAO_OK["justificativa"]
    tipos_da_trilha = [evento["tipo"] for evento in detalhe["trilha"]]
    assert tipos_da_trilha == [
        "onchain.transferencia", "case.aberto", "case.em_analise", "case.decidido",
    ]
    with psycopg.connect(APP_DATABASE_URL) as conn:
        eventos = chain.ler_cadeia(conn, tid)
    chain.verificar(eventos)
    assert eventos[-1].tipo == "case.decidido"
    assert eventos[-1].payload["decidido_por"] == DECISAO_OK["decidido_por"]


def test_decidir_sem_justificativa_e_impossivel_na_api(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    _, chave = tenant_api()
    case_id = _abrir_case_por_violacao(client, chave)
    client.post(f"/cases/{case_id}/analisar", headers=_headers(chave))
    sem_campo = client.post(
        f"/cases/{case_id}/decidir",
        json={"decisao": "procedente", "decidido_por": "analista"},
        headers=_headers(chave),
    )
    so_espacos = client.post(
        f"/cases/{case_id}/decidir",
        json={**DECISAO_OK, "justificativa": "   "},
        headers=_headers(chave),
    )
    assert sem_campo.status_code == 422
    assert so_espacos.status_code == 422
    detalhe = client.get(f"/cases/{case_id}", headers=_headers(chave)).json()
    assert detalhe["case"]["status"] == "em_analise"


def test_decidir_sem_justificativa_e_impossivel_no_banco(
    client: TestClient, tenant_api: FabricaTenant, admin_conn: psycopg.Connection
) -> None:
    _, chave = tenant_api()
    case_id = _abrir_case_por_violacao(client, chave)
    with pytest.raises(errors.CheckViolation):
        admin_conn.execute(
            "update core.cases set status = 'decidido' where id = %s", (case_id,)
        )


def test_transicao_invalida_e_case_inexistente(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    _, chave = tenant_api()
    case_id = _abrir_case_por_violacao(client, chave)
    pulando_analise = client.post(
        f"/cases/{case_id}/decidir", json=DECISAO_OK, headers=_headers(chave)
    )
    assert pulando_analise.status_code == 409
    fantasma = "00000000-0000-0000-0000-000000000000"
    assert (
        client.post(f"/cases/{fantasma}/analisar", headers=_headers(chave)).status_code
        == 404
    )


def test_painel_lista_o_case_e_recusa_chave_invalida(
    client: TestClient, tenant_api: FabricaTenant
) -> None:
    _, chave = tenant_api()
    case_id = _abrir_case_por_violacao(client, chave)
    pagina = client.get("/painel", params={"chave": chave})
    assert pagina.status_code == 200
    assert case_id in pagina.text
    assert "case.aberto" in pagina.text
    assert client.get("/painel", params={"chave": "nao-existe"}).status_code == 401
