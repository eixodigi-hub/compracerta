import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

export const Route = createFileRoute("/_authenticated/admin/produtos-coletados")({
  component: Page,
});

const PAGE_SIZE = 25;

function Page() {
  const [q, setQ] = useState("");
  const [storeId, setStoreId] = useState<string>("all");
  const [matched, setMatched] = useState<"all" | "yes" | "no">("all");
  const [page, setPage] = useState(0);

  const { data: stores } = useQuery({
    queryKey: ["admin", "stores-list"],
    queryFn: async () => {
      const { data, error } = await supabase.from("stores").select("id, name").order("name");
      if (error) throw error;
      return data;
    },
  });

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "collected", q, storeId, matched, page],
    queryFn: async () => {
      let query = supabase
        .from("store_products")
        .select(
          "id, external_name, brand_raw, quantity_raw, unit_raw, barcode_raw, image_url, canonical_product_id, active, available, store_id, stores(name)",
          { count: "exact" },
        )
        .order("updated_at", { ascending: false })
        .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1);
      if (q) query = query.ilike("external_name", `%${q}%`);
      if (storeId !== "all") query = query.eq("store_id", storeId);
      if (matched === "yes") query = query.not("canonical_product_id", "is", null);
      if (matched === "no") query = query.is("canonical_product_id", null);
      const { data, error, count } = await query;
      if (error) throw error;
      return { rows: data, count: count ?? 0 };
    },
  });

  const total = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Produtos coletados</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Input
            placeholder="Buscar por nome coletado..."
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(0); }}
          />
          <Select value={storeId} onValueChange={(v) => { setStoreId(v); setPage(0); }}>
            <SelectTrigger><SelectValue placeholder="Mercado" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos os mercados</SelectItem>
              {stores?.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={matched} onValueChange={(v) => { setMatched(v as typeof matched); setPage(0); }}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="yes">Associados</SelectItem>
              <SelectItem value="no">Sem associação</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {isLoading ? (
          <Skeleton className="h-64" />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-4">Nome coletado</th>
                    <th className="py-2 pr-4">Mercado</th>
                    <th className="py-2 pr-4">Marca</th>
                    <th className="py-2 pr-4">Qtd/Un</th>
                    <th className="py-2 pr-4">Cód. barras</th>
                    <th className="py-2 pr-4">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.rows?.map((r) => (
                    <tr key={r.id} className="border-t">
                      <td className="py-2 pr-4 font-medium">{r.external_name}</td>
                      <td className="py-2 pr-4">{r.stores?.name ?? "—"}</td>
                      <td className="py-2 pr-4">{r.brand_raw ?? "—"}</td>
                      <td className="py-2 pr-4">{r.quantity_raw ?? "—"} {r.unit_raw ?? ""}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{r.barcode_raw ?? "—"}</td>
                      <td className="py-2 pr-4">
                        {r.canonical_product_id
                          ? <Badge>associado</Badge>
                          : <Badge variant="destructive">pendente</Badge>}
                        {!r.available && <Badge variant="secondary" className="ml-1">indisp.</Badge>}
                      </td>
                    </tr>
                  ))}
                  {data?.rows?.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-muted-foreground">
                        Nenhum produto encontrado.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">{total} produto(s)</p>
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
