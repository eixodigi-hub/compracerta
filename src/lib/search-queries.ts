import { supabase } from "@/integrations/supabase/client";
import { queryOptions } from "@tanstack/react-query";

export type SortBy = "price_asc" | "discount_desc" | "name_asc" | "recent";

export type SearchFilters = {
  q?: string;
  category?: string;
  brand?: string;
  storeId?: string;
  onlyAvailable?: boolean;
  onlyOffers?: boolean;
  minPrice?: number;
  maxPrice?: number;
  sortBy?: SortBy;
  limit?: number;
  offset?: number;
};

export type SearchProductRow = {
  id: string;
  name: string;
  brand: string | null;
  quantity: number | null;
  unit: string | null;
  image_url: string | null;
  barcode: string | null;
  category_id: string | null;
  category_name: string | null;
  category_slug: string | null;
  min_price: number;
  reference_price: number | null;
  max_discount_pct: number;
  market_count: number;
  last_updated: string;
  has_promotion: boolean;
};

export function searchProductsQuery(filters: SearchFilters) {
  return queryOptions({
    queryKey: ["search-products", filters],
    queryFn: async () => {
      const { data, error } = await supabase.rpc("search_products", {
        q: filters.q?.trim() || undefined,
        category_slug: filters.category || undefined,
        brand_filter: filters.brand || undefined,
        store_id_filter: filters.storeId || undefined,
        only_available: !!filters.onlyAvailable,
        only_offers: !!filters.onlyOffers,
        min_price: filters.minPrice ?? undefined,
        max_price: filters.maxPrice ?? undefined,
        sort_by: filters.sortBy ?? "price_asc",
        limit_count: filters.limit ?? 30,
        offset_count: filters.offset ?? 0,
      });
      if (error) throw error;
      return (data ?? []) as SearchProductRow[];
    },
  });
}

export const brandsQuery = queryOptions({
  queryKey: ["search-brands"],
  queryFn: async () => {
    const { data, error } = await supabase.rpc("list_search_brands");
    if (error) throw error;
    return ((data ?? []) as { brand: string }[]).map((r) => r.brand);
  },
  staleTime: 5 * 60_000,
});
