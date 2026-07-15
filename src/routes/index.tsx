import { createFileRoute, Link } from "@tanstack/react-router";
import { Search, ListChecks, Tag, ShoppingBasket } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  return (
    <div>
      <section className="bg-secondary/40">
        <div className="mx-auto max-w-4xl px-4 py-10 md:py-16">
          <div className="flex items-center gap-2 text-sm font-medium text-primary">
            <ShoppingBasket className="h-4 w-4" aria-hidden="true" />
            Compra Certa Marília
          </div>
          <h1 className="mt-3 text-3xl font-bold leading-tight md:text-5xl">
            Compare preços dos supermercados de Marília
          </h1>
          <p className="mt-3 max-w-2xl text-muted-foreground">
            Pesquise produtos, monte sua lista e descubra em qual mercado sua compra fica mais barata.
          </p>

          <form className="mt-6 flex gap-2" role="search">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input type="search" placeholder="Pesquisar produto..." className="pl-9" aria-label="Pesquisar produto" />
            </div>
            <Button asChild>
              <Link to="/pesquisar">Buscar</Link>
            </Button>
          </form>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-4 py-8 md:py-12">
        <h2 className="text-lg font-semibold">Atalhos</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <Link to="/pesquisar">
            <Card className="flex items-center gap-3 p-5 transition-colors hover:bg-secondary">
              <Search className="h-5 w-5 text-primary" aria-hidden="true" />
              <div>
                <p className="font-medium">Pesquisar</p>
                <p className="text-xs text-muted-foreground">Encontre um produto</p>
              </div>
            </Card>
          </Link>
          <Link to="/lista">
            <Card className="flex items-center gap-3 p-5 transition-colors hover:bg-secondary">
              <ListChecks className="h-5 w-5 text-primary" aria-hidden="true" />
              <div>
                <p className="font-medium">Minha lista</p>
                <p className="text-xs text-muted-foreground">Monte sua compra</p>
              </div>
            </Card>
          </Link>
          <Link to="/ofertas">
            <Card className="flex items-center gap-3 p-5 transition-colors hover:bg-secondary">
              <Tag className="h-5 w-5 text-primary" aria-hidden="true" />
              <div>
                <p className="font-medium">Ofertas</p>
                <p className="text-xs text-muted-foreground">Promoções da semana</p>
              </div>
            </Card>
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-4 pb-12">
        <h2 className="text-lg font-semibold">Como funciona</h2>
        <ol className="mt-4 grid gap-4 sm:grid-cols-3">
          <li className="rounded-lg border border-border p-5">
            <span className="text-sm font-bold text-primary">1</span>
            <p className="mt-1 font-medium">Pesquise produtos</p>
            <p className="text-sm text-muted-foreground">Busque por nome ou categoria.</p>
          </li>
          <li className="rounded-lg border border-border p-5">
            <span className="text-sm font-bold text-primary">2</span>
            <p className="mt-1 font-medium">Compare mercados</p>
            <p className="text-sm text-muted-foreground">Veja o preço em cada supermercado.</p>
          </li>
          <li className="rounded-lg border border-border p-5">
            <span className="text-sm font-bold text-primary">3</span>
            <p className="mt-1 font-medium">Economize</p>
            <p className="text-sm text-muted-foreground">Descubra onde comprar tudo mais barato.</p>
          </li>
        </ol>
      </section>
    </div>
  );
}
