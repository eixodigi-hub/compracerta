import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

export type ShoppingList = {
  id: string;
  name: string;
  city_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ShoppingListItem = {
  id: string;
  shopping_list_id: string;
  canonical_product_id: string;
  quantity: number;
  allow_similar_products: boolean;
  product?: {
    id: string;
    name: string;
    brand: string | null;
    quantity: number | null;
    unit: string | null;
    image_url: string | null;
  } | null;
};

export type ComparisonLine = {
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: number | null;
  line_total: number | null;
  missing: boolean;
};

export type StoreSummary = {
  store_id: string;
  store_name: string;
  store_slug: string;
  logo_url: string | null;
  has_missing: boolean;
  total_all: number | null;
  lines: ComparisonLine[];
  missing_names: string[] | null;
};

export type BestPerItemLine = {
  product_id: string;
  product_name: string;
  quantity: number;
  store_id: string;
  store_name: string;
  unit_price: number;
  line_total: number;
};

export type ComparisonPayload = {
  items: Array<{ product_id: string; product_name: string; product_brand: string | null; image_url: string | null; quantity: number; allow_similar_products: boolean }>;
  stores: StoreSummary[];
  best_complete: { store_id: string; store_name: string; total_all: number } | null;
  per_item: {
    total: number | null;
    stores_needed: number;
    breakdown: BestPerItemLine[];
    missing_names: string[] | null;
  } | null;
  savings: number | null;
};

export const listsOptions = () =>
  queryOptions({
    queryKey: ["shopping-lists"],
    queryFn: async (): Promise<ShoppingList[]> => {
      const { data, error } = await supabase
        .from("shopping_lists")
        .select("*")
        .order("created_at", { ascending: false });
      if (error) throw error;
      return data ?? [];
    },
  });

export const listItemsOptions = (listId: string | null) =>
  queryOptions({
    queryKey: ["shopping-list-items", listId],
    enabled: !!listId,
    queryFn: async (): Promise<ShoppingListItem[]> => {
      if (!listId) return [];
      const { data, error } = await supabase
        .from("shopping_list_items")
        .select(
          "id, shopping_list_id, canonical_product_id, quantity, allow_similar_products, product:canonical_products(id, name, brand, quantity, unit, image_url)",
        )
        .eq("shopping_list_id", listId);
      if (error) throw error;
      return (data as unknown as ShoppingListItem[]) ?? [];
    },
  });

export const comparisonOptions = (listId: string | null) =>
  queryOptions({
    queryKey: ["shopping-list-comparison", listId],
    enabled: !!listId,
    queryFn: async (): Promise<ComparisonPayload | null> => {
      if (!listId) return null;
      const { data, error } = await supabase.rpc("compute_list_comparison", { p_list_id: listId });
      if (error) throw error;
      return data as unknown as ComparisonPayload;
    },
  });

export async function createList(name: string) {
  const { data: userData } = await supabase.auth.getUser();
  if (!userData.user) throw new Error("Não autenticado");
  const { data, error } = await supabase
    .from("shopping_lists")
    .insert({ name, user_id: userData.user.id })
    .select()
    .single();
  if (error) throw error;
  return data as ShoppingList;
}

export async function renameList(id: string, name: string) {
  const { error } = await supabase.from("shopping_lists").update({ name }).eq("id", id);
  if (error) throw error;
}

export async function deleteList(id: string) {
  const { error } = await supabase.from("shopping_lists").delete().eq("id", id);
  if (error) throw error;
}

export async function addItem(listId: string, productId: string, quantity = 1, allowSimilar = false) {
  const { error } = await supabase.from("shopping_list_items").insert({
    shopping_list_id: listId,
    canonical_product_id: productId,
    quantity,
    allow_similar_products: allowSimilar,
  });
  if (error) throw error;
}

export async function updateItem(id: string, patch: { quantity?: number; allow_similar_products?: boolean }) {
  const { error } = await supabase.from("shopping_list_items").update(patch).eq("id", id);
  if (error) throw error;
}

export async function removeItem(id: string) {
  const { error } = await supabase.from("shopping_list_items").delete().eq("id", id);
  if (error) throw error;
}
