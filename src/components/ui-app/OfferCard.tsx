import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tag, ListPlus, ImageOff } from "lucide-react";
import { Link } from "@tanstack/react-router";

export type Offer = {
  id: string;
  product: string;
  market: string;
  price?: string;
  oldPrice?: string;
  validUntil?: string;
  imageUrl?: string | null;
  canonicalId?: string | null;
};

export function OfferCard({
  offer,
  onAddToList,
  adding,
}: {
  offer: Offer;
  onAddToList?: (offer: Offer) => void;
  adding?: boolean;
}) {
  const hasProduct = !!offer.canonicalId;

  const media = (
    <div className="relative aspect-video overflow-hidden bg-secondary">
      {offer.imageUrl ? (
        <img
          src={offer.imageUrl}
          alt={offer.product}
          loading="lazy"
          className="h-full w-full object-contain transition-transform duration-200 group-hover:scale-105"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-muted-foreground">
          <ImageOff className="h-8 w-8" aria-hidden="true" />
        </div>
      )}
      {offer.oldPrice && (
        <span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-promo px-2.5 py-1 text-xs font-semibold text-promo-foreground shadow">
          <Tag className="h-3 w-3" aria-hidden="true" />
          Oferta
        </span>
      )}
    </div>
  );

  return (
    <Card className="group overflow-hidden p-0 shadow-sm transition-shadow hover:shadow-md">
      {hasProduct ? (
        <Link
          to="/produto/$id"
          params={{ id: offer.canonicalId! }}
          aria-label={`Ver detalhes de ${offer.product}`}
        >
          {media}
        </Link>
      ) : (
        media
      )}
      <div className="p-4">
        {hasProduct ? (
          <Link
            to="/produto/$id"
            params={{ id: offer.canonicalId! }}
            className="hover:underline"
          >
            <h3 className="line-clamp-2 font-semibold">{offer.product}</h3>
          </Link>
        ) : (
          <h3 className="line-clamp-2 font-semibold">{offer.product}</h3>
        )}
        <p className="mt-1 text-xs text-muted-foreground">{offer.market}</p>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-lg font-bold text-promo">{offer.price ?? "—"}</span>
          {offer.oldPrice && (
            <span className="text-xs text-muted-foreground line-through">{offer.oldPrice}</span>
          )}
        </div>
        {offer.validUntil && (
          <p className="mt-1 text-xs text-muted-foreground">Válido até {offer.validUntil}</p>
        )}
        {onAddToList && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-3 w-full rounded-xl"
            onClick={() => onAddToList(offer)}
            disabled={!hasProduct || adding}
            title={hasProduct ? "Adicionar à minha lista" : "Produto ainda não catalogado"}
          >
            <ListPlus className="mr-2 h-4 w-4" aria-hidden="true" />
            {adding ? "Adicionando..." : "Adicionar à minha lista"}
          </Button>
        )}
      </div>
    </Card>
  );
}
