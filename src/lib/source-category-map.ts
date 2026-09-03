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
};
