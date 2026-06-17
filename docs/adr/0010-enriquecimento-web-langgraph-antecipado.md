# ADR-0010: Enriquecimento Web por Agente e Antecipação do LangGraph

**Status:** Aceito (revisado em parte por [ADR-0011](0011-registry-de-fontes-cadastravel.md) — cadastro de fonte deixou de ser deferido para `tipo='api'`; segue deferido para `csv`/`scraping`)
**Data:** 2026-06-16

## Contexto

O BTG entrega dado pobre: ISIN, classe e vencimento (ADR-0003). Falta o que descreve comercialmente o ativo — emissor real, securitizadora, lastro/devedor, rating, setor, nome longo. Esses campos não estão no XML do custodiante; estão em **fontes externas** (CVM, B3, ANBIMA, site da securitizadora, web).

Decisão de produto: o sistema deve **trabalhar para completar os dados do ativo** — um nó agêntico que pesquisa essas fontes, enriquece as características e, quando encontra um campo forte faltante, levanta candidato para o humano. Isso muda duas coisas que estavam deferidas:

1. **LangGraph** estava deferido (ADR-0002) até existir orquestração que o exigisse. O enriquecimento é multi-passo (extrair → resolver identidade → enriquecer → entregar), com nó best-effort em paralelo e ponto de HITL — é exatamente a orquestração que justifica o grafo.
2. O enriquecimento via web introduz uma **fonte não-determinística e mutável** (página muda, some, mente) no pipeline. O ADR-0007 já fixou a postura ("não-determinismo nunca toca a identidade"); este ADR aplica a mesma postura à web e define o plano de proveniência que ela exige.

Importante: isto **não** destrava a extração de texto caótico não-BTG (segue bloqueada por amostra real). Enriquecimento web opera sobre ativos **já identificados** (ISIN conhecido), logo roda sobre o dado BTG que já temos.

## Decisão

### 1. Dado web é sempre não-autoritativo

Nada vindo da web persiste como verdade do ativo sem confirmação humana. O enriquecimento alimenta **exibição** e **aid do HITL**, não o registro autoritativo. Característica enriquecida fica numa camada própria, marcada como sugerida, com sua fonte. Consequência: a internet nunca vira "fato" do sistema sozinha.

### 2. Web nunca toca a identidade; pode propor campo forte como candidato HITL

Mesma fronteira do LLM (ADR-0007). Campos **não-identidade** (rating, setor, devedor, lastro detalhado, nome longo) são enriquecidos. Quando a pesquisa encontra um **campo forte faltante** (CNPJ emissor, série/emissão, vencimento), ela **não auto-cunha nem auto-liga** — entra como **candidato na fila HITL** (`pending_resolution`), com fonte e confiança, para o humano confirmar. O IUP segue determinístico, surrogate, reproduzível do bruto imutável. A FK do Oikos nunca oscila com a internet.

### 3. Fontes híbridas: oficial primeiro, web aberta como fallback marcado

A pesquisa tenta **registros oficiais** primeiro (CVM, B3, ANBIMA, site da securitizadora) — mais confiáveis, menos ruído. Cai para **web aberta + LLM** como fallback, **marcado com confiança menor**. A confiança e a fonte viajam com cada campo enriquecido; o HITL e a futura calibração de limiares (ADR-0007) usam esse sinal.

### 4. Plano de proveniência próprio (não é a landing zone)

A landing zone (ADR-0006) guarda os **bytes do custodiante** para re-find intra-fonte. Web é **outra fonte** e exige store separado: tabela `enrichment` com `iup`, `campo`, `valor`, `fonte` (oficial|web), `fonte_url`, `query`, `confianca`, `fetched_at`, `modelo/versão`. Como web **não é reproduzível**, guarda-se o **snapshot do que foi buscado** (não só a URL) para auditoria. Versionado, igual à extração (ADR-0007).

### 5. Nó best-effort, degradação graciosa

O nó de enriquecimento roda **depois** da resolução de identidade, em paralelo à entrega, com **timeout**. Falha/timeout da web → entrega segue **sem enriquecimento**, nunca bloqueia (mesma postura da integração Oikos, ADR-0008). Enriquecimento é turbinador, nunca dependência.

### Forma alvo do grafo

```
ingest → extract (determinístico: regex/XML)
       → resolve_identity (chave forte → IUP | HITL)        [interrupt_before]
       → enrich_web (agente: oficial → web, best-effort)     [paralelo, timeout]
            ├─ característica → enrichment (não-autoritativo)
            └─ campo forte faltante → candidato HITL
       → deliver (posição + IUP + enrichment) → Oikos
```

## Implementação (primeira fatia)

Constrói o **esqueleto + a fronteira**, não os conectores reais (cada registro oficial é fatia própria, como o extrator por custodiante):

- **Grafo LangGraph** (`graph.py`) envolvendo o que já existe como nós determinísticos: `extract → resolve_identity → enrich → deliver`. Nós = funções atuais (`parser_btg`, `IupRegistry`), sem reescrever lógica.
- **Porta `EnrichmentSource`** (interface): `buscar(ativo) -> list[EnrichmentResult]`. Conector oficial (CVM/B3) e web aberta implementam a porta depois; o teste usa uma **fonte fake**.
- **Tabela `enrichment`** (não-autoritativa, nunca escreve em `iup_registry`).
- **Roteamento da fronteira provado por teste:** característica → grava `enrichment`; campo forte faltante → candidato em `pending_resolution`; erro/timeout da fonte → entrega sem enriquecimento (best-effort).

## Consequências

**Positivo:** destrava valor sobre o dado BTG pobre que já existe, sem esperar amostra não-BTG; LangGraph entra com uso real (não infra ociosa — respeita ADR-0002); a postura do ADR-0007 cobre a web sem exceção nova; identidade segue determinística e auditável; enriquecimento degrada gracioso.

**Negativo:** novo plano de proveniência (tabela `enrichment` + snapshot) a manter; integração por fonte oficial é trabalho incremental (cada registro é um conector); web aberta exige cuidado anti-alucinação (confiança + snapshot obrigatórios); LangGraph entra mais cedo no stack.

**Supera:** a linha "LangGraph — Deferido" do ADR-0002 (agora **Adotado**, antecipado por esta fatia). Mantém deferidos: `langchain_ollama` para texto caótico não-BTG, DuckDB/Polars, Faiss/Chroma.

**Fora de escopo (deferido):** os conectores concretos de cada registro oficial (entram por fonte, como o extrator por custodiante); limiares de confiança para promover característica enriquecida (bloqueados por dado rotulado, ADR-0007).

> **Revisão (2026-06-17 — ADR-0011):** o **cadastro** de fonte deixou de exigir código/env para `tipo='api'`: o operador cadastra pela UI (`/sources`) e a fonte liga viva no grafo (`HttpEnrichmentSource` por linha, contrato via `field_map`). O que **continua deferido** é a *execução* de `csv`/`scraping` (bloqueada por amostra) e os conectores que exigem parse próprio (como o `CvmCriSource`, que segue em código por causa do download/cache do zip). A fronteira não-autoritativa (§1/§2) vale igual para fonte cadastrada.
