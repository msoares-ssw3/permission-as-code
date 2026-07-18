-- Watchlist de endereços por tenant (Sessão 5). É PROJEÇÃO do log: toda
-- mutação nasce de um evento watchlist.* na cadeia e a tabela é reconstruível
-- do zero (src/projections/watchlist.py::rebuild). RLS obrigatória
-- (guardrail 5), mesmo padrão da 001: policy por app.tenant_id + FORCE.
create table core.watchlist (
  tenant_id uuid not null references core.tenants(id),
  endereco text not null,
  motivo text not null,
  criado_em timestamptz not null default now(),
  primary key (tenant_id, endereco)
);

alter table core.watchlist enable row level security;
create policy tenant_isolation on core.watchlist
  using (tenant_id = current_setting('app.tenant_id')::uuid);
alter table core.watchlist force row level security;
alter table core.watchlist owner to simbios3_app;
