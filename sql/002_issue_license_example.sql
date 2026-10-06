-- Admin: substitua o UUID pelo ID de um usuário criado em Authentication > Users.
-- Executar no SQL Editor, nunca dentro do app. Copie a chave retornada uma vez.
do $$
begin
  if not exists(select 1 from auth.users where id='00000000-0000-0000-0000-000000000000') then
    raise exception 'Substitua o UUID por um usuário real antes de executar';
  end if;
end $$;
with new_key as (select encode(extensions.gen_random_bytes(32),'hex') as secret),
issued as (
  insert into public.licenses(key_hash,user_id,daily_ai_limit)
  select encode(extensions.digest(secret,'sha256'),'hex'),'00000000-0000-0000-0000-000000000000'::uuid,30 from new_key
  returning id
)
select new_key.secret as license_key,issued.id from new_key cross join issued;
