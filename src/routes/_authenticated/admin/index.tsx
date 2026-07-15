import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { fetchOverview } from "@/lib/admin-queries";
import { AlertCircle } from "lucide-react";

export const Route = createFileRoute("/_authenticated/admin/")({
  component: OverviewPage,
});

function fmt(dt: string | null) {
  if (!dt) return "—";
  return new Date(dt).toLocaleString("pt-BR");
}

function OverviewPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "overview"],
    queryFn: fetchOverview,
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }
  if (error || !data) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Não foi possível carregar</AlertTitle>
        <AlertDescription>{(error as Error)?.message ?? "Erro desconhecido"}</AlertDescription>
      </Alert>
    );
  }

  const cards = [
    { label: "Produtos ativos", value: data.active_products },
    { label: "Mercados ativos", value: data.active_stores },
    { label: "Sem correspondência canônica", value: data.unmatched_store_products },
    { label: "Preços atualizados (24h)", value: data.prices_updated_24h },
    { label: "Preços desatualizados (>72h)", value: data.prices_stale },
  ];

  return (
    <div className="space-y-6">
      <section aria-label="Resumo" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => (
          <Card key={c.label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground font-normal">{c.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold tabular-nums">{c.value.toLocaleString("pt-BR")}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Última execução por mercado</CardTitle>
        </CardHeader>
        <CardContent>
          {data.last_run_by_store.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum mercado ativo.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-4">Mercado</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Início</th>
                    <th className="py-2 pr-4">Fim</th>
                    <th className="py-2 pr-4 text-right">Encontrados</th>
                    <th className="py-2 text-right">Atualizados</th>
                  </tr>
                </thead>
                <tbody>
                  {data.last_run_by_store.map((r) => (
                    <tr key={r.store_id} className="border-t">
                      <td className="py-2 pr-4 font-medium">{r.store_name}</td>
                      <td className="py-2 pr-4">
                        {r.last_status ? <Badge variant="secondary">{r.last_status}</Badge> : "—"}
                      </td>
                      <td className="py-2 pr-4">{fmt(r.last_started_at)}</td>
                      <td className="py-2 pr-4">{fmt(r.last_finished_at)}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{r.products_found ?? "—"}</td>
                      <td className="py-2 text-right tabular-nums">{r.products_updated ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Erros recentes de coleta</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_errors.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum erro recente registrado.</p>
          ) : (
            <ul className="space-y-3">
              {data.recent_errors.map((e) => (
                <li key={e.id} className="rounded-md border p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <strong>{e.store_name ?? "Mercado desconhecido"}</strong>
                    <Badge variant="destructive">{e.status}</Badge>
                  </div>
                  <p className="mt-1 text-muted-foreground">{fmt(e.started_at)}</p>
                  {e.error_message && (
                    <p className="mt-2 whitespace-pre-wrap text-destructive">{e.error_message}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
