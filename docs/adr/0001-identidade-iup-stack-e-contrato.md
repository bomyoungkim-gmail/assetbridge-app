# ADR-0001: Modelo de Identidade (IUP), Stack e Contrato de Integração

**Status:** Aceito
**Data:** 2026-06-14

## Contexto

A especificação original (`engine-normalizacao-portabilidade.md`) descrevia um MVP local com SQLite, geração de uma chave sintética SHA-256 sobre todos os metadados extraídos (inclusive os incertos), matching por série temporal de caixa (DTW + Faiss) e extração via regex/`if` hardcoded por classe.

Ao definir o produto, três premissas mudaram:

1. O AssetBridge é a **autoridade única do IUP** que alimenta o Oikos — é um system of record, com ingestão assíncrona concorrente de muitas carteiras.
2. Não há garantia de que os campos fortes (CNPJ emissor, vencimento, série) venham do custodiante; e o input ainda **não tem amostras reais** disponíveis.
3. A extração de texto caótico e variado de múltiplos custodiantes não escala com regex/listas hardcoded.

## Decisão

### Identidade em duas camadas

- A **chave sintética provisória** (hash dos metadados extraídos) é apenas um balde de primeira passada; pode ser instável/duplicada. **Não é exposta** a consumidores.
- O **IUP** é a identidade canônica, atribuída após **resolução**: match contra o registro → existente; chave incompleta/ambígua → **HITL**; senão cunha novo.
- Duplicatas são consolidadas ao longo do tempo via **alias table** (`provisório → IUP`), com **merge reversível, logado e nunca silencioso**. Consumidores (Oikos) sempre referenciam o IUP canônico. No merge de dois IUPs já cunhados, **sobrevive o mais antigo por default, com override humano**; o perdedor vira alias permanente → vencedor.
- O **IUP canônico é um surrogate opaco e imutável**; a string semântica (`IUP-CRI-CNPJ-SERIE-VENC`) é um **rótulo derivado, só de exibição**, recalculável e mutável. Correção via HITL atualiza o rótulo, nunca a identidade — protege as FKs dos consumidores.

### Extração híbrida (Camada 1)

Regex/parse determinístico para campos fortes (CNPJ, datas, taxa); LLM local (Ollama) estruturado em Pydantic para campos fuzzy (classe, emissor, série, subordinação). Emissor por tabela de lookup. LLM só propõe; campos fortes e o humano mandam.

### Camada 2 reduzida no MVP

Apenas coerência de PU entre snapshots do mesmo IUP. DTW, regressão e busca vetorial (Faiss/Chroma) **deferidos** até existir série temporal real e um problema de falso-positivo comprovado.

### Stack de armazenamento

**Postgres** para o registro autoritativo de IUP + aliases + auditoria. **DuckDB/Polars** para processamento em memória. **LangGraph SqliteSaver** para checkpoints no MVP. Isso **contraria** a regra "sem Postgres" da spec original, justificado pelo papel de system of record.

### Contrato com o Oikos

**REST API versionada, sem banco compartilhado.** `POST /resolve-iup` (Oikos → AssetBridge) e entrega de posições+IUP (AssetBridge → Oikos via endpoint de ingestão).

Payload **híbrido** (campos fortes opcionais + `raw_description` opcional) com **extração condicional**. Resposta **híbrida sync/pending**: match exato → IUP síncrono; ambíguo → `pending` + `thread_id` (poll/webhook + backfill). Trade-off aceito: duas formas de resposta e fast-path fora do grão do grafo, em troca de latência baixa no caso determinístico comum. O fast-path síncrono **não** pode bloquear esperando HITL — ambiguidade sempre vira `pending`.

## Consequências

**Positivo:** IUP estável apesar de extração não-determinística (a identidade vive no registro, não no hash); duplicatas tratáveis sem corromper referências; extração resiliente a layouts novos; system of record durável e concorrente; produtos desacoplados.

**Negativo:** mais infra que a spec previa (Postgres + Ollama, não só SQLite local); custo/latência do LLM local; necessidade de processo de merge e de UI/fluxo de HITL; contrato REST a versionar e manter.

**Bloqueio conhecido:** sem amostras reais de custodiantes não-BTG, os regex e prompts de Camada 1 não podem ser finalizados — calibrar somente com amostra.
