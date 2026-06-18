# ADR-0014: Design System do Backoffice — Tokens, Shell &amp; Acessibilidade

**Status:** Aceito
**Data:** 2026-06-18

## Contexto

O [ADR-0009](0009-frontend-backoffice-hitl-proprio-nextjs.md) decidiu **tecnologia, estrutura e governança** do backoffice (Next.js, monorepo, cliente fino, soberania do IUP), mas deixou a **camada visual** propositalmente mínima: o `globals.css` do scaffold tem ~60 linhas (topbar flat, tabela crua, `.stub`), inputs empilhados com `<br>` no Resolver, sem estados de foco, sem tema escuro, sem badges de status. Era o suficiente para provar o contrato (Fila/Resolver/Acervo/Fontes lastreados por endpoints reais) — não para uso diário por analista de backoffice.

Faltava decidir a **linguagem visual e os mínimos de acessibilidade** do produto. A questão não é estética por estética: o operador HITL passa o dia nessa UI confirmando campos fortes e cunhando IUP — densidade de informação, foco visível, leitura de números e estados de pendência (dentro/fora do SLA) são **ferramenta de trabalho**, não enfeite.

A referência adotada foram as **Web Interface Guidelines** (foco visível obrigatório, `:focus-visible`, `aria-*`, `tabular-nums`, empty states, `prefers-reduced-motion`, `prefers-color-scheme`, `inputmode`/`autocomplete`, semântica antes de ARIA).

## Decisão

### 1. Design tokens via CSS custom properties — sem framework de CSS

A paleta, o espaçamento, o raio e a tipografia vivem como **CSS variables** em `:root` no `globals.css`. **Não** entra Tailwind nem CSS-in-JS: o backoffice é pequeno, o scaffold já é CSS puro, e tokens em variáveis dão tema claro/escuro de graça sem build extra nem dependência nova. Manter o stack Node enxuto (ADR-0009 já cita o custo de dois ecossistemas).

### 2. Tema claro/escuro automático

`color-scheme: light dark` no `:root` + bloco `@media (prefers-color-scheme: dark)` que sobrescreve os tokens. `<meta name="theme-color">` por esquema. Sem toggle manual no MVP (segue o SO) — toggle persistido fica deferido até alguém pedir.

### 3. Shell com navegação lateral + skip link

Layout em **sidebar fixa** (`Painel · Fila HITL · Acervo · Fontes`) + topbar com busca, no lugar da topbar horizontal. O item ativo marca `aria-current="page"` via um client component fino (`nav.tsx`, usa `usePathname`) — guideline de navegação. **Skip link** ("Pular para o conteúdo") como primeiro elemento focável.

### 4. Mínimos de acessibilidade são contrato, não opcional

Todo componente novo respeita: foco visível (`:focus-visible` ring, nunca `outline:none` solto), `<label>`/`aria-label` em todo controle, `<button>` para ação e `<Link>` para navegação, `aria-live="polite"` em status assíncrono, `tabular-nums` em coluna numérica, `…` real (não `...`), `&nbsp;` em unidades (`10&nbsp;MB`, `48&nbsp;h`), `inputmode`/`autocomplete`/`spellcheck=false` em ISIN/CNPJ, empty states explícitos, `prefers-reduced-motion` honrado.

### 5. Vocabulário visual de estado (badges)

Estados do domínio ganham **badge** com cor semântica e rótulo textual (nunca só cor): `ok` (chave forte / fonte viva), `warn` (ambíguo / deferido / SLA estourando), `danger` (acima do SLA), `muted` (neutro/landing zone). Cor é reforço, o texto é a fonte de verdade (daltonismo).

### 6. Honestidade do stub preservada (não regride o ADR-0009 §5)

O restyle é **puramente visual**. As telas marcadas como stub no ADR-0009 §5 (Painel/Dashboard, Detalhe rico, Histórico de de-para) **continuam stub** — o Painel ganha card mais bonito mas **não** fabrica métricas que o backend não expõe. Nenhuma regra de identidade migra para o front; o cliente segue fino.

## Consequências

**Positivo:**
- UI utilizável por analista no dia a dia (densidade, foco, leitura de números, estados de SLA).
- Tema escuro sem custo de dependência; tokens centralizam a paleta (troca num lugar só).
- Acessibilidade vira baseline herdado pelo `globals.css`, não retrabalho por tela.
- Zero dependência nova — `package.json` intacto.

**Negativo:**
- CSS puro escala pior que utilitários se a UI crescer muito (aceitável no tamanho atual; revisitar se virar app grande).
- Sidebar fixa exige tratamento responsivo (colapsa em < 760px).
- Mais um client component (`nav.tsx`) só para `aria-current` — custo pequeno, ganho de a11y.

**Não revoga:** ADR-0009 (tecnologia/estrutura/governança/honestidade do stub) nem a fronteira de cliente fino — só preenche a camada visual que o ADR-0009 deixou mínima.

## Relacionados

- **ADR-0009** — backoffice próprio Next.js; este ADR concretiza a camada visual deixada mínima lá; §5 (honestidade do stub) preservado.
- **ADR-0011** — registry de fontes; a tela Fontes adota os badges de estado (viva/deferida/desligada).
- **CONTEXT.md** — "Fase de UI": telas reais entregues; este ADR cobre o design system aplicado sobre elas.
- **Web Interface Guidelines** (vercel-labs) — fonte dos mínimos de acessibilidade adotados.
