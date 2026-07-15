import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/_authenticated/admin/precos")({
  component: Page,
});

const PAGE_SIZE = 25;

function Page() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "prices", q, page],
    queryFn: async () => {
      const { data, error, count } = await supabase
        .from("current_prices")
        .select(
          "id, regular_price, promotional_price, effective_price, in_stock, promotion_end_at, collected_at, store_products!inner(external_name, stores(name))",
          { count: "exact" },
        )
        .order("collected_at", { ascending: false })
        .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1);
      if (error) throw error;
      const rows = q
        ? (data ?? []).filter((r) =>
            (r as { store_products?: { external_name?: string } }).store_products?.external_name?.toLowerCase().includes(q.toLowerCase()),
          )
        : (data ?? []);
      return { rows, count: count ?? 0 };
    },
  });

  const total = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Preços atuais</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Input
          placeholder="Filtrar por nome do produto coletado..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-md"
        />
        {isLoading ? (
          <Skeleton className="h-64" />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-4">Produto</th>
                    <th className="py-2 pr-4">Mercado</th>
                    <th className="py-2 pr-4 text-right">Normal</th>
                    <th className="py-2 pr-4 text-right">Promo</th>
                    <th className="py-2 pr-4 text-right">Efetivo</th>
                    <th className="py-2 pr-4">Estoque</th>
                    <th className="py-2 pr-4">Coleta</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.rows.map((r) => {
                    const sp = (r as { store_products?: { external_name?: string; stores?: { name?: string } } }).store_products;
                    return (
                      <tr key={r.id} className="border-t">
                        <td className="py-2 pr-4">{sp?.external_name ?? "—"}</td>
                        <td className="py-2 pr-4">{sp?.stores?.name ?? "—"}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">{r.regular_price ?? "—"}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">{r.promotional_price ?? "—"}</td>
                        <td className="py-2 pr-4 text-right tabular-nums font-medium">{r.effective_price ?? "—"}</td>
                        <td className="py-2 pr-4">
                          {r.in_stock ? <Badge>disponível</Badge> : <Badge variant="secondary">indisp.</Badge>}
                        </td>
                        <td className="py-2 pr-4">{new Date(r.collected_at).toLocaleString("pt-BR")}</td>
                      </tr>
                    );
                  })}
                  {data?.rows.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-muted-foreground">Sem preços.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">{total} preço(s)</p>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Anterior</Button>
                <span className="text-sm">{page + 1} / {totalPages}</span>
                <Button variant="outline" size="sm" disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>Próxima</Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
