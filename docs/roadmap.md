# Roadmap de Implementação — AssetBridge

Ordem por **dependência + risco**: fundação/correção primeiro, features depois, bloqueado por último.

**Contexto para qualquer chat de execução:** ler [CONTEXT.md](../CONTEXT.md) (arquitetura-alvo + "Estado da implementação") e o ADR citado em cada item. Código atual em `src/assetbridge/` (`identity.py`, `registry.py`, `db.py`, `parser_btg.py`, `api.py`). MVP é BTG-only, identidade, TDD contra Postgres real em Docker (`docker compose run --rm test`).

Tags: **[ready]** decidido e codável · **[blk:sample]** precisa amostra real de custodiante · **[blk:consumer]** precisa 1º caller real · **[blk:oikos]** conjunto com o Oikos.

Princípios transversais (não violar): sem dado derivado denormalizado em muitas linhas (rótulo, IUP); nenhuma decisão por omissão (drop silencioso proibido); campo estruturado/forte manda, texto livre é fallback.

---

## Fase 1 — Fundações de schema (destrava o resto) [ready]

1. **Adotar Alembic.** [DEFERIDO — greenfield] Hoje schema via `create_all` (`db.py`), sem dado real e DB de teste efêmero. A migração de PK (nº2) foi feita por **drop+recreate do volume** (`docker compose down -v`), inofensivo sem dado. **Gatilho confirmado:** `create_all` **não faz `ALTER`** — no 1º deploy com dado real, Alembic vira obrigatório (qualquer mudança de schema seria destrutiva). Adotar então, consistente com ADR-0002.
2. **Migração de PK — ADR-0004.** [FEITO] Surrogate `id` PK; `chave_sintetica` nullable + **unique parcial** `WHERE NOT NULL` (`uq_iup_registry_chave_sintetica`); `iup` único; `created_at`. Lookup em `registry.resolve` passou a query por coluna (não `session.get` por PK). Ref: `db.py`, `registry.py`.
3. **Landing zone — ADR-0006.** [FEITO] Tabela `landing_zone` (file-hash unique, custodiante, raw, created_at) + `landing.store_raw` idempotente por hash. Âncora sub-arquivo `(extractor_version, source_locator)` fica para a fatia de extrator (ADR-0006). Ref: `landing.py`, `db.py`. **Falta wiring** no `/ingest` (item 5).
4. **`pending_resolution` — Q1.** [FEITO] Tabela (chave_provisoria indexed, payload JSONB, motivo, status default `pending`, created_at), store separado que **nunca guarda IUP**. `registry.resolve` enfileira na pendência (dedup por chave provisória, idempotente). Lastreia `GET /pending` (endpoint = item 8). `thread_id` entra depois como coluna (Fase 4). Ref: `db.py`, `registry.py`.

## Fase 2 — Correção de identidade & roteamento (depende F1)

5. **Roteamento em três vias — ADR-0005** [FEITO]. `parse_carteira`→`ParseResult(instrumentos, excluidos)`; gate estrutural `_is_instrumento` (não em `Desc` nem em chave forte); ISIN-sem-Desc não some mais. `/ingest` guarda raw na landing zone + roteia forte→`resolve` / fraco→`pending` (via registry) / não-instrumento→`excluded_log`. Bug de perda silenciosa fechado. Ref: `parser_btg.py`, `db.py` (`ExcludedRecord`), `api.py`.
6. **Classe por código CVM, não `split()[0]` — ADR-0005** [FEITO — calibrado em amostra]. `cvm.classificar` mapeia `FinInstrmAttrbts/ClssfctnTp/AltrnClssfctn/Id`: 196→RF privada (CRI/CDB/LF refinado por Desc), 193→PUBLICO, 197→FUNDO, 37→LISTADO; sem CVM→fallback Desc. Parser extrai código CVM + CNPJ de `OthrId` (Cd=CNPJ). Validado: 4058 instrumentos, classificação correta. Ref: `cvm.py`, `parser_btg.py`, `docs/btg-formato-real.md`.
7. **Rótulo não-persistido — Q3** [FEITO]. Coluna `rotulo_semantico` removida; recalculado on read em `registry.resolve` (sempre do `ativo` em mãos); degrada para ISIN+classe+venc quando faltam CNPJ/série (`_rotulo_isin`). Ref: `identity.py`, `registry.py`.
8. **Endpoints HITL** [PARCIAL]. [FEITO] `GET /pending` (fila aberta), `POST /pending/{id}/decision` (cunha via `registry.cunhar_hitl` — surrogate `chave=NULL` sem chave forte, ADR-0004; pegajosa via tabela `hitl_decision`; 404 se pendência inexiste). Ref: `hitl.py`, `registry.py`, `db.py`. [PENDENTE / blk:sample] `POST /merge` + revert — **depende da alias table (item 18)**, não meio-construído.

## Fase 3 — Posição & caixa (escopo: fontes que o AssetBridge ingere; depende landing zone)

9. **Modelo interno de posição — Q2/Q6** [PARCIAL / reescopo]. [FEITO] Tabela `positions` + serviço `upsert_posicoes` delete+replace por `(carteira, custodiante, asof)`. **Reescopo (decisão):** AB é **isolado**; BTG positions são ingeridas por **outros (Oikos, direção b)** → AB só `/resolve-iup`. Direção (a) do AB = **modo standalone diagnóstico** (parseia, resolve, mostra/exporta na tela — `/ingest` devolve `resumo`), **não entrega a ninguém**. Paths reais p/ qty/PU em `docs/btg-formato-real.md` (`AggtBal/Qty/Qty/Qty/Unit`, `PricDtls/Val/Amt`) — extração de posição completa só se/quando AB ingerir direto e precisar exibir valores. Ref: `parser_btg.py`, `positions.py`, `api.py`.
10. **Cash pass-through — Q7** [ready]. Normaliza estrutura (`entry_type/amount/balance/asof/account`); **sem coluna IUP nas linhas** (IUP single-sourced em `instrument.iup` do Oikos, alcançado por recon); delete+replace por dia (extrato diário completo). AssetBridge não interpreta caixa.
11. **Reimport do AssetBridge — Q9** [ready]. Reimporta a própria projeção a partir da landing zone. Gatilho: HITL `log_excluded→instrumento` re-roteia + marca re-entrega. Não cascateia automático ao Oikos (ver nº14).

## Fase 4 — Runtime agêntico & contrato (maior)

12. **LangGraph — ADR-0002 (gatilho).** `thread_id`, checkpoints (`SqliteSaver` no MVP), `interrupt_before` antes de gravar IUP. `thread_id` vira coluna de `pending_resolution`. Resposta híbrida sync/pending no `resolve-iup`. Postura agêntica: ADR-0007.
13. **Versionamento de extração — ADR-0007.** Modelo + versão por campo; reprocesso em massa de itens auto-resolvidos; itens confirmados por humano são pegajosos.
14. **Contrato de entrega AB→Oikos** [blk:consumer]. Push/pull + **sinal de versão/staleness** por `(carteira, asof)`; gatilho de re-reconciliação no Oikos. Sem ele, Oikos opera projeção stale sem saber (decisão silenciosa — proibida).
15. **Auth service-to-service** [blk:oikos] + versionamento REST (`/v1` vs header) + política de retry no fluxo (b).

## Fase 5 — Bloqueado por dado real (não começar antes da amostra)

16. **Camada 1 não-BTG** [blk:sample]. Regex/prompts por custodiante, `detect_source`, `is_instrument` config, LLM local (Ollama `qwen3:8b` por enquanto; alvo `qwen3:14b`), tabela CVM→classe. **Próximo passo concreto quando chegar a 1ª amostra.**
17. **Limiares de confiança / zona cinzenta (0.75–0.90)** [blk:sample]. Calibrar com o rotulado que o HITL conservador gera.
18. **Alias/merge (portabilidade)** [blk:sample]. Tabela de alias, merge reversível com log, sobrevivência "mais antigo vence + override humano". Precisa do 2º custodiante. Ref: ADR-0001/0004.
19. **Camada 2 cheia** [blk:sample]. DTW/regressão/Faiss; precisa série temporal de PU acumulada + falso-positivo comprovado.
20. **Harness 300 carteiras concorrentes.** Artefato de carga; quando o pipeline assíncrono (F4) existir.

---

## Caminho crítico

`1 → 2 → {3,4} → 5` destrava quase tudo e fecha o bug de perda de dado.

**Sugestão de 1º PR:** nº **1+2+7** juntos (uma migração só: surrogate PK + drop rótulo + `chave_sintetica` nullable). Em seguida nº **3+4** (landing zone + pending), depois nº **5** (roteamento).

## Índice de ADRs

- **0001** — Identidade (IUP), stack, contrato
- **0002** — Stack incremental por fatia
- **0003** — ISIN como chave forte quando presente
- **0004** — PK surrogate, `chave_sintetica` nullable + unique parcial
- **0005** — Ingestão sem drop silencioso, roteamento em três vias
- **0006** — Âncora de conteúdo intra-fonte; portabilidade por alias/merge
- **0007** — Postura agêntica: LLM proposer sob gate determinístico/HITL
