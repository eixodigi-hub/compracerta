
-- Tighten public SELECT to active rows only; admins still see everything.

DROP POLICY IF EXISTS "Cities are viewable by everyone" ON public.cities;
CREATE POLICY "Public sees active cities"
  ON public.cities FOR SELECT
  USING (active = true OR public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Stores are viewable by everyone" ON public.stores;
CREATE POLICY "Public sees active stores"
  ON public.stores FOR SELECT
  USING (active = true OR public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Categories are viewable by everyone" ON public.categories;
CREATE POLICY "Public sees active categories"
  ON public.categories FOR SELECT
  USING (active = true OR public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Canonical products are viewable by everyone" ON public.canonical_products;
CREATE POLICY "Public sees active canonical products"
  ON public.canonical_products FOR SELECT
  USING (active = true OR public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Store products are viewable by everyone" ON public.store_products;
CREATE POLICY "Public sees active store products"
  ON public.store_products FOR SELECT
  USING (active = true OR public.has_role(auth.uid(), 'admin'));

-- Prices remain publicly readable (no active flag on these tables).
-- Existing policies "Current prices are viewable by everyone" and
-- "Price history is viewable by everyone" already cover this and stay in place.

-- Ensure only service_role can insert into ingestion_runs from outside the app
-- (admins may still view/manage via existing policies; no anon grant).
REVOKE INSERT, UPDATE, DELETE ON public.ingestion_runs FROM authenticated;
