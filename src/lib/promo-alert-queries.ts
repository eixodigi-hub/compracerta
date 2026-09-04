import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

export type PromoAlert = {
  alert_id: string;
  canonical_product_id: string;
  name: string;
  brand: string | null;
  quantity: number | null;
  unit: string | null;
  image_url: string | null;
  min_price: number | null;
  reference_price: number | null;
  has_promotion: boolean;
  best_store_name: string | null;
  created_at: string;
};

export const promoAlertsOptions = () =>
  queryOptions({
    queryKey: ["promo-alerts"],
    queryFn: async (): Promise<PromoAlert[]> => {
      const { data, error } = await supabase.rpc("get_my_promo_alerts");
      if (error) throw error;
      return (data as PromoAlert[]) ?? [];
    },
  });

export const promoAlertIdsOptions = () =>
  queryOptions({
    queryKey: ["promo-alert-ids"],
    queryFn: async (): Promise<Set<string>> => {
      const { data, error } = await supabase.from("promo_alerts").select("canonical_product_id");
      if (error) throw error;
      return new Set((data ?? []).map((r) => r.canonical_product_id));
    },
  });

const DUPLICATE_ALERT_CODE = "23505";

export async function subscribeAlert(canonicalProductId: string) {
  const { data: userData } = await supabase.auth.getUser();
  if (!userData.user) throw new Error("Não autenticado");
  const { error } = await supabase.from("promo_alerts").insert({
    user_id: userData.user.id,
    canonical_product_id: canonicalProductId,
  });
  if (error && error.code !== DUPLICATE_ALERT_CODE) throw error;
}

export async function unsubscribeAlert(canonicalProductId: string) {
  const { error } = await supabase
    .from("promo_alerts")
    .delete()
    .eq("canonical_product_id", canonicalProductId);
  if (error) throw error;
}

export async function unsubscribeAlertById(alertId: string) {
  const { error } = await supabase.from("promo_alerts").delete().eq("id", alertId);
  if (error) throw error;
}
