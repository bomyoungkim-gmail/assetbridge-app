# ADR-0004: PK Surrogate no Registro de IUP, `chave_sintetica` Nullable com Unique Parcial

**Status:** Aceito
**Data:** 2026-06-15

## Contexto

O MVP nasceu com `iup_registry.chave_sintetica` como **primary key** e como chave de match (ver `db.py`/`registry.py`). Isso funciona para ativos com **chave forte** (ISIN no BTG, ou CNPJ+venc+série no texto): a chave é determinística e dedupa naturalmente.

Mas um ativo cai no HITL **justamente porque não tem chave forte** (`tem_chave_forte` falso) ou é ambíguo. Quando o humano resolve e o IUP é finalmente cunhado, não há `chave_sintetica` significativa para a PK: o caminho composto produziria `tipo|''|venc|''|False` — um balde quase vazio. Consequências:

- Dois ativos HITL não relacionados, mesma classe e vencimento, **colidem na mesma PK**.
- O próximo ativo fracamente descrito poderia **casar silenciosamente** com um IUP cunhado por HITL via essa chave-lixo — desfazendo a garantia do HITL conservador (não auto-ligar sem chave forte completa).

Ou seja, o **modelo de match por chave forte** e o **modelo de cunhagem por HITL** querem PKs diferentes.

## Decisão

- O registro de IUP passa a ter uma **PK surrogate (`id`)**, independente da chave de negócio.
- `chave_sintetica` vira **nullable** com um **índice único parcial** (`UNIQUE WHERE chave_sintetica IS NOT NULL`).
- **Linhas com chave forte** carregam `chave_sintetica` e dedupam pelo unique parcial — idempotência preservada.
- **Linhas cunhadas por HITL** ficam com `chave_sintetica = NULL` e **nunca** participam do auto-match por chave; são alcançáveis só pelo surrogate (e, no futuro, pela alias table, que referencia IUP por surrogate).

A invariante "ativo sem chave forte nunca auto-casa" passa a ser garantida pela **constraint do banco**, não só pela lógica de app — não-forjável.

## Consequências

**Positivo:** separa de forma limpa os dois caminhos de identidade; a dedup de chave forte continua barata e determinística; IUPs de HITL não podem ser atingidos por colisão de hash; pré-modela a alias table (referencia IUP por surrogate).

**Negativo:** a idempotência "reingestão idêntica = no-op" (CONTEXT) **não** pode mais se apoiar em `chave_sintetica` para itens HITL (chave é NULL). O re-find de um item fraco já resolvido por humano precisa ancorar no **hash de conteúdo da landing zone** — que é a âncora correta de qualquer forma, e conecta com o versionamento de re-extração.

**Migração:** troca de PK em tabela existente (hoje só `iup_registry` via `create_all`, sem Alembic). Fazer junto da fatia que introduz a landing zone e a `pending_resolution`.
