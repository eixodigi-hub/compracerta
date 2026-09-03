REVOKE ALL ON FUNCTION public.auto_link_or_create_canonical(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.auto_link_or_create_canonical(uuid) TO service_role;