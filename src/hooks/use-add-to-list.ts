import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/use-auth";

const DUPLICATE_ITEM_CODE = "23505";

/**
 * Adiciona um produto canônico à lista de compras mais recente do
 * usuário (cria a lista na primeira vez). Compartilhado entre a home,
 * a busca e a página de detalhe do produto.
 */
export function useAddToList() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [addingId, setAddingId] = useState<string | null>(null);

  async function addToList(canonicalProductId: string | null | undefined, trackingId?: string) {
    if (!canonicalProductId) {
      toast.error("Produto ainda não catalogado para comparação.");
      return;
    }
    if (!user) {
      toast.error("Entre para adicionar produtos à sua lista.");
      navigate({ to: "/auth" });
      return;
    }

    const id = trackingId ?? canonicalProductId;
    setAddingId(id);
    try {
      const { data: existing, error: findError } = await supabase
        .from("shopping_lists")
        .select("id")
        .order("created_at", { ascending: false })
        .limit(1);
      if (findError) throw findError;

      let listId = existing?.[0]?.id as string | undefined;
      if (!listId) {
        const { data: created, error: createError } = await supabase
          .from("shopping_lists")
          .insert({ name: "Minha lista", user_id: user.id })
          .select("id")
          .single();
        if (createError) throw createError;
        listId = created.id;
      }

      const { error: insertError } = await supabase.from("shopping_list_items").insert({
        shopping_list_id: listId,
        canonical_product_id: canonicalProductId,
        quantity: 1,
        allow_similar_products: false,
      });
      if (insertError) {
        if (insertError.code === DUPLICATE_ITEM_CODE) {
          toast.info("Esse produto já está na sua lista.");
          return;
        }
        throw insertError;
      }

      toast.success("Adicionado à sua lista");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao adicionar à lista");
    } finally {
      setAddingId(null);
    }
  }

  return { addToList, addingId };
}
