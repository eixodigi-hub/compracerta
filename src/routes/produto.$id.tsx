import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { ExternalLink, TrendingDown, TrendingUp, AlertCircle } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  productDetailOptions,
  priceHistoryOptions,
  priceStatsOptions,
} from "@/lib/product-detail-queries";

const brl = (v: number | null | undefined) =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const dateTimeFmt = (iso: string | null | undefined) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
};

const dayFmt = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });

export const Route = createFileRoute("/produto/$id")({
  loader: ({ params, context }) => {
    context.queryClient.ensureQueryData(productDetailOptions(params.id));
    context.queryClient.ensureQueryData(priceHistoryOptions(params.id, 30));
    context.queryClient.ensureQueryData(priceStatsOptions(params.id, 30));
  },
  head: () => ({
    meta: [
      { title: "Detalhes do produto — Compra Certa Marília" },
      { name: "description", content: "Compare o preço deste produto entre os supermercados de Marília." },
    ],
  }),
  errorComponent: ({ error }) => (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>Não foi possível carregar o produto: {error.message}</AlertDescription>
      </Alert>
    </div>
  ),
  notFoundComponent: () => (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <p>Produto não encontrado.</p>
    </div>
  ),
  component: ProdutoPage,
});

function ProdutoPage() {
  const { id } = Route.useParams();
  const router = useRouter();
  const { data } = useSuspenseQuery(productDetailOptions(id));
  const { data: history } = useSuspenseQuery(priceHistoryOptions(id, 30));
  const { data: stats } = useSuspenseQuery(priceStatsOptions(id, 30));

  if (!data.product) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10">
        <p className="text-muted-foreground">Produto não encontrado ou indisponível.</p>
        <Button className="mt-4" variant="outline" onClick={() => router.history.back()}>
          Voltar
        </Button>
      </div>
    );
  }

  const p = data.product;
  const offers = [...data.offers].sort((a, b) => {
    const av = a.effective_price ?? Number.POSITIVE_INFINITY;
    const bv = b.effective_price ?? Number.POSITIVE_INFINITY;
    return av - bv;
  });

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:py-10 space-y-8">
      {/* Header */}
      <div className="grid gap-6 md:grid-cols-[220px_1fr]">
        <div className="aspect-square overflow-hidden rounded-lg bg-secondary">
          {p.image_url ? (
            <img src={p.image_url} alt={p.name} className="h-full w-full object-contain" />
          ) : null}
        </div>
        <div>
          {p.category_name ? (
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{p.category_name}</p>
          ) : null}
          <h1 className="mt-1 text-2xl font-bold md:text-3xl">{p.name}</h1>
          <div className="mt-2 flex flex-wrap gap-2 text-sm text-muted-foreground">
            {p.brand ? <Badge variant="secondary">{p.brand}</Badge> : null}
            {p.quantity != null ? (
              <Badge variant="outline">
                {p.quantity} {p.unit ?? ""}
              </Badge>
            ) : null}
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            Última atualização: {dateTimeFmt(data.last_updated)}
          </p>
          <Button className="mt-4">Adicionar à lista</Button>
        </div>
      </div>

      {/* Stats last 30 days */}
      <section>
        <h2 className="text-lg font-semibold">Resumo dos últimos 30 dias</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Menor preço" value={brl(stats.min)} />
          <StatCard label="Maior preço" value={brl(stats.max)} />
          <StatCard label="Preço médio" value={brl(stats.avg)} />
          <StatCard
            label="Variação atual vs. média"
            value={stats.variation_pct == null ? "—" : `${stats.variation_pct > 0 ? "+" : ""}${stats.variation_pct}%`}
            icon={
              stats.variation_pct == null ? null : stats.variation_pct < 0 ? (
                <TrendingDown className="h-4 w-4 text-green-600" />
              ) : (
                <TrendingUp className="h-4 w-4 text-orange-600" />
              )
            }
          />
        </div>
      </section>

      {/* Chart */}
      <section>
        <h2 className="text-lg font-semibold">Histórico de preços (30 dias)</h2>
        <Card className="mt-3 p-4">
          {history.length < 2 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Ainda não há histórico suficiente para exibir o gráfico. Volte em breve.
            </p>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="day" tickFormatter={dayFmt} fontSize={12} />
                  <YAxis tickFormatter={(v) => `R$ ${Number(v).toFixed(2)}`} fontSize={12} width={70} />
                  <Tooltip
                    formatter={(v: number) => brl(v)}
                    labelFormatter={(l: string) => dayFmt(l)}
                  />
                  <Line
                    type="monotone"
                    dataKey="min_price"
                    name="Menor"
                    stroke="hsl(var(--primary))"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="avg_price"
                    name="Média"
                    stroke="hsl(var(--muted-foreground))"
                    strokeDasharray="4 4"
                    strokeWidth={1.5}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </section>

      {/* Comparison table */}
      <section>
        <h2 className="text-lg font-semibold">Comparação entre mercados</h2>
        <Card className="mt-3 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mercado</TableHead>
                <TableHead className="text-right">Preço normal</TableHead>
                <TableHead className="text-right">Promoção</TableHead>
                <TableHead className="text-right">Efetivo</TableHead>
                <TableHead>Estoque</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {offers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-6">
                    Nenhum mercado com este produto no momento.
                  </TableCell>
                </TableRow>
              ) : (
                offers.map((o, idx) => (
                  <TableRow key={o.store_id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{o.store_name}</span>
                        {idx === 0 && o.effective_price != null ? (
                          <Badge className="bg-green-600 hover:bg-green-600">Melhor preço</Badge>
                        ) : null}
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{brl(o.regular_price)}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {o.promotional_price != null ? (
                        <span className="font-medium text-orange-600">{brl(o.promotional_price)}</span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums font-semibold">
                      {brl(o.effective_price)}
                    </TableCell>
                    <TableCell>
                      {o.in_stock === false ? (
                        <Badge variant="outline" className="text-muted-foreground">
                          Sem estoque
                        </Badge>
                      ) : (
                        <Badge variant="secondary">Disponível</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {o.product_url || o.website_url ? (
                        <Button asChild size="sm" variant="outline">
                          <a href={o.product_url ?? o.website_url ?? "#"} target="_blank" rel="noopener noreferrer">
                            Ir para o mercado
                            <ExternalLink className="ml-1 h-3 w-3" />
                          </a>
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Card>

        <Alert className="mt-4">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Preços e disponibilidade podem mudar a qualquer momento no site do supermercado. Confirme sempre antes de finalizar a compra.
          </AlertDescription>
        </Alert>
      </section>

      <div>
        <Button variant="ghost" onClick={() => router.history.back()}>
          ← Voltar
        </Button>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
        {icon}
      </div>
      <p className="mt-2 text-xl font-semibold tabular-nums">{value}</p>
    </Card>
  );
}
