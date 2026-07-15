import { Link } from "@tanstack/react-router";
import { getCategoryIcon } from "@/lib/category-icons";

export type Category = { slug: string; name: string; icon: string | null };

export function CategoryCard({ category }: { category: Category }) {
  const Icon = getCategoryIcon(category.icon);
  return (
    <Link
      to="/pesquisar"
      className="group flex flex-col items-center justify-center gap-2 rounded-2xl border border-border bg-card p-4 text-center shadow-sm transition-colors hover:border-primary/40 hover:bg-primary-soft"
    >
      <span className="grid h-12 w-12 place-items-center rounded-full bg-primary-soft text-primary transition-transform group-hover:scale-105">
        <Icon className="h-6 w-6" aria-hidden="true" />
      </span>
      <span className="text-sm font-medium text-foreground">{category.name}</span>
    </Link>
  );
}
