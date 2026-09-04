import { supabase } from "@/integrations/supabase/client";
import { queryOptions } from "@tanstack/react-query";

export const citiesQuery = queryOptions({
  queryKey: ["cities", "active"],
  queryFn: async () => {
    const { data, error } = await supabase
      .from("cities")
      .select("id, slug, name, state")
      .eq("active", true)
      .order("name", { ascending: true });
    if (error) throw error;
    return data ?? [];
  },
});

export const categoriesQuery = queryOptions({
  queryKey: ["categories"],
  queryFn: async () => {
    const { data, error } = await supabase
      .from("categories")
      .select("id, slug, name, icon")
      .eq("active", true)
      .order("name", { ascending: true });
    if (error) throw error;
    return data ?? [];
  },
});

export const marketsQuery = queryOptions({
  queryKey: ["stores"],
  queryFn: async () => {
    const { data, error } = await supabase
      .from("stores")
      .select("id, slug, name, address, logo_url")
      .eq("active", true)
      .order("name", { ascending: true });
    if (error) throw error;
    return data ?? [];
  },
});

export type OfferRow = {
  id: string;
  regular_price: number;
  promotional_price: number | null;
  effective_price: number;
  promotion_end_at: string | null;
  collected_at: string;
  store_products: {
    id: string;
    external_name: string;
    image_url: string | null;
    stores: { id: string; name: string } | null;
    canonical_products: { id: string; name: string; brand: string | null; image_url: string | null } | null;
  } | null;
};

export const topOffersQuery = queryOptions({
  queryKey: ["offers", "top"],
  queryFn: async () => {
    const { data, error } = await supabase
      .from("current_prices")
      .select(
        "id, regular_price, promotional_price, effective_price, promotion_end_at, collected_at, store_products!inner(id, external_name, image_url, stores!inner(id, name), canonical_products(id, name, brand, image_url))",
      )
      .not("promotional_price", "is", null)
      .eq("in_stock", true)
      .order("collected_at", { ascending: false })
      .limit(6);
    if (error) throw error;
    return (data ?? []) as unknown as OfferRow[];
  },
});

export type HomeCategoryProductRow = {
  category_id: string;
  category_slug: string;
  category_name: string;
  category_icon: string | null;
  id: string;
  name: string;
  brand: string | null;
  quantity: number | null;
  unit: string | null;
  image_url: string | null;
  barcode: string | null;
  min_price: number;
  reference_price: number | null;
  max_discount_pct: number;
  market_count: number;
  last_updated: string;
  has_promotion: boolean;
  offers: Array<{
    store_id: string;
    store_name: string;
    effective_price: number | null;
    promotion_end_at: string | null;
  }>;
};

export type HomeCategorySection = {
  category_id: string;
  category_slug: string;
  category_name: string;
  category_icon: string | null;
  products: HomeCategoryProductRow[];
};

const HOME_PRODUCTS_PER_CATEGORY = 10;

export const homeCategoryFeedQuery = queryOptions({
  queryKey: ["home", "category-feed", HOME_PRODUCTS_PER_CATEGORY],
  queryFn: async () => {
    const { data, error } = await supabase.rpc("home_category_feed", {
      products_per_category: HOME_PRODUCTS_PER_CATEGORY,
    });
    if (error) throw error;
    const rows = (data ?? []) as HomeCategoryProductRow[];
    const sections = new Map<string, HomeCategorySection>();
    for (const row of rows) {
      let section = sections.get(row.category_id);
      if (!section) {
        section = {
          category_id: row.category_id,
          category_slug: row.category_slug,
          category_name: row.category_name,
          category_icon: row.category_icon,
          products: [],
        };
        sections.set(row.category_id, section);
      }
      section.products.push(row);
    }
    return Array.from(sections.values());
  },
});

export const lastUpdatedQuery = queryOptions({
  queryKey: ["current_prices", "last-updated"],
  queryFn: async () => {
    const { data, error } = await supabase
      .from("current_prices")
      .select("collected_at")
      .order("collected_at", { ascending: false })
      .limit(1)
      .maybeSingle();
    if (error) throw error;
    return data?.collected_at ?? null;
  },
});
