import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  LogOut,
  User as UserIcon,
  ShieldAlert,
  Search,
  Bell,
  ImageOff,
  Trash2,
  Sparkles,
  ListChecks,
  ChevronRight,
} from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "sonner";
import { useAuth } from "@/hooks/use-auth";
import {
  promoAlertsOptions,
  subscribeAlert,
  unsubscribeAlertById,
  type PromoAlert,
} from "@/lib/promo-alert-queries";
import { listsOptions } from "@/lib/shopping-list-queries";

export const Route = createFileRoute("/_authenticated/perfil")({
  head: () => ({
    meta: [
      { title: "Meu perfil — Compra Certa" },
      { name: "description", content: "Gerencie suas informações, listas salvas e preferências." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: PerfilPage,
});

function PerfilPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const profile = useQuery({
    queryKey: ["profile", user?.id],
    enabled: !!user,
    queryFn: async () => {
      const { data, error } = await supabase
        .from("profiles")
        .select("id, full_name, display_name, city_id")
        .eq("id", user!.id)
        .maybeSingle();
      if (error) throw error;
      return data;
    },
  });

  const isAdmin = useQuery({
    queryKey: ["is-admin", user?.id],
    enabled: !!user,
    queryFn: async () => {
      const { data, error } = await supabase.rpc("has_role", {
        _user_id: user!.id,
        _role: "admin",
      });
      if (error) throw error;
      return !!data;
    },
  });

  async function handleSignOut() {
    await queryClient.cancelQueries();
    queryClient.clear();
    await supabase.auth.signOut();
    toast.success("Você saiu da conta.");
    navigate({ to: "/auth", replace: true });
  }

  const name = profile.data?.full_name ?? profile.data?.display_name ?? user?.email ?? "Usuário";

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 md:py-10">
      <div className="flex items-center gap-4">
        <div className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-secondary">
          <UserIcon className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-bold">{name}</h1>
          <p className="truncate text-sm text-muted-foreground">{user?.email}</p>
        </div>
        <Button variant="outline" onClick={handleSignOut}>
          <LogOut className="mr-2 h-4 w-4" aria-hidden="true" />
          Sair
        </Button>
      </div>

      <div className="mt-8">
        <SavedListsCard />
      </div>

      <div className="mt-6">
        <PromoAlertsCard userEmail={user?.email ?? null} />
      </div>

      {isAdmin.data && (
        <div className="mt-6">
          <Button asChild variant="default">
            <Link to="/admin">
              <ShieldAlert className="mr-2 h-4 w-4" aria-hidden="true" />
              Acessar painel administrativo
            </Link>
          </Button>
        </div>
      )}
    </div>
  );
}

/* --------------------------- Promo alerts --------------------------- */

function PromoAlertsCard({ userEmail }: { userEmail: string | null }) {
  const qc = useQueryClient();
  const alertsQuery = useQuery(promoAlertsOptions());
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  const suggestQuery = useQuery({
    queryKey: ["product-suggest-alerts", debounced],
    enabled: debounced.trim().length >= 2,
    queryFn: async () => {
      const { data, error } = await supabase.rpc("search_canonical_products", {
        q: debounced,
        max_results: 8,
      });
      if (error) throw error;
      return (data ?? []) as Array<{
        id: string;
        name: string;
        brand: string | null;
        quantity: number | null;
        unit: string | null;
      }>;
    },
  });

  const alertedIds = new Set((alertsQuery.data ?? []).map((a) => a.canonical_product_id));

  const addMut = useMutation({
    mutationFn: (productId: string) => subscribeAlert(productId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["promo-alerts"] });
      qc.invalidateQueries({ queryKey: ["promo-alert-ids"] });
      setQ("");
      setOpen(false);
      toast.success("Produto adicionado aos seus alertas");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const removeMut = useMutation({
    mutationFn: (alertId: string) => unsubscribeAlertById(alertId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["promo-alerts"] });
      qc.invalidateQueries({ queryKey: ["promo-alert-ids"] });
      toast.success("Alerta removido");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const alerts = alertsQuery.data ?? [];

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <Bell className="h-5 w-5 text-primary" aria-hidden="true" />
        <h2 className="font-semibold">Alertas de promoção</h2>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Escolha os produtos que você quer acompanhar. Assim que um deles entrar em promoção em
        algum mercado, avisamos por e-mail{userEmail ? ` em ${userEmail}` : ""}.
      </p>

      <div className="relative mt-4">
        <Label htmlFor="alert-search" className="sr-only">
          Buscar produto
        </Label>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          id="alert-search"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder="Digite o nome de um produto para acompanhar…"
          className="pl-9"
        />
        {open && debounced.trim().length >= 2 && (
          <div className="absolute z-30 mt-1 max-h-72 w-full overflow-auto rounded-md border border-border bg-popover shadow-md">
            {suggestQuery.isLoading && (
              <p className="p-3 text-sm text-muted-foreground">Buscando…</p>
            )}
            {!suggestQuery.isLoading && (suggestQuery.data?.length ?? 0) === 0 && (
              <p className="p-3 text-sm text-muted-foreground">Nenhum produto encontrado.</p>
            )}
            {suggestQuery.data?.map((p) => {
              const already = alertedIds.has(p.id);
              return (
                <button
                  key={p.id}
                  type="button"
                  disabled={already || addMut.isPending}
                  onClick={() => addMut.mutate(p.id)}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-accent disabled:cursor-default disabled:opacity-60"
                >
                  <span className="min-w-0 truncate">
                    <span className="font-medium">{p.name}</span>
                    {p.brand ? <span className="ml-2 text-muted-foreground">{p.brand}</span> : null}
                  </span>
                  {already ? (
                    <span className="shrink-0 text-xs text-muted-foreground">Já acompanhando</span>
                  ) : p.quantity != null ? (
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {p.quantity} {p.unit ?? ""}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="mt-4">
        {alertsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Carregando…</p>
        ) : alerts.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Você ainda não está acompanhando nenhum produto. Use a busca acima.
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border">
            {alerts.map((a) => (
              <PromoAlertRow
                key={a.alert_id}
                alert={a}
                onRemove={() => removeMut.mutate(a.alert_id)}
                removing={removeMut.isPending && removeMut.variables === a.alert_id}
              />
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

function PromoAlertRow({
  alert,
  onRemove,
  removing,
}: {
  alert: PromoAlert;
  onRemove: () => void;
  removing: boolean;
}) {
  const brl = (v: number | null) =>
    v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

  return (
    <li className="flex items-center gap-3 p-3">
      <div className="grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-lg bg-secondary">
        {alert.image_url ? (
          <img
            src={alert.image_url}
            alt={alert.name}
            className="h-full w-full object-contain"
            loading="lazy"
          />
        ) : (
          <ImageOff className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{alert.name}</p>
        <p className="truncate text-xs text-muted-foreground">
          {alert.brand ?? "Sem marca"}
          {alert.quantity != null ? ` · ${alert.quantity} ${alert.unit ?? ""}` : ""}
        </p>
        {alert.has_promotion ? (
          <Badge className="mt-1 gap-1 bg-promo text-promo-foreground hover:bg-promo">
            <Sparkles className="h-3 w-3" aria-hidden="true" />
            Em promoção agora — {brl(alert.min_price)}
            {alert.best_store_name ? ` na ${alert.best_store_name}` : ""}
          </Badge>
        ) : (
          <p className="mt-1 text-xs text-muted-foreground">
            {alert.min_price != null ? `Sem promoção agora — ${brl(alert.min_price)}` : "Aguardando preço"}
          </p>
        )}
      </div>
      <Button size="icon" variant="ghost" onClick={onRemove} disabled={removing} aria-label="Remover alerta">
        <Trash2 className="h-4 w-4" aria-hidden="true" />
      </Button>
    </li>
  );
}

/* ---------------------------- Saved lists ---------------------------- */

function SavedListsCard() {
  const listsQuery = useQuery(listsOptions());
  const lists = listsQuery.data ?? [];

  const fmt = (iso: string) =>
    new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <ListChecks className="h-5 w-5 text-primary" aria-hidden="true" />
        <h2 className="font-semibold">Listas salvas</h2>
      </div>

      {listsQuery.isLoading ? (
        <p className="mt-2 text-sm text-muted-foreground">Carregando…</p>
      ) : lists.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">
          Você ainda não tem listas.{" "}
          <Link to="/lista" className="text-primary hover:underline">
            Criar minha primeira lista
          </Link>
          .
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-border rounded-lg border border-border">
          {lists.map((l) => (
            <li key={l.id}>
              <Link
                to="/lista"
                className="flex items-center justify-between gap-3 p-3 text-sm hover:bg-accent"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{l.name}</p>
                  <p className="text-xs text-muted-foreground">Criada em {fmt(l.created_at)}</p>
                </div>
                <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
