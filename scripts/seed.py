"""Cria o tenant de demonstração e imprime a API key (demo do Bloco 0)."""

import hashlib
import secrets
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import psycopg

from src.shared.config import DATABASE_URL


def main() -> int:
    api_key = secrets.token_hex(16)
    chave_hash = hashlib.sha256(api_key.encode()).hexdigest()
    with psycopg.connect(DATABASE_URL) as conn:
        linha = conn.execute(
            "insert into core.tenants (nome, api_key_hash)"
            " values ('demo', %s) returning id",
            (chave_hash,),
        ).fetchone()
        assert linha is not None
        conn.commit()
    print(f"tenant demo: {linha[0]}")
    print(f"API key: {api_key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
