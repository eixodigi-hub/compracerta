import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

export type ProductOffer = {
  store_id: string;
  store_name: string;
  store_slug: string;
  logo_url: string | null;
  website_url: string | null;
  product_url: string | null;
  external_name: string | null;
  available: boolean | null;
  regular_price: number | null;
  promotional_price: number | null;
  effective_price: number | null;
  in_stock: boolean | null;
  promotion_text: string | null;
  promotion_end_at: string | null;
  collected_at: string | null;
};

export type ProductDetail = {
  id: string;
  name: string;
  brand: string | null;
  quantity: number | null;
  unit: string | null;
  image_url: string | null;
  description: string | null;
  category_name: string | null;
  category_slug: string | null;
};

export type ProductDetailPayload = {
  product: ProductDetail | null;
  offers: ProductOffer[];
  last_updated: string | null;
};

export type PricePoint = {
  day: string;
  min_price: number;
  avg_price: number;
  max_price: number;
};

export type PriceStats = {
  min: number | null;
  max: number | null;
  avg: number | null;
  sample: number;
  current: number | null;
  variation_pct: number | null;
};

export const productDetailOptions = (id: string) =>
  queryOptions({
    queryKey: ["product-detail", id],
    queryFn: async (): Promise<ProductDetailPayload> => {
      const { data, error } = await supabase.rpc("get_product_detail", { p_product_id: id });
      if (error) throw error;
      return (data as unknown as ProductDetailPayload) ?? { product: null, offers: [], last_updated: null };
    },
  });

export const priceHistoryOptions = (id: string, days = 30) =>
  queryOptions({
    queryKey: ["price-history", id, days],
    queryFn: async (): Promise<PricePoint[]> => {
      const { data, error } = await supabase.rpc("get_price_history", { p_product_id: id, p_days: days });
      if (error) throw error;
      return (data as unknown as PricePoint[]) ?? [];
    },
  });

export const priceStatsOptions = (id: string, days = 30) =>
  queryOptions({
    queryKey: ["price-stats", id, days],
    queryFn: async (): Promise<PriceStats> => {
      const { data, error } = await supabase.rpc("get_price_stats", { p_product_id: id, p_days: days });
      if (error) throw error;
      return (data as unknown as PriceStats) ?? { min: null, max: null, avg: null, sample: 0, current: null, variation_pct: null };
    },
  });
