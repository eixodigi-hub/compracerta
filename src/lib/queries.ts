import { supabase } from "@/integrations/supabase/client";
import { queryOptions } from "@tanstack/react-query";

export const categoriesQuery = queryOptions({
  queryKey: ["categories"],
  queryFn: async () => {
    const { data, error } = await supabase
      .from("categories")
      .select("id, slug, name, icon, sort_order")
      .order("sort_order", { ascending: true });
    if (error) throw error;
    return data ?? [];
  },
});

export const marketsQuery = queryOptions({
  queryKey: ["markets"],
  queryFn: async () => {
    const { data, error } = await supabase
      .from("markets")
      .select("id, slug, name, address, logo_url")
      .eq("active", true)
      .order("name", { ascending: true });
    if (error) throw error;
    return data ?? [];
  },
});

export type OfferRow = {
  id: string;
  price: number;
  old_price: number | null;
  valid_until: string | null;
  collected_at: string;
  products: { id: string; name: string; brand: string | null; image_url: string | null } | null;
  markets: { id: string; name: string } | null;
};

export const topOffersQuery = queryOptions({
  queryKey: ["offers", "top"],
  queryFn: async () => {
    const { data, error } = await supabase
      .from("prices")
      .select(
        "id, price, old_price, valid_until, collected_at, products!inner(id, name, brand, image_url), markets!inner(id, name)",
      )
      .eq("is_promo", true)
      .order("collected_at", { ascending: false })
      .limit(6);
    if (error) throw error;
    return (data ?? []) as unknown as OfferRow[];
  },
});

export const lastUpdatedQuery = queryOptions({
  queryKey: ["prices", "last-updated"],
  queryFn: async () => {
    const { data, error } = await supabase
      .from("prices")
      .select("collected_at")
      .order("collected_at", { ascending: false })
      .limit(1)
      .maybeSingle();
    if (error) throw error;
    return data?.collected_at ?? null;
  },
});
