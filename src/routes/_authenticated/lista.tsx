import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Plus, Trash2, Pencil, Check, X, Search, ShoppingBasket, AlertCircle, Store as StoreIcon, Sparkles } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import {
  listsOptions,
  listItemsOptions,
  comparisonOptions,
  createList,
  renameList,
  deleteList,
  addItem,
  updateItem,
  removeItem,
  type ShoppingList,
  type ShoppingListItem,
} from "@/lib/shopping-list-queries";

export const Route = createFileRoute("/_authenticated/lista")({
  head: () => ({
    meta: [
      { title: "Minhas listas — Compra Certa Marília" },
      { name: "description", content: "Monte sua lista de compras e descubra em qual mercado sai mais barato." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: ListaPage,
});

const brl = (v: number | null | undefined) =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function ListaPage() {
  const qc = useQueryClient();
  const listsQuery = useQuery(listsOptions());
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Auto-select first list once loaded
  const lists = listsQuery.data ?? [];
  const currentId = selectedId ?? lists[0]?.id ?? null;
  const current = lists.find((l) => l.id === currentId) ?? null;

  const itemsQuery = useQuery(listItemsOptions(currentId));
  const cmpQuery = useQuery(comparisonOptions(currentId));

  const invalidateAll = (id: string | null) => {
    qc.invalidateQueries({ queryKey: ["shopping-lists"] });
    if (id) {
      qc.invalidateQueries({ queryKey: ["shopping-list-items", id] });
      qc.invalidateQueries({ queryKey: ["shopping-list-comparison", id] });
    }
  };

  const createMut = useMutation({
    mutationFn: (name: string) => createList(name),
    onSuccess: (list) => {
      setSelectedId(list.id);
      invalidateAll(list.id);
      toast.success("Lista criada");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:py-10 space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold md:text-3xl">Minhas listas</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Crie listas, adicione produtos e compare os supermercados.
          </p>
        </div>
        <NewListButton onCreate={(name) => createMut.mutate(name)} />
      </header>

      {listsQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Carregando…</p>
      ) : lists.length === 0 ? (
        <EmptyLists onCreate={(name) => createMut.mutate(name)} />
      ) : (
        <>
          <ListSelector
            lists={lists}
            currentId={currentId}
            onSelect={setSelectedId}
            onRenamed={() => invalidateAll(currentId)}
            onDeleted={(deletedId) => {
              const rest = lists.filter((l) => l.id !== deletedId);
              setSelectedId(rest[0]?.id ?? null);
              invalidateAll(null);
            }}
            current={current}
          />

          {current ? (
            <>
              <AddItemPanel
                listId={current.id}
                onAdded={() => invalidateAll(current.id)}
              />
              <ItemsPanel
                items={itemsQuery.data ?? []}
                loading={itemsQuery.isLoading}
                onChanged={() => invalidateAll(current.id)}
              />
              <ComparisonPanel
                loading={cmpQuery.isLoading}
                data={cmpQuery.data ?? null}
              />
            </>
          ) : null}
        </>
      )}
    </div>
  );
}

/* ------------------------------ New list ------------------------------ */

function NewListButton({ onCreate }: { onCreate: (name: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  if (!editing) {
    return (
      <Button onClick={() => setEditing(true)}>
        <Plus className="mr-1 h-4 w-4" /> Nova lista
      </Button>
    );
  }
  return (
    <form
      className="flex items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        const trimmed = name.trim();
        if (!trimmed) return;
        onCreate(trimmed);
        setName("");
        setEditing(false);
      }}
    >
      <Input
        autoFocus
        placeholder="Ex.: Compra do mês"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-56"
      />
      <Button type="submit" size="icon" aria-label="Criar"><Check className="h-4 w-4" /></Button>
      <Button type="button" size="icon" variant="ghost" onClick={() => { setEditing(false); setName(""); }} aria-label="Cancelar">
        <X className="h-4 w-4" />
      </Button>
    </form>
  );
}

function EmptyLists({ onCreate }: { onCreate: (name: string) => void }) {
  return (
    <Card className="flex flex-col items-center justify-center gap-3 p-10 text-center">
      <ShoppingBasket className="h-8 w-8 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">Você ainda não tem listas.</p>
      <Button onClick={() => onCreate("Minha lista")}>
        <Plus className="mr-1 h-4 w-4" /> Criar primeira lista
      </Button>
    </Card>
  );
}

/* ---------------------------- List selector --------------------------- */

function ListSelector({
  lists,
  currentId,
  current,
  onSelect,
  onRenamed,
  onDeleted,
}: {
  lists: ShoppingList[];
  currentId: string | null;
  current: ShoppingList | null;
  onSelect: (id: string) => void;
  onRenamed: () => void;
  onDeleted: (id: string) => void;
}) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState("");

  const renameMut = useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) => renameList(id, name),
    onSuccess: () => { setRenaming(false); onRenamed(); toast.success("Lista renomeada"); },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: async (id: string) => deleteList(id),
    onSuccess: (_v, id) => { onDeleted(id); toast.success("Lista excluída"); },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={currentId ?? undefined} onValueChange={onSelect}>
        <SelectTrigger className="w-64"><SelectValue placeholder="Escolha uma lista" /></SelectTrigger>
        <SelectContent>
          {lists.map((l) => (
            <SelectItem key={l.id} value={l.id}>{l.name}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      {current && !renaming && (
        <>
          <Button variant="outline" size="sm" onClick={() => { setName(current.name); setRenaming(true); }}>
            <Pencil className="mr-1 h-4 w-4" /> Renomear
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (confirm(`Excluir a lista "${current.name}"? Esta ação não pode ser desfeita.`)) {
                deleteMut.mutate(current.id);
              }
            }}
          >
            <Trash2 className="mr-1 h-4 w-4" /> Excluir
          </Button>
        </>
      )}

      {current && renaming && (
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            const trimmed = name.trim();
            if (!trimmed) return;
            renameMut.mutate({ id: current.id, name: trimmed });
          }}
        >
          <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} className="w-56" />
          <Button size="icon" type="submit" aria-label="Salvar"><Check className="h-4 w-4" /></Button>
          <Button size="icon" variant="ghost" type="button" onClick={() => setRenaming(false)} aria-label="Cancelar"><X className="h-4 w-4" /></Button>
        </form>
      )}
    </div>
  );
}

/* ------------------------------ Add item ------------------------------ */

type ProductSuggestion = { id: string; name: string; brand: string | null; quantity: number | null; unit: string | null };

function AddItemPanel({ listId, onAdded }: { listId: string; onAdded: () => void }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  const suggestQuery = useQuery({
    queryKey: ["product-suggest", debounced],
    enabled: debounced.trim().length >= 2,
    queryFn: async (): Promise<ProductSuggestion[]> => {
      const { data, error } = await supabase.rpc("search_canonical_products", { q: debounced, max_results: 8 });
      if (error) throw error;
      return (data as ProductSuggestion[]) ?? [];
    },
  });

  const addMut = useMutation({
    mutationFn: (productId: string) => addItem(listId, productId, 1, false),
    onSuccess: () => {
      onAdded();
      setQ("");
      setOpen(false);
      toast.success("Produto adicionado");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Card className="p-4">
      <Label htmlFor="add-item">Adicionar produto</Label>
      <div className="relative mt-2">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          id="add-item"
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder="Digite ao menos 2 letras…"
          className="pl-9"
        />
        {open && debounced.trim().length >= 2 && (
          <div className="absolute z-30 mt-1 max-h-72 w-full overflow-auto rounded-md border border-border bg-popover shadow-md">
            {suggestQuery.isLoading && <p className="p-3 text-sm text-muted-foreground">Buscando…</p>}
            {!suggestQuery.isLoading && (suggestQuery.data?.length ?? 0) === 0 && (
              <p className="p-3 text-sm text-muted-foreground">Nenhum produto encontrado.</p>
            )}
            {suggestQuery.data?.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => addMut.mutate(p.id)}
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-accent"
              >
                <span className="min-w-0 truncate">
                  <span className="font-medium">{p.name}</span>
                  {p.brand ? <span className="ml-2 text-muted-foreground">{p.brand}</span> : null}
                </span>
                {p.quantity != null ? (
                  <span className="shrink-0 text-xs text-muted-foreground">{p.quantity} {p.unit ?? ""}</span>
                ) : null}
              </button>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

/* ------------------------------ Items ------------------------------ */

function ItemsPanel({
  items,
  loading,
  onChanged,
}: {
  items: ShoppingListItem[];
  loading: boolean;
  onChanged: () => void;
}) {
  const updateMut = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: { quantity?: number; allow_similar_products?: boolean } }) =>
      updateItem(id, patch),
    onSuccess: onChanged,
    onError: (e: Error) => toast.error(e.message),
  });
  const removeMut = useMutation({
    mutationFn: (id: string) => removeItem(id),
    onSuccess: onChanged,
    onError: (e: Error) => toast.error(e.message),
  });

  if (loading) return <p className="text-sm text-muted-foreground">Carregando itens…</p>;
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">Sua lista está vazia. Use o campo acima para adicionar produtos.</p>;
  }

  return (
    <Card className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Produto</TableHead>
            <TableHead className="w-28">Quantidade</TableHead>
            <TableHead className="w-56">Similares</TableHead>
            <TableHead className="w-16" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((it) => (
            <TableRow key={it.id}>
              <TableCell>
                <div className="font-medium">{it.product?.name ?? "Produto"}</div>
                <div className="text-xs text-muted-foreground">
                  {it.product?.brand ?? ""}
                  {it.product?.quantity != null ? ` · ${it.product?.quantity} ${it.product?.unit ?? ""}` : ""}
                </div>
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  min={1}
                  step={1}
                  value={it.quantity}
                  onChange={(e) => {
                    const v = Math.max(1, Number(e.target.value) || 1);
                    updateMut.mutate({ id: it.id, patch: { quantity: v } });
                  }}
                  className="h-8 w-20"
                />
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <Switch
                    id={`sim-${it.id}`}
                    checked={it.allow_similar_products}
                    onCheckedChange={(v) => updateMut.mutate({ id: it.id, patch: { allow_similar_products: v } })}
                  />
                  <Label htmlFor={`sim-${it.id}`} className="text-xs text-muted-foreground">
                    {it.allow_similar_products ? "Permitir similares" : "Somente este produto"}
                  </Label>
                </div>
              </TableCell>
              <TableCell>
                <Button size="icon" variant="ghost" onClick={() => removeMut.mutate(it.id)} aria-label="Remover">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

/* --------------------------- Comparison --------------------------- */

function ComparisonPanel({
  loading,
  data,
}: {
  loading: boolean;
  data: import("@/lib/shopping-list-queries").ComparisonPayload | null;
}) {
  if (loading) return <p className="text-sm text-muted-foreground">Calculando…</p>;
  if (!data || data.items.length === 0) return null;

  const perItem = data.per_item;
  const bestComplete = data.best_complete;

  return (
    <div className="space-y-6">
      {/* Cenário 1: compra completa */}
      <section>
        <h2 className="text-lg font-semibold">Cenário 1 — Compra completa em um único mercado</h2>
        <p className="text-sm text-muted-foreground">
          Só entra no cálculo o mercado que tem todos os produtos da lista.
        </p>

        {bestComplete ? (
          <Alert className="mt-3 border-green-600/50 bg-green-50 dark:bg-green-950/20">
            <Sparkles className="h-4 w-4" />
            <AlertDescription>
              Mercado mais barato: <strong>{bestComplete.store_name}</strong> — total <strong>{brl(bestComplete.total_all)}</strong>.
            </AlertDescription>
          </Alert>
        ) : (
          <Alert className="mt-3">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Nenhum mercado possui todos os itens da sua lista neste momento.
            </AlertDescription>
          </Alert>
        )}

        <div className="mt-4 grid gap-3">
          {data.stores.map((s) => (
            <Card key={s.store_id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 font-medium">
                  <StoreIcon className="h-4 w-4 text-muted-foreground" />
                  {s.store_name}
                </div>
                <div className="text-right">
                  {s.has_missing ? (
                    <span className="text-sm text-muted-foreground">Sem cálculo total</span>
                  ) : (
                    <span className="text-lg font-semibold tabular-nums">{brl(s.total_all)}</span>
                  )}
                </div>
              </div>
              {s.has_missing && (
                <p className="mt-2 text-sm text-orange-700 dark:text-orange-300">
                  Este mercado não possui todos os itens da sua lista.
                </p>
              )}
              {s.missing_names && s.missing_names.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {s.missing_names.map((n) => (
                    <Badge key={n} variant="outline" className="text-muted-foreground">{n}</Badge>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      </section>

      {/* Cenário 2: menor preço por produto */}
      <section>
        <h2 className="text-lg font-semibold">Cenário 2 — Menor preço por produto</h2>
        <p className="text-sm text-muted-foreground">
          Comprando cada item no mercado mais barato. Não substituímos marcas automaticamente.
        </p>

        {!perItem ? (
          <p className="mt-3 text-sm text-muted-foreground">Sem dados suficientes para calcular.</p>
        ) : (
          <>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <MiniStat label="Total combinado" value={brl(perItem.total)} />
              <MiniStat label="Mercados a visitar" value={String(perItem.stores_needed)} />
              <MiniStat
                label="Economia vs. compra completa"
                value={data.savings == null ? "—" : brl(data.savings)}
                highlight={data.savings != null && data.savings > 0}
              />
            </div>

            {perItem.missing_names && perItem.missing_names.length > 0 && (
              <Alert className="mt-3">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  Itens indisponíveis em qualquer mercado: {perItem.missing_names.join(", ")}.
                </AlertDescription>
              </Alert>
            )}

            <Card className="mt-3 overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Produto</TableHead>
                    <TableHead>Melhor mercado</TableHead>
                    <TableHead className="text-right">Qtd.</TableHead>
                    <TableHead className="text-right">Unit.</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {perItem.breakdown.map((b) => (
                    <TableRow key={b.product_id}>
                      <TableCell className="font-medium">{b.product_name}</TableCell>
                      <TableCell>{b.store_name}</TableCell>
                      <TableCell className="text-right tabular-nums">{b.quantity}</TableCell>
                      <TableCell className="text-right tabular-nums">{brl(b.unit_price)}</TableCell>
                      <TableCell className="text-right tabular-nums font-semibold">{brl(b.line_total)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          </>
        )}
      </section>
    </div>
  );
}

function MiniStat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <Card className={`p-4 ${highlight ? "border-green-600/50 bg-green-50 dark:bg-green-950/20" : ""}`}>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
    </Card>
  );
}
