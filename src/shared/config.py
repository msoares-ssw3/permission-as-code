"""Configuração via variáveis de ambiente."""

import os

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", "postgresql://simbios3:simbios3@localhost:5432/simbios3"
)
