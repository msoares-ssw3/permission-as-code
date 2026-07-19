# Demo do Guard (MVP-1) — roteiro de ~5 minutos

O que a demo prova, na ordem: **tudo vira evento numa cadeia imutável → violação de
perímetro abre case sozinha → decisão é humana e justificada → qualquer um verifica a
prova em máquina limpa → adulterar é impossível sem ser pego.**

## 0 · Preparação (antes da demo, 2 min)

```bash
make up        # Postgres 16 em Docker (ou um Postgres 16 local equivalente)
make migrate   # aplica migrations 001–004
make run &     # API em http://localhost:8000
python scripts/seed.py
```

O seed imprime o tenant e a API key. Exporte para os comandos abaixo:

```bash
export CHAVE="<API key impressa pelo seed>"
```

## 1 · "Todo movimento vira evento" (1 min)

Adicione um endereço à watchlist — repare que **até isso** vira evento na cadeia:

```bash
curl -s -X POST localhost:8000/watchlist \
  -H "X-API-Key: $CHAVE" -H 'content-type: application/json' \
  -d '{"endereco": "0xdeadbeef", "motivo": "lista de sanções"}'

curl -s "localhost:8000/events" -H "X-API-Key: $CHAVE"
# → evento watchlist.adicionado, seq 1, prev_hash = 64 zeros (genesis)
```

## 2 · "Violação abre case sozinha, na mesma transação" (1 min)

Simule o webhook do provider com uma transferência para o endereço da watchlist:

```bash
curl -s -X POST localhost:8000/webhooks/onchain \
  -H "X-API-Key: $CHAVE" -H 'content-type: application/json' \
  -d '{"tx": "0xabc123", "de": "0xaaa", "para": "0xdeadbeef",
       "valor": 150000, "token": "BRLX", "bloco": 42}'
# → 201, casos_abertos: [{case_id, regra_id: destino-watchlist, regra_versao: 1}]
```

Ponto de venda: o case nasceu **linkado ao evento de origem no banco** (foreign key),
com evento `case.aberto` na mesma cadeia — não existe "violação que se perdeu no meio
do caminho". Repita o mesmo curl: volta 200, `criado: false`, **nenhum case duplicado**
(idempotência por tx).

Abra o painel no navegador: `http://localhost:8000/painel?chave=$CHAVE`.

## 3 · "IA nunca decide — decisão é humana e justificada" (1 min)

```bash
export CASE="<case_id devolvido acima>"

curl -s -X POST "localhost:8000/cases/$CASE/analisar" -H "X-API-Key: $CHAVE"

# Tentar decidir sem justificativa → 422, sempre:
curl -s -X POST "localhost:8000/cases/$CASE/decidir" \
  -H "X-API-Key: $CHAVE" -H 'content-type: application/json' \
  -d '{"decisao": "procedente", "decidido_por": "ana"}'

# Com justificativa e autor → 200, evento case.decidido entra na cadeia:
curl -s -X POST "localhost:8000/cases/$CASE/decidir" \
  -H "X-API-Key: $CHAVE" -H 'content-type: application/json' \
  -d '{"decisao": "procedente", "decidido_por": "ana",
       "justificativa": "endereço consta na lista oficial de sanções"}'
```

E nem SQL direto escapa — o **schema** recusa decisão sem justificativa:

```bash
psql postgresql://simbios3:simbios3@localhost:5432/simbios3 \
  -c "update core.cases set status = 'decidido' where id = '$CASE'"
# ERROR: ... violates check constraint "decisao_exige_justificativa"
```

## 4 · "A prova roda em máquina limpa" (1 min)

```bash
make verify-demo
# → export gerado: /tmp/export.json ... / OK: seq 1..5 íntegro, hash_final=…
```

O `verifier/verify.py` é stdlib pura — mande o `export.json` + o `verify.py` para o
auditor/regulador e ele verifica **sem instalar nada nosso**. Agora flippe 1 byte:

```bash
python3 - <<'EOF'
import json
m = json.load(open("/tmp/export.json"))
m["eventos"][0]["payload"]["valor_centavos"] += 1
json.dump(m, open("/tmp/adulterado.json", "w"))
EOF
python verifier/verify.py /tmp/adulterado.json
# → INVÁLIDO: hash divergente no seq 1   (exit 1)
```

## 5 · O golpe final: "nem o dono do banco adultera" (30 s)

```bash
psql postgresql://simbios3:simbios3@localhost:5432/simbios3 \
  -c "update core.events set payload = '{}' where seq = 1"
# ERROR: core.events é append-only
psql postgresql://simbios3:simbios3@localhost:5432/simbios3 \
  -c "delete from core.events"
# ERROR: core.events é append-only
```

**Fechamento:** "Tudo que você viu — watchlist, violação, análise, decisão — está numa
cadeia de hash por tenant que o banco se recusa a alterar e que qualquer terceiro
verifica em segundos. Isso é o Guard."
