
-- =========================================================
-- Reset old tables (early-stage restructure)
-- =========================================================
DROP VIEW IF EXISTS public.latest_prices CASCADE;
DROP TABLE IF EXISTS public.shopping_list_items CASCADE;
DROP TABLE IF EXISTS public.shopping_lists CASCADE;
DROP TABLE IF EXISTS public.prices CASCADE;
DROP TABLE IF EXISTS public.products CASCADE;
DROP TABLE IF EXISTS public.markets CASCADE;
DROP TABLE IF EXISTS public.categories CASCADE;

-- =========================================================
-- Extensions for accent-insensitive text search
-- =========================================================
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;

-- Immutable wrapper so we can use unaccent inside an index expression
CREATE OR REPLACE FUNCTION public.immutable_unaccent(text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE STRICT
SET search_path = extensions, public
AS $$
  SELECT extensions.unaccent('extensions.unaccent'::regdictionary, lower($1))
$$;

-- =========================================================
-- cities
-- =========================================================
CREATE TABLE public.cities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  state text NOT NULL,
  slug text NOT NULL UNIQUE,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON public.cities TO anon, authenticated;
GRANT ALL ON public.cities TO service_role;
ALTER TABLE public.cities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Cities are viewable by everyone"
  ON public.cities FOR SELECT USING (true);
CREATE POLICY "Admins manage cities"
  ON public.cities FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- Seed the launch city
INSERT INTO public.cities (name, state, slug)
VALUES ('Marília', 'SP', 'marilia-sp');

-- =========================================================
-- stores
-- =========================================================
CREATE TABLE public.stores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  city_id uuid NOT NULL REFERENCES public.cities(id) ON DELETE RESTRICT,
  name text NOT NULL,
  slug text NOT NULL,
  logo_url text,
  website_url text,
  address text,
  active boolean NOT NULL DEFAULT true,
  last_successful_sync_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (city_id, slug)
);
CREATE INDEX idx_stores_city_id ON public.stores(city_id);
GRANT SELECT ON public.stores TO anon, authenticated;
GRANT ALL ON public.stores TO service_role;
ALTER TABLE public.stores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Stores are viewable by everyone"
  ON public.stores FOR SELECT USING (true);
CREATE POLICY "Admins manage stores"
  ON public.stores FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
CREATE TRIGGER stores_updated_at BEFORE UPDATE ON public.stores
  FOR EACH ROW EXECUTE FUNCTION public.tg_set_updated_at();

-- =========================================================
-- categories
-- =========================================================
CREATE TABLE public.categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  slug text NOT NULL UNIQUE,
  icon text,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON public.categories TO anon, authenticated;
GRANT ALL ON public.categories TO service_role;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Categories are viewable by everyone"
  ON public.categories FOR SELECT USING (true);
CREATE POLICY "Admins manage categories"
  ON public.categories FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

INSERT INTO public.categories (name, slug, icon) VALUES
  ('Alimentos',      'alimentos',      'ShoppingBasket'),
  ('Bebidas',        'bebidas',        'CupSoda'),
  ('Higiene pessoal','higiene-pessoal','Bath'),
  ('Limpeza',        'limpeza',        'SprayCan'),
  ('Bebês',          'bebes',          'Baby'),
  ('Pet',            'pet',            'PawPrint'),
  ('Congelados',     'congelados',     'Snowflake'),
  ('Padaria',        'padaria',        'Croissant');

-- =========================================================
-- canonical_products
-- =========================================================
CREATE TABLE public.canonical_products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id uuid REFERENCES public.categories(id) ON DELETE SET NULL,
  name text NOT NULL,
  brand text,
  quantity numeric(12,3),
  unit text,
  barcode text UNIQUE,
  image_url text,
  description text,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_canonical_products_name    ON public.canonical_products(name);
CREATE INDEX idx_canonical_products_brand   ON public.canonical_products(brand);
CREATE INDEX idx_canonical_products_barcode ON public.canonical_products(barcode);
CREATE INDEX idx_canonical_products_name_trgm
  ON public.canonical_products
  USING gin (public.immutable_unaccent(name) extensions.gin_trgm_ops);
CREATE INDEX idx_canonical_products_brand_trgm
  ON public.canonical_products
  USING gin (public.immutable_unaccent(brand) extensions.gin_trgm_ops);

GRANT SELECT ON public.canonical_products TO anon, authenticated;
GRANT ALL ON public.canonical_products TO service_role;
ALTER TABLE public.canonical_products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Canonical products are viewable by everyone"
  ON public.canonical_products FOR SELECT USING (true);
CREATE POLICY "Admins manage canonical products"
  ON public.canonical_products FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
CREATE TRIGGER canonical_products_updated_at BEFORE UPDATE ON public.canonical_products
  FOR EACH ROW EXECUTE FUNCTION public.tg_set_updated_at();

-- =========================================================
-- store_products
-- =========================================================
CREATE TABLE public.store_products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id uuid NOT NULL REFERENCES public.stores(id) ON DELETE CASCADE,
  canonical_product_id uuid REFERENCES public.canonical_products(id) ON DELETE SET NULL,
  external_id text NOT NULL,
  external_name text NOT NULL,
  product_url text,
  image_url text,
  brand_raw text,
  quantity_raw text,
  unit_raw text,
  barcode_raw text,
  active boolean NOT NULL DEFAULT true,
  available boolean NOT NULL DEFAULT true,
  last_seen_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (store_id, external_id)
);
CREATE INDEX idx_store_products_external_name ON public.store_products(external_name);
CREATE INDEX idx_store_products_store_id ON public.store_products(store_id);
CREATE INDEX idx_store_products_canonical_product_id ON public.store_products(canonical_product_id);
CREATE INDEX idx_store_products_external_name_trgm
  ON public.store_products
  USING gin (public.immutable_unaccent(external_name) extensions.gin_trgm_ops);

GRANT SELECT ON public.store_products TO anon, authenticated;
GRANT ALL ON public.store_products TO service_role;
ALTER TABLE public.store_products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Store products are viewable by everyone"
  ON public.store_products FOR SELECT USING (true);
CREATE POLICY "Admins manage store products"
  ON public.store_products FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
CREATE TRIGGER store_products_updated_at BEFORE UPDATE ON public.store_products
  FOR EACH ROW EXECUTE FUNCTION public.tg_set_updated_at();

-- =========================================================
-- current_prices (one row per store_product)
-- =========================================================
CREATE TABLE public.current_prices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_product_id uuid NOT NULL UNIQUE
    REFERENCES public.store_products(id) ON DELETE CASCADE,
  regular_price numeric(12,2) NOT NULL,
  promotional_price numeric(12,2),
  effective_price numeric(12,2) NOT NULL,
  price_per_unit numeric(12,4),
  promotion_text text,
  promotion_end_at timestamptz,
  in_stock boolean NOT NULL DEFAULT true,
  collected_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_current_prices_effective_price ON public.current_prices(effective_price);

GRANT SELECT ON public.current_prices TO anon, authenticated;
GRANT ALL ON public.current_prices TO service_role;
ALTER TABLE public.current_prices ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Current prices are viewable by everyone"
  ON public.current_prices FOR SELECT USING (true);
CREATE POLICY "Admins manage current prices"
  ON public.current_prices FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
CREATE TRIGGER current_prices_updated_at BEFORE UPDATE ON public.current_prices
  FOR EACH ROW EXECUTE FUNCTION public.tg_set_updated_at();

-- =========================================================
-- price_history
-- =========================================================
CREATE TABLE public.price_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_product_id uuid NOT NULL REFERENCES public.store_products(id) ON DELETE CASCADE,
  regular_price numeric(12,2) NOT NULL,
  promotional_price numeric(12,2),
  effective_price numeric(12,2) NOT NULL,
  in_stock boolean NOT NULL DEFAULT true,
  collected_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_price_history_product_time
  ON public.price_history(store_product_id, collected_at DESC);

GRANT SELECT ON public.price_history TO anon, authenticated;
GRANT ALL ON public.price_history TO service_role;
ALTER TABLE public.price_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Price history is viewable by everyone"
  ON public.price_history FOR SELECT USING (true);
CREATE POLICY "Admins manage price history"
  ON public.price_history FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- =========================================================
-- profiles (recreate with full_name + city_id)
-- Role stays in user_roles for security.
-- =========================================================
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS full_name text,
  ADD COLUMN IF NOT EXISTS city_id uuid REFERENCES public.cities(id) ON DELETE SET NULL;

-- Backfill full_name from existing display_name
UPDATE public.profiles SET full_name = display_name WHERE full_name IS NULL;

-- Default new profiles to Marília
UPDATE public.profiles p
SET city_id = c.id
FROM public.cities c
WHERE p.city_id IS NULL AND c.slug = 'marilia-sp';

-- Update handle_new_user to populate full_name + default city
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  default_city uuid;
BEGIN
  SELECT id INTO default_city FROM public.cities WHERE slug = 'marilia-sp' LIMIT 1;
  INSERT INTO public.profiles (id, display_name, full_name, city_id)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'display_name', split_part(NEW.email, '@', 1)),
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'display_name', split_part(NEW.email, '@', 1)),
    default_city
  );
  RETURN NEW;
END;
$$;

-- Ensure trigger exists on auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- =========================================================
-- shopping_lists (recreate with city_id)
-- =========================================================
CREATE TABLE public.shopping_lists (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name text NOT NULL DEFAULT 'Minha lista',
  city_id uuid REFERENCES public.cities(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_shopping_lists_user_id ON public.shopping_lists(user_id);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.shopping_lists TO authenticated;
GRANT ALL ON public.shopping_lists TO service_role;
ALTER TABLE public.shopping_lists ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own shopping lists"
  ON public.shopping_lists FOR ALL TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
CREATE TRIGGER shopping_lists_updated_at BEFORE UPDATE ON public.shopping_lists
  FOR EACH ROW EXECUTE FUNCTION public.tg_set_updated_at();

-- =========================================================
-- shopping_list_items
-- =========================================================
CREATE TABLE public.shopping_list_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shopping_list_id uuid NOT NULL REFERENCES public.shopping_lists(id) ON DELETE CASCADE,
  canonical_product_id uuid NOT NULL REFERENCES public.canonical_products(id) ON DELETE CASCADE,
  quantity numeric(10,2) NOT NULL DEFAULT 1 CHECK (quantity > 0),
  allow_similar_products boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (shopping_list_id, canonical_product_id)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.shopping_list_items TO authenticated;
GRANT ALL ON public.shopping_list_items TO service_role;
ALTER TABLE public.shopping_list_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage items on own lists"
  ON public.shopping_list_items FOR ALL TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.shopping_lists l
    WHERE l.id = shopping_list_items.shopping_list_id AND l.user_id = auth.uid()
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM public.shopping_lists l
    WHERE l.id = shopping_list_items.shopping_list_id AND l.user_id = auth.uid()
  ));
CREATE TRIGGER shopping_list_items_updated_at BEFORE UPDATE ON public.shopping_list_items
  FOR EACH ROW EXECUTE FUNCTION public.tg_set_updated_at();

-- =========================================================
-- ingestion_runs (scraper activity log)
-- =========================================================
DO $$ BEGIN
  CREATE TYPE public.ingestion_status AS ENUM ('running','success','partial','failed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE public.ingestion_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id uuid NOT NULL REFERENCES public.stores(id) ON DELETE CASCADE,
  status public.ingestion_status NOT NULL DEFAULT 'running',
  products_found integer NOT NULL DEFAULT 0,
  products_updated integer NOT NULL DEFAULT 0,
  error_message text,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE INDEX idx_ingestion_runs_store_started ON public.ingestion_runs(store_id, started_at DESC);
GRANT SELECT ON public.ingestion_runs TO authenticated;
GRANT ALL ON public.ingestion_runs TO service_role;
ALTER TABLE public.ingestion_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Admins view ingestion runs"
  ON public.ingestion_runs FOR SELECT TO authenticated
  USING (public.has_role(auth.uid(), 'admin'));
CREATE POLICY "Admins manage ingestion runs"
  ON public.ingestion_runs FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- =========================================================
-- Helper: text search on canonical products (accent + partial word tolerant)
-- =========================================================
CREATE OR REPLACE FUNCTION public.search_canonical_products(
  q text,
  max_results integer DEFAULT 30
)
RETURNS SETOF public.canonical_products
LANGUAGE sql
STABLE
SET search_path = public, extensions
AS $$
  SELECT cp.*
  FROM public.canonical_products cp
  WHERE cp.active = true
    AND (
      public.immutable_unaccent(cp.name)  ILIKE '%' || public.immutable_unaccent(q) || '%'
      OR public.immutable_unaccent(cp.brand) ILIKE '%' || public.immutable_unaccent(q) || '%'
    )
  ORDER BY
    similarity(public.immutable_unaccent(cp.name), public.immutable_unaccent(q)) DESC
  LIMIT max_results;
$$;
