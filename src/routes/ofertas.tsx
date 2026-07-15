import { createFileRoute } from "@tanstack/react-router";
import { Card } from "@/components/ui/card";

export const Route = createFileRoute("/ofertas")({
  head: () => ({
    meta: [
      { title: "Ofertas — Compra Certa Marília" },
      { name: "description", content: "Veja as principais ofertas dos supermercados de Marília." },
      { property: "og:title", content: "Ofertas — Compra Certa Marília" },
      { property: "og:description", content: "Veja as principais ofertas dos supermercados de Marília." },
    ],
  }),
  component: OfertasPage,
});

function OfertasPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-6 md:py-10">
      <h1 className="text-2xl font-bold md:text-3xl">Ofertas</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Promoções da semana nos supermercados de Marília.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {["Todos os mercados", "Supermercado A", "Supermercado B", "Supermercado C"].map((m) => (
          <button
            key={m}
            type="button"
            className="rounded-full border border-border px-3 py-1 text-sm text-muted-foreground hover:bg-secondary"
          >
            {m}
          </button>
        ))}
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i} className="overflow-hidden">
            <div className="aspect-video bg-secondary" aria-hidden="true" />
            <div className="p-4">
              <p className="text-xs uppercase tracking-wide text-primary">Oferta</p>
              <h2 className="mt-1 font-semibold">Produto em promoção</h2>
              <p className="mt-1 text-sm text-muted-foreground">Supermercado — validade</p>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
