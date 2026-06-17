# ADR-0005: Ingestão sem Drop Silencioso — Roteamento Explícito em Três Vias

**Status:** Aceito
**Data:** 2026-06-15

## Contexto

O parser BTG (`parser_btg.py`) descartava qualquer linha com `Desc` vazio (`if not desc: continue`). Duas falhas:

1. **Gate no campo errado.** `Desc` é metadado auxiliar (texto para humano ler); a identidade forte é o **ISIN**. Um instrumento real com `Desc=""` mas ISIN válido era **excluído silenciosamente** da carteira.
2. **Drop silencioso = decisão de identidade por omissão.** O design proíbe decidir identidade silenciosamente — "timeout nunca decide identidade" (CONTEXT, HITL). Omissão no parser é um timeout silencioso: o ativo some sem registro.

Uma correção ingênua (`if not tem_chave_forte: continue`) troca um drop silencioso por outro: um ativo real sem chave forte cairia no mesmo `continue` que uma linha de saldo, quando deveria ir para **HITL** (sem chave forte → HITL, não → drop).

O erro de fundo: **um gate respondendo duas perguntas distintas** —
- *É um instrumento financeiro?* (linha de saldo/header/total **não** é) → resposta semântica, pela estrutura da linha.
- *Consigo identificá-lo?* (ativo real, chave fraca) → resposta de identidade, pela presença de chave forte.

Presença de chave forte responde a segunda, não a primeira. Usá-la como gate único faz as duas falharem juntas.

## Decisão

**Nenhuma linha some por `continue`. Toda linha é roteada explicitamente para um de três destinos:**

```
for row in rows:
    if tem_chave_forte(row):
        process_instrument(row)   # forte → fluxo normal de resolução
    elif is_instrument(row):
        enqueue_hitl(row)         # ativo-shaped, sem chave forte → HITL
    else:
        log_excluded(row, reason) # não-instrumento → EXCLUSÃO AUDITADA
```

1. **Nenhum drop silencioso em nenhum caminho.** `log_excluded` grava registro de auditoria (contagem + motivo + bruto); a decisão "isto não é instrumento" é explícita e revisável, nunca omissão.
2. **HITL reservado para ambiguidade de identidade, não para ruído de controle.** Linhas de saldo/header não vão para o humano em regime — isso afogaria o HITL e poluiria o dataset rotulado que o HITL existe para gerar. Elas vão para exclusão auditada (explícita, sem humano).
3. **`is_instrument` é config aprendida por custodiante, não lógica hardcoded no parser.** Para um custodiante **novo sem amostra**, `is_instrument` ainda não existe → o `elif` não dispara → tudo fraco colapsa em **HITL** (bootstrap: o humano ensina quais linhas são controle). Aprendida a estrutura, `is_instrument` vira config (por custodiante) e o regime para de mandar saldo para HITL. É a fatia de extrator por custodiante, bloqueada por amostra (`detect_source`).

Relacionado (mesma raiz — hierarquia de confiança invertida): a **classe (`tipo`) deixa de vir de `desc.split()[0]`** e passa a vir da **classificação CVM estruturada** do XML BTG, mapeada por tabela de lookup (config, nunca `if` hardcoded); `Desc` vira fallback. O elemento exato e a tabela CVM→classe ficam deferidos à amostra real (calibração de Camada 1). Ver ADR-0003 / CONTEXT (`Desc` é texto fraco; campos estruturados mandam).

## Consequências

**Positivo:** nenhuma posição se perde silenciosamente; o HITL fica conservador e útil (só identidade ambígua de ativo real); exclusões são auditáveis e reversíveis; `is_instrument` por custodiante encaixa no roadmap de extrator por amostra; identidade (IUP) intacta — nada disso toca o surrogate.

**Negativo:** mais máquinas que um `continue` (tabela/log de exclusão, fila HITL alimentada também na ingestão, `is_instrument` config por custodiante); no bootstrap de custodiante novo o HITL recebe volume maior (aceito — é o preço de aprender a estrutura sem amostra prévia).

**Bloqueio conhecido:** `is_instrument` e a tabela CVM→classe só se finalizam com amostra real do custodiante — até lá, BTG usa regras estruturais conhecidas e o resto colapsa em HITL.
