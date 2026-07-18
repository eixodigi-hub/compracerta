
-- store_product_collection_scopes
CREATE TABLE public.store_product_collection_scopes (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  store_product_id UUID NOT NULL REFERENCES public.store_products(id) ON DELETE CASCADE,
  scope_key TEXT NOT NULL,
  last_seen_at TIMESTAMPTZ,
  consecutive_misses INTEGER NOT NULL DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT store_product_collection_scopes_unique UNIQUE (store_product_id, scope_key)
);

CREATE INDEX idx_spcs_store_product ON public.store_product_collection_scopes(store_product_id);
CREATE INDEX idx_spcs_scope_key ON public.store_product_collection_scopes(scope_key);
CREATE INDEX idx_spcs_active ON public.store_product_collection_scopes(active);

GRANT ALL ON public.store_product_collection_scopes TO service_role;

ALTER TABLE public.store_product_collection_scopes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage collection scopes"
  ON public.store_product_collection_scopes
  FOR ALL
  TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE TRIGGER trg_spcs_updated_at
  BEFORE UPDATE ON public.store_product_collection_scopes
  FOR EACH ROW EXECUTE FUNCTION public.tg_set_updated_at();

-- category_sync_runs
CREATE TABLE public.category_sync_runs (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  store_id UUID NOT NULL REFERENCES public.stores(id) ON DELETE CASCADE,
  category_key TEXT NOT NULL,
  sync_token TEXT NOT NULL,
  collected_at TIMESTAMPTZ,
  seen_count INTEGER NOT NULL DEFAULT 0,
  missed_count INTEGER NOT NULL DEFAULT 0,
  unavailable_count INTEGER NOT NULL DEFAULT 0,
  restored_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'success',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT category_sync_runs_unique UNIQUE (store_id, category_key, sync_token)
);

CREATE INDEX idx_csr_store_category ON public.category_sync_runs(store_id, category_key);

GRANT ALL ON public.category_sync_runs TO service_role;

ALTER TABLE public.category_sync_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view category sync runs"
  ON public.category_sync_runs
  FOR SELECT
  TO authenticated
  USING (public.has_role(auth.uid(), 'admin'));

-- Finalization function (transactional, idempotent)
CREATE OR REPLACE FUNCTION public.finalize_category_sync(
  p_store_id UUID,
  p_category_key TEXT,
  p_sync_token TEXT,
  p_seen_external_ids TEXT[],
  p_collected_at TIMESTAMPTZ
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_existing public.category_sync_runs%ROWTYPE;
  v_seen_count INTEGER := 0;
  v_missed_count INTEGER := 0;
  v_unavailable_count INTEGER := 0;
  v_restored_count INTEGER := 0;
  r RECORD;
BEGIN
  -- Idempotency check
  SELECT * INTO v_existing
    FROM public.category_sync_runs
   WHERE store_id = p_store_id
     AND category_key = p_category_key
     AND sync_token = p_sync_token;

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status', 'success',
      'idempotent', true,
      'counts', jsonb_build_object(
        'seen', v_existing.seen_count,
        'missed', v_existing.missed_count,
        'marked_unavailable', v_existing.unavailable_count,
        'restored', v_existing.restored_count
      )
    );
  END IF;

  -- Lock all scopes for this store+category
  PERFORM 1
    FROM public.store_product_collection_scopes scp
    JOIN public.store_products sp ON sp.id = scp.store_product_id
   WHERE sp.store_id = p_store_id
     AND scp.scope_key = p_category_key
   FOR UPDATE;

  -- Process each scope in this store+category
  FOR r IN
    SELECT scp.id AS scope_id,
           scp.store_product_id,
           scp.consecutive_misses,
           scp.active AS scope_active,
           sp.external_id,
           sp.available AS product_available
      FROM public.store_product_collection_scopes scp
      JOIN public.store_products sp ON sp.id = scp.store_product_id
     WHERE sp.store_id = p_store_id
       AND scp.scope_key = p_category_key
  LOOP
    IF r.external_id = ANY(p_seen_external_ids) THEN
      -- Seen: reset
      UPDATE public.store_product_collection_scopes
         SET consecutive_misses = 0,
             active = true,
             last_seen_at = COALESCE(p_collected_at, now()),
             updated_at = now()
       WHERE id = r.scope_id;
      v_seen_count := v_seen_count + 1;

      -- Restore product availability if no active scope currently and product is unavailable
      IF NOT r.product_available THEN
        UPDATE public.store_products
           SET available = true, updated_at = now()
         WHERE id = r.store_product_id;

        UPDATE public.current_prices
           SET in_stock = true,
               collected_at = COALESCE(p_collected_at, now())
         WHERE store_product_id = r.store_product_id;

        INSERT INTO public.price_history (store_product_id, regular_price, promotional_price, effective_price, in_stock, collected_at)
        SELECT r.store_product_id, cp.regular_price, cp.promotional_price, cp.effective_price, true, COALESCE(p_collected_at, now())
          FROM public.current_prices cp
         WHERE cp.store_product_id = r.store_product_id;

        v_restored_count := v_restored_count + 1;
      END IF;
    ELSE
      -- Missed: increment
      UPDATE public.store_product_collection_scopes
         SET consecutive_misses = r.consecutive_misses + 1,
             active = CASE WHEN r.consecutive_misses + 1 >= 3 THEN false ELSE active END,
             updated_at = now()
       WHERE id = r.scope_id;
      v_missed_count := v_missed_count + 1;

      -- If this scope just became inactive AND no other active scope exists for the product,
      -- mark product unavailable (only if currently available).
      IF r.consecutive_misses + 1 >= 3 AND r.product_available THEN
        IF NOT EXISTS (
          SELECT 1 FROM public.store_product_collection_scopes other
           WHERE other.store_product_id = r.store_product_id
             AND other.id <> r.scope_id
             AND other.active = true
        ) THEN
          UPDATE public.store_products
             SET available = false, updated_at = now()
           WHERE id = r.store_product_id;

          UPDATE public.current_prices
             SET in_stock = false,
                 collected_at = COALESCE(p_collected_at, now())
           WHERE store_product_id = r.store_product_id;

          INSERT INTO public.price_history (store_product_id, regular_price, promotional_price, effective_price, in_stock, collected_at)
          SELECT r.store_product_id, cp.regular_price, cp.promotional_price, cp.effective_price, false, COALESCE(p_collected_at, now())
            FROM public.current_prices cp
           WHERE cp.store_product_id = r.store_product_id;

          v_unavailable_count := v_unavailable_count + 1;
        END IF;
      END IF;
    END IF;
  END LOOP;

  INSERT INTO public.category_sync_runs (
    store_id, category_key, sync_token, collected_at,
    seen_count, missed_count, unavailable_count, restored_count, status
  ) VALUES (
    p_store_id, p_category_key, p_sync_token, p_collected_at,
    v_seen_count, v_missed_count, v_unavailable_count, v_restored_count, 'success'
  );

  RETURN jsonb_build_object(
    'status', 'success',
    'idempotent', false,
    'counts', jsonb_build_object(
      'seen', v_seen_count,
      'missed', v_missed_count,
      'marked_unavailable', v_unavailable_count,
      'restored', v_restored_count
    )
  );
END;
$$;
