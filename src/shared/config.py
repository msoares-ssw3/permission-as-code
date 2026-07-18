"""Configuração via variáveis de ambiente."""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent

# Diretório das regras versionadas (rules/*.yaml).
RULES_DIR: Path = Path(os.environ.get("RULES_DIR", str(RAIZ / "rules")))

# Conexão de sistema (migrations e jobs): role administrador, bypass de RLS
# explícito e justificado.
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", "postgresql://simbios3:simbios3@localhost:5432/simbios3"
)

# Conexão de aplicação: role sem bypass de RLS; exige set_tenant por transação.
APP_DATABASE_URL: str = os.environ.get(
    "APP_DATABASE_URL", "postgresql://simbios3_app:simbios3_app@localhost:5432/simbios3"
)
