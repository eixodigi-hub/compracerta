import { supabase } from "@/integrations/supabase/client";
import { queryOptions } from "@tanstack/react-query";

export type SortBy = "relevance" | "price_asc" | "discount_desc" | "name_asc" | "recent";

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
  offers: SearchProductOffer[];
  is_canonical: boolean;
};

export type SearchProductOffer = {
  store_id: string;
  store_name: string;
  store_slug: string | null;
  store_logo_url: string | null;
  store_product_id: string;
  external_name: string;
  product_url: string | null;
  regular_price: number | null;
  promotional_price: number | null;
  effective_price: number | null;
  promotion_text: string | null;
  promotion_end_at: string | null;
  collected_at: string;
  is_lowest: boolean;
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
      return ((data ?? []) as SearchProductRow[]).map((product) => ({
        ...product,
        offers: Array.isArray(product.offers) ? product.offers : [],
      }));
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
