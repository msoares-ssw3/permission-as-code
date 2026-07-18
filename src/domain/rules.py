"""Regras versionadas com vigência (rules/ YAML) — Sessão 5.

Mesma id pode ter várias versões, desde que as vigências não se sobreponham.
Bordas inclusivas: a regra vale em vigente_de e em vigente_ate; vigente_ate
nulo = vigência aberta. "Qual regra valia em D" é consulta de primeira classe.
"""

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


class Regra(BaseModel):
    id: str = Field(min_length=1)
    versao: int = Field(ge=1)
    vigente_de: date
    vigente_ate: date | None = None
    aplica_a: str
    criterio: str
    parametros: dict[str, Any] = Field(default_factory=dict)
    severidade: str
    descricao: str

    @model_validator(mode="after")
    def _vigencia_coerente(self) -> "Regra":
        if self.vigente_ate is not None and self.vigente_ate < self.vigente_de:
            raise ValueError(
                f"regra {self.id} v{self.versao}: vigente_ate < vigente_de"
            )
        return self

    def vigente_em(self, dia: date) -> bool:
        if dia < self.vigente_de:
            return False
        return self.vigente_ate is None or dia <= self.vigente_ate


def carregar_regras(caminho: Path) -> list[Regra]:
    """Carrega e valida o YAML; recusa vigências sobrepostas na mesma id."""
    bruto = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    regras = [Regra.model_validate(item) for item in bruto["regras"]]
    _recusar_sobreposicao(regras)
    return regras


def _recusar_sobreposicao(regras: list[Regra]) -> None:
    for i, a in enumerate(regras):
        for b in regras[i + 1 :]:
            if a.id == b.id and _sobrepoe(a, b):
                raise ValueError(
                    f"vigências sobrepostas na regra {a.id}: v{a.versao} e v{b.versao}"
                )


def _sobrepoe(a: Regra, b: Regra) -> bool:
    fim_a = a.vigente_ate or date.max
    fim_b = b.vigente_ate or date.max
    return a.vigente_de <= fim_b and b.vigente_de <= fim_a


def vigentes_em(regras: list[Regra], dia: date) -> list[Regra]:
    """Regras vigentes no dia D, na ordem do arquivo."""
    return [regra for regra in regras if regra.vigente_em(dia)]


def vigente_em(regras: list[Regra], id_regra: str, dia: date) -> Regra | None:
    """Qual versão da regra `id_regra` valia em D (None se nenhuma)."""
    for regra in regras:
        if regra.id == id_regra and regra.vigente_em(dia):
            return regra
    return None
