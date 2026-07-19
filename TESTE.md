# TESTE.md — como validar o Guard (MVP-1) e o que esperar

Duas lentes, mesmo produto:

- **Parte 1 · Quality (QA/engenharia)**: suítes automatizadas + checklist adversarial.
  Aqui "passar" tem dois sentidos — os comandos verdes E os ataques falhando com o
  erro certo.
- **Parte 2 · Usuário (compliance officer)**: a jornada de quem opera, passo a passo,
  com a resposta esperada de cada chamada.
- **Parte 3 · Mapa promessa → prova**: qual teste sustenta cada promessa de venda.

## 0 · Preparação (comum às duas partes)

```bash
make up          # Postgres 16 em Docker (ou um Postgres 16 local equivalente)
make migrate     # → "aplicada: 001..004" na 1ª vez; "nenhuma migration pendente" depois
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## Parte 1 · Visão Quality

### 1.1 Suíte principal — `make test`

**Esperado: `63 passed`** (unit + integração contra Postgres real, sem mock de banco).

| O que está coberto | Se quebrar, significa |
|---|---|
| Vetores CONGELADOS da spec 1.3 (canônico + hash) | A serialização/cadeia mudou — reprovação imediata, exige migração de cadeia |
| Export/verifier: flip de 1 byte aponta o seq exato | A prova verificável não detecta adulteração |
| Vigência de regras com datas de borda (30/06 → v1, 01/07 → v2) | Regra errada seria aplicada na data errada |
| Trigger append-only em `core.events` | O banco deixaria reescrever história |
| Isolamento RLS nas 3 tabelas (`events`, `watchlist`, `cases`) | Um tenant enxergaria dados de outro |
| Idempotência por `dedupe_key` (API e webhook) | Replay duplicaria eventos/cases |
| Webhook → case em uma transação, linkado por FK | Violação poderia "se perder no meio do caminho" |
| Justificativa obrigatória em 2 camadas (API 422 + check constraint) | Alguém decidiria caso sem justificar |
| Payload com float recusado (422) | Dinheiro em float entraria no log |

### 1.2 Propriedades — `make prop`

**Esperado: `5 passed`.** Hypothesis gera payloads arbitrários e prova: recomputar a
cadeia inteira do banco bate byte a byte; o canônico é estável; adulteração em memória
é detectada. (A concorrência — 20 workers × 500 eventos, cadeia íntegra e seq sem
buraco — roda dentro do `make test`.)

### 1.3 Lint — `ruff check .`

**Esperado: `All checks passed!`**

### 1.4 Prova verificável — `make verify-demo`

**Esperado (2 linhas):**

```
export gerado: /tmp/export.json (5 eventos, tenant <uuid>)
OK: seq 1..5 íntegro, hash_final=<64 hex>
```

O uuid e o hash mudam por rodada (tenant novo a cada execução); o `OK` e a faixa
`seq 1..5` são fixos.

### 1.5 Checklist adversarial — o que DEVE falhar, e como

A promessa do produto é o **erro certo na hora certa**. Rode cada ataque e confira:

```bash
DB=postgresql://simbios3:simbios3@localhost:5432/simbios3

# a) Reescrever história → o BANCO recusa (não é validação de aplicação)
psql $DB -c "update core.events set payload = '{}' where seq = 1"
# ERROR:  core.events é append-only
psql $DB -c "delete from core.events"
# ERROR:  core.events é append-only

# b) Decidir case sem justificativa por SQL direto → o SCHEMA recusa
psql $DB -c "update core.cases set status = 'decidido' where true"
# ERROR: ... violates check constraint "decisao_exige_justificativa"
# (se não houver case ainda: "UPDATE 0" — crie um pela Parte 2 e repita)

# c) Espiar outro tenant → 0 linhas, nunca erro que vaze existência
psql "postgresql://simbios3_app:simbios3_app@localhost:5432/simbios3" -c \
  "begin; select set_config('app.tenant_id', gen_random_uuid()::text, true);
   select count(*) from core.events; rollback;"
# count = 0

# d) Adulterar 1 byte do export → INVÁLIDO apontando o seq, exit 1
make verify-demo
python3 -c "
import json; m = json.load(open('/tmp/export.json'))
m['eventos'][0]['payload']['valor_centavos'] += 1
json.dump(m, open('/tmp/adulterado.json', 'w'))"
python verifier/verify.py /tmp/adulterado.json; echo "exit=$?"
# INVÁLIDO: hash divergente no seq 1
# exit=1

# e) Manifest de versão desconhecida → recusado
python3 -c "
import json; m = json.load(open('/tmp/export.json'))
m['versao'] = 2; json.dump(m, open('/tmp/v2.json', 'w'))"
python verifier/verify.py /tmp/v2.json; echo "exit=$?"
# INVÁLIDO: versão de manifest não suportada: 2
# exit=1

# f) Entrada quebrada no CLI → mensagem curta, exit 2 (nunca traceback)
python verifier/verify.py /tmp/nao-existe.json; echo "exit=$?"   # exit=2
echo "{quebrado" > /tmp/quebrado.json
python verifier/verify.py /tmp/quebrado.json; echo "exit=$?"     # exit=2
```

### 1.6 Determinismo (guardrail 1)

Rodar `make verify-demo` duas vezes seguidas: cada rodada cria um tenant novo e o
veredito é sempre `OK: seq 1..5 íntegro`. Nota honesta: a suíte golden byte a byte
(`make golden`) ainda está vazia — entra na S12 (relatórios/snapshots); hoje o
determinismo é provado pelos vetores congelados + property tests + verify-demo.

---

## Parte 2 · Visão Usuário (jornada do compliance officer)

Suba a API e crie seu tenant:

```bash
make run &                     # API em http://localhost:8000
python scripts/seed.py         # → imprime "tenant demo: <uuid>" e "API key: <hex>"
export CHAVE="<API key impressa>"
```

**Passo 1 — Cadastro um endereço suspeito e isso já vira auditável.**

```bash
curl -s -X POST localhost:8000/watchlist \
  -H "X-API-Key: $CHAVE" -H 'content-type: application/json' \
  -d '{"endereco": "0xdeadbeef", "motivo": "lista de sanções"}'
# → {"endereco":"0xdeadbeef","evento_seq":1}

curl -s localhost:8000/events -H "X-API-Key: $CHAVE"
# → evento seq 1, tipo "watchlist.adicionado", prev_hash = 64 zeros (genesis)
```

**Passo 2 — Uma transferência suspeita chega e o case abre sozinho.**

```bash
curl -s -X POST localhost:8000/webhooks/onchain \
  -H "X-API-Key: $CHAVE" -H 'content-type: application/json' \
  -d '{"tx": "0xabc123", "de": "0xaaa", "para": "0xdeadbeef",
       "valor": 150000, "token": "BRLX", "bloco": 42}'
# → 201 {"evento_seq":2,"criado":true,
#        "casos_abertos":[{"case_id":"…","regra_id":"destino-watchlist","regra_versao":1}]}
export CASE="<case_id devolvido>"
```

**Passo 3 — O provider reenvia o mesmo webhook; nada duplica.**

```bash
# repita o curl do passo 2 →
# 200 {"evento_seq":2,"criado":false,"casos_abertos":[]}
```

**Passo 4 — Vejo minha fila de trabalho.**

Navegador: `http://localhost:8000/painel?chave=$CHAVE` → tabela com o case `aberto`
(regra `destino-watchlist v1`, evento de origem 2) + a trilha da cadeia.
Via API: `curl -s "localhost:8000/cases?status=aberto" -H "X-API-Key: $CHAVE"`.

**Passo 5 — O sistema me impede de tomar atalhos.**

```bash
# decidir sem analisar antes → 409 (fluxo é aberto → em_analise → decidido)
curl -s -o /dev/null -w "%{http_code}\n" -X POST "localhost:8000/cases/$CASE/decidir" \
  -H "X-API-Key: $CHAVE" -H 'content-type: application/json' \
  -d '{"decisao":"procedente","decidido_por":"ana","justificativa":"x"}'     # → 409

curl -s -X POST "localhost:8000/cases/$CASE/analisar" -H "X-API-Key: $CHAVE"
# → {"case_id":"…","status":"em_analise"}

# decidir sem justificativa (ou só espaços) → 422, sempre
curl -s -o /dev/null -w "%{http_code}\n" -X POST "localhost:8000/cases/$CASE/decidir" \
  -H "X-API-Key: $CHAVE" -H 'content-type: application/json' \
  -d '{"decisao":"procedente","decidido_por":"ana"}'                          # → 422
```

**Passo 6 — Decido como humano, justificando; a trilha fica completa.**

```bash
curl -s -X POST "localhost:8000/cases/$CASE/decidir" \
  -H "X-API-Key: $CHAVE" -H 'content-type: application/json' \
  -d '{"decisao":"procedente","decidido_por":"ana",
       "justificativa":"endereço consta na lista oficial de sanções"}'
# → {"case_id":"…","status":"decidido"}

curl -s "localhost:8000/cases/$CASE" -H "X-API-Key: $CHAVE"
# → trilha com exatamente:
#   ["onchain.transferencia", "case.aberto", "case.em_analise", "case.decidido"]
```

**Passo 7 — Regras têm versão e a versão certa vale na data certa.**

```bash
curl -s -X POST localhost:8000/webhooks/onchain \
  -H "X-API-Key: $CHAVE" -H 'content-type: application/json' \
  -d '{"tx": "0xdef456", "de": "0xbbb", "para": "0xccc",
       "valor": 5000001, "token": "BRLX", "bloco": 43}'
# → casos_abertos: [{"regra_id":"valor-maximo","regra_versao":2}]
#   (v2, limite 5.000.000, vigente desde 01/07/2026 — a versão fica registrada no case)
```

**Passo 8 — Presto contas com prova que roda em máquina limpa.**

```bash
make verify-demo
# → OK: seq 1..5 íntegro, hash_final=…
```

Envie `verifier/verify.py` + o `export.json` ao auditor: `python verify.py export.json`
funciona com Python puro, zero dependências. Se qualquer byte tiver sido alterado, a
saída é `INVÁLIDO: hash divergente no seq N` — apontando onde.

---

## Parte 3 · Mapa promessa → prova

| Promessa de venda | Teste automatizado | Passo manual |
|---|---|---|
| "Ninguém reescreve história, nem o dono do banco" | `test_events_imutaveis.py` | 1.5a |
| "Qualquer terceiro verifica a prova sem nos instalar" | `test_verify_standalone.py` (CLI via subprocess) | 1.5d / Passo 8 |
| "Um tenant nunca vê o outro" | `test_rls_isolamento.py`, `test_watchlist.py`, `test_perimetro.py` | 1.5c |
| "Violação abre case sozinha, linkada à origem" | `test_perimetro.py` | Passo 2 |
| "Replay não duplica nada" | `test_api.py`, `test_perimetro.py` | Passo 3 |
| "Decisão é humana e justificada — sem exceção" | `test_cases_flow.py` (422 + constraint) | 1.5b / Passos 5–6 |
| "A regra que valia na data é a registrada" | `test_rules.py` (bordas), `test_perimetro.py` | Passo 7 |
| "Mesma entrada, mesmo byte" | vetores congelados, `make prop`, mock determinístico | 1.6 |
