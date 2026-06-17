# ADR-0009: Frontend — Backoffice HITL Próprio em Next.js (Monorepo)

**Status:** Aceito
**Data:** 2026-06-15

## Contexto

O CONTEXT.md já decidiu que o HITL é **API-first** (`GET /pending`, `POST /pending/{id}/decision`, e — fatia futura — `POST /merge`, `POST /merge/{id}/revert`) e que uma **"UI própria fina"** consome esses endpoints "logo depois", **nunca pendurada no frontend do Oikos** (mataria o standalone). O que ficou em aberto (item "Fase de UI"): **qual tecnologia, qual estrutura de repositório e quem opera**.

A spec original (`engine-normalizacao-portabilidade.md`) é backend puro — não menciona frontend. Mas dois pontos exigem um humano interagindo com o sistema: ativos pausados via `interrupt_before` aguardando decisão, e o de-para manual com histórico/reversão.

A questão de fundo é de **governança**, não de UI: o AssetBridge é a **autoridade única do IUP** (CONTEXT.md). Delegar a decisão de ambiguidade via REST a um consumidor externo inverteria o controle — o caller viraria árbitro do IUP e o audit trail se fragmentaria fora do system of record. Logo a decisão HITL precisa morar **dentro** do AssetBridge, operada por gente do AssetBridge.

## Decisão

### 1. O AssetBridge tem frontend próprio — backoffice HITL soberano

A decisão de ambiguidade (cunho/merge de IUP) é exercida por **operador interno do AssetBridge**, nunca pelo consumidor (Oikos) nem pelo custodiante. Consequência direta: o AssetBridge **expõe seu próprio backoffice**, não delega a UI a terceiros. Isso preserva a soberania do IUP e mantém o audit trail no system of record (Postgres, CONTEXT.md).

### 2. Dois canais para o mesmo contrato — CLI e Web UI

Os operadores são **mistos** (devs/analistas técnicos + analistas de backoffice financeiro). Cada perfil escolhe seu canal:

- **CLI/API direta** — para o operador técnico (curl/httpie sobre os mesmos endpoints).
- **Web UI** — para o analista financeiro, sem terminal.

Ambos consomem **o mesmo contrato HTTP** (`hitl.router`). A UI não tem lógica de identidade própria — é cliente fino. Nenhuma regra de cunho/merge migra para o frontend.

### 3. Tecnologia: React / Next.js (App Router, TypeScript)

A Web UI é **Next.js** com App Router e TypeScript. Separação limpa frontend/backend, ecossistema maduro, escala melhor que um painel server-side se a UI crescer. Idioma **PT-BR** (alinhado ao ADR-0009 do Oikos).

### 4. Estrutura: monorepo — `frontend/` dentro do `assetbridge-app`

O frontend vive em `frontend/` no mesmo repositório do backend Python. Coexistência: `pyproject.toml` na raiz (backend), `frontend/package.json` (Node). O `docker-compose.yml` orquestra ambos quando o serviço `api` existir. Um só repo, uma só história de versão para a decisão de produto.

### 5. Escopo de telas do MVP (derivado do grill)

| Tela | Backend hoje | Status |
|---|---|---|
| **Fila HITL** — pendências abertas | `GET /pending` | ✅ Entregue |
| **Resolver ativo** — confirmar/cunhar IUP | `POST /pending/{id}/decision` | ✅ Entregue |
| **Acervo** — imports/posições/IUPs injetados | `GET /assets`,`/positions`,`/imports` | ✅ Entregue (2026-06-17) |
| **Upload de import** — enviar XML BTG | `POST /ingest` | ✅ Entregue (2026-06-17) |
| **Fontes** — registry de enriquecimento (ADR-0011) | `GET/POST/PATCH/DELETE /sources` | ✅ Entregue (2026-06-17) |
| **Detalhe do ativo** — bruto + metadados extraídos | parcial (`payload` em `/pending`) | Bloqueado por dado rico (série temporal/IUP candidato não expostos) |
| **Histórico de de-para** — log auditável + reversão | `/merge`, `/merge/revert` | Bloqueado — merge/alias é fatia futura (CONTEXT.md) |
| **Dashboard** — volume, taxa de ambiguidade, threads pausadas | nenhum endpoint | Bloqueado por endpoint de métricas |

O scaffold do MVP entregou **Fila + Resolver**; **Acervo** (browse read-only), **Upload de import** (`POST /ingest`, client component dentro do Acervo) e **Fontes** (registry CRUD, ADR-0011) entraram em 2026-06-17 lastreados por endpoints reais. As telas Detalhe/Histórico/Dashboard entram quando o backend expuser o dado, e **não** são simuladas como se prontas.

## Consequências

**Positivo:**
- Soberania do IUP preservada — decisão e audit trail dentro do AssetBridge.
- Standalone intacto — UI própria, nunca acoplada ao Oikos.
- Cliente fino — nenhuma regra de identidade vaza para o frontend; CLI e Web compartilham contrato.
- Monorepo mantém a decisão de produto numa só história de versão.

**Negativo:**
- Dois ecossistemas (Python + Node) no mesmo repo — CI/build precisa lidar com ambos.
- Telas Detalhe/Histórico/Dashboard ficam como stub até o backend expor o dado — risco de UI parecer "mais pronta" do que o backend sustenta (mitigado: stubs marcados explicitamente).
- A premissa da spec ("rodar local leve") ganha um processo Node além do Python.

## Relacionados

- **CONTEXT.md** — HITL API-first, UI própria fina, soberania do IUP, item aberto "Fase de UI" (resolvido aqui).
- **ADR-0007** — postura agêntica; o humano (via este backoffice) é o gate de identidade sob ambiguidade.
- **ADR-0008** — integração Oikos direção B; `pending` como resposta legítima que esta UI resolve.
- **ADR-0009 (Oikos)** — convenção PT-BR, espelhada aqui.
