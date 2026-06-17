# ADR-0011: Registry de Fontes de Enriquecimento Cadastrável

**Status:** Aceito
**Data:** 2026-06-17

## Contexto

O ADR-0010 fixou o enriquecimento (fonte = de onde o AssetBridge puxa características de ativo já identificado: emissor, securitizadora, lastro, rating, indexador) e modelou a fonte como porta `EnrichmentSource` no código. O **cadastro dinâmico** de fontes ficou deferido: cada fonte nova exigia código (`HttpEnrichmentSource`/`CvmCriSource`) e wiring por env (`ASSETBRIDGE_CVM_CRI_CACHE_DIR`). Consequências operacionais:

1. O operador **não enxergava** quais fontes existiam nem se estavam ligadas.
2. Ligar uma fonte-api nova (B3, ANBIMA, securitizadora) exigia mexer em env/código e redeploy — o operador de backoffice (ADR-0009) não conseguia fazer sozinho.

Decisão de produto: expor o cadastro de fontes como **registry** consumível pela UI do backoffice, sem reabrir a extração de texto caótico (segue bloqueada por amostra) nem dar à web/scraping execução autônoma (ADR-0010 §1/§4 valem).

## Decisão

### 1. Tabela `source_config` + endpoints CRUD

Postgres (system of record, ADR-0001) ganha `source_config`: `nome` (único), `tipo` (`api`|`csv`|`scraping`), `base_url`, `path`, `param` (default `isin`), `field_map` (JSONB — contrato da fonte plugado por config, não código), `confianca`, `enabled`, `created_at`. Endpoints: `GET /sources`, `POST /sources` (201), `PATCH /sources/{id}` (liga/desliga), `DELETE /sources/{id}` (204). Nome duplicado → 409; tipo inválido → 422.

### 2. Só `tipo='api'` liga vivo; `csv`/`scraping` ficam catalogados com execução deferida

Coerente com ADR-0010 (deferido por amostra). Uma linha `enabled` de `tipo='api'` com `base_url` vira um `HttpEnrichmentSource` em runtime (`build_db_sources`). `csv`/`scraping` são **cadastráveis e visíveis** (campo `vivo=false` no GET) mas **não executam** — não há regra de parse/scrape sem amostra real, e dar execução autônoma à web aberta violaria a postura do ADR-0010. Quando houver amostra, a execução desses tipos entra por fatia, sem mudar o contrato de cadastro.

### 3. Composição por `ChainEnrichmentSource`, lida por request

`hitl.get_graph` compõe a fonte estática gated por env (CVM CRI, ADR-0010) **+** as fontes-api do registry (`build_db_sources(session)`), encadeadas num `ChainEnrichmentSource` best-effort: cada fonte é tentada com try/except, uma que cai não derruba as outras (turbinador nunca bloqueia a entrega — ADR-0008/0010). Como o registry é lido **por request**, ligar/desligar/cadastrar uma fonte-api reflete sem restart (o env CVM segue cacheado em `_enrichment_source`).

### 4. Fonte cadastrada continua não-autoritativa

Toda a fronteira do ADR-0010 vale igual: característica → `enrichment`; campo forte sugerido → candidato `pending_resolution`, nunca auto-cunha. O registry só muda **de onde** vêm as sugestões, nunca **o que elas podem fazer** à identidade.

## Consequências

- O operador do backoffice (ADR-0009) cadastra/liga/desliga fonte-api pela UI (`/fontes`) sem env/código/redeploy.
- `GET /sources` dá visibilidade do catálogo (vivo/deferido/desligado).
- ADR-0010 revisado: "cadastro dinâmico de fontes deferido" deixa de valer **para `tipo='api'`**; segue deferido para `csv`/`scraping` (execução, não cadastro).
- Não muda a autoridade do IUP nem a fronteira de identidade. Não destrava texto caótico não-BTG.

## Alternativas consideradas

- **Seguir só com env/código (status quo):** rejeitado — operador não-técnico não liga fonte; sem visibilidade.
- **Executor dinâmico de scraping no DB agora:** rejeitado — sem amostra real é chute (ADR-0010), e execução autônoma de web aberta fere a postura não-autoritativa. Catalogar sem executar é o meio-termo honesto.
