"""Gera um export de demonstração em /tmp/export.json (manifest v1 — spec 1.4)."""

import hashlib
import json
import secrets
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import psycopg

from src.core import chain
from src.core.canonical import iso_utc
from src.core.export import gerar_manifest
from src.shared.config import APP_DATABASE_URL, DATABASE_URL

EXPORT_PATH = Path("/tmp/export.json")

EVENTOS_DEMO = [
    ("pix", {"valor_centavos": 15000, "para": "conta-1"}),
    ("pix", {"valor_centavos": 2500, "para": "conta-2"}),
    ("onchain", {"tx": "0xabc", "endereco": "0xdead"}),
    ("kyc", {"referencia_externa": "kyc-ref-001"}),
    ("pix", {"valor_centavos": 999900, "para": "conta-3"}),
]


def _criar_tenant_demo() -> str:
    api_key_hash = hashlib.sha256(secrets.token_hex(16).encode()).hexdigest()
    with psycopg.connect(DATABASE_URL) as conn:
        linha = conn.execute(
            "insert into core.tenants (nome, api_key_hash)"
            " values ('demo-export', %s) returning id",
            (api_key_hash,),
        ).fetchone()
        assert linha is not None
        conn.commit()
    return str(linha[0])


def _popular_e_exportar(tenant_id: str) -> dict:
    with psycopg.connect(APP_DATABASE_URL) as conn:
        for tipo, payload in EVENTOS_DEMO:
            chain.append(conn, tenant_id, tipo, "demo_export", payload)
        eventos = chain.ler_cadeia(conn, tenant_id)
        agora = conn.execute("select now()").fetchone()
    assert agora is not None
    return gerar_manifest(tenant_id, eventos, iso_utc(agora[0]))


def main() -> int:
    tenant_id = _criar_tenant_demo()
    manifest = _popular_e_exportar(tenant_id)
    EXPORT_PATH.write_text(
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    n = len(EVENTOS_DEMO)
    print(f"export gerado: {EXPORT_PATH} ({n} eventos, tenant {tenant_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
