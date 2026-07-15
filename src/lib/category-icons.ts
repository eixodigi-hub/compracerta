import {
  Apple,
  CupSoda,
  Sparkles,
  SprayCan,
  Baby,
  Dog,
  Snowflake,
  Croissant,
  ShoppingBasket,
  type LucideIcon,
} from "lucide-react";

// Mapa de ícones (nomes armazenados no banco) para componentes lucide-react.
const ICON_MAP: Record<string, LucideIcon> = {
  Apple,
  CupSoda,
  Sparkles,
  SprayCan,
  Baby,
  Dog,
  Snowflake,
  Croissant,
};

export function getCategoryIcon(name: string | null | undefined): LucideIcon {
  if (!name) return ShoppingBasket;
  return ICON_MAP[name] ?? ShoppingBasket;
}
