import { Link } from "@tanstack/react-router";
import { ShoppingBasket } from "lucide-react";

const items: Array<{ to: "/" | "/pesquisar" | "/lista" | "/ofertas" | "/perfil"; label: string; exact?: boolean }> = [
  { to: "/", label: "Início", exact: true },
  { to: "/pesquisar", label: "Pesquisar" },
  { to: "/lista", label: "Lista" },
  { to: "/ofertas", label: "Ofertas" },
  { to: "/perfil", label: "Perfil" },
];

export function TopNav() {
  return (
    <header className="sticky top-0 z-40 hidden border-b border-border bg-background/95 backdrop-blur md:block">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2 font-bold text-foreground">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-foreground">
            <ShoppingBasket className="h-5 w-5" aria-hidden="true" />
          </span>
          <span>Compra Certa Marília</span>
        </Link>
        <nav aria-label="Navegação principal">
          <ul className="flex items-center gap-1">
            {items.map(({ to, label, exact }) => (
              <li key={to}>
                <Link
                  to={to}
                  activeOptions={{ exact: !!exact }}
                  activeProps={{ className: "bg-secondary text-foreground" }}
                  inactiveProps={{ className: "text-muted-foreground hover:text-foreground" }}
                  className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-secondary"
                >
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
