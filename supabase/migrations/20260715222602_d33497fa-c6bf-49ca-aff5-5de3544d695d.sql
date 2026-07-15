
-- 1) View com security_invoker
ALTER VIEW public.latest_prices SET (security_invoker = on);

-- 2) Mover pg_trgm para o schema extensions
CREATE SCHEMA IF NOT EXISTS extensions;
GRANT USAGE ON SCHEMA extensions TO anon, authenticated, service_role;
ALTER EXTENSION pg_trgm SET SCHEMA extensions;

-- 3) Restringir EXECUTE das funções SECURITY DEFINER
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.has_role(UUID, public.app_role) FROM PUBLIC, anon;
-- authenticated ainda precisa executar has_role (usada em RLS)
GRANT EXECUTE ON FUNCTION public.has_role(UUID, public.app_role) TO authenticated;
