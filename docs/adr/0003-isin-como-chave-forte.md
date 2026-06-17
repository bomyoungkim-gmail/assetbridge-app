# ADR-0003: ISIN como Chave Forte do IUP quando Presente

**Status:** Aceito
**Data:** 2026-06-14

## Contexto

A premissa fundadora do AssetBridge é normalizar ativos **sem depender de chaves regulatórias fortes** (ISIN/CUSIP), porque custodiantes com texto caótico frequentemente não as fornecem — daí a extração híbrida e a chave sintética.

Ao inspecionar os dados reais do BTG (XML ISO 20022 `semt.003.001.04`), constatou-se que os instrumentos de renda fixa **trazem ISIN** (ex: `BRIMWLCRI6O9`), `MtrtyDt`, classificação CVM e código de depositária — mas **não** trazem CNPJ do emissor nem série de forma estruturada. Ou seja, para o BTG a chave forte natural é o **ISIN**, não os campos que a spec assumia extrair do texto.

Isso cria uma aparente tensão com a premissa "não depender de ISIN".

## Decisão

**Quando o ISIN está presente (e não é o placeholder `BR0000000000`), ele é a chave forte do ativo** e basta para cunhar/casar o IUP sem HITL. A `chave_sintetica` é derivada do ISIN nesse caso; sem ISIN, é composta pelos campos do texto (CNPJ emissor + vencimento + série/subordinação). Há **chave forte** se houver ISIN **ou** CNPJ do emissor; sem nenhum dos dois → HITL.

A premissa "não depender de ISIN" é reinterpretada: vale para a **unificação cross-custodiante** (custodiante A tem ISIN, B não — a portabilidade se resolve via alias/merge + HITL, não exigindo ISIN em todos), e **não** proíbe usar o ISIN como chave forte onde ele existe.

O IUP canônico continua sendo um **surrogate opaco** (ADR-0001): o ISIN entra na chave de match e na resolução, **não** vira o IUP.

## Consequências

**Positivo:** para o BTG, a resolução é determinística e barata (sem LLM, sem HITL no caso comum); aproveita o identificador forte que o dado realmente tem; mantém o IUP opaco e estável.

**Negativo:** o mesmo ativo pode receber chaves provisórias diferentes em custodiantes diferentes (um com ISIN, outro só com texto) — resolvido pela dedup/alias/merge ao longo do tempo, não pela chave inicial. Exige cuidado para o placeholder `BR0000000000` e ISINs ausentes não serem tratados como chave.

**Aberto:** quando dois provisórios (um por ISIN, outro por texto) forem o mesmo ativo, a consolidação depende do processo de merge (ADR-0001) — e de sinais além do ISIN (metadata, futura Camada 2).
