import { createFileRoute } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export const Route = createFileRoute("/produto/$id")({
  head: () => ({
    meta: [
      { title: "Detalhes do produto — Compra Certa Marília" },
      { name: "description", content: "Compare o preço deste produto entre os supermercados de Marília." },
      { property: "og:title", content: "Detalhes do produto — Compra Certa Marília" },
      { property: "og:description", content: "Compare o preço deste produto entre os supermercados de Marília." },
    ],
  }),
  component: ProdutoPage,
});

function ProdutoPage() {
  const { id } = Route.useParams();

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 md:py-10">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">Produto #{id}</p>
      <h1 className="mt-1 text-2xl font-bold md:text-3xl">Nome do produto</h1>
      <p className="mt-1 text-sm text-muted-foreground">Descrição breve do produto virá aqui.</p>

      <div className="mt-6 grid gap-6 md:grid-cols-[220px_1fr]">
        <div className="aspect-square rounded-lg bg-secondary" aria-hidden="true" />
        <div>
          <h2 className="text-lg font-semibold">Preços por supermercado</h2>
          <ul className="mt-3 space-y-2">
            {["Supermercado A", "Supermercado B", "Supermercado C"].map((m) => (
              <Card key={m} className="flex items-center justify-between p-4">
                <span className="font-medium">{m}</span>
                <span className="text-muted-foreground">—</span>
              </Card>
            ))}
          </ul>
          <Button className="mt-6 w-full md:w-auto">Adicionar à lista</Button>
        </div>
      </div>
    </div>
  );
}
