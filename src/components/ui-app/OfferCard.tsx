import { Card } from "@/components/ui/card";
import { Tag } from "lucide-react";

export type Offer = {
  id: string;
  product: string;
  market: string;
  price?: string;
  oldPrice?: string;
  validUntil?: string;
};

export function OfferCard({ offer }: { offer: Offer }) {
  return (
    <Card className="overflow-hidden p-0 shadow-sm transition-shadow hover:shadow-md">
      <div className="relative aspect-video bg-secondary" aria-hidden="true">
        <span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-promo px-2.5 py-1 text-xs font-semibold text-promo-foreground">
          <Tag className="h-3 w-3" aria-hidden="true" />
          Oferta
        </span>
      </div>
      <div className="p-4">
        <h3 className="line-clamp-2 font-semibold">{offer.product}</h3>
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
      </div>
    </Card>
  );
}
