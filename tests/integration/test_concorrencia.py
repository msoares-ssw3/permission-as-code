"""Sessão 2: 20 workers × 500 eventos no mesmo tenant → cadeia íntegra,
seq sem buraco."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import psycopg

from src.core import chain
from src.shared.config import APP_DATABASE_URL

WORKERS = 20
POR_WORKER = 500


def _worker(tenant_id: UUID, worker: int) -> None:
    with psycopg.connect(APP_DATABASE_URL) as conn:
        for i in range(POR_WORKER):
            chain.append(conn, tenant_id, "carga", "s2", {"worker": worker, "i": i})


def test_concorrencia_20_workers_x_500(
    app_conn: psycopg.Connection, tenant_novo: UUID
) -> None:
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futuros = [pool.submit(_worker, tenant_novo, w) for w in range(WORKERS)]
        for futuro in futuros:
            futuro.result()
    eventos = chain.ler_cadeia(app_conn, tenant_novo)
    total = WORKERS * POR_WORKER
    assert len(eventos) == total
    assert [e.seq for e in eventos] == list(range(1, total + 1))
    chain.verificar(eventos)
