# ADR-0002: Stack Incremental por Fatia (Divergência da Spec)

**Status:** Superado por [ADR-0012](0012-adocao-antecipada-stack-completo.md) (2026-06-17 — stack-alvo adotado de forma antecipada: amostra real + derisk do pipeline + demo). O histórico e o mapa abaixo seguem como registro da decisão original.
**Data:** 2026-06-14

## Contexto

A especificação original (`engine-normalizacao-portabilidade.md`, mantida no repo do Oikos) prescreve um stack fechado: LangGraph, DuckDB, Polars, `langchain_ollama` (ChatOllama), SQLite (MemorySaver/SqliteSaver), Faiss/ChromaDB, e um simulador de carga de 300 carteiras — tudo de uma vez, 100% local no notebook.

Ao construir o MVP por TDD (escopo BTG-only, identidade), nenhuma dessas peças foi necessária para os comportamentos sob teste. Adotá-las de imediato significaria escrever infraestrutura sem uso (o oposto de YAGNI) e antes de ter os dados/decisões que justificam cada uma.

## Decisão

**Implementar o stack incrementalmente: cada dependência entra na fatia que a exige, justificada por um teste/uso real.** A spec é tratada como visão-alvo, não como checklist a cumprir antecipadamente.

Mapa de cada componente da spec e quando entra:

| Componente da spec | Status | Gatilho para entrar |
| --- | --- | --- |
| **Postgres** (no lugar de SQLite) | **Adotado** | É a autoridade/system-of-record do IUP (ADR-0001). |
| FastAPI / Pydantic / SQLAlchemy | **Adotado** | Contrato REST + identidade testável. |
| **LangGraph** | **Adotado** (antecipado, ADR-0010) | Ativado pela fatia de enriquecimento web (grafo extract→resolve→enrich→deliver). |
| **langchain_ollama / LLM** | Deferido | Extração de texto caótico não-BTG — bloqueado por amostras reais. |
| **DuckDB / Polars** | Deferido | Parsing/analytics em volume; hoje XML via `xml.etree` basta. |
| **Faiss / ChromaDB** | Deferido | Camada 2 (matching por série/vetorial) — YAGNI até ter série temporal. |
| Harness 300 carteiras | Deferido | Artefato de teste de carga; quando o pipeline assíncrono existir. |
| **Frontend** | Deferido | Decisão API-first; UI fina do backoffice HITL depois. |

## Consequências

**Positivo:** sem código/infra ociosa; cada peça entra com um caso de uso e teste que a justificam; o MVP roda com um stack pequeno e auditável; reduz risco de acoplar a decisões erradas (ex: SQLite) cedo demais.

**Negativo:** diverge visivelmente da spec — um leitor que espere o stack completo pode achar que falta algo (por isso este ADR + a seção "Estado da implementação" no CONTEXT). Algumas escolhas atuais (ex: `xml.etree` em vez de Polars/DuckDB) podem ser trocadas quando a fatia de volume chegar.

**Regra prática:** ao abrir uma fatia nova, conferir aqui qual componente da spec ela ativa e adotá-lo então — não antes.
