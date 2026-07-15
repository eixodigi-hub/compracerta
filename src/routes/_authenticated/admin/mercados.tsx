import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

export const Route = createFileRoute("/_authenticated/admin/mercados")({
  component: MercadosPage,
});

function MercadosPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "stores", q],
    queryFn: async () => {
      let query = supabase
        .from("stores")
        .select("id, name, slug, website_url, address, active, last_successful_sync_at")
        .order("name");
      if (q) query = query.ilike("name", `%${q}%`);
      const { data, error } = await query;
      if (error) throw error;
      return data;
    },
  });

  async function toggleActive(id: string, active: boolean) {
    const { error } = await supabase.from("stores").update({ active }).eq("id", id);
    if (error) toast.error(error.message);
    else {
      toast.success(active ? "Mercado ativado" : "Mercado desativado");
      qc.invalidateQueries({ queryKey: ["admin", "stores"] });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mercados</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Input
          placeholder="Buscar por nome..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-sm"
        />
        {isLoading ? (
          <Skeleton className="h-40" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr>
                  <th className="py-2 pr-4">Nome</th>
                  <th className="py-2 pr-4">Slug</th>
                  <th className="py-2 pr-4">Site</th>
                  <th className="py-2 pr-4">Última sincronização</th>
                  <th className="py-2 pr-4">Ativo</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {data?.map((s) => (
                  <tr key={s.id} className="border-t">
                    <td className="py-2 pr-4 font-medium">{s.name}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{s.slug}</td>
                    <td className="py-2 pr-4">
                      {s.website_url ? (
                        <a href={s.website_url} target="_blank" rel="noreferrer" className="text-primary underline">
                          abrir
                        </a>
                      ) : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      {s.last_successful_sync_at ? new Date(s.last_successful_sync_at).toLocaleString("pt-BR") : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      <Switch checked={s.active} onCheckedChange={(v) => toggleActive(s.id, v)} />
                    </td>
                    <td className="py-2">
                      <Button size="sm" variant="ghost" asChild>
                        <a href={s.website_url ?? "#"} target="_blank" rel="noreferrer">Ver site</a>
                      </Button>
                    </td>
                  </tr>
                ))}
                {data?.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-muted-foreground">
                      Nenhum mercado encontrado.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
