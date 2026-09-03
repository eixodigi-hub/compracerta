import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { zodValidator, fallback } from "@tanstack/zod-adapter";
import { z } from "zod";
import { ExternalLink, ListPlus, Tag, Filter as FilterIcon } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { categoriesQuery, marketsQuery } from "@/lib/queries";
import { useAuth } from "@/hooks/use-auth";

const searchSchema = z.object({
  store: fallback(z.string(), "").default(""),
  category: fallback(z.string(), "").default(""),
  brand: fallback(z.string(), "").default(""),
  min_discount: fallback(z.number(), 0).default(0),
});

export const Route = createFileRoute("/ofertas")({
  validateSearch: zodValidator(searchSchema),
  head: () => ({
    meta: [
      { title: "Ofertas de hoje — Compra Certa" },
      { name: "description", content: "As melhores promoções válidas nos supermercados de Marília, atualizadas diariamente." },
      { property: "og:title", content: "Ofertas de hoje — Compra Certa" },
      { property: "og:description", content: "Promoções válidas nos supermercados de Marília, ordenadas pelo maior desconto." },
    ],
  }),
  component: OfertasPage,
});

type OfferRow = {
  store_product_id: string;
  product_id: string;
  product_name: string;
  brand: string | null;
  quantity: number | null;
  unit: string | null;
  image_url: string | null;
  category_name: string | null;
  category_slug: string | null;
  store_id: string;
  store_name: string;
  store_slug: string;
  product_url: string | null;
  regular_price: number;
  promotional_price: number;
  discount_pct: number;
  promotion_end_at: string | null;
  collected_at: string;
};

const brl = (v: number | null | undefined) =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const dateFmt = (iso: string | null) => {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
};

function OfertasPage() {
  const { store, category, brand, min_discount } = Route.useSearch();
  const navigate = useNavigate({ from: "/ofertas" });
  const { user } = useAuth();

  const categoriesQ = useQuery(categoriesQuery);
  const storesQ = useQuery(marketsQuery);
  const brandsQ = useQuery({
    queryKey: ["search-brands"],
    queryFn: async () => {
      const { data, error } = await supabase.rpc("list_search_brands");
      if (error) throw error;
      return (data ?? []) as { brand: string }[];
    },
  });

  const offersQ = useQuery({
    queryKey: ["offers-list", store, category, brand, min_discount],
    queryFn: async (): Promise<OfferRow[]> => {
      const { data, error } = await supabase.rpc("list_current_offers", {
        store_id_filter: store || null,
        category_slug: category || null,
        brand_filter: brand || null,
        min_discount: Number.isFinite(min_discount) ? Math.max(0, min_discount) : 0,
      });
      if (error) throw error;
      return (data as OfferRow[]) ?? [];
    },
  });

  const update = (patch: Partial<z.infer<typeof searchSchema>>) =>
    navigate({ search: (prev: z.infer<typeof searchSchema>) => ({ ...prev, ...patch }) });

  async function handleAddToList(offer: OfferRow) {
    if (!user) {
      toast.error("Entre para adicionar produtos à sua lista.");
      navigate({ to: "/auth" });
      return;
    }
    try {
      // Pick most recent list or create one
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
        canonical_product_id: offer.product_id,
        quantity: 1,
        allow_similar_products: false,
      });
      if (e3) throw e3;
      toast.success("Adicionado à sua lista");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao adicionar");
    }
  }

  const offers = offersQ.data ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 md:py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold md:text-3xl">Ofertas de hoje</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Promoções válidas nos supermercados de Marília, ordenadas pelo maior desconto.
          </p>
        </div>
      </header>

      {/* Filters */}
      <Card className="mt-6 p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <FilterIcon className="h-4 w-4" /> Filtros
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Label htmlFor="f-store" className="text-xs">Mercado</Label>
            <Select value={store || "all"} onValueChange={(v) => update({ store: v === "all" ? "" : v })}>
              <SelectTrigger id="f-store"><SelectValue placeholder="Todos" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os mercados</SelectItem>
                {storesQ.data?.map((s) => (
                  <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="f-cat" className="text-xs">Categoria</Label>
            <Select value={category || "all"} onValueChange={(v) => update({ category: v === "all" ? "" : v })}>
              <SelectTrigger id="f-cat"><SelectValue placeholder="Todas" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas as categorias</SelectItem>
                {categoriesQ.data?.map((c) => (
                  <SelectItem key={c.id} value={c.slug}>{c.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="f-brand" className="text-xs">Marca</Label>
            <Select value={brand || "all"} onValueChange={(v) => update({ brand: v === "all" ? "" : v })}>
              <SelectTrigger id="f-brand"><SelectValue placeholder="Todas" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas as marcas</SelectItem>
                {brandsQ.data?.map((b) => (
                  <SelectItem key={b.brand} value={b.brand}>{b.brand}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="f-disc" className="text-xs">Desconto mínimo (%)</Label>
            <Input
              id="f-disc"
              type="number"
              min={0}
              max={100}
              step={5}
              value={min_discount || 0}
              onChange={(e) => {
                const v = Math.max(0, Math.min(100, Number(e.target.value) || 0));
                update({ min_discount: v });
              }}
            />
          </div>
        </div>

        {(store || category || brand || min_discount > 0) && (
          <div className="mt-3">
            <Button variant="ghost" size="sm" onClick={() => navigate({ search: { store: "", category: "", brand: "", min_discount: 0 } })}>
              Limpar filtros
            </Button>
          </div>
        )}
      </Card>

      {/* Results */}
      {offersQ.isLoading ? (
        <p className="mt-6 text-sm text-muted-foreground">Carregando ofertas…</p>
      ) : offersQ.isError ? (
        <p className="mt-6 text-sm text-destructive">Não foi possível carregar as ofertas.</p>
      ) : offers.length === 0 ? (
        <Card className="mt-6 p-10 text-center">
          <Tag className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            Nenhuma oferta encontrada com esses filtros no momento.
          </p>
        </Card>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {offers.map((o) => (
            <Card key={o.store_product_id} className="flex flex-col overflow-hidden">
              <div className="relative aspect-video bg-secondary">
                {o.image_url ? (
                  <img src={o.image_url} alt={o.product_name} className="h-full w-full object-contain" />
                ) : null}
                <Badge className="absolute left-2 top-2 bg-orange-500 hover:bg-orange-500">
                  -{o.discount_pct}%
                </Badge>
              </div>
              <div className="flex flex-1 flex-col p-4">
                {o.category_name ? (
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">{o.category_name}</p>
                ) : null}
                <h2 className="mt-1 line-clamp-2 font-semibold">{o.product_name}</h2>
                <p className="text-xs text-muted-foreground">
                  {o.brand ?? ""}{o.quantity != null ? ` · ${o.quantity} ${o.unit ?? ""}` : ""}
                </p>

                <div className="mt-3">
                  <div className="text-xs text-muted-foreground line-through tabular-nums">{brl(o.regular_price)}</div>
                  <div className="text-2xl font-bold text-orange-600 tabular-nums">{brl(o.promotional_price)}</div>
                </div>

                <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                  <div><strong className="text-foreground">{o.store_name}</strong></div>
                  <div>Coletado em {dateFmt(o.collected_at)}</div>
                  {o.promotion_end_at ? <div>Válido até {dateFmt(o.promotion_end_at)}</div> : null}
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => handleAddToList(o)}>
                    <ListPlus className="mr-1 h-4 w-4" /> Adicionar
                  </Button>
                  <Button size="sm" variant="outline" asChild>
                    <Link to="/produto/$id" params={{ id: o.product_id }}>
                      Ver produto
                    </Link>
                  </Button>
                  {o.product_url ? (
                    <Button size="sm" variant="ghost" asChild>
                      <a href={o.product_url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="mr-1 h-3 w-3" /> Mercado
                      </a>
                    </Button>
                  ) : null}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
