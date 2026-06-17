# AssetBridge — Frontend (Backoffice HITL)

Backoffice próprio do AssetBridge para resolução humana de ambiguidade de IUP.
Decisão e racional: **ADR-0009** (`docs/adr/0009-frontend-backoffice-hitl-proprio-nextjs.md`).

Cliente **fino**: nenhuma regra de identidade vive aqui. A UI consome o contrato
HITL do backend (`hitl.router`). O AssetBridge é a autoridade única do IUP — a
decisão de cunho mora no backend, não no frontend.

## Stack

Next.js (App Router) · React · TypeScript. Idioma PT-BR (ADR-0009 do Oikos).

## Rodar (Docker — recomendado)

Tudo em container, junto com a API e o Postgres (ver `docker-compose.yml` na raiz):

```bash
docker compose up -d api frontend
# Web UI:  http://localhost:3001
# API:     http://localhost:8001  (docs em /docs)
```

Portas no host são **3001/8001** porque **3000/8000 são do stack Oikos vizinho**.
Dentro da rede do compose a API segue em `http://api:8000`.

**Hot reload:** `WATCHPACK_POLLING=true` no serviço — inotify não propaga em bind
mount no Windows, então o watch é por polling. Sem isso, edições não recompilam.

## Rodar (host, sem Docker)

```bash
cd frontend
cp ../.env.example .env.local   # template único na raiz; Next usa só as vars do frontend
npm install
npm run dev                  # http://localhost:3000
```

## Testes

```bash
docker compose run --rm frontend-test   # next build + vitest
```

## Telas

| Rota | Tela | Backend | Status |
|---|---|---|---|
| `/hitl` | Fila HITL + Resolver | `GET /pending`, `POST /pending/{id}/decision` | Funcional |
| `/` | Painel (métricas) | — | Stub — sem endpoint de métricas ainda |

Histórico de de-para (merge/revert) e Detalhe rico do ativo entram quando o
backend expuser `/merge`, `/merge/{id}/revert` e payload de série temporal /
IUP candidato (fatia futura — ver CONTEXT.md "Fase de UI").
