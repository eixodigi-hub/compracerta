import { createFileRoute, Link } from "@tanstack/react-router";
import { Search, ListChecks, Clock } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { SectionHeader } from "@/components/ui-app/SectionHeader";
import { CategoryCard } from "@/components/ui-app/CategoryCard";
import { OfferCard, type Offer } from "@/components/ui-app/OfferCard";
import { MarketCard, type Market } from "@/components/ui-app/MarketCard";
import { CATEGORIES } from "@/lib/categories";

export const Route = createFileRoute("/")({
  component: Index,
});

const OFFERS: Offer[] = [
  { id: "1", product: "Produto em destaque", market: "Supermercado A", price: "R$ —", validUntil: "domingo" },
  { id: "2", product: "Produto em destaque", market: "Supermercado B", price: "R$ —", validUntil: "sábado" },
  { id: "3", product: "Produto em destaque", market: "Supermercado C", price: "R$ —", validUntil: "sexta" },
];

const MARKETS: Market[] = [
  { id: "a", name: "Supermercado A" },
  { id: "b", name: "Supermercado B" },
  { id: "c", name: "Supermercado C" },
  { id: "d", name: "Supermercado D" },
];

function Index() {
  return (
    <div>
      {/* Hero */}
      <section className="bg-primary-soft/60">
        <div className="mx-auto max-w-6xl px-4 py-8 md:py-12">
          <p className="text-sm font-medium text-primary">Olá 👋</p>
          <h1 className="mt-1 text-2xl font-bold leading-tight md:text-4xl">
            Vamos economizar na compra de hoje?
          </h1>

          <form className="mt-6 flex flex-col gap-3 sm:flex-row" role="search">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input
                type="search"
                placeholder="O que você procura hoje?"
                aria-label="O que você procura hoje?"
                className="h-14 rounded-2xl border-border bg-card pl-12 text-base shadow-sm"
              />
            </div>
            <Button asChild size="lg" className="h-14 rounded-2xl px-6 text-base font-semibold shadow-sm">
              <Link to="/lista">
                <ListChecks className="mr-2 h-5 w-5" aria-hidden="true" />
                Comparar minha lista
              </Link>
            </Button>
          </form>

          <p className="mt-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            Preços atualizados hoje às 08:00
          </p>
        </div>
      </section>

      {/* Ofertas */}
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
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {OFFERS.map((o) => (
            <OfferCard key={o.id} offer={o} />
          ))}
        </div>
      </section>

      {/* Categorias */}
      <section className="mx-auto max-w-6xl px-4 py-4 md:py-6">
        <SectionHeader title="Categorias" subtitle="Explore por seção do mercado" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {CATEGORIES.map((c) => (
            <CategoryCard key={c.slug} category={c} />
          ))}
        </div>
      </section>

      {/* Mercados */}
      <section className="mx-auto max-w-6xl px-4 py-8 md:py-10">
        <SectionHeader
          title="Mercados disponíveis"
          subtitle="Supermercados de Marília com preços monitorados"
        />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {MARKETS.map((m) => (
            <MarketCard key={m.id} market={m} />
          ))}
        </div>
      </section>
    </div>
  );
}
