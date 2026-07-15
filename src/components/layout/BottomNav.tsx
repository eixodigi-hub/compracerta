import { Link } from "@tanstack/react-router";
import { Home, Search, ListChecks, Tag, User } from "lucide-react";

const items = [
  { to: "/", label: "Início", icon: Home },
  { to: "/pesquisar", label: "Pesquisar", icon: Search },
  { to: "/lista", label: "Lista", icon: ListChecks },
  { to: "/ofertas", label: "Ofertas", icon: Tag },
  { to: "/perfil", label: "Perfil", icon: User },
] as const;

export function BottomNav() {
  return (
    <nav
      aria-label="Navegação principal"
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-background/95 backdrop-blur md:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <ul className="grid grid-cols-5">
        {items.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <Link
              to={to}
              activeOptions={{ exact: to === "/" }}
              activeProps={{ className: "text-primary" }}
              inactiveProps={{ className: "text-muted-foreground" }}
              className="flex flex-col items-center justify-center gap-1 py-2 text-xs font-medium transition-colors"
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
              <span>{label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
