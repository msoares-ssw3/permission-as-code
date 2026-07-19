"""Sessão 5: regras versionadas — vigência com datas de borda e sobreposição."""

from datetime import date
from pathlib import Path

import pytest

from src.domain.rules import Regra, carregar_regras, vigente_em, vigentes_em
from src.shared.config import RULES_DIR


def _regra(**kwargs: object) -> Regra:
    base: dict[str, object] = {
        "id": "r", "versao": 1, "vigente_de": date(2026, 1, 1), "vigente_ate": None,
        "aplica_a": "onchain.transferencia", "criterio": "c", "parametros": {},
        "severidade": "alta", "descricao": "teste",
    }
    return Regra.model_validate({**base, **kwargs})


def test_bordas_de_vigencia_sao_inclusivas() -> None:
    regra = _regra(vigente_de=date(2026, 1, 10), vigente_ate=date(2026, 1, 20))
    assert not regra.vigente_em(date(2026, 1, 9))
    assert regra.vigente_em(date(2026, 1, 10))
    assert regra.vigente_em(date(2026, 1, 20))
    assert not regra.vigente_em(date(2026, 1, 21))


def test_vigencia_aberta_nao_expira() -> None:
    regra = _regra(vigente_de=date(2026, 1, 1), vigente_ate=None)
    assert regra.vigente_em(date(2099, 12, 31))
    assert not regra.vigente_em(date(2025, 12, 31))


def test_vigente_ate_antes_de_vigente_de_e_recusado() -> None:
    with pytest.raises(ValueError, match="vigente_ate"):
        _regra(vigente_de=date(2026, 2, 1), vigente_ate=date(2026, 1, 1))


def test_qual_regra_valia_em_d_na_troca_de_versao() -> None:
    v1 = _regra(versao=1, vigente_de=date(2026, 1, 1), vigente_ate=date(2026, 6, 30))
    v2 = _regra(versao=2, vigente_de=date(2026, 7, 1), vigente_ate=None)
    regras = [v1, v2]
    na_borda_v1 = vigente_em(regras, "r", date(2026, 6, 30))
    na_borda_v2 = vigente_em(regras, "r", date(2026, 7, 1))
    assert na_borda_v1 is not None and na_borda_v1.versao == 1
    assert na_borda_v2 is not None and na_borda_v2.versao == 2
    assert vigente_em(regras, "nao-existe", date(2026, 7, 1)) is None


def test_sobreposicao_de_vigencia_na_mesma_id_e_recusada(tmp_path: Path) -> None:
    yaml_ruim = tmp_path / "regras.yaml"
    yaml_ruim.write_text(
        """
regras:
  - {id: r, versao: 1, vigente_de: 2026-01-01, vigente_ate: 2026-06-30,
     aplica_a: t, criterio: c, severidade: alta, descricao: a}
  - {id: r, versao: 2, vigente_de: 2026-06-30, vigente_ate: null,
     aplica_a: t, criterio: c, severidade: alta, descricao: b}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="sobrepostas"):
        carregar_regras(yaml_ruim)


def test_yaml_real_do_repo_carrega_com_3_regras() -> None:
    regras = carregar_regras(RULES_DIR / "perimetro.yaml")
    assert {r.id for r in regras} == {
        "destino-watchlist", "origem-watchlist", "valor-maximo",
    }
    antes = vigente_em(regras, "valor-maximo", date(2026, 6, 30))
    depois = vigente_em(regras, "valor-maximo", date(2026, 7, 1))
    assert antes is not None and antes.parametros["limite"] == 10_000_000
    assert depois is not None and depois.parametros["limite"] == 5_000_000
    assert isinstance(antes.parametros["limite"], int)
    assert len(vigentes_em(regras, date(2026, 7, 18))) == 3
