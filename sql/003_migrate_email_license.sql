-- BANCO ANTIGO já criado pela versão com Supabase Auth: execute somente este arquivo.
-- Mantém IDs, registros, hash das licenças, validade e cotas. Invalida sessões antigas.
begin;
alter table public.licenses add column email text;
alter table public.licenses add column session_hash text;
alter table public.licenses add column session_expires_at timestamptz;
-- Único uso da tabela antiga de Auth: copiar e-mail na migração, não no login.
update public.licenses l set email=lower(btrim(u.email)) from auth.users u where u.id=l.user_id;
-- Se um proprietário não tiver e-mail válido, a migração inteira é revertida.
alter table public.licenses alter column email set not null;
alter table public.licenses add constraint licenses_email_key unique(email);
alter table public.licenses add constraint licenses_email_check check(email=lower(btrim(email)) and position('@' in email)>1);
alter table public.licenses add constraint licenses_session_hash_key unique(session_hash);
alter table public.licenses drop constraint licenses_user_id_fkey;
alter table public.licenses alter column user_id set default gen_random_uuid();
alter table public.records drop constraint records_user_id_fkey;
alter table public.ai_usage drop constraint ai_usage_user_id_fkey;
alter table public.records add constraint records_user_id_fkey foreign key(user_id) references public.licenses(user_id) on delete cascade;
alter table public.ai_usage add constraint ai_usage_user_id_fkey foreign key(user_id) references public.licenses(user_id) on delete cascade;
update public.licenses set active_session=null,lease_until=null;
revoke all on public.licenses,public.ai_usage,public.records from anon,authenticated;
drop policy if exists own_licensed_records on public.records;
drop function if exists public.acquire_license(text);
drop function if exists public.heartbeat_license();
drop function if exists public.release_license();
drop function if exists public.reserve_ai_call();
drop function if exists public.has_active_license();

create schema if not exists private;
revoke all on schema private from public,anon,authenticated;

create or replace function public.license_login(p_email text,p_key text) returns jsonb
language plpgsql security definer set search_path='' as $$
declare l public.licenses; token text;
begin
  if p_email is null or p_key is null or length(p_email)>254 or length(p_key)<16 or length(p_key)>200 then raise exception 'access_denied'; end if;
  select * into l from public.licenses where email=lower(btrim(p_email))
    and key_hash=encode(extensions.digest(p_key,'sha256'),'hex') for update;
  if not found or not l.enabled or (l.expires_at is not null and l.expires_at<=now()) then raise exception 'access_denied'; end if;
  if l.session_hash is not null and l.lease_until>now() and l.session_expires_at>now() then raise exception 'session_in_use'; end if;
  token:=encode(extensions.gen_random_bytes(32),'hex');
  update public.licenses set session_hash=encode(extensions.digest(token,'sha256'),'hex'),
    active_session=gen_random_uuid()::text,lease_until=now()+interval '2 minutes',session_expires_at=now()+interval '8 hours' where id=l.id;
  return jsonb_build_object('token',token,'user_id',l.user_id);
end;
$$;

create or replace function private.require_license_session(p_token text,p_allow_renew boolean default false) returns public.licenses
language plpgsql security definer set search_path='' as $$
declare l public.licenses;
begin
  if p_token is null or length(p_token)<>64 then raise exception 'access_denied'; end if;
  select * into l from public.licenses where session_hash=encode(extensions.digest(p_token,'sha256'),'hex') for update;
  if not found or not l.enabled or (l.expires_at is not null and l.expires_at<=now())
    or l.session_expires_at<=now() or l.session_expires_at is null
    or (not p_allow_renew and (l.lease_until<=now() or l.lease_until is null)) then raise exception 'access_denied'; end if;
  return l;
end;
$$;
revoke all on function private.require_license_session(text,boolean) from public,anon,authenticated;

create or replace function public.license_heartbeat(p_token text) returns boolean
language plpgsql security definer set search_path='' as $$
declare l public.licenses;
begin
  l:=private.require_license_session(p_token,true);
  update public.licenses set lease_until=least(now()+interval '2 minutes',session_expires_at) where id=l.id;
  return true;
end;
$$;
create or replace function public.license_logout(p_token text) returns boolean
language plpgsql security definer set search_path='' as $$
begin
  if p_token is null or length(p_token)<>64 then raise exception 'access_denied'; end if;
  update public.licenses set session_hash=null,active_session=null,lease_until=null,session_expires_at=null
    where session_hash=encode(extensions.digest(p_token,'sha256'),'hex');
  return true;
end;
$$;
create or replace function public.license_records_list(p_token text,p_kind text,p_offset integer default 0,p_limit integer default 500)
returns setof public.records language plpgsql security definer set search_path='' as $$
declare l public.licenses;
begin
  l:=private.require_license_session(p_token);
  if p_offset<0 or p_limit<1 or p_limit>500 then raise exception 'invalid_pagination'; end if;
  return query select r.* from public.records r where r.user_id=l.user_id and r.kind=p_kind
    order by r.created_at,r.id offset p_offset limit p_limit;
end;
$$;
create or replace function public.license_record_put(p_token text,p_kind text,p_payload jsonb,p_id uuid) returns jsonb
language plpgsql security definer set search_path='' as $$
declare l public.licenses; saved public.records;
begin
  l:=private.require_license_session(p_token);
  if p_id is null or p_payload is null then raise exception 'invalid_record'; end if;
  insert into public.records(id,user_id,kind,payload) values(p_id,l.user_id,p_kind,p_payload)
    on conflict(id) do update set payload=excluded.payload
    where public.records.user_id=l.user_id and public.records.kind=p_kind returning * into saved;
  if not found then raise exception 'access_denied'; end if;
  return to_jsonb(saved);
end;
$$;
create or replace function public.license_reserve_ai(p_token text) returns boolean
language plpgsql security definer set search_path='' as $$
declare l public.licenses; today date:=(now() at time zone 'UTC')::date;
begin
  l:=private.require_license_session(p_token);
  insert into public.ai_usage(user_id,day,calls) values(l.user_id,today,0) on conflict do nothing;
  update public.ai_usage set calls=calls+1 where user_id=l.user_id and day=today and calls<l.daily_ai_limit;
  if not found then raise exception 'daily_ai_limit'; end if;
  return true;
end;
$$;
revoke all on function public.license_login(text,text),public.license_heartbeat(text),public.license_logout(text),public.license_records_list(text,text,integer,integer),public.license_record_put(text,text,jsonb,uuid),public.license_reserve_ai(text) from public,authenticated;
grant execute on function public.license_login(text,text),public.license_heartbeat(text),public.license_logout(text),public.license_records_list(text,text,integer,integer),public.license_record_put(text,text,jsonb,uuid),public.license_reserve_ai(text) to anon;

commit;
