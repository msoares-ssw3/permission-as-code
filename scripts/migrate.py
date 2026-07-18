"""Aplica migrations SQL pendentes de migrations/, em ordem lexical.

Cada migration roda em transação própria e é registrada em
public.schema_migrations; rodar de novo é no-op (idempotente).
Migrations já aplicadas são imutáveis — correção é migration nova.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import psycopg

from src.shared.config import DATABASE_URL

MIGRATIONS_DIR = RAIZ / "migrations"


def migrations_pendentes(conn: psycopg.Connection) -> list[Path]:
    with conn.transaction():
        conn.execute(
            "create table if not exists public.schema_migrations ("
            " filename text primary key,"
            " aplicado_em timestamptz not null default now())"
        )
    registros = conn.execute("select filename from public.schema_migrations")
    aplicadas = {linha[0] for linha in registros}
    return [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.name not in aplicadas]


def aplicar(conn: psycopg.Connection, migration: Path) -> None:
    with conn.transaction():
        conn.execute(migration.read_text(encoding="utf-8"))
        conn.execute(
            "insert into public.schema_migrations (filename) values (%s)",
            (migration.name,),
        )


def main() -> int:
    with psycopg.connect(DATABASE_URL) as conn:
        pendentes = migrations_pendentes(conn)
        for migration in pendentes:
            aplicar(conn, migration)
            print(f"aplicada: {migration.name}")
        if not pendentes:
            print("nenhuma migration pendente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
