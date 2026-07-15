import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LogOut, User as UserIcon } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "sonner";
import { useAuth } from "@/hooks/use-auth";

export const Route = createFileRoute("/_authenticated/perfil")({
  head: () => ({
    meta: [
      { title: "Meu perfil — Compra Certa Marília" },
      { name: "description", content: "Gerencie suas informações, listas salvas e preferências." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: PerfilPage,
});

function PerfilPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const profile = useQuery({
    queryKey: ["profile", user?.id],
    enabled: !!user,
    queryFn: async () => {
      const { data, error } = await supabase
        .from("profiles")
        .select("id, full_name, display_name, city_id")
        .eq("id", user!.id)
        .maybeSingle();
      if (error) throw error;
      return data;
    },
  });

  async function handleSignOut() {
    await queryClient.cancelQueries();
    queryClient.clear();
    await supabase.auth.signOut();
    toast.success("Você saiu da conta.");
    navigate({ to: "/auth", replace: true });
  }

  const name = profile.data?.full_name ?? profile.data?.display_name ?? user?.email ?? "Usuário";

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 md:py-10">
      <div className="flex items-center gap-4">
        <div className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-secondary">
          <UserIcon className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-bold">{name}</h1>
          <p className="truncate text-sm text-muted-foreground">{user?.email}</p>
        </div>
        <Button variant="outline" onClick={handleSignOut}>
          <LogOut className="mr-2 h-4 w-4" aria-hidden="true" />
          Sair
        </Button>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <Card className="p-5">
          <h2 className="font-semibold">Listas salvas</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Suas listas de compras aparecerão aqui.
          </p>
        </Card>
        <Card className="p-5">
          <h2 className="font-semibold">Preferências</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Mercados favoritos e alertas de preço em breve.
          </p>
        </Card>
      </div>
    </div>
  );
}
