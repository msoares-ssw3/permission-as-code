-- Role de aplicação: não-superuser, sem bypass de RLS, dono de core.events.
-- Com FORCE RLS, até o owner fica sujeito à política de tenant — superuser
-- ignora RLS sempre, por isso a aplicação NÃO conecta como superuser.
-- Jobs de sistema (migrations, fixtures) seguem no role administrador,
-- com bypass explícito e justificado.
-- Senha padrão de dev (par do docker-compose); produção troca via secrets.
do $$
begin
  if not exists (select from pg_roles where rolname = 'simbios3_app') then
    create role simbios3_app login password 'simbios3_app' nosuperuser nobypassrls;
  end if;
end $$;

grant usage on schema core to simbios3_app;
alter table core.tenants owner to simbios3_app;
alter table core.events owner to simbios3_app;
alter function core.no_touch() owner to simbios3_app;
