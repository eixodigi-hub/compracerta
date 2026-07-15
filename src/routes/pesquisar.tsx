import { createFileRoute } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/pesquisar")({
  head: () => ({
    meta: [
      { title: "Pesquisar produtos — Compra Certa Marília" },
      { name: "description", content: "Pesquise produtos e compare preços entre supermercados de Marília." },
      { property: "og:title", content: "Pesquisar produtos — Compra Certa Marília" },
      { property: "og:description", content: "Pesquise produtos e compare preços entre supermercados de Marília." },
    ],
  }),
  component: PesquisarPage,
});

function PesquisarPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6 md:py-10">
      <h1 className="text-2xl font-bold md:text-3xl">Pesquisar produtos</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Encontre um produto e veja onde ele está mais barato.
      </p>

      <form className="mt-6 flex gap-2" role="search">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            type="search"
            placeholder="Ex: arroz, leite, café..."
            className="pl-9"
            aria-label="Pesquisar produto"
          />
        </div>
        <Button type="submit">Buscar</Button>
      </form>

      <div className="mt-4 flex flex-wrap gap-2">
        {["Todos", "Alimentos", "Bebidas", "Higiene", "Limpeza"].map((c) => (
          <button
            key={c}
            type="button"
            className="rounded-full border border-border px-3 py-1 text-sm text-muted-foreground hover:bg-secondary"
          >
            {c}
          </button>
        ))}
      </div>

      <div className="mt-10 rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
        Digite algo acima para começar a comparar preços.
      </div>
    </div>
  );
}
