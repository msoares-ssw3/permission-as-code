create extension if not exists pgcrypto;
create schema if not exists core;

create table core.tenants (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  nivel text,
  api_key_hash text not null,
  criado_em timestamptz not null default now()
);

create table core.events (
  tenant_id uuid not null references core.tenants(id),
  seq bigint not null,
  id uuid not null default gen_random_uuid(),
  tipo text not null,
  origem text not null,
  dedupe_key text,
  payload jsonb not null,
  ts timestamptz not null default now(),
  prev_hash char(64) not null,
  hash char(64) not null,
  primary key (tenant_id, seq)
);
create unique index ux_events_dedupe
  on core.events (tenant_id, dedupe_key) where dedupe_key is not null;

create or replace function core.no_touch() returns trigger
language plpgsql as $$
begin
  raise exception 'core.events é append-only';
end $$;

create trigger trg_events_immutable
  before update or delete on core.events
  for each row execute function core.no_touch();

alter table core.events enable row level security;
create policy tenant_isolation on core.events
  using (tenant_id = current_setting('app.tenant_id')::uuid);
alter table core.events force row level security;
