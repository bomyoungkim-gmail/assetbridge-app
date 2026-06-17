# ADR-0012: Adoção Antecipada do Stack Completo (Supera ADR-0002)

**Status:** Aceito
**Data:** 2026-06-17

## Contexto

O [ADR-0002](0002-stack-incremental-por-fatia.md) fixou adoção incremental: cada dependência da spec só entraria na fatia que a exigisse, justificada por teste/uso real (YAGNI). Sob essa regra, o stack já tinha antecipado **LangGraph** (ADR-0010) e o **frontend backoffice** (ADR-0009); seguiam deferidos `langchain_ollama`/LLM, DuckDB/Polars, Faiss/ChromaDB e o harness de carga.

Três fatos mudaram a base da decisão de 0002:

1. **Amostras e dados reais chegaram.** A extração de texto caótico não-BTG estava bloqueada por amostra (ADR-0002/0007); a amostra existe. Some-se volume de dados que justifica analytics colunar (DuckDB/Polars) e série/vetorial para matching (Faiss/Chroma). Os gatilhos que 0002 exigia agora existem.
2. **Decisão de derisk: construir o pipeline ponta-a-ponta agora.** Em vez de descobrir a integração das peças tarde, materializa-se o pipeline assíncrono completo + teste de carga já, expondo acoplamentos cedo.
3. **Necessidade de demo/stakeholder.** O stack completo (incluindo frontend já adotado) precisa rodar end-to-end para demonstração.

Com amostra real + decisão de derisk + demo, manter as peças deferidas deixou de respeitar YAGNI e passou a ser atraso artificial.

## Decisão

**Adotar agora todos os componentes que o ADR-0002 mantinha deferidos.** A spec deixa de ser visão-alvo incremental e passa a alvo de implementação corrente. A fronteira de não-determinismo dos ADR-0007/0010 (LLM e web nunca tocam identidade) **continua valendo sem exceção** — antecipar o stack não relaxa nenhuma garantia de identidade.

Mapa atualizado:

| Componente da spec | Status anterior (0002) | Status agora | Gatilho |
| --- | --- | --- | --- |
| **langchain_ollama / LLM** | Deferido | **Adotado** | Amostra real de texto caótico não-BTG existe; extração sob gate determinístico (ADR-0007). |
| **DuckDB / Polars** | Deferido | **Adotado** | Volume de dados justifica parsing/analytics colunar; substitui `xml.etree` na fatia de volume. |
| **Faiss / ChromaDB** | Deferido | **Adotado** | Matching por série/vetorial (Camada 2) — derisk do pipeline completo. |
| **Harness de carteiras BTG** | Deferido (300 genérico) | **Adotado, escopo BTG** | Teste de carga do pipeline assíncrono sobre **carteiras BTG reais** (não 300 sintéticas). |
| **LangGraph** | Adotado (ADR-0010) | Adotado | — |
| **Frontend** | Deferido | Adotado (ADR-0009) | — |

**Mudança ao harness:** o simulador de 300 carteiras da spec era artefato sintético. Substituído por **harness sobre carteiras BTG reais** — mede o pipeline contra o dado que o sistema realmente processa, não carga fictícia.

## Consequências

**Positivo:** pipeline ponta-a-ponta materializado; acoplamentos entre peças expostos cedo (derisk); demo roda o stack completo; harness mede carga real (BTG), não sintética; garantias de identidade dos ADR-0007/0010 intactas.

**Negativo:** reverte o princípio YAGNI de 0002 — risco de infra adotada antes de cada uso estar 100% provado por teste (ex: Faiss antes de série temporal madura). Mitigação: cada peça antecipada ainda entra **com teste** (regra de TDD do projeto vale igual); o que muda é o gatilho (decisão de derisk/demo + amostra), não a disciplina de teste. Mais superfície a manter de imediato.

**Supera:** o [ADR-0002](0002-stack-incremental-por-fatia.md) por inteiro — a regra "cada peça só na fatia que a exige" deixa de valer; o stack-alvo é adotado agora. Não revoga as fronteiras de não-determinismo (ADR-0007/0010) nem as decisões de identidade (ADR-0001/0003/0004).

**Regra prática nova:** o stack-alvo da spec está adotado; novas peças fora da spec ainda passam por ADR. Cada componente antecipado precisa de teste antes de ser declarado pronto (TDD).

## Estado da implementação (entregue por TDD, fatia a fatia)

| Fatia | Módulo | O que entrou | Fronteira preservada |
| --- | --- | --- | --- |
| 1. LLM/Ollama — extração versionada | `extraction.py` (`registrar_extracao`), `db.ExtractionRecord`, ligado no `deliver` do `graph.py` | **Upsert** de proveniência fuzzy por `(raw_hash, campo, modelo)`: mesmo modelo sobrescreve (mais recente vence; backfilla `iup` pós-HITL), modelo novo versiona. Adapter `OllamaProposer`/`build_ollama_proposer` (lazy) já existia. | LLM nunca toca campo forte (regex manda); sem duplicatas mas mantém histórico por modelo. |
| 2. DuckDB/Polars — analytics colunar | `analytics.py` (`posicoes_frame`, `resumo_por_carteira`) | Projeção `positions` (Postgres) → DataFrame Polars; DuckDB roda o SQL agregado (replacement scan). | Postgres segue autoritativo; camada derivada read-only; `pu` nulo conta 0 mas a posição é contada (nada some, ADR-0005). |
| 3. Harness de carteiras BTG | `harness.py` (`gerar_carteiras_btg`, `rodar_carga`, `LoadReport`) | Replica um template BTG real em N carteiras distintas (CNPJ de fundo variado) e roda o pipeline medindo throughput + invariantes. | Carteiras BTG reais (não 300 sintéticas); idempotência sob carga provada (reingestão = no-op). |
| 4. Faiss — matching Camada 2 | `matching.py` (`VectorMatcher`, porta `Embedder`, `MatchCandidate`) | Índice `IndexFlatIP` sobre vetores normalizados (cosseno); para ativo sem chave forte sugere IUPs parecidos como AID do HITL. | Propõe candidato, **nunca auto-liga identidade** (ADR-0007/0010); pura, não escreve no `iup_registry`. |

**Deps adicionadas:** `polars`, `duckdb`, `pyarrow`, `faiss-cpu`, `numpy`.

**LLM real LIGADO em 2026-06-17 (modelo via env — ADR-0013):** o serviço `ollama` está no compose sob `profiles: ["llm"]` (não sobe em teste/`up` normal); `hitl._field_proposer` liga o `OllamaProposer` no nó `extract` quando `ASSETBRIDGE_OLLAMA_MODEL` está setado, senão `None` → passthrough (default seguro, sem rede). Ativado: `ASSETBRIDGE_OLLAMA_MODEL=qwen3:8b` no `.env`, serviço `ollama` no ar, modelo puxado; invoke real verificado e2e (LLM=fuzzy, regex=forte). Testes seguem com env vazia → passthrough (sem rede). Faiss/DuckDB/Polars são libs in-process (sem serviço); só o LLM exige runtime à parte.

**Segue deferido (bloqueado por dado/amostra, não por decisão):** regex/prompts por custodiante, modelo de embeddings real, DTW/regressão (esperam série temporal de PU acumulada), calibração de limiares de confiança.

**Nota de infra (sem Alembic ainda):** o schema vem de `create_all`; o `db` do compose é **efêmero de propósito** — volume persistente + `create_all` causaria drift de schema (tabela velha sobrevive sem constraints novos). Adicionar volume de dados só quando entrar migration.
