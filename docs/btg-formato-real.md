# BTG — Formato Real (calibrado em amostra)

Calibrado em amostra real (`oikos-testes/data`, jun/2026). Destrava itens 6, 9-resto, 11 do roadmap. **Antes era chute; agora é dado.**

## Layout de arquivos

- **Posições:** um XML por **fundo por dia**. Filename `FD{CNPJ_FUNDO}_{YYYYMMDD}_{YYYYMMDD000000}_{NOME FUNDO}.xml`.
  - **`id_carteira` (fundo) e `asof` vêm do FILENAME** — fonte limpa. O CNPJ do filename = CNPJ do próprio fundo (bate com o `OthrId` da 1ª holding self). **`AcctOwnr` no XML é OUTRO CNPJ** (conta/admin), não o fundo — não usar como carteira.
  - `asof` também está no XML (`StmtGnlDtls/StmtDtTm/Dt`) e concorda com o filename.
- **Transações (caixa):** um **xlsx por dia, todos os fundos** (`2026-05-19.xlsx`). **Excel = lado Oikos** (`btg_transaction_excel`), confirma item 10 fora do AssetBridge.

## Estrutura XML (ANBIMA + ISO 20022 semt.003.001.04)

Root `PosicaoAtivosCarteira` envolve `HEADER:AppHdr` (head.001.001.01) + `ISO:Document/SctiesBalAcctgRpt`. NS ISO = `urn:iso:std:iso:20022:tech:xsd:semt.003.001.04`.

Holdings ficam sob **`BalForAcct`** (linha self do fundo, sem `ClssfctnTp`) **e `BalForSubAcct`** (demais, com `ClssfctnTp`) — **iterar os dois**.

Paths por holding (container = pai do `FinInstrmId`):

| Campo | Path (relativo ao container do holding) |
| --- | --- |
| ISIN | `FinInstrmId/ISIN` |
| Desc (humano) | `FinInstrmId/Desc` |
| **Classe CVM** | `FinInstrmAttrbts/ClssfctnTp/AltrnClssfctn/Id` (Issr=`CVM`) |
| Vencimento | `FinInstrmAttrbts/MtrtyDt` |
| Emissão | `FinInstrmAttrbts/IsseDt` |
| **Quantidade** | `AggtBal/Qty/Qty/Qty/Unit` (triplo aninhamento) |
| **PU** | `PricDtls/Val/Amt` (`Ccy`), tipo NAVL/PARV |
| Valor da posição | `AcctBaseCcyAmts/HldgVal/Amt` (`Ccy`, `Sgn`) |
| asof (carteira) | `StmtGnlDtls/StmtDtTm/Dt` |

## Tabela CVM→classe (empírica, da amostra)

| Código CVM | Classe | Exemplos (Desc) |
| --- | --- | --- |
| **196** | **Renda fixa privada** (domínio do AssetBridge) | LF, CRI, CDB |
| 193 | Título público / derivativo | NTNB, LFT, LTN, NTNF, INDFM26/WINFM26/DOLFN26 (futuros) |
| 197 | Cota de fundo | FIDC, FII, FIC/FIM/FIA (CSHG, KINEA, SPX…) |
| 37 | Cota listada / unit | BPAC11, BIPD11, BGS115 |
| (sem CVM) | Cota self do fundo / ETF | linha self (`BalForAcct`), BOVA11 |

Notas:
- Todo holding tem **ISIN** (84/84 no BLUE BIRD) → resolução por chave forte ISIN é trivial p/ tudo. A classe é **enriquecimento** (ClassRules/rótulo), não gate de identidade.
- **CVM=196 é o bucket-alvo** (LF/CRI/CDB). Dentro de 196, o `Desc[0]` (LF vs CRI vs CDB) é o sinal fino — único disponível, então Desc-as-fallback **dentro** de 196 é aceitável (ADR-0005).
- 193 mistura Tesouro e futuros sob o mesmo código — código CVM é coarse; refino exige Desc.

## Validação na amostra (187 arquivos, jun/2026)

- **4058 instrumentos parseados, 0 excluídos** — parser real não perde nada silenciosamente.
- Distribuição: FUNDO 3014 · PUBLICO 588 · LF 91 · CRI 76 · LISTADO 45 · (cotas self por Desc).
- **Resolução end-to-end:** todos resolvem (idempotência confirmada — mesmo ISIN repetido → mesmo IUP; rótulo degrada p/ ISIN). Ex.: `CRI BRIMWLCRI6O9 2059-05-15 → IUP-CRI-BRIMWLCRI6O9-2059-05-15`.
- **0% HITL no BTG:** todo holding tem chave forte (ISIN, ou CNPJ em `OthrId/Tp/Cd=CNPJ`). Confirma determinismo do BTG (ADR-0003). O caminho sem-chave-forte→HITL segue válido para **custodiantes futuros** (não-BTG), não para o BTG.
- **`OthrId` não-CNPJ** (`SHAR`, `GOVE`, `TABELA NIVEL 1`) é ignorado como chave; só `Tp/Cd=CNPJ` vira `cnpj_emissor`.

## Implicação para o parser

- Classe = código CVM estruturado (coarse) + Desc (fino dentro de 196). **Nunca** `desc.split()[0]` como autoridade (ADR-0005).
- `id_carteira`/`asof` entram por parâmetro (do filename), não saem do conteúdo XML de forma confiável.
- Iterar `BalForAcct` + `BalForSubAcct`.
