-- Execute uma vez no SQL Editor do Supabase como administrador.
begin;
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;

create table public.licenses (
  id uuid primary key default gen_random_uuid(),
  key_hash text unique not null,
  user_id uuid unique not null references auth.users(id) on delete cascade,
  enabled boolean not null default true,
  expires_at timestamptz,
  active_session text,
  lease_until timestamptz,
  daily_ai_limit integer not null default 30 check (daily_ai_limit between 0 and 10000),
  created_at timestamptz not null default now()
);
create table public.ai_usage (
  user_id uuid not null references auth.users(id) on delete cascade,
  day date not null,
  calls integer not null default 0,
  primary key(user_id,day)
);
create table public.records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('edital','plan','booklet','board','question','simulation','attempt','essay')),
  payload jsonb not null check (jsonb_typeof(payload)='object' and octet_length(payload::text)<=4000000),
  created_at timestamptz not null default now()
);
create index records_owner_kind on public.records(user_id,kind,created_at);
alter table public.licenses enable row level security;
alter table public.ai_usage enable row level security;
alter table public.records enable row level security;
revoke all on public.licenses,public.ai_usage,public.records from anon,authenticated;
grant select,insert,update,delete on public.records to authenticated;

create function public.has_active_license() returns boolean
language sql stable security definer set search_path='' as $$
  select exists(select 1 from public.licenses l where l.user_id=auth.uid()
    and l.enabled and (l.expires_at is null or l.expires_at>now())
    and l.active_session=auth.jwt()->>'session_id' and l.lease_until>now());
$$;
create policy own_licensed_records on public.records for all to authenticated
  using (user_id=auth.uid() and public.has_active_license())
  with check (user_id=auth.uid() and public.has_active_license());

create function public.acquire_license(p_key text) returns boolean
language plpgsql security definer set search_path='' as $$
declare l public.licenses; sid text:=auth.jwt()->>'session_id';
begin
  if auth.uid() is null or sid is null or length(p_key)>200 then raise exception 'access_denied'; end if;
  select * into l from public.licenses
    where key_hash=encode(extensions.digest(p_key,'sha256'),'hex') and user_id=auth.uid() for update;
  if not found or not l.enabled or (l.expires_at is not null and l.expires_at<=now()) then raise exception 'access_denied'; end if;
  if l.active_session is not null and l.active_session<>sid and l.lease_until>now() then raise exception 'session_in_use'; end if;
  update public.licenses set active_session=sid,lease_until=now()+interval '2 minutes' where id=l.id;
  return true;
end;
$$;
create function public.heartbeat_license() returns boolean
language plpgsql security definer set search_path='' as $$
begin
  update public.licenses set lease_until=now()+interval '2 minutes'
    where user_id=auth.uid() and active_session=auth.jwt()->>'session_id' and enabled
    and (expires_at is null or expires_at>now());
  if not found then raise exception 'access_denied'; end if;
  return true;
end;
$$;
create function public.release_license() returns boolean
language plpgsql security definer set search_path='' as $$
begin
  update public.licenses set active_session=null,lease_until=null
    where user_id=auth.uid() and active_session=auth.jwt()->>'session_id';
  return true;
end;
$$;
create function public.reserve_ai_call() returns boolean
language plpgsql security definer set search_path='' as $$
declare lim integer; today date:=(now() at time zone 'UTC')::date;
begin
  if not public.has_active_license() then raise exception 'access_denied'; end if;
  select daily_ai_limit into lim from public.licenses where user_id=auth.uid();
  insert into public.ai_usage(user_id,day,calls) values(auth.uid(),today,0) on conflict do nothing;
  update public.ai_usage set calls=calls+1 where user_id=auth.uid() and day=today and calls<lim;
  if not found then raise exception 'daily_ai_limit'; end if;
  return true;
end;
$$;
revoke all on function public.has_active_license(),public.acquire_license(text),public.heartbeat_license(),public.release_license(),public.reserve_ai_call() from public,anon;
grant execute on function public.has_active_license(),public.acquire_license(text),public.heartbeat_license(),public.release_license(),public.reserve_ai_call() to authenticated;
commit;
