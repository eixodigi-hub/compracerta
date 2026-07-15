import { createFileRoute } from "@tanstack/react-router";
import { ShieldAlert } from "lucide-react";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Administração — Compra Certa Marília" },
      { name: "description", content: "Área administrativa protegida." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminPage,
});

function AdminPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <div className="rounded-lg border border-border p-8 text-center">
        <ShieldAlert className="mx-auto h-10 w-10 text-primary" aria-hidden="true" />
        <h1 className="mt-4 text-2xl font-bold">Área administrativa</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Acesso restrito. A autenticação será implementada em uma etapa futura.
        </p>
      </div>
    </div>
  );
}
