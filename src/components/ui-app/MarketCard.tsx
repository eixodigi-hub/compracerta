import { Store } from "lucide-react";

export type Market = { id: string; name: string };

export function MarketCard({ market }: { market: Market }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-border bg-card p-3 shadow-sm">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
        <Store className="h-5 w-5" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{market.name}</p>
        <p className="text-xs text-muted-foreground">Marília, SP</p>
      </div>
    </div>
  );
}
