-- Cases de compliance (Sessão 6). Nascem de violação de regra na ingestão,
-- linkados no banco ao evento de origem (fk composta para core.events).
-- Decisão exige justificativa E decisão no próprio schema — decidir sem
-- justificar é impossível também para quem falar SQL direto (Sessão 7).
-- RLS obrigatória (guardrail 5), mesmo padrão da 001.
create table core.cases (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references core.tenants(id),
  status text not null default 'aberto'
    check (status in ('aberto', 'em_analise', 'decidido')),
  regra_id text not null,
  regra_versao int not null,
  evento_origem_seq bigint not null,
  aberto_em timestamptz not null default now(),
  decidido_em timestamptz,
  decidido_por text,
  decisao text check (decisao in ('procedente', 'improcedente')),
  justificativa text,
  constraint decisao_exige_justificativa check (
    status <> 'decidido'
    or (justificativa is not null and decisao is not null
        and decidido_por is not null)
  ),
  foreign key (tenant_id, evento_origem_seq)
    references core.events (tenant_id, seq)
);

alter table core.cases enable row level security;
create policy tenant_isolation on core.cases
  using (tenant_id = current_setting('app.tenant_id')::uuid);
alter table core.cases force row level security;
alter table core.cases owner to simbios3_app;
