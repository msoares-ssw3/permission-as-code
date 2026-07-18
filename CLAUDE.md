# Plataforma simbios3 — regras do projeto

## O que é
Event store imutável + evidência verificável + conectores. Specs: doc do produto técnico
+ este plano. Tudo que o sistema afirma precisa ser reproduzível e verificável.

## Stack e convenções
- Python 3.12, FastAPI, psycopg (SQL direto, sem ORM), Pydantic v2, PyYAML.
- Deps permitidas: fastapi, uvicorn, psycopg[binary], pydantic, boto3, pyyaml,
  pytest, hypothesis, httpx, ruff. NADA além sem perguntar. Sem pandas, sem ORM.
- Ports & adapters: core não importa boto3 nem SDK de provider — só interfaces.
- Funções <40 linhas; type hints em tudo; ruff limpo.

## Guardrails inegociáveis
1. DETERMINISMO É SAGRADO: mesma entrada → mesmo byte de saída. Nada de dict sem ordem,
   set iterado, datetime.now() dentro de geração de relatório, ou float.
2. DINHEIRO É INTEIRO EM CENTAVOS. Float em valor monetário é bug de reprovação imediata.
3. A serialização canônica e o algoritmo de hash (seção 1.3 do plano) são CONGELADOS
   após a Sessão 2. Mudar exige migração de cadeia — ou seja, não muda.
4. Migrations de `events` são imutáveis depois de aplicadas. Correção = migration nova.
5. RLS em TODA tabela nova, com teste de isolamento. Sem exceção "porque é interna".
6. IA redige rascunho e resume; IA NUNCA decide caso nem calcula número regulatório.
7. Logs sem payload completo e sem identificador pessoal em claro (mascarar).
8. Todo bug encontrado vira teste ANTES do fix.

## Comandos
make up · make migrate · make test · make prop · make golden · make run · make verify-demo

## Definição de pronto (toda sessão)
make test verde · código novo com teste · determinismo: suítes golden rodadas 2x com diff vazio.
