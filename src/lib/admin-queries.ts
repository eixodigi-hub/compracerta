import { supabase } from "@/integrations/supabase/client";

export type OverviewStats = {
  active_products: number;
  active_stores: number;
  unmatched_store_products: number;
  prices_updated_24h: number;
  prices_stale: number;
  recent_errors: Array<{
    id: string;
    store_id: string | null;
    store_name: string | null;
    status: string;
    error_message: string | null;
    started_at: string | null;
    finished_at: string | null;
  }>;
  last_run_by_store: Array<{
    store_id: string;
    store_name: string;
    last_started_at: string | null;
    last_finished_at: string | null;
    last_status: string | null;
    products_found: number | null;
    products_updated: number | null;
  }>;
};

export async function fetchOverview(): Promise<OverviewStats> {
  const { data, error } = await (supabase.rpc as unknown as (name: string) => Promise<{ data: unknown; error: Error | null }>)(
    "admin_overview_stats",
  );
  if (error) throw error;
  return data as OverviewStats;
}

export type CanonicalSuggestion = {
  id: string;
  name: string;
  brand: string | null;
  quantity: number | null;
  unit: string | null;
  barcode: string | null;
  image_url: string | null;
  category_name: string | null;
  score: number;
};

export async function suggestCanonical(storeProductId: string) {
  const { data, error } = await (supabase.rpc as unknown as (name: string, args: Record<string, unknown>) => Promise<{ data: unknown; error: Error | null }>)(
    "admin_suggest_canonical",
    { p_store_product_id: storeProductId },
  );
  if (error) throw error;
  return (data ?? []) as CanonicalSuggestion[];
}

export async function linkStoreProduct(storeProductId: string, canonicalId: string | null) {
  const { error } = await (supabase.rpc as unknown as (name: string, args: Record<string, unknown>) => Promise<{ data: unknown; error: Error | null }>)(
    "admin_link_store_product",
    { p_store_product_id: storeProductId, p_canonical_id: canonicalId },
  );
  if (error) throw error;
}
