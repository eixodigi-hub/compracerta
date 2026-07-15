import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

export const Route = createFileRoute("/_authenticated/admin/execucoes")({
  component: Page,
});

const PAGE_SIZE = 25;

function Page() {
  const [status, setStatus] = useState<string>("all");
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "runs", status, page],
    queryFn: async () => {
      let q = supabase
        .from("ingestion_runs")
        .select("id, status, products_found, products_updated, error_message, started_at, finished_at, stores(name)", { count: "exact" })
        .order("started_at", { ascending: false })
        .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1);
      if (status !== "all") q = q.eq("status", status);
      const { data, error, count } = await q;
      if (error) throw error;
      return { rows: data ?? [], count: count ?? 0 };
    },
  });

  const total = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Execuções do robô</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Select value={status} onValueChange={(v) => { setStatus(v); setPage(0); }}>
          <SelectTrigger className="max-w-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos os status</SelectItem>
            <SelectItem value="success">Sucesso</SelectItem>
            <SelectItem value="failed">Falha</SelectItem>
            <SelectItem value="running">Em execução</SelectItem>
          </SelectContent>
        </Select>

        {isLoading ? (
          <Skeleton className="h-64" />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-4">Mercado</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Início</th>
                    <th className="py-2 pr-4">Fim</th>
                    <th className="py-2 pr-4 text-right">Encontrados</th>
                    <th className="py-2 pr-4 text-right">Atualizados</th>
                    <th className="py-2">Erro</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.rows.map((r) => (
                    <tr key={r.id} className="border-t align-top">
                      <td className="py-2 pr-4">{(r as { stores?: { name?: string } }).stores?.name ?? "—"}</td>
                      <td className="py-2 pr-4">
                        <Badge variant={r.status === "success" ? "default" : r.status === "failed" ? "destructive" : "secondary"}>
                          {r.status}
                        </Badge>
                      </td>
                      <td className="py-2 pr-4">{r.started_at ? new Date(r.started_at).toLocaleString("pt-BR") : "—"}</td>
                      <td className="py-2 pr-4">{r.finished_at ? new Date(r.finished_at).toLocaleString("pt-BR") : "—"}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{r.products_found ?? "—"}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{r.products_updated ?? "—"}</td>
                      <td className="py-2 max-w-xs text-destructive">
                        {r.error_message ?? ""}
                      </td>
                    </tr>
                  ))}
                  {data?.rows.length === 0 && (
                    <tr><td colSpan={7} className="py-6 text-center text-muted-foreground">Nenhuma execução.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">{total} execução(ões)</p>
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
