# ADR-0007: Postura Agêntica — LLM Proposer sob Gate Determinístico e HITL

**Status:** Aceito
**Data:** 2026-06-15

## Contexto

O AssetBridge usa um LLM local para extrair campos fuzzy (classe, emissor, série, subordinação, lastro) de texto caótico. Isso introduz **não-determinismo** no caminho que produz a identidade canônica (IUP) — a mesma entrada pode gerar saídas diferentes entre execuções/versões de modelo. Mas o IUP é **system of record** consumido por FK no Oikos: não pode oscilar.

Três decisões agênticas vinham espalhadas (uma linha no ADR-0001, o resto só no CONTEXT) e mereciam um registro próprio, porque definem **quanta autonomia o sistema tem e onde ela é contida**:

1. Como uma fonte não-determinística (LLM) pode lastrear uma identidade estável.
2. Quando o sistema age sozinho vs. quando para para o humano.
3. Como tornar a extração auditável/reproduzível apesar de modelo+prompt evoluírem.

Esta é a postura agêntica do produto. A camada de **orquestração** agêntica em si (LangGraph, fan-out por `thread_id`, checkpoints, `interrupt_before`) está **deferida** (ADR-0002) e **não** é decidida aqui — entra com a fatia que a exige.

## Decisão

### 1. Não-determinismo do agente nunca toca a identidade

O **IUP é um surrogate opaco no registro** (ADR-0001/0004); a identidade vive no registro, **não** no output do LLM nem no hash do extraído. O LLM **só propõe** campos fuzzy; **campos fortes (regex/estruturado) mandam**; o LLM **nunca inventa** CNPJ/data/valor. Re-extração com modelo melhor **nunca sobrescreve** IUP confirmado por humano — abre item de revisão. Consequência: a saída do agente pode variar sem nunca desestabilizar a FK que o Oikos guarda.

### 2. Fronteira de autonomia conservadora (auto-act só em certeza forte)

O sistema **auto-cunha/auto-liga apenas em match exato de chave forte completa** (ISIN, ou CNPJ+venc+série). **Qualquer ambiguidade** — CNPJ ausente, múltiplos candidatos, baixa confiança do LLM, linha não classificável — **vai para HITL**, nunca decide sozinho. Omissão também é decisão proibida (ADR-0005): nada some por `continue`. A zona cinzenta por confiança/correlação (limiares calibráveis) fica **deferida até haver dado rotulado** — gerado pelo próprio HITL conservador. O humano é o gate da autonomia; o timeout nunca decide identidade.

### 3. Extração versionada para auditoria e reprocessamento

Toda extração carrega **modelo + versão por campo**. Itens auto-resolvidos podem ser reprocessados em massa quando o modelo melhora; itens confirmados por humano são pegajosos (só geram item de revisão). Isso dá reprodutibilidade ("o que o agente leu, com qual modelo") e permite rerodar extratores melhorados sobre o bruto imutável da landing zone (ADR-0006).

## Consequências

**Positivo:** identidade determinística e estável apesar de um componente não-determinístico no pipeline; autonomia explicitamente contida (age só com certeza forte, resto ao humano); o HITL conservador gera o dataset rotulado que falta para calibrar a autonomia futura; extração auditável e reprocessável; nenhuma decisão silenciosa do agente.

**Negativo:** mais HITL no início (preço de não adivinhar); zona cinzenta automática só chega depois; versionamento de extração é máquina extra (coluna de modelo/versão, lógica de reprocesso).

**Fora de escopo (deferido):** a orquestração agêntica concreta (LangGraph, `thread_id`, checkpoints, interrupts) — ADR-0002; os limiares de confiança/zona cinzenta — bloqueados por dado rotulado. Este ADR fixa a **postura**, não o runtime.
