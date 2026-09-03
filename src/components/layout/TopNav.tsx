import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ShoppingBasket, LogIn, MapPin } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useSelectedCity } from "@/hooks/use-selected-city";
import { citiesQuery } from "@/lib/queries";

const items: Array<{ to: "/" | "/pesquisar" | "/lista" | "/ofertas" | "/perfil"; label: string; exact?: boolean }> = [
  { to: "/", label: "Início", exact: true },
  { to: "/pesquisar", label: "Pesquisar" },
  { to: "/lista", label: "Lista" },
  { to: "/ofertas", label: "Ofertas" },
  { to: "/perfil", label: "Perfil" },
];

export function TopNav() {
  const { isAuthenticated } = useAuth();
  const { citySlug, clearCity } = useSelectedCity();
  const { data: cities } = useQuery(citiesQuery);
  const currentCity = cities?.find((city) => city.slug === citySlug);

  return (
    <header className="sticky top-0 z-40 hidden border-b border-border bg-background/95 backdrop-blur md:block">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2 font-bold text-foreground">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-foreground">
              <ShoppingBasket className="h-5 w-5" aria-hidden="true" />
            </span>
            <span>Compra Certa</span>
          </Link>
          {currentCity && (
            <button
              type="button"
              onClick={clearCity}
              title="Trocar cidade"
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
              {currentCity.name}
            </button>
          )}
        </div>
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
            {!isAuthenticated && (
              <li>
                <Link
                  to="/auth"
                  className="ml-2 inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  <LogIn className="h-4 w-4" aria-hidden="true" />
                  Entrar
                </Link>
              </li>
            )}
          </ul>
        </nav>
      </div>
    </header>
  );
}
