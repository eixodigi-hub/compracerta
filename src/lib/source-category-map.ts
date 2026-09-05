// Mapeia a chave de categoria bruta que cada coletor envia (`source_category`)
// para o slug de categoria exibido no site (tabela `categories`).
// Chaves sem mapeamento (ex.: "marcas_exclusivas", "bazar_utilidades") ficam
// sem categoria — aparecem só em "Todos", não quebram o filtro.
export const SOURCE_CATEGORY_TO_SLUG: Record<string, string> = {
  // Tauste
  arroz: "alimentos",
  feijao: "alimentos",
  cafe: "alimentos",
  leite: "alimentos",
  oleo: "alimentos",
  acucar: "alimentos",
  macarrao: "alimentos",
  refrigerante: "bebidas",
  papel_higienico: "higiene-pessoal",
  detergente: "limpeza",
  farinha: "alimentos",
  sal: "alimentos",
  biscoitos: "alimentos",
  conservas_enlatados: "alimentos",
  creme_de_leite: "alimentos",
  leite_condensado: "alimentos",
  azeite_vinagre: "alimentos",
  creme_dental: "higiene-pessoal",
  fraldas: "bebes",
  iogurtes: "alimentos",

  // Confiança
  alimentos_basicos: "alimentos",
  matinais: "alimentos",
  padaria: "padaria",
  hortifruti: "alimentos",
  acougue: "alimentos",
  emporium: "alimentos",
  bebidas: "bebidas",
  higiene_beleza: "higiene-pessoal",
  pet_shop: "pet",

  // Spani
  pet: "pet",
  biscoitos_chocolates: "alimentos",
  carnes: "alimentos",
  cereais_farinaceos: "alimentos",
  congelados: "congelados",
  frios_laticinios: "alimentos",
  matinais_sobremesas: "alimentos",
  mercearia: "alimentos",
  perfumaria_higiene: "higiene-pessoal",

  // Atacadão (chaves não compartilhadas com Spani/Kawakami — os
  // departamentos deles agrupam diferente)
  limpeza: "limpeza",
  padaria_matinais: "padaria",
  frios_congelados: "alimentos",
  cafeteria: "alimentos",
};

function normalize(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

const BABY_WIPE_MARKERS = [
  "baby",
  "bebe",
  "infantil",
  "nascido",
  "johnson",
  "pampers",
  "huggies",
  "cotondela",
];
const BABY_WIPE_EXCLUDE = ["feminin", "intimo", "intima", "antissept"];

/**
 * Nenhum coletor mapeia uma categoria bruta "bebês" além das fraldas do
 * Tauste — mamadeira, chupeta e lenço/toalha umedecida de bebê chegam
 * pela categoria genérica de higiene/perfumaria da loja e ficam presos
 * lá. Detecta esses itens pelo nome pra sempre corrigir pra "bebes",
 * não importa a categoria bruta de origem. Fralda fica de fora daqui
 * de propósito — geriátrica/adulto usa o mesmo termo e já é
 * corretamente mapeada só pelas chaves de categoria dedicadas.
 */
export function isBabyProductName(name: string): boolean {
  const n = normalize(name);
  if (n.includes("mamadeira") || n.includes("chupeta")) return true;
  if (/toalha.*umedecid/.test(n)) return true;
  if (/lenco.*umedecid/.test(n)) {
    if (BABY_WIPE_EXCLUDE.some((w) => n.includes(w))) return false;
    return BABY_WIPE_MARKERS.some((w) => n.includes(w));
  }
  return false;
}
