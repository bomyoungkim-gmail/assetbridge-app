# ADR-0015: Agregação de Sub-posições por IUP no Grão de Posição

**Status:** Aceito
**Data:** 2026-06-18

## Contexto

A projeção de posição do AssetBridge (direção a) tem grão **uma linha por `(id_carteira, custodiante, IUP, asof)`** — espelha a regra do Oikos "uma linha por `(fund_id, instrument_id, reference_date)`" no grão de carteira (CONTEXT.md, ADR-0001). O `db.py` impõe isso com o unique `uq_position`.

Ao ingerir um **XML BTG real** pelo `/ingest`, o parser (`parse_position_xml`) emite **uma `ParsedPosition` por `BalForSubAcct`** percorrendo os `SubAcctDtls`. Um mesmo instrumento (mesmo ISIN → mesmo IUP) aparece em **múltiplos sub-accounts** do fundo (disponível / garantia / bloqueado). Como `upsert_posicoes` inseria uma linha por `ParsedPosition`, duas sub-posições do mesmo instrumento colidiam:

```
psycopg.errors.UniqueViolation: duplicate key value violates unique constraint "uq_position"
DETAIL: Key (id_carteira, custodiante, iup, asof)=(63462960000193, BTG, IUP-9ab0…771eb, 2026-06-10) already exists.
```

Os 99→106 testes passavam porque os fixtures não tinham instrumento repetido em sub-accounts; só o dado real expôs o caso. O bug bloqueava o `/ingest` com `500` (ver o backoffice/Acervo enviando o XML).

A pergunta de fundo: **uma sub-posição é um ativo distinto?** Não. Disponível e garantia do mesmo ISIN são o **mesmo ativo** (mesmo IUP) — o desdobramento é estado de custódia, não identidade. O grão decidido (uma linha por IUP/carteira/dia) é, portanto, o correto; faltava o engine **consolidar** o que o custodiante desdobra.

## Decisão

`upsert_posicoes` **agrega as sub-posições do mesmo IUP** antes de gravar, dentro do `(id_carteira, custodiante, asof)`:

1. **Quantidade:** soma (`Σ qtd`). Nada é descartado (ADR-0005, "nada some").
2. **PU:** **média ponderada pela quantidade** — `pu_agg = Σ(qtd·pu) / Σ qtd`. Isso **conserva o valor total** (`Σ qtd·pu`) mesmo se o PU divergir entre sub-accounts. Quando o PU é igual entre elas (caso comum — é preço de mercado do dia), a média ponderada devolve o mesmo PU, sem drift.
3. **PU indeterminável:** se alguma sub-posição vem com PU nulo, ou a quantidade total é zero, não há como ponderar → PU nulo (preenchido depois). A posição **continua contada** (alinhado a `analytics.py`: PU nulo conta 0, posição não some).
4. **IUP nulo (pendente HITL) NÃO agrega:** cada pendência fica na sua própria linha — `NULL` é distinto no unique do Postgres, e cada uma é backfillada individualmente quando o HITL resolve. Agregar pendências misturaria ativos ainda não identificados.

A consolidação vive no `upsert_posicoes` (engine), **não** no parser: o parser permanece fiel ao bruto (uma `ParsedPosition` por bloco do XML, auditável contra a landing zone); a regra de grão é do engine de projeção.

## Consequências

**Positivo:**
- `/ingest` aceita XML BTG real com instrumento repetido em sub-accounts (bug de `500` eliminado).
- Grão `(id_carteira, custodiante, IUP, asof)` respeitado de fato; `uq_position` mantido (não relaxa a invariante).
- Conservação de valor garantida pela média ponderada (entrega coerente ao Oikos para reconciliação de AUM).
- Parser intacto e fiel ao bruto; consolidação isolada e testável no engine.

**Negativo:**
- A projeção **perde a granularidade por sub-account** (disponível × garantia) — aceitável: o consumidor (Oikos) reconcilia no grão instrumento/dia, e o desdobramento por custódia vive no bruto da landing zone se um dia for preciso.
- Média ponderada pode gerar PU com mais casas decimais quando os PUs divergem (raro); o `Numeric` da coluna acomoda.

**Não revoga:** o grão de posição (CONTEXT.md/ADR-0001), o delete+replace por `(id_carteira, custodiante, asof)` (Q6), nem a postura "nada some" (ADR-0005) — este ADR **realiza** essas regras para o dado real.

## Relacionados

- **CONTEXT.md** — §"Estado da implementação" / projeção de posição (grão, delete+replace); nota de agregação adicionada.
- **ADR-0001** — grão de posição alinhado ao Oikos (uma linha por instrumento/dia).
- **ADR-0005** — roteamento três-vias e "nada some"; aqui a soma de quantidade e a ponderação de PU conservam o total.
- **`positions.py` / `test_positions.py`** — implementação e testes (sub-posições agregam; PU divergente conserva valor).
