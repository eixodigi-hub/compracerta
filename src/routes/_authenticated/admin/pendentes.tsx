import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { linkStoreProduct, suggestCanonical, type CanonicalSuggestion } from "@/lib/admin-queries";
import { Link2, Plus, RotateCcw, ImageOff } from "lucide-react";

export const Route = createFileRoute("/_authenticated/admin/pendentes")({
  component: Page,
});

const PAGE_SIZE = 15;

type StoreProductRow = {
  id: string;
  external_name: string;
  brand_raw: string | null;
  quantity_raw: string | null;
  unit_raw: string | null;
  barcode_raw: string | null;
  image_url: string | null;
  canonical_product_id: string | null;
  stores: { name: string } | null;
};

function Page() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<"pending" | "all">("pending");
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "pending", q, mode, page],
    queryFn: async () => {
      let query = supabase
        .from("store_products")
        .select(
          "id, external_name, brand_raw, quantity_raw, unit_raw, barcode_raw, image_url, canonical_product_id, stores(name)",
          { count: "exact" },
        )
        .order("updated_at", { ascending: false })
        .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1);
      if (mode === "pending") query = query.is("canonical_product_id", null);
      if (q) query = query.ilike("external_name", `%${q}%`);
      const { data, error, count } = await query;
      if (error) throw error;
      return { rows: (data ?? []) as StoreProductRow[], count: count ?? 0 };
    },
  });

  const unlink = useMutation({
    mutationFn: (id: string) => linkStoreProduct(id, null),
    onSuccess: () => {
      toast.success("Associação desfeita");
      qc.invalidateQueries({ queryKey: ["admin", "pending"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const total = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pendentes de associação</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            placeholder="Buscar por nome coletado..."
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(0); }}
            className="max-w-sm"
          />
          <Button
            variant={mode === "pending" ? "default" : "outline"}
            size="sm"
            onClick={() => { setMode("pending"); setPage(0); }}
          >
            Pendentes
          </Button>
          <Button
            variant={mode === "all" ? "default" : "outline"}
            size="sm"
            onClick={() => { setMode("all"); setPage(0); }}
          >
            Todos
          </Button>
        </div>

        {isLoading ? (
          <Skeleton className="h-64" />
        ) : data?.rows.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Nenhum produto {mode === "pending" ? "pendente" : ""}.
          </p>
        ) : (
          <ul className="space-y-3">
            {data?.rows.map((r) => (
              <PendingItem key={r.id} row={r} onUnlink={() => unlink.mutate(r.id)} />
            ))}
          </ul>
        )}

        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">{total} produto(s)</p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Anterior</Button>
            <span className="text-sm">{page + 1} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>Próxima</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function PendingItem({ row, onUnlink }: { row: StoreProductRow; onUnlink: () => void }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  const suggestions = useQuery({
    queryKey: ["admin", "suggest", row.id],
    queryFn: () => suggestCanonical(row.id),
    enabled: open,
  });

  const link = useMutation({
    mutationFn: (canonicalId: string) => linkStoreProduct(row.id, canonicalId),
    onSuccess: () => {
      toast.success("Produto associado");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["admin", "pending"] });
      qc.invalidateQueries({ queryKey: ["admin", "overview"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <li className="rounded-lg border p-3">
      <div className="flex gap-3">
        {row.image_url ? (
          <img
            src={row.image_url}
            alt=""
            className="h-16 w-16 rounded object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-16 w-16 items-center justify-center rounded bg-muted">
            <ImageOff className="h-6 w-6 text-muted-foreground" aria-hidden />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="font-medium">{row.external_name}</p>
          <p className="text-xs text-muted-foreground">
            {row.stores?.name ?? "—"} · {row.brand_raw ?? "sem marca"} · {row.quantity_raw ?? "?"} {row.unit_raw ?? ""} · {row.barcode_raw ?? "sem cód."}
          </p>
          {row.canonical_product_id && (
            <Badge className="mt-1" variant="secondary">já associado</Badge>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Link2 className="mr-1 h-4 w-4" />
                Associar
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Sugestões compatíveis</DialogTitle>
                <DialogDescription>
                  Só aparecem produtos canônicos com quantidade e unidade compatíveis com o item coletado.
                </DialogDescription>
              </DialogHeader>
              {suggestions.isLoading ? (
                <Skeleton className="h-40" />
              ) : suggestions.data?.length === 0 ? (
                <Alert>
                  <AlertDescription>
                    Nenhuma sugestão compatível. Você pode criar um novo produto canônico.
                  </AlertDescription>
                </Alert>
              ) : (
                <ul className="max-h-80 space-y-2 overflow-y-auto">
                  {suggestions.data?.map((s: CanonicalSuggestion) => (
                    <li key={s.id} className="flex items-center gap-3 rounded border p-2">
                      {s.image_url ? (
                        <img src={s.image_url} alt="" className="h-10 w-10 rounded object-cover" loading="lazy" />
                      ) : (
                        <div className="h-10 w-10 rounded bg-muted" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{s.name}</p>
                        <p className="truncate text-xs text-muted-foreground">
                          {s.brand ?? "—"} · {s.quantity ?? "?"} {s.unit ?? ""} · {s.barcode ?? "sem cód."}
                        </p>
                      </div>
                      <Badge variant="secondary" className="tabular-nums">
                        {(s.score * 100).toFixed(0)}%
                      </Badge>
                      <Button size="sm" onClick={() => link.mutate(s.id)} disabled={link.isPending}>
                        Associar
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
              <DialogFooter>
                <CreateCanonicalDialog
                  open={createOpen}
                  onOpenChange={setCreateOpen}
                  storeProduct={row}
                  onCreated={(id) => { setCreateOpen(false); link.mutate(id); }}
                />
              </DialogFooter>
            </DialogContent>
          </Dialog>
          {row.canonical_product_id && (
            <Button size="sm" variant="ghost" onClick={onUnlink}>
              <RotateCcw className="mr-1 h-4 w-4" />
              Desfazer
            </Button>
          )}
        </div>
      </div>
    </li>
  );
}

function CreateCanonicalDialog({
  open, onOpenChange, storeProduct, onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  storeProduct: StoreProductRow;
  onCreated: (id: string) => void;
}) {
  const [name, setName] = useState(storeProduct.external_name);
  const [brand, setBrand] = useState(storeProduct.brand_raw ?? "");
  const [quantity, setQuantity] = useState(storeProduct.quantity_raw ?? "");
  const [unit, setUnit] = useState(storeProduct.unit_raw ?? "");
  const [barcode, setBarcode] = useState(storeProduct.barcode_raw ?? "");
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    const qty = quantity ? Number(quantity.replace(",", ".")) : null;
    const { data, error } = await supabase
      .from("canonical_products")
      .insert({
        name,
        brand: brand || null,
        quantity: qty,
        unit: unit || null,
        barcode: barcode || null,
        image_url: storeProduct.image_url,
        active: true,
      })
      .select("id")
      .single();
    setSaving(false);
    if (error) return toast.error(error.message);
    toast.success("Produto canônico criado");
    onCreated(data.id);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Plus className="mr-1 h-4 w-4" />
          Criar novo canônico
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Novo produto canônico</DialogTitle>
          <DialogDescription>
            Os dados foram pré-preenchidos com o item coletado. Ajuste antes de salvar.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <label className="text-sm">Nome
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="text-sm">Marca
            <Input value={brand} onChange={(e) => setBrand(e.target.value)} />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-sm">Quantidade
              <Input value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            </label>
            <label className="text-sm">Unidade
              <Input value={unit} onChange={(e) => setUnit(e.target.value)} />
            </label>
          </div>
          <label className="text-sm">Código de barras
            <Input value={barcode} onChange={(e) => setBarcode(e.target.value)} />
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={submit} disabled={saving || !name}>Criar e associar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
