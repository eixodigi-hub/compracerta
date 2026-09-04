import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Search, ListChecks, Clock } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselPrevious,
  CarouselNext,
} from "@/components/ui/carousel";
import { SectionHeader } from "@/components/ui-app/SectionHeader";
import { OfferCard, type Offer } from "@/components/ui-app/OfferCard";
import { MarketCard } from "@/components/ui-app/MarketCard";
import { getCategoryIcon } from "@/lib/category-icons";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/use-auth";
import {
  marketsQuery,
  lastUpdatedQuery,
  homeCategoryFeedQuery,
  type HomeCategorySection,
  type HomeCategoryProductRow,
} from "@/lib/queries";

const PESQUISAR_DEFAULTS = {
  q: "",
  brand: "",
  store: "",
  available: false,
  offers: false,
  min: 0,
  max: 0,
  sort: "price_asc" as const,
};

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

function toOfferCard(row: HomeCategoryProductRow): Offer {
  const cheapest = row.offers[0];
  const showsDiscount =
    row.has_promotion && row.reference_price != null && row.reference_price > row.min_price;
  return {
    id: row.id,
    product: row.name,
    market: row.market_count > 1 ? `${row.market_count} mercados` : (cheapest?.store_name ?? "—"),
    price: formatCurrency(row.min_price),
    oldPrice: showsDiscount ? formatCurrency(row.reference_price as number) : undefined,
    validUntil: cheapest?.promotion_end_at
      ? new Date(cheapest.promotion_end_at).toLocaleDateString("pt-BR")
      : undefined,
    imageUrl: row.image_url,
    canonicalId: row.id,
  };
}

function CategorySection({
  section,
  onAddToList,
  addingId,
}: {
  section: HomeCategorySection;
  onAddToList: (offer: Offer) => void;
  addingId: string | null;
}) {
  const Icon = getCategoryIcon(section.category_icon);

  return (
    <section className="mx-auto max-w-6xl px-4 py-6">
      <SectionHeader
        title={
          <span className="inline-flex items-center gap-2">
            <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
            {section.category_name}
          </span>
        }
        action={
          <Link
            to="/pesquisar"
            search={{ ...PESQUISAR_DEFAULTS, category: section.category_slug }}
            className="text-sm font-medium text-primary hover:underline"
          >
            Ver categoria completa
          </Link>
        }
      />
      <Carousel opts={{ align: "start", dragFree: true }} className="mt-3">
        <CarouselContent>
          {section.products.map((row) => (
            <CarouselItem
              key={row.id}
              className="basis-[72%] sm:basis-1/3 md:basis-1/4 lg:basis-1/5"
            >
              <OfferCard
                offer={toOfferCard(row)}
                onAddToList={onAddToList}
                adding={addingId === row.id}
              />
            </CarouselItem>
          ))}
        </CarouselContent>
        <CarouselPrevious className="static left-auto top-auto h-8 w-8 -translate-y-0 translate-x-0" />
        <CarouselNext className="static left-auto top-auto h-8 w-8 -translate-y-0 translate-x-0" />
      </Carousel>
    </section>
  );
}

function Index() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [addingId, setAddingId] = useState<string | null>(null);
  const markets = useQuery(marketsQuery);
  const categoryFeed = useQuery(homeCategoryFeedQuery);
  const lastUpdated = useQuery(lastUpdatedQuery);

  function handleSearch(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const term = String(formData.get("q") ?? "").trim();
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
                name="q"
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

      <div className="mx-auto max-w-6xl px-4 pt-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold md:text-xl">Ofertas por categoria</h2>
          <Link to="/ofertas" className="text-sm font-medium text-primary hover:underline">
            Ver todas as ofertas
          </Link>
        </div>
      </div>

      {categoryFeed.isLoading ? (
        <p className="mx-auto max-w-6xl px-4 py-6 text-sm text-muted-foreground">
          Carregando categorias...
        </p>
      ) : (categoryFeed.data?.length ?? 0) === 0 ? (
        <p className="mx-auto max-w-6xl px-4 py-6 text-sm text-muted-foreground">
          Ainda não há produtos categorizados. Assim que o coletor enviar os primeiros preços, eles aparecerão aqui organizados por categoria.
        </p>
      ) : (
        categoryFeed.data!.map((section) => (
          <CategorySection
            key={section.category_id}
            section={section}
            onAddToList={handleAddToList}
            addingId={addingId}
          />
        ))
      )}

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
