-- Concede o papel admin para a conta cadastrada no site novo.
insert into public.user_roles (user_id, role)
select id, 'admin'::public.app_role
from auth.users
where email = 'willbrother22@gmail.com'
on conflict do nothing;
