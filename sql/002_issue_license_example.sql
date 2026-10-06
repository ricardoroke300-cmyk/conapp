-- Admin: substitua aluno@example.com pelo e-mail do aluno (não precisa de Auth).
-- Execute no SQL Editor. Guarde a chave retornada; o banco salva apenas seu hash.
with new_key as (select encode(extensions.gen_random_bytes(32),'hex') as secret),
issued as (
 insert into public.licenses(key_hash,email,daily_ai_limit)
 select encode(extensions.digest(secret,'sha256'),'hex'),lower(btrim('aluno@example.com')),30 from new_key
 returning id,user_id
)
select new_key.secret as license_key,issued.id,issued.user_id from new_key cross join issued;
