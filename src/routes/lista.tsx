import { createFileRoute } from "@tanstack/react-router";
import { ListChecks } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/lista")({
  head: () => ({
    meta: [
      { title: "Minha lista — Compra Certa Marília" },
      { name: "description", content: "Monte sua lista de compras e descubra em qual mercado sai mais barato." },
      { property: "og:title", content: "Minha lista — Compra Certa Marília" },
      { property: "og:description", content: "Monte sua lista de compras e descubra em qual mercado sai mais barato." },
    ],
  }),
  component: ListaPage,
});

function ListaPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6 md:py-10">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold md:text-3xl">Minha lista</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Adicione produtos e veja onde a compra completa sai mais barata.
          </p>
        </div>
        <Button variant="outline" className="shrink-0">Limpar</Button>
      </div>

      <section className="mt-6 rounded-lg border border-border p-6">
        <h2 className="text-sm font-semibold text-muted-foreground">Melhor mercado</h2>
        <p className="mt-1 text-lg font-bold">— a definir —</p>
        <p className="text-sm text-muted-foreground">Adicione itens para calcular.</p>
      </section>

      <div className="mt-6 flex flex-col items-center justify-center rounded-lg border border-dashed border-border p-10 text-center">
        <ListChecks className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
        <p className="mt-3 text-sm text-muted-foreground">Sua lista está vazia.</p>
      </div>
    </div>
  );
}
