import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/hooks/use-auth";
import {
  promoAlertIdsOptions,
  subscribeAlert,
  unsubscribeAlert,
} from "@/lib/promo-alert-queries";

/**
 * Liga/desliga o aviso por e-mail de promoção de um produto canônico.
 * Compartilhado entre a busca e a página de detalhe do produto.
 */
export function usePromoAlert() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [pendingId, setPendingId] = useState<string | null>(null);

  const idsQuery = useQuery({ ...promoAlertIdsOptions(), enabled: !!user });
  const alertedIds = idsQuery.data ?? new Set<string>();

  async function toggleAlert(canonicalProductId: string | null | undefined, productName?: string) {
    if (!canonicalProductId) {
      toast.error("Produto ainda não catalogado para comparação.");
      return;
    }
    if (!user) {
      toast.error("Entre para receber avisos de promoção por e-mail.");
      navigate({ to: "/auth" });
      return;
    }

    const alreadyAlerted = alertedIds.has(canonicalProductId);
    setPendingId(canonicalProductId);
    try {
      if (alreadyAlerted) {
        await unsubscribeAlert(canonicalProductId);
        toast.success("Aviso removido.");
      } else {
        await subscribeAlert(canonicalProductId);
        toast.success(
          productName
            ? `Você será avisado(a) por e-mail quando "${productName}" entrar em promoção.`
            : "Você será avisado(a) por e-mail quando este produto entrar em promoção.",
        );
      }
      qc.invalidateQueries({ queryKey: ["promo-alert-ids"] });
      qc.invalidateQueries({ queryKey: ["promo-alerts"] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao atualizar o aviso");
    } finally {
      setPendingId(null);
    }
  }

  return { alertedIds, toggleAlert, pendingId };
}
