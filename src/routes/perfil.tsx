import { createFileRoute, Link } from "@tanstack/react-router";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { User } from "lucide-react";

export const Route = createFileRoute("/perfil")({
  head: () => ({
    meta: [
      { title: "Meu perfil — Compra Certa Marília" },
      { name: "description", content: "Gerencie suas informações, listas salvas e preferências." },
      { property: "og:title", content: "Meu perfil — Compra Certa Marília" },
      { property: "og:description", content: "Gerencie suas informações, listas salvas e preferências." },
    ],
  }),
  component: PerfilPage,
});

function PerfilPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-6 md:py-10">
      <div className="flex items-center gap-4">
        <div className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-secondary">
          <User className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-bold">Visitante</h1>
          <p className="text-sm text-muted-foreground">Você ainda não entrou.</p>
        </div>
      </div>

      <div className="mt-6 flex gap-2">
        <Button asChild>
          <Link to="/entrar">Entrar ou cadastrar</Link>
        </Button>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <Card className="p-5">
          <h2 className="font-semibold">Listas salvas</h2>
          <p className="mt-1 text-sm text-muted-foreground">Nenhuma lista salva ainda.</p>
        </Card>
        <Card className="p-5">
          <h2 className="font-semibold">Preferências</h2>
          <p className="mt-1 text-sm text-muted-foreground">Mercados favoritos e notificações.</p>
        </Card>
      </div>
    </div>
  );
}
