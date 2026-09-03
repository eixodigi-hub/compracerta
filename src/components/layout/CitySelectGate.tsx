import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { MapPin } from "lucide-react";

import { citiesQuery } from "@/lib/queries";
import { useSelectedCity } from "@/hooks/use-selected-city";
import { Skeleton } from "@/components/ui/skeleton";

export function CitySelectGate({ children }: { children: ReactNode }) {
  const { citySlug, selectCity } = useSelectedCity();
  const { data: cities, isLoading } = useQuery(citiesQuery);

  // Ainda não checamos o localStorage (SSR / primeiro paint) ou já há
  // cidade escolhida — não bloqueia a navegação.
  if (citySlug === undefined || citySlug) {
    return <>{children}</>;
  }

  return (
    <>
      {children}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="city-gate-title"
        className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4"
      >
        <div className="w-full max-w-sm rounded-lg border border-border bg-background p-6 shadow-lg">
          <div className="mb-3 flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-foreground">
              <MapPin className="h-5 w-5" aria-hidden="true" />
            </span>
            <h2 id="city-gate-title" className="text-lg font-semibold text-foreground">
              Escolha sua cidade
            </h2>
          </div>
          <p className="mb-4 text-sm text-muted-foreground">
            Comparamos preços de supermercados por cidade. Selecione a sua para começar.
          </p>

          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-11 w-full" />
              <Skeleton className="h-11 w-full" />
            </div>
          ) : (cities ?? []).length > 0 ? (
            <div className="space-y-2">
              {cities!.map((city) => (
                <button
                  key={city.id}
                  type="button"
                  onClick={() => selectCity(city.slug)}
                  className="flex w-full items-center justify-between rounded-md border border-input px-4 py-2.5 text-left text-sm font-medium text-foreground transition-colors hover:bg-secondary"
                >
                  {city.name} - {city.state}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Nenhuma cidade disponível no momento.</p>
          )}
        </div>
      </div>
    </>
  );
}
