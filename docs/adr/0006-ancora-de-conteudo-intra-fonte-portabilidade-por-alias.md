# ADR-0006: Âncora de Conteúdo é Intra-Fonte; Portabilidade Cross-Custodiante é Alias/Merge

**Status:** Aceito
**Data:** 2026-06-15

## Contexto

A landing zone guarda o bruto imutável do custodiante por **hash de conteúdo** (ADR-0002/CONTEXT), o que permite rerodar extratores melhorados e dá idempotência ("reingestão idêntica = no-op"). Ao definir como um item HITL (sem chave forte) é **re-encontrado** numa re-extração — para honrar a decisão pegajosa do humano (CONTEXT) — surgiu a tentação de usar um **hash por ativo** (slice do bruto) como âncora.

Um hash de slice por ativo **não é robusto** assim que existem custodiantes além do BTG:

1. **Drift de segmentação.** Em texto ruidoso, "o slice do ativo" é um chute do extrator. Melhorar o extrator (o gatilho exato da re-extração) re-segmenta → bytes do slice mudam → hash muda. A âncora se move justamente quando é necessária.
2. **Variedade de formato.** BTG é XML com fronteira limpa (`FinInstrmId`); outro custodiante manda PDF/CSV/texto. Um único primitivo de hash de slice não atravessa esses formatos.
3. **Overload.** Mesmo ativo em dois custodiantes = dois slices diferentes = dois hashes diferentes, **sempre**. Hash de conteúdo **nunca** unifica cross-custodiante.

## Decisão

**Separar a âncora por estabilidade, e proibir hash de conteúdo como mecanismo de portabilidade.**

- **File-hash** do import imutável — estável para **todo** custodiante (bytes nunca mudam). Serve lineage + no-op de reingestão exata.
- **Âncora sub-arquivo = par `(extractor_version, source_locator)`, NÃO um hash.** `source_locator` é endereço estrutural no bruto, fornecido pelo extrator versionado por custodiante. **BTG:** locator = ISIN / índice do elemento `FinInstrmId` (cristalino agora). **Texto caótico:** locator é span best-effort e o re-find vira **candidato para o HITL, nunca automático**. O esquema geral de `source_locator` fica **deferido** à fatia de extrator por custodiante (bloqueada por amostra — `detect_source`).

**Invariante (a parte surpreendente):** a âncora de conteúdo é **re-find intra-fonte só**. **Unificação cross-custodiante é alias/merge sobre o IUP surrogate (ADR-0001, ADR-0004), nunca o hash.** Mesmo ativo em dois custodiantes gera slices/hashes diferentes por construção; consolidá-los é trabalho do processo de merge (com sinais além do hash: metadata, futura Camada 2), não da âncora de conteúdo.

## Consequências

**Positivo:** BTG ganha âncora por-ativo crista­lina já (ISIN/elemento); o caso ruidoso degrada para HITL em vez de fingir automação sobre um hash instável; a variabilidade por custodiante é roteada para a camada de extrator+locator (versionada), não congelada num primitivo de hash; ninguém confunde dedup de reingestão com portabilidade.

**Negativo:** dois grãos de âncora para manter (file-hash + locator); o `source_locator` geral fica em aberto até a amostra; exige disciplina para nunca apoiar portabilidade no hash.

**Relacionado:** ADR-0004 (surrogate é o alvo do alias/merge), ADR-0005 (extrator config por custodiante, mesma fatia que define `source_locator`).
