import { Link } from "@tanstack/react-router";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ImageOff, Store, Clock, GitCompareArrows, Plus, Trophy } from "lucide-react";
import type { SearchProductRow } from "@/lib/search-queries";

function currency(v: number | null | undefined) {
  if (v == null) return "—";
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatQty(quantity: number | null, unit: string | null) {
  if (!quantity && !unit) return null;
  const q = quantity != null ? String(quantity).replace(/\.0+$/, "") : "";
  return [q, unit].filter(Boolean).join(" ");
}

function formatUpdated(iso: string) {
  const d = new Date(iso);
  return `${d.toLocaleDateString("pt-BR")} ${d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}

export function ProductCard({
  product,
  onAddToList,
}: {
  product: SearchProductRow;
  onAddToList?: (p: SearchProductRow) => void;
}) {
  const qty = formatQty(product.quantity, product.unit);
  const discount = Math.round(product.max_discount_pct);
  const detailLink = product.is_canonical ? "/produto/$id" : undefined;

  return (
    <Card className="flex flex-col gap-3 overflow-hidden p-4 transition-shadow hover:shadow-md">
      <div className="flex gap-3">
        <div className="grid h-20 w-20 shrink-0 place-items-center overflow-hidden rounded-xl bg-secondary">
          {product.image_url ? (
            <img
              src={product.image_url}
              alt={product.name}
              className="h-full w-full object-contain"
              loading="lazy"
            />
          ) : (
            <ImageOff className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start gap-1.5">
            {product.is_canonical ? (
              <Link
                to="/produto/$id"
                params={{ id: product.id }}
                className="line-clamp-2 flex-1 text-sm font-semibold leading-tight hover:underline"
              >
                {product.name}
              </Link>
            ) : (
              <h3 className="line-clamp-2 flex-1 text-sm font-semibold leading-tight">
                {product.name}
              </h3>
            )}
            {product.has_promotion && discount > 0 && (
              <Badge className="bg-promo text-promo-foreground hover:bg-promo">
                -{discount}%
              </Badge>
            )}
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {product.brand ?? "Sem marca"}
            {qty ? ` · ${qty}` : ""}
          </p>
          {!product.is_canonical && (
            <p className="mt-1 text-xs text-muted-foreground">Produto ainda não catalogado</p>
          )}
        </div>
      </div>

      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs text-muted-foreground">A partir de</p>
          <p className="text-lg font-bold text-primary">{currency(product.min_price)}</p>
          {product.has_promotion &&
            product.reference_price != null &&
            product.reference_price > product.min_price && (
              <p className="text-xs text-muted-foreground line-through">
                {currency(product.reference_price)}
              </p>
            )}
        </div>
        <div className="text-right text-xs text-muted-foreground">
          <p className="inline-flex items-center gap-1">
            <Store className="h-3 w-3" aria-hidden="true" />
            {product.market_count} {product.market_count === 1 ? "mercado" : "mercados"}
          </p>
          <p className="mt-0.5 inline-flex items-center gap-1">
            <Clock className="h-3 w-3" aria-hidden="true" />
            {formatUpdated(product.last_updated)}
          </p>
        </div>
      </div>

      <div className="space-y-2 rounded-lg border border-border bg-secondary/30 p-2.5">
        {product.offers.map((offer) => (
          <div
            key={offer.store_product_id}
            className="flex items-start justify-between gap-3 rounded-md bg-card px-2.5 py-2"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5">
                <p className="truncate text-xs font-semibold">{offer.store_name}</p>
                {offer.is_lowest && (
                  <Badge variant="secondary" className="gap-1 border-primary/20 bg-primary-soft text-primary">
                    <Trophy className="h-3 w-3" aria-hidden="true" />
                    menor preço
                  </Badge>
                )}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Normal: {currency(offer.regular_price)}
                {offer.promotional_price != null ? ` · Promo: ${currency(offer.promotional_price)}` : ""}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Coleta: {formatUpdated(offer.collected_at)}
              </p>
            </div>
            <p className="shrink-0 text-right text-sm font-bold text-primary">
              {currency(offer.effective_price)}
            </p>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        {detailLink ? (
          <Button asChild size="sm" className="flex-1">
            <Link to="/produto/$id" params={{ id: product.id }}>
              <GitCompareArrows className="mr-1.5 h-4 w-4" aria-hidden="true" />
              Comparar preços
            </Link>
          </Button>
        ) : (
          <Button size="sm" className="flex-1" disabled>
            <GitCompareArrows className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Aguardando catálogo
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => onAddToList?.(product)}
          disabled={!product.is_canonical}
          aria-label="Adicionar à lista"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </Card>
  );
}
