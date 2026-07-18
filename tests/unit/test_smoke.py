"""Smoke da Sessão 0: a estrutura de pacotes importa limpa."""

import importlib

MODULOS = [
    "src.core.canonical",
    "src.core.chain",
    "src.core.events",
    "src.domain.models",
    "src.domain.money",
    "src.domain.rules",
    "src.domain.cases",
    "src.projections.ledger",
    "src.projections.mirrors",
    "src.engines.perimeter",
    "src.engines.reconcile",
    "src.engines.reports",
    "src.engines.cases_flow",
    "src.adapters.pg",
    "src.adapters.storage_local",
    "src.adapters.storage_s3",
    "src.adapters.provider_onchain",
    "src.adapters.partner_mock",
    "src.adapters.kyc_relay",
    "src.api.main",
    "src.api.auth",
    "src.api.routes",
    "src.shared.config",
    "src.shared.log",
]


def test_pacotes_importam() -> None:
    for nome in MODULOS:
        importlib.import_module(nome)
