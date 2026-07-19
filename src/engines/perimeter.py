"""Avaliação de regras de perímetro na ingestão — Sessão 6, o coração do Guard.

Do webhook ao case em UMA transação: evento onchain.transferencia (idempotente
por tx), avaliação das regras vigentes NA DATA DO EVENTO contra a watchlist do
tenant, e cada violação abre um case linkado ao evento de origem + evento
case.aberto na cadeia. Replay do webhook não reavalia nem duplica case.
"""

from datetime import date
from typing import Any
from uuid import UUID

import psycopg

from src.adapters.pg import set_tenant
from src.core import chain
from src.core.events import Evento
from src.domain.ports import TransferenciaOnchain
from src.domain.rules import Regra, carregar_regras, vigentes_em
from src.projections import watchlist
from src.shared.config import RULES_DIR

TIPO_TRANSFERENCIA = "onchain.transferencia"
ORIGEM_WEBHOOK = "webhook.onchain"

_CRITERIOS = {
    "destino_na_watchlist": lambda p, regra, wl: p["para"] in wl,
    "origem_na_watchlist": lambda p, regra, wl: p["de"] in wl,
    "valor_acima_limite": lambda p, regra, wl: p["valor"] > regra.parametros["limite"],
}


def avaliar(
    tipo: str, payload: dict[str, Any], regras: list[Regra], enderecos: set[str]
) -> list[Regra]:
    """Regras violadas pelo evento — função pura, sem I/O."""
    violadas = []
    for regra in regras:
        if regra.aplica_a != tipo:
            continue
        if _CRITERIOS[regra.criterio](payload, regra, enderecos):
            violadas.append(regra)
    return violadas


def ingerir_transferencia(
    conn: psycopg.Connection, tenant_id: UUID | str, transf: TransferenciaOnchain
) -> tuple[Evento, bool, list[dict[str, Any]]]:
    """Webhook → evento → avaliação → cases, tudo numa transação rastreável.

    Devolve (evento, criado, casos_abertos); replay (criado=False) devolve o
    evento existente sem reavaliar — nenhum case é duplicado.
    """
    payload = {
        "tx": transf.tx, "de": transf.de, "para": transf.para,
        "valor": transf.valor, "token": transf.token, "bloco": transf.bloco,
    }
    with conn.transaction():
        set_tenant(conn, tenant_id)
        evento, criado = chain.append(
            conn, tenant_id, TIPO_TRANSFERENCIA, ORIGEM_WEBHOOK, payload,
            dedupe_key=f"onchain:{transf.tx}",
        )
        if not criado:
            return evento, False, []
        dia = date.fromisoformat(evento.ts[:10])
        regras = vigentes_em(carregar_regras(RULES_DIR / "perimetro.yaml"), dia)
        enderecos = watchlist.enderecos(conn, tenant_id)
        violadas = avaliar(evento.tipo, payload, regras, enderecos)
        casos = [_abrir_case(conn, tenant_id, evento, regra) for regra in violadas]
    return evento, True, casos


def _abrir_case(
    conn: psycopg.Connection, tenant_id: UUID | str, origem: Evento, regra: Regra
) -> dict[str, Any]:
    """Insere o case linkado ao evento de origem + evento case.aberto na cadeia."""
    linha = conn.execute(
        "insert into core.cases (tenant_id, regra_id, regra_versao, evento_origem_seq)"
        " values (%s, %s, %s, %s) returning id",
        (str(tenant_id), regra.id, regra.versao, origem.seq),
    ).fetchone()
    assert linha is not None
    case_id = str(linha[0])
    chain.append(
        conn, tenant_id, "case.aberto", "engine.perimetro",
        {
            "case_id": case_id, "regra_id": regra.id, "regra_versao": regra.versao,
            "evento_origem_seq": origem.seq, "severidade": regra.severidade,
        },
    )
    return {"case_id": case_id, "regra_id": regra.id, "regra_versao": regra.versao}
