import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Trash2 } from "lucide-react";

export const Route = createFileRoute("/_authenticated/admin/produtos-canonicos")({
  component: Page,
});

const PAGE_SIZE = 20;

function Page() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "canonical", q, page],
    queryFn: async () => {
      let query = supabase
        .from("canonical_products")
        .select("id, name, brand, quantity, unit, barcode, image_url, active", { count: "exact" })
        .order("name")
        .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1);
      if (q) query = query.or(`name.ilike.%${q}%,brand.ilike.%${q}%,barcode.eq.${q}`);
      const { data, error, count } = await query;
      if (error) throw error;
      return { rows: data, count: count ?? 0 };
    },
  });

  async function remove(id: string) {
    const { error } = await supabase.from("canonical_products").update({ active: false }).eq("id", id);
    if (error) toast.error(error.message);
    else {
      toast.success("Produto desativado");
      qc.invalidateQueries({ queryKey: ["admin", "canonical"] });
    }
  }

  const total = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Produtos canônicos</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Input
          placeholder="Buscar por nome, marca ou código de barras..."
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(0); }}
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
                    <th className="py-2 pr-4">Nome</th>
                    <th className="py-2 pr-4">Marca</th>
                    <th className="py-2 pr-4">Qtd</th>
                    <th className="py-2 pr-4">Un</th>
                    <th className="py-2 pr-4">Cód. barras</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {data?.rows?.map((p) => (
                    <tr key={p.id} className="border-t">
                      <td className="py-2 pr-4 font-medium">{p.name}</td>
                      <td className="py-2 pr-4">{p.brand ?? "—"}</td>
                      <td className="py-2 pr-4 tabular-nums">{p.quantity ?? "—"}</td>
                      <td className="py-2 pr-4">{p.unit ?? "—"}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{p.barcode ?? "—"}</td>
                      <td className="py-2 pr-4">
                        {p.active ? <Badge>ativo</Badge> : <Badge variant="secondary">inativo</Badge>}
                      </td>
                      <td className="py-2 text-right">
                        {p.active && (
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button variant="ghost" size="icon" aria-label="Desativar">
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Desativar produto?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  O produto <strong>{p.name}</strong> ficará oculto para os usuários. Você pode reativá-lo depois.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                                <AlertDialogAction onClick={() => remove(p.id)}>Desativar</AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        )}
                      </td>
                    </tr>
                  ))}
                  {data?.rows?.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-muted-foreground">
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
                <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                  Anterior
                </Button>
                <span className="text-sm">{page + 1} / {totalPages}</span>
                <Button variant="outline" size="sm" disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>
                  Próxima
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
