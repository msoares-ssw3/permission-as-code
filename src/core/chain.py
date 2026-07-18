"""Cadeia de hash por tenant — spec 1.3, CONGELADA após a Sessão 2.

hash = sha256_hex(bytes.fromhex(prev_hash) + sha256(canonical(e)).digest());
genesis tem prev_hash = "0" * 64. Cadeia POR TENANT, ordenada por seq
(bigint sequencial, sem buraco). Concorrência serializada com
pg_advisory_xact_lock(hashtext(tenant_id)) antes de ler o último seq;
hash calculado NA MESMA transação do insert, depois de seq e ts atribuídos.
"""

import hashlib
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from src.adapters.pg import set_tenant
from src.core.canonical import canonical, iso_utc, validar_payload
from src.core.events import Evento

GENESIS = "0" * 64

_COLUNAS = "tenant_id, seq, id, tipo, origem, dedupe_key, payload, ts, prev_hash, hash"


class CadeiaInvalida(Exception):
    """A cadeia não bate com o recomputado — adulteração ou bug."""


def hash_evento(prev_hash: str, corpo: bytes) -> str:
    """Elo da cadeia, exatamente como na spec 1.3."""
    interno = hashlib.sha256(corpo).digest()
    return hashlib.sha256(bytes.fromhex(prev_hash) + interno).hexdigest()


def append(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    tipo: str,
    origem: str,
    payload: dict[str, Any],
    dedupe_key: str | None = None,
) -> Evento:
    """Anexa um evento à cadeia do tenant; idempotente por dedupe_key."""
    if not isinstance(payload, dict):
        raise ValueError("payload deve ser objeto JSON")
    validar_payload(payload)
    tid = str(tenant_id)
    with conn.transaction():
        set_tenant(conn, tid)
        conn.execute("select pg_advisory_xact_lock(hashtext(%s))", (tid,))
        if dedupe_key is not None:
            existente = _por_dedupe(conn, tid, dedupe_key)
            if existente is not None:
                return existente
        return _novo_evento(conn, tid, tipo, origem, payload, dedupe_key)


def _novo_evento(
    conn: psycopg.Connection,
    tid: str,
    tipo: str,
    origem: str,
    payload: dict[str, Any],
    dedupe_key: str | None,
) -> Evento:
    ultimo_seq, prev = _ultimo(conn, tid)
    seq = ultimo_seq + 1
    agora = conn.execute("select now()").fetchone()
    assert agora is not None
    ts = iso_utc(agora[0])
    corpo = canonical(
        {"tenant_id": tid, "seq": seq, "tipo": tipo, "origem": origem,
         "payload": payload, "ts": ts}
    )
    novo_hash = hash_evento(prev, corpo)
    linha = conn.execute(
        "insert into core.events"
        " (tenant_id, seq, tipo, origem, dedupe_key, payload, ts, prev_hash, hash)"
        " values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning id",
        (tid, seq, tipo, origem, dedupe_key, Jsonb(payload), agora[0], prev, novo_hash),
    ).fetchone()
    assert linha is not None
    return Evento(
        tenant_id=tid, seq=seq, id=str(linha[0]), tipo=tipo, origem=origem,
        dedupe_key=dedupe_key, payload=payload, ts=ts, prev_hash=prev, hash=novo_hash,
    )


def _ultimo(conn: psycopg.Connection, tid: str) -> tuple[int, str]:
    linha = conn.execute(
        "select seq, hash from core.events where tenant_id = %s"
        " order by seq desc limit 1",
        (tid,),
    ).fetchone()
    return (linha[0], linha[1]) if linha else (0, GENESIS)


def _por_dedupe(conn: psycopg.Connection, tid: str, dedupe_key: str) -> Evento | None:
    linha = conn.execute(
        f"select {_COLUNAS} from core.events where tenant_id = %s and dedupe_key = %s",
        (tid, dedupe_key),
    ).fetchone()
    return _evento_da_linha(linha) if linha else None


def _evento_da_linha(linha: tuple) -> Evento:
    return Evento(
        tenant_id=str(linha[0]), seq=linha[1], id=str(linha[2]), tipo=linha[3],
        origem=linha[4], dedupe_key=linha[5], payload=linha[6],
        ts=iso_utc(linha[7]), prev_hash=linha[8], hash=linha[9],
    )


def ler_cadeia(conn: psycopg.Connection, tenant_id: UUID | str) -> list[Evento]:
    """Todos os eventos do tenant em ordem de seq (sob a visão RLS da conexão)."""
    tid = str(tenant_id)
    with conn.transaction():
        set_tenant(conn, tid)
        linhas = conn.execute(
            f"select {_COLUNAS} from core.events where tenant_id = %s order by seq",
            (tid,),
        ).fetchall()
    return [_evento_da_linha(linha) for linha in linhas]


def _corpo(evento: Evento) -> bytes:
    return canonical(
        {"tenant_id": evento.tenant_id, "seq": evento.seq, "tipo": evento.tipo,
         "origem": evento.origem, "payload": evento.payload, "ts": evento.ts}
    )


def verificar(eventos: Sequence[Evento]) -> None:
    """Recomputa a cadeia inteira; levanta CadeiaInvalida apontando o seq."""
    prev = GENESIS
    for esperado, evento in enumerate(eventos, start=1):
        if evento.seq != esperado:
            raise CadeiaInvalida(
                f"buraco na cadeia: esperado seq {esperado}, veio {evento.seq}"
            )
        if evento.prev_hash != prev:
            raise CadeiaInvalida(f"prev_hash divergente no seq {evento.seq}")
        if hash_evento(prev, _corpo(evento)) != evento.hash:
            raise CadeiaInvalida(f"hash divergente no seq {evento.seq}")
        prev = evento.hash
