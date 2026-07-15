# Etapa 1 — Estrutura inicial do "Compra Certa Marília"

Objetivo: criar apenas o esqueleto visual e a navegação (mobile-first, com jeito de app instalado). Sem dados fictícios extensos, sem Supabase, sem coletor de preços.

## Design
- Mobile-first, responsivo, acessível (landmarks, aria-labels, foco visível).
- Paleta clara e amigável (verde/laranja de mercado) definida como tokens em `src/styles.css` (light + dark), sem cores hardcoded nos componentes.
- Tipografia: Inter (carregada via `<link>` em `__root.tsx`).
- Componentes shadcn já disponíveis (Button, Card, Input, Tabs, Sheet, Avatar, etc.).
- Sensação de app: safe areas, bottom nav fixo no mobile, top nav no desktop, transições suaves.

## Rotas (TanStack Start, arquivos em `src/routes/`)
Cada rota terá `head()` próprio (title + description + og).

| Arquivo | URL | Conteúdo |
|---|---|---|
| `index.tsx` (reescrever placeholder) | `/` | Home: busca em destaque, atalhos (Ofertas, Lista, Pesquisar), seção "Como funciona" |
| `pesquisar.tsx` | `/pesquisar` | Campo de busca, filtros (categoria, mercado), grid/lista de resultados vazios com estado "sem resultados" |
| `produto.$id.tsx` | `/produto/$id` | Cabeçalho do produto, tabela comparativa de preços por mercado (placeholders), botão "Adicionar à lista" |
| `lista.tsx` | `/lista` | Itens da lista (vazio por padrão), resumo "Melhor mercado" (placeholder), botão limpar |
| `ofertas.tsx` | `/ofertas` | Grid de cards de oferta (placeholders), filtros por mercado |
| `entrar.tsx` | `/entrar` | Abas Login / Cadastro (form visual, sem auth real ainda) |
| `perfil.tsx` | `/perfil` | Dados do usuário (placeholder), listas salvas, preferências, sair |
| `_admin.tsx` + `_admin.index.tsx` | `/admin` | Layout admin com aviso "Área protegida — em breve"; gate visual apenas (sem auth funcional nesta etapa) |

Rota 404 já existe no `__root.tsx`.

## Navegação
- `src/components/layout/AppShell.tsx` renderizado em `__root.tsx` (envolve `<Outlet />`):
  - **Desktop (`md+`)**: `TopNav` fixo no topo com logo "Compra Certa Marília" e links: Início, Pesquisar, Lista, Ofertas, Perfil.
  - **Mobile**: `BottomNav` fixo com 5 ícones (Home, Search, ListChecks, Tag, User) usando `lucide-react` e `<Link>` do TanStack com `activeProps` para estado ativo.
  - Padding-bottom no `<main>` no mobile para não ficar atrás do bottom nav.
- Admin fica fora da navegação principal (acessível só pela URL).

## Metadados
- `__root.tsx`: atualizar title/description/og para "Compra Certa Marília — Compare preços dos supermercados de Marília".
- Cada rota: `head()` próprio com título e descrição específicos.

## Arquivos a criar/editar
Criar:
- `src/components/layout/AppShell.tsx`
- `src/components/layout/TopNav.tsx`
- `src/components/layout/BottomNav.tsx`
- `src/routes/pesquisar.tsx`
- `src/routes/produto.$id.tsx`
- `src/routes/lista.tsx`
- `src/routes/ofertas.tsx`
- `src/routes/entrar.tsx`
- `src/routes/perfil.tsx`
- `src/routes/_admin.tsx` (layout com `<Outlet/>`)
- `src/routes/_admin.index.tsx` (página `/admin`)

Editar:
- `src/routes/__root.tsx` (metadados + fonte Inter + envolver Outlet no AppShell)
- `src/routes/index.tsx` (substituir placeholder pela home real)
- `src/styles.css` (tokens de cor da marca)

## Fora do escopo desta etapa
- Autenticação real, Supabase, banco de dados.
- Coletor/robô de preços.
- Dados fictícios extensos (usar apenas placeholders mínimos para ilustrar layouts).
- PWA/manifest (pode entrar em etapa futura junto com "app instalado").

Ao final, todas as 8 páginas estarão navegáveis e o menu inferior (mobile) e superior (desktop) funcionarão em todas as rotas públicas.