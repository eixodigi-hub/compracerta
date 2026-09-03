import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator, fallback } from "@tanstack/zod-adapter";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Search, SlidersHorizontal, X, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { ProductCard } from "@/components/ui-app/ProductCard";
import {
  searchProductsQuery,
  brandsQuery,
  type SortBy,
} from "@/lib/search-queries";
import { categoriesQuery, marketsQuery } from "@/lib/queries";
import { toast } from "sonner";

const searchSchema = z.object({
  q: fallback(z.string(), "").default(""),
  category: fallback(z.string(), "").default(""),
  brand: fallback(z.string(), "").default(""),
  store: fallback(z.string(), "").default(""),
  available: fallback(z.boolean(), false).default(false),
  offers: fallback(z.boolean(), false).default(false),
  min: fallback(z.number(), 0).default(0),
  max: fallback(z.number(), 0).default(0),
  sort: fallback(z.string(), "price_asc").default("price_asc"),
});

export const Route = createFileRoute("/pesquisar")({
  validateSearch: zodValidator(searchSchema),
  head: () => ({
    meta: [
      { title: "Pesquisar produtos — Compra Certa" },
      { name: "description", content: "Pesquise produtos e compare preços entre supermercados de Marília." },
      { property: "og:title", content: "Pesquisar produtos — Compra Certa" },
      { property: "og:description", content: "Pesquise produtos e compare preços entre supermercados de Marília." },
    ],
  }),
  component: PesquisarPage,
});

const SORT_LABEL: Record<SortBy, string> = {
  relevance: "Relevância",
  price_asc: "Menor preço",
  discount_desc: "Maior desconto",
  name_asc: "Nome (A-Z)",
  recent: "Mais recente",
};

const SORT_KEYS = ["relevance", "price_asc", "discount_desc", "name_asc", "recent"] as const;

// Busca ao digitar: espera o usuário parar de digitar antes de refazer a
// busca, pra não disparar uma consulta a cada tecla.
const LIVE_SEARCH_DEBOUNCE_MS = 350;

function PesquisarPage() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: "/pesquisar" });
  const [qDraft, setQDraft] = useState(search.q);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  function applyQuery(nextQuery: string) {
    navigate({
      search: (prev: any) => ({
        ...prev,
        q: nextQuery,
        // Pesquisar por texto é sobre achar o produto certo primeiro —
        // troca pra ordenação por relevância automaticamente. Limpar a
        // busca volta pro padrão de menor preço.
        sort: nextQuery ? "relevance" : prev.sort === "relevance" ? "price_asc" : prev.sort,
      }),
      replace: true,
    });
  }

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const formData = new FormData(event.currentTarget);
    applyQuery(String(formData.get("q") ?? "").trim());
  }

  function handleQueryChange(value: string) {
    setQDraft(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => applyQuery(value.trim()), LIVE_SEARCH_DEBOUNCE_MS);
  }

  function clearQuery() {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setQDraft("");
    applyQuery("");
  }

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const sortBy = (SORT_KEYS as readonly string[]).includes(search.sort)
    ? (search.sort as SortBy)
    : "price_asc";

  const results = useQuery(
    searchProductsQuery({
      q: search.q || undefined,
      category: search.category || undefined,
      brand: search.brand || undefined,
      storeId: search.store || undefined,
      onlyAvailable: search.available,
      onlyOffers: search.offers,
      minPrice: search.min > 0 ? search.min : undefined,
      maxPrice: search.max > 0 ? search.max : undefined,
      sortBy,
    }),
  );

  const categories = useQuery(categoriesQuery);
  const markets = useQuery(marketsQuery);
  const brands = useQuery(brandsQuery);

  const activeFilterCount =
    (search.category ? 1 : 0) +
    (search.brand ? 1 : 0) +
    (search.store ? 1 : 0) +
    (search.available ? 1 : 0) +
    (search.offers ? 1 : 0) +
    (search.min > 0 || search.max > 0 ? 1 : 0);

  function clearFilters() {
    navigate({
      search: {
        q: search.q,
        category: "",
        brand: "",
        store: "",
        available: false,
        offers: false,
        min: 0,
        max: 0,
        sort: sortBy,
      },
    });
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:py-10">
      <h1 className="text-2xl font-bold md:text-3xl">Pesquisar produtos</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Encontre um produto e veja onde ele está mais barato em Marília.
      </p>

      <form className="mt-6 flex gap-2" role="search" onSubmit={handleSearchSubmit}>
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            placeholder="Nome, marca ou código de barras"
            aria-label="Pesquisar produto"
            name="q"
            className="pl-9 pr-8"
            value={qDraft}
            onChange={(e) => handleQueryChange(e.target.value)}
          />
          {qDraft && (
            <button
              type="button"
              onClick={clearQuery}
              aria-label="Limpar pesquisa"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>

        <Button type="submit" className="shrink-0">
          <Search className="mr-1.5 h-4 w-4" aria-hidden="true" />
          Buscar
        </Button>

        <Sheet>
          <SheetTrigger asChild>
            <Button variant="outline" className="shrink-0">
              <SlidersHorizontal className="mr-1.5 h-4 w-4" aria-hidden="true" />
              Filtros
              {activeFilterCount > 0 && (
                <span className="ml-1.5 rounded-full bg-primary px-1.5 text-xs font-bold text-primary-foreground">
                  {activeFilterCount}
                </span>
              )}
            </Button>
          </SheetTrigger>
          <SheetContent className="w-full sm:max-w-md">
            <SheetHeader>
              <SheetTitle>Filtros</SheetTitle>
            </SheetHeader>
            <div className="mt-6 space-y-5 overflow-y-auto pb-6 pr-1">
              <div className="space-y-2">
                <Label>Categoria</Label>
                <Select
                  value={search.category || "all"}
                  onValueChange={(v) =>
                    navigate({
                      search: (prev: any) => ({ ...prev, category: v === "all" ? "" : v }),
                    })
                  }
                >
                  <SelectTrigger><SelectValue placeholder="Todas" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todas</SelectItem>
                    {(categories.data ?? []).map((c) => (
                      <SelectItem key={c.id} value={c.slug}>{c.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Marca</Label>
                <Select
                  value={search.brand || "all"}
                  onValueChange={(v) =>
                    navigate({
                      search: (prev: any) => ({ ...prev, brand: v === "all" ? "" : v }),
                    })
                  }
                >
                  <SelectTrigger><SelectValue placeholder="Todas" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todas</SelectItem>
                    {(brands.data ?? []).map((b) => (
                      <SelectItem key={b} value={b}>{b}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Mercado</Label>
                <Select
                  value={search.store || "all"}
                  onValueChange={(v) =>
                    navigate({
                      search: (prev: any) => ({ ...prev, store: v === "all" ? "" : v }),
                    })
                  }
                >
                  <SelectTrigger><SelectValue placeholder="Todos" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos</SelectItem>
                    {(markets.data ?? []).map((m) => (
                      <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between rounded-lg border border-border p-3">
                <Label htmlFor="filter-available" className="cursor-pointer">
                  Apenas produtos disponíveis
                </Label>
                <Switch
                  id="filter-available"
                  checked={search.available}
                  onCheckedChange={(v) =>
                    navigate({ search: (prev: any) => ({ ...prev, available: v }) })
                  }
                />
              </div>

              <div className="flex items-center justify-between rounded-lg border border-border p-3">
                <Label htmlFor="filter-offers" className="cursor-pointer">
                  Apenas ofertas
                </Label>
                <Switch
                  id="filter-offers"
                  checked={search.offers}
                  onCheckedChange={(v) =>
                    navigate({ search: (prev: any) => ({ ...prev, offers: v }) })
                  }
                />
              </div>

              <div className="space-y-2">
                <Label>Faixa de preço (R$)</Label>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step={0.5}
                    placeholder="Mín"
                    value={search.min || ""}
                    onChange={(e) =>
                      navigate({
                        search: (prev: any) => ({ ...prev, min: Number(e.target.value) || 0 }),
                        replace: true,
                      })
                    }
                  />
                  <span className="text-muted-foreground">até</span>
                  <Input
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step={0.5}
                    placeholder="Máx"
                    value={search.max || ""}
                    onChange={(e) =>
                      navigate({
                        search: (prev: any) => ({ ...prev, max: Number(e.target.value) || 0 }),
                        replace: true,
                      })
                    }
                  />
                </div>
              </div>

              {activeFilterCount > 0 && (
                <Button variant="ghost" onClick={clearFilters} className="w-full">
                  <X className="mr-1.5 h-4 w-4" aria-hidden="true" />
                  Limpar filtros
                </Button>
              )}
            </div>
          </SheetContent>
        </Sheet>
      </form>

      {/* Categories quick pills */}
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => navigate({ search: (prev: any) => ({ ...prev, category: "" }) })}
          className={`rounded-full border px-3 py-1 text-sm transition-colors ${
            !search.category
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border text-muted-foreground hover:bg-secondary"
          }`}
        >
          Todos
        </button>
        {(categories.data ?? []).map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() =>
              navigate({ search: (prev: any) => ({ ...prev, category: c.slug }) })
            }
            className={`rounded-full border px-3 py-1 text-sm transition-colors ${
              search.category === c.slug
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground hover:bg-secondary"
            }`}
          >
            {c.name}
          </button>
        ))}
      </div>

      {/* Sort */}
      <div className="mt-4 flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {results.isLoading
            ? "Buscando..."
            : `${results.data?.length ?? 0} ${results.data?.length === 1 ? "produto" : "produtos"}`}
        </p>
        <div className="flex items-center gap-2">
          <Label htmlFor="sort" className="text-sm text-muted-foreground">
            Ordenar:
          </Label>
          <Select
            value={sortBy}
            onValueChange={(v) =>
              navigate({ search: (prev: any) => ({ ...prev, sort: v }) })
            }
          >
            <SelectTrigger id="sort" className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(SORT_LABEL) as SortBy[]).map((k) => (
                <SelectItem key={k} value={k}>{SORT_LABEL[k]}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Results */}
      <div className="mt-6">
        {results.isLoading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden="true" />
          </div>
        ) : results.isError ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
            Não foi possível carregar os produtos. Tente novamente.
          </div>
        ) : (results.data?.length ?? 0) === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
            {search.q || activeFilterCount > 0
              ? "Nenhum produto encontrado com esses critérios."
              : "Digite algo acima ou escolha uma categoria para começar."}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {results.data!.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                onAddToList={() =>
                  toast.info("Em breve: monte listas permanentes ao entrar na sua conta.")
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
