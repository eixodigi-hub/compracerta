import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { Copy, Pencil, Plus, Trash2 } from "lucide-react";

export const Route = createFileRoute("/_authenticated/admin/mercados")({
  component: MercadosPage,
});

type StoreRow = {
  id: string;
  name: string;
  slug: string;
  website_url: string | null;
  address: string | null;
  logo_url: string | null;
  active: boolean;
  last_successful_sync_at: string | null;
  city_id: string;
};

type FormState = {
  name: string;
  slug: string;
  website_url: string;
  address: string;
  logo_url: string;
  active: boolean;
};

const emptyForm: FormState = {
  name: "",
  slug: "",
  website_url: "",
  address: "",
  logo_url: "",
  active: true,
};

function slugify(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function MercadosPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<StoreRow | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<StoreRow | null>(null);
  const [slugTouched, setSlugTouched] = useState(false);

  const { data: cities } = useQuery({
    queryKey: ["cities"],
    queryFn: async () => {
      const { data, error } = await supabase.from("cities").select("id, slug, name").order("name");
      if (error) throw error;
      return data;
    },
  });

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "stores", q],
    queryFn: async () => {
      let query = supabase
        .from("stores")
        .select("id, name, slug, website_url, address, logo_url, active, last_successful_sync_at, city_id")
        .order("name");
      if (q) query = query.ilike("name", `%${q}%`);
      const { data, error } = await query;
      if (error) throw error;
      return data as StoreRow[];
    },
  });

  useEffect(() => {
    if (!dialogOpen) return;
    if (editing) {
      setForm({
        name: editing.name,
        slug: editing.slug,
        website_url: editing.website_url ?? "",
        address: editing.address ?? "",
        logo_url: editing.logo_url ?? "",
        active: editing.active,
      });
      setSlugTouched(true);
    } else {
      setForm(emptyForm);
      setSlugTouched(false);
    }
  }, [dialogOpen, editing]);

  async function toggleActive(id: string, active: boolean) {
    const { error } = await supabase.from("stores").update({ active }).eq("id", id);
    if (error) toast.error(error.message);
    else {
      toast.success(active ? "Mercado ativado" : "Mercado desativado");
      qc.invalidateQueries({ queryKey: ["admin", "stores"] });
    }
  }

  function openCreate() {
    setEditing(null);
    setDialogOpen(true);
  }

  function openEdit(row: StoreRow) {
    setEditing(row);
    setDialogOpen(true);
  }

  async function handleSave() {
    if (!form.name.trim()) {
      toast.error("Informe o nome do mercado");
      return;
    }
    const slug = (form.slug.trim() || slugify(form.name)).trim();
    if (!slug) {
      toast.error("Slug inválido");
      return;
    }
    if (form.website_url && !/^https?:\/\//i.test(form.website_url)) {
      toast.error("O site deve começar com http:// ou https://");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        slug,
        website_url: form.website_url.trim() || null,
        address: form.address.trim() || null,
        logo_url: form.logo_url.trim() || null,
        active: form.active,
      };
      if (editing) {
        const { error } = await supabase.from("stores").update(payload).eq("id", editing.id);
        if (error) throw error;
        toast.success("Mercado atualizado");
      } else {
        const cityId = cities?.[0]?.id;
        if (!cityId) {
          toast.error("Nenhuma cidade cadastrada");
          setSaving(false);
          return;
        }
        const { error } = await supabase.from("stores").insert({ ...payload, city_id: cityId });
        if (error) throw error;
        toast.success("Mercado criado");
      }
      setDialogOpen(false);
      qc.invalidateQueries({ queryKey: ["admin", "stores"] });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erro ao salvar mercado";
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    const { error } = await supabase.from("stores").delete().eq("id", deleteTarget.id);
    if (error) toast.error(error.message);
    else {
      toast.success("Mercado excluído");
      qc.invalidateQueries({ queryKey: ["admin", "stores"] });
    }
    setDeleteTarget(null);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle>Mercados</CardTitle>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm" onClick={openCreate}>
              <Plus className="mr-1 h-4 w-4" /> Novo mercado
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editing ? "Editar mercado" : "Novo mercado"}</DialogTitle>
              <DialogDescription>
                Informe os dados do mercado e o site oficial usado pelo robô de coleta.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="name">Nome</Label>
                <Input
                  id="name"
                  value={form.name}
                  onChange={(e) => {
                    const name = e.target.value;
                    setForm((f) => ({
                      ...f,
                      name,
                      slug: slugTouched ? f.slug : slugify(name),
                    }));
                  }}
                  placeholder="Ex.: Supermercado Central"
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="slug">Slug</Label>
                <Input
                  id="slug"
                  value={form.slug}
                  onChange={(e) => {
                    setSlugTouched(true);
                    setForm((f) => ({ ...f, slug: e.target.value }));
                  }}
                  placeholder="supermercado-central"
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="website_url">Site</Label>
                <Input
                  id="website_url"
                  type="url"
                  value={form.website_url}
                  onChange={(e) => setForm((f) => ({ ...f, website_url: e.target.value }))}
                  placeholder="https://..."
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="address">Endereço</Label>
                <Input
                  id="address"
                  value={form.address}
                  onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))}
                  placeholder="Rua, número, bairro"
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="logo_url">URL do logo</Label>
                <Input
                  id="logo_url"
                  type="url"
                  value={form.logo_url}
                  onChange={(e) => setForm((f) => ({ ...f, logo_url: e.target.value }))}
                  placeholder="https://..."
                />
              </div>
              <div className="flex items-center justify-between rounded-md border p-3">
                <div>
                  <Label htmlFor="active">Ativo</Label>
                  <p className="text-xs text-muted-foreground">Mercado aparece nas comparações públicas.</p>
                </div>
                <Switch
                  id="active"
                  checked={form.active}
                  onCheckedChange={(v) => setForm((f) => ({ ...f, active: v }))}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setDialogOpen(false)} disabled={saving}>
                Cancelar
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? "Salvando..." : "Salvar"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardHeader>
      <CardContent className="space-y-4">
        <Input
          placeholder="Buscar por nome..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-sm"
        />
        {isLoading ? (
          <Skeleton className="h-40" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr>
                  <th className="py-2 pr-4">Nome</th>
                  <th className="py-2 pr-4">store_id</th>
                  <th className="py-2 pr-4">Slug</th>
                  <th className="py-2 pr-4">Site</th>
                  <th className="py-2 pr-4">Última sincronização</th>
                  <th className="py-2 pr-4">Ativo</th>
                  <th className="py-2 text-right">Ações</th>
                </tr>
              </thead>
              <tbody>
                {data?.map((s) => (
                  <tr key={s.id} className="border-t">
                    <td className="py-2 pr-4 font-medium">{s.name}</td>
                    <td className="py-2 pr-4">
                      <div className="flex items-center gap-1">
                        <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{s.id.slice(0, 8)}…</code>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0"
                          onClick={() => {
                            navigator.clipboard.writeText(s.id);
                            toast.success("store_id copiado");
                          }}
                        >
                          <Copy className="h-3 w-3" />
                          <span className="sr-only">Copiar store_id</span>
                        </Button>
                      </div>
                    </td>
                    <td className="py-2 pr-4 text-muted-foreground">{s.slug}</td>
                    <td className="py-2 pr-4">
                      {s.website_url ? (
                        <a href={s.website_url} target="_blank" rel="noreferrer" className="text-primary underline">
                          abrir
                        </a>
                      ) : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      {s.last_successful_sync_at ? new Date(s.last_successful_sync_at).toLocaleString("pt-BR") : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      <Switch checked={s.active} onCheckedChange={(v) => toggleActive(s.id, v)} />
                    </td>
                    <td className="py-2">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => openEdit(s)}>
                          <Pencil className="h-4 w-4" />
                          <span className="sr-only">Editar</span>
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setDeleteTarget(s)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                          <span className="sr-only">Excluir</span>
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {data?.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-muted-foreground">
                      Nenhum mercado encontrado.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir mercado?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação removerá <strong>{deleteTarget?.name}</strong> e todos os produtos coletados e preços vinculados.
              Não é possível desfazer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
