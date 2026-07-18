import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Search, ListChecks, Clock } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { SectionHeader } from "@/components/ui-app/SectionHeader";
import { CategoryCard } from "@/components/ui-app/CategoryCard";
import { OfferCard, type Offer } from "@/components/ui-app/OfferCard";
import { MarketCard } from "@/components/ui-app/MarketCard";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/use-auth";
import {
  categoriesQuery,
  marketsQuery,
  topOffersQuery,
  lastUpdatedQuery,
} from "@/lib/queries";

export const Route = createFileRoute("/")({
  component: Index,
});

function formatCurrency(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatUpdated(iso: string | null) {
  if (!iso) return "Ainda sem coletas de preços";
  const d = new Date(iso);
  return `Atualizado em ${d.toLocaleDateString("pt-BR")} às ${d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}

function Index() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [addingId, setAddingId] = useState<string | null>(null);
  const categories = useQuery(categoriesQuery);
  const markets = useQuery(marketsQuery);
  const offers = useQuery(topOffersQuery);
  const lastUpdated = useQuery(lastUpdatedQuery);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const term = q.trim();
    navigate({ to: "/pesquisar", search: { q: term, category: "", brand: "", store: "", available: false, offers: false, min: 0, max: 0, sort: "price_asc" } });
  }

  async function handleAddToList(offer: Offer) {
    if (!offer.canonicalId) return;
    if (!user) {
      toast.error("Entre para adicionar produtos à sua lista.");
      navigate({ to: "/auth" });
      return;
    }
    setAddingId(offer.id);
    try {
      const { data: existing, error: e1 } = await supabase
        .from("shopping_lists")
        .select("id")
        .order("created_at", { ascending: false })
        .limit(1);
      if (e1) throw e1;
      let listId = existing?.[0]?.id;
      if (!listId) {
        const { data: created, error: e2 } = await supabase
          .from("shopping_lists")
          .insert({ name: "Minha lista", user_id: user.id })
          .select("id")
          .single();
        if (e2) throw e2;
        listId = created.id;
      }
      const { error: e3 } = await supabase.from("shopping_list_items").insert({
        shopping_list_id: listId,
        canonical_product_id: offer.canonicalId,
        quantity: 1,
        allow_similar_products: false,
      });
      if (e3) throw e3;
      toast.success("Adicionado à sua lista");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao adicionar");
    } finally {
      setAddingId(null);
    }
  }

  const offerCards: Offer[] =
    offers.data?.map((o) => {
      const sp = o.store_products;
      const cp = sp?.canonical_products;
      const productName = cp?.name ?? sp?.external_name ?? "Produto";
      return {
        id: o.id,
        product: productName,
        market: sp?.stores?.name ?? "—",
        price: formatCurrency(Number(o.effective_price)),
        oldPrice:
          o.promotional_price != null && o.regular_price != null
            ? formatCurrency(Number(o.regular_price))
            : undefined,
        validUntil: o.promotion_end_at
          ? new Date(o.promotion_end_at).toLocaleDateString("pt-BR")
          : undefined,
        imageUrl: cp?.image_url ?? sp?.image_url ?? null,
        canonicalId: cp?.id ?? null,
      };
    }) ?? [];

  return (
    <div>
      <section className="bg-primary-soft/60">
        <div className="mx-auto max-w-6xl px-4 py-8 md:py-12">
          <p className="text-sm font-medium text-primary">Olá 👋</p>
          <h1 className="mt-1 text-2xl font-bold leading-tight md:text-4xl">
            Vamos economizar na compra de hoje?
          </h1>

          <form className="mt-6 flex flex-col gap-3 sm:flex-row" role="search" onSubmit={handleSearch}>
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input
                type="search"
                placeholder="O que você procura hoje?"
                aria-label="O que você procura hoje?"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                className="h-14 rounded-2xl border-border bg-card pl-12 text-base shadow-sm"
              />
            </div>
            <Button type="submit" size="lg" className="h-14 rounded-2xl px-6 text-base font-semibold shadow-sm">
              <Search className="mr-2 h-5 w-5" aria-hidden="true" />
              Pesquisar
            </Button>
            <Button asChild variant="outline" size="lg" className="h-14 rounded-2xl px-6 text-base font-semibold shadow-sm">
              <Link to="/lista">
                <ListChecks className="mr-2 h-5 w-5" aria-hidden="true" />
                Comparar minha lista
              </Link>
            </Button>
          </form>

          <p className="mt-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            {formatUpdated(lastUpdated.data ?? null)}
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-8 md:py-10">
        <SectionHeader
          title="Maiores ofertas de hoje"
          subtitle="As promoções mais fortes dos supermercados"
          action={
            <Link to="/ofertas" className="text-sm font-medium text-primary hover:underline">
              Ver todas
            </Link>
          }
        />
        {offers.isLoading ? (
          <p className="text-sm text-muted-foreground">Carregando ofertas...</p>
        ) : offerCards.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Ainda não há ofertas cadastradas. Assim que o coletor enviar os primeiros preços, elas aparecerão aqui.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {offerCards.map((o) => (
              <OfferCard
                key={o.id}
                offer={o}
                onAddToList={handleAddToList}
                adding={addingId === o.id}
              />
            ))}
          </div>
        )}
      </section>

      <section className="mx-auto max-w-6xl px-4 py-4 md:py-6">
        <SectionHeader title="Categorias" subtitle="Explore por seção do mercado" />
        {categories.isLoading ? (
          <p className="text-sm text-muted-foreground">Carregando...</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
            {(categories.data ?? []).map((c) => (
              <CategoryCard
                key={c.id}
                category={{ slug: c.slug, name: c.name, icon: c.icon }}
              />
            ))}
          </div>
        )}
      </section>

      <section className="mx-auto max-w-6xl px-4 py-8 md:py-10">
        <SectionHeader
          title="Mercados disponíveis"
          subtitle="Supermercados de Marília com preços monitorados"
        />
        {markets.isLoading ? (
          <p className="text-sm text-muted-foreground">Carregando...</p>
        ) : (markets.data?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum mercado cadastrado ainda. Adicione mercados na área administrativa.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {(markets.data ?? []).map((m) => (
              <MarketCard key={m.id} market={{ id: m.id, name: m.name }} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
