
REVOKE ALL ON FUNCTION public.finalize_category_sync(UUID, TEXT, TEXT, TEXT[], TIMESTAMPTZ) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.finalize_category_sync(UUID, TEXT, TEXT, TEXT[], TIMESTAMPTZ) FROM anon;
REVOKE ALL ON FUNCTION public.finalize_category_sync(UUID, TEXT, TEXT, TEXT[], TIMESTAMPTZ) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.finalize_category_sync(UUID, TEXT, TEXT, TEXT[], TIMESTAMPTZ) TO service_role;
