# ADR-0013: Modelo LLM da Extração Fuzzy — qwen3:8b (Ativação)

**Status:** Aceito
**Data:** 2026-06-17

## Contexto

O [ADR-0012](0012-adocao-antecipada-stack-completo.md) adotou o stack LLM (`langchain_ollama`) e deixou o wiring pronto, mas a execução seguia **gated por env** (`ASSETBRIDGE_OLLAMA_MODEL` vazio → `_field_proposer` devolve `None` → nó `extract` passthrough). Faltava a decisão operacional: **qual modelo** ligar e como.

A fronteira de não-determinismo (ADR-0007) já garante que o LLM nunca toca campo forte (ISIN/CNPJ/data saem de regex em `extraction.py`); o modelo só propõe campos fuzzy (classe/série/subordinação). Logo a escolha do modelo é tradeoff **qualidade fuzzy × custo de hardware**, sem risco para a identidade.

Candidatos Ollama considerados:

| Modelo | Tamanho | Hardware | Qualidade fuzzy |
| --- | --- | --- | --- |
| qwen3:4b | ~2.5 GB | CPU puro viável | menor |
| **qwen3:8b** | ~5.2 GB | GPU média / CPU lento | suficiente |
| qwen3:14b | ~9 GB | exige VRAM | maior |

## Decisão

**Ligar `qwen3:8b`** como modelo de extração fuzzy. Casa com o default já documentado em `proposers.DEFAULT_OLLAMA_MODEL`; a fonte de verdade em runtime continua a env `ASSETBRIDGE_OLLAMA_MODEL` (gate em `hitl._field_proposer`), não a constante.

Ativação executada:

1. `.env` (+ `.env.example` em sincronia): `ASSETBRIDGE_OLLAMA_MODEL=qwen3:8b`, `ASSETBRIDGE_OLLAMA_BASE_URL=http://ollama:11434`.
2. `docker compose --profile llm up -d ollama` + `docker compose exec ollama ollama pull qwen3:8b`.
3. `docker compose up -d api` (recarrega a env no container vivo).

Verificação: invoke real end-to-end sobre texto caótico — LLM preencheu fuzzy (tipo/série), regex os campos fortes; fronteira ADR-0007 intacta. Suite 101 passed (testes rodam com env vazia → passthrough, sem rede).

## Consequências

**Positivo:** extração fuzzy real ligada; liga/desliga continua sendo só a env (`ASSETBRIDGE_OLLAMA_MODEL` vazia → passthrough); testes não tocam Ollama; modelo casa com o default do código (sem surpresa).

**Negativo:** qwen3:8b pesa ~5.2 GB e roda lento em CPU puro; runtime Ollama é serviço à parte (profile `llm`) que precisa estar no ar para o `extract` não falhar quando a env está setada. Confiança ainda não-calibrada (`OllamaProposer` usa default conservador 0.5) — calibração deferida até dado rotulado pelo HITL.

**Caminho de evolução:** subir para qwen3:14b em host com VRAM é troca de uma env (`ASSETBRIDGE_OLLAMA_MODEL=qwen3:14b` + `ollama pull`), sem código. Fica para ADR futuro quando houver host com VRAM + amostra rotulada que justifique o ganho.

**Não revoga:** fronteiras de não-determinismo (ADR-0007/0010) nem o gate determinístico — o modelo só propõe fuzzy.
