DROP POLICY IF EXISTS "Public sees active canonical products" ON public.canonical_products;
CREATE POLICY "Public sees active canonical products"
ON public.canonical_products
FOR SELECT
TO anon, authenticated
USING (active = true);

DROP POLICY IF EXISTS "Public sees active categories" ON public.categories;
CREATE POLICY "Public sees active categories"
ON public.categories
FOR SELECT
TO anon, authenticated
USING (active = true);

DROP POLICY IF EXISTS "Public sees active cities" ON public.cities;
CREATE POLICY "Public sees active cities"
ON public.cities
FOR SELECT
TO anon, authenticated
USING (active = true);

DROP POLICY IF EXISTS "Public sees active store products" ON public.store_products;
CREATE POLICY "Public sees active store products"
ON public.store_products
FOR SELECT
TO anon, authenticated
USING (active = true);

DROP POLICY IF EXISTS "Public sees active stores" ON public.stores;
CREATE POLICY "Public sees active stores"
ON public.stores
FOR SELECT
TO anon, authenticated
USING (active = true);