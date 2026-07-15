import { createFileRoute, Link, Outlet, redirect } from "@tanstack/react-router";
import { supabase } from "@/integrations/supabase/client";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Store,
  Package,
  ShoppingBasket,
  Link2,
  Tag,
  Bot,
  Users,
  ShieldAlert,
} from "lucide-react";

export const Route = createFileRoute("/_authenticated/admin")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Administração — Compra Certa" },
      { name: "description", content: "Painel administrativo restrito." },
      { name: "robots", content: "noindex" },
    ],
  }),
  beforeLoad: async ({ context, location }) => {
    // context.user is set by the parent _authenticated layout
    const user = (context as { user?: { id: string } }).user;
    if (!user) {
      throw redirect({ to: "/auth", search: { redirect: location.href } });
    }
    const { data, error } = await supabase.rpc("has_role", {
      _user_id: user.id,
      _role: "admin",
    });
    if (error || !data) {
      throw redirect({ to: "/" });
    }
  },
  component: AdminLayout,
});

const nav: Array<{ to: string; label: string; icon: typeof LayoutDashboard; exact?: boolean }> = [
  { to: "/admin", label: "Visão geral", icon: LayoutDashboard, exact: true },
  { to: "/admin/mercados", label: "Mercados", icon: Store },
  { to: "/admin/produtos-canonicos", label: "Produtos canônicos", icon: Package },
  { to: "/admin/produtos-coletados", label: "Produtos coletados", icon: ShoppingBasket },
  { to: "/admin/pendentes", label: "Pendentes de associação", icon: Link2 },
  { to: "/admin/precos", label: "Preços", icon: Tag },
  { to: "/admin/execucoes", label: "Execuções do robô", icon: Bot },
  { to: "/admin/usuarios", label: "Usuários", icon: Users },
];

function AdminLayout() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-6 flex items-center gap-2">
        <ShieldAlert className="h-5 w-5 text-primary" aria-hidden="true" />
        <h1 className="text-xl font-bold">Painel administrativo</h1>
      </div>
      <div className="grid gap-6 md:grid-cols-[220px_1fr]">
        <nav aria-label="Seções do painel" className="space-y-1">
          {nav.map((item) => (
            <Link
              key={item.to}
              to={item.to as never}
              activeOptions={{ exact: item.exact ?? false }}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors text-muted-foreground hover:bg-muted",
              )}
              activeProps={{
                className: "bg-primary/10 text-primary font-medium hover:bg-primary/10",
              }}
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </Link>
          ))}
        </nav>
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
