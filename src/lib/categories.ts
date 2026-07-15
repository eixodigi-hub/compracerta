import { Apple, CupSoda, Sparkles, SprayCan, Baby, Dog, Snowflake, Croissant } from "lucide-react";
import type { Category } from "@/components/ui-app/CategoryCard";

export const CATEGORIES: Category[] = [
  { slug: "alimentos", name: "Alimentos", icon: Apple },
  { slug: "bebidas", name: "Bebidas", icon: CupSoda },
  { slug: "higiene", name: "Higiene pessoal", icon: Sparkles },
  { slug: "limpeza", name: "Limpeza", icon: SprayCan },
  { slug: "bebes", name: "Bebês", icon: Baby },
  { slug: "pet", name: "Pet", icon: Dog },
  { slug: "congelados", name: "Congelados", icon: Snowflake },
  { slug: "padaria", name: "Padaria", icon: Croissant },
];
