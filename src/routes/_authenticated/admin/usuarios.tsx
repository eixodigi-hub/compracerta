import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";

export const Route = createFileRoute("/_authenticated/admin/usuarios")({
  component: Page,
});

function Page() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "users", q],
    queryFn: async () => {
      let query = supabase.from("profiles").select("id, display_name, full_name, city, created_at").order("created_at", { ascending: false }).limit(100);
      if (q) query = query.or(`display_name.ilike.%${q}%,full_name.ilike.%${q}%`);
      const { data, error } = await query;
      if (error) throw error;

      const { data: roles, error: rolesError } = await supabase.from("user_roles").select("user_id, role");
      if (rolesError) throw rolesError;
      const roleMap = new Map<string, string[]>();
      for (const r of roles ?? []) {
        const arr = roleMap.get(r.user_id) ?? [];
        arr.push(r.role);
        roleMap.set(r.user_id, arr);
      }

      return (data ?? []).map((p) => ({ ...p, roles: roleMap.get(p.id) ?? ["user"] }));
    },
  });

  async function toggleAdmin(userId: string, makeAdmin: boolean) {
    if (makeAdmin) {
      const { error } = await supabase.from("user_roles").insert({ user_id: userId, role: "admin" });
      if (error) return toast.error(error.message);
      toast.success("Usuário promovido a admin");
    } else {
      const { error } = await supabase.from("user_roles").delete().eq("user_id", userId).eq("role", "admin");
      if (error) return toast.error(error.message);
      toast.success("Papel admin removido");
    }
    qc.invalidateQueries({ queryKey: ["admin", "users"] });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Usuários</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Input
          placeholder="Buscar por nome..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-sm"
        />
        {isLoading ? (
          <Skeleton className="h-64" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr>
                  <th className="py-2 pr-4">Nome</th>
                  <th className="py-2 pr-4">Cadastrado em</th>
                  <th className="py-2 pr-4">Papéis</th>
                  <th className="py-2 text-right">Ações</th>
                </tr>
              </thead>
              <tbody>
                {data?.map((u) => {
                  const isAdmin = u.roles.includes("admin");
                  return (
                    <tr key={u.id} className="border-t">
                      <td className="py-2 pr-4 font-medium">{u.display_name ?? u.full_name ?? "—"}</td>
                      <td className="py-2 pr-4">{new Date(u.created_at).toLocaleString("pt-BR")}</td>
                      <td className="py-2 pr-4">
                        {u.roles.map((r) => (
                          <Badge key={r} variant={r === "admin" ? "default" : "secondary"} className="mr-1">{r}</Badge>
                        ))}
                      </td>
                      <td className="py-2 text-right">
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button size="sm" variant={isAdmin ? "outline" : "default"}>
                              {isAdmin ? "Remover admin" : "Tornar admin"}
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>{isAdmin ? "Remover papel admin?" : "Conceder papel admin?"}</AlertDialogTitle>
                              <AlertDialogDescription>
                                {isAdmin
                                  ? "O usuário perderá o acesso administrativo imediatamente."
                                  : "O usuário passará a ter acesso total ao painel administrativo."}
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancelar</AlertDialogCancel>
                              <AlertDialogAction onClick={() => toggleAdmin(u.id, !isAdmin)}>
                                Confirmar
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </td>
                    </tr>
                  );
                })}
                {data?.length === 0 && (
                  <tr><td colSpan={4} className="py-6 text-center text-muted-foreground">Nenhum usuário.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
