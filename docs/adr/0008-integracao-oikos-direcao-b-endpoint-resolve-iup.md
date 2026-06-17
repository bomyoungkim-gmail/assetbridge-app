# ADR-0008: Integração com o Oikos — Direção B, Endpoint resolve-iup e Degradação Graciosa

**Status:** Aceito
**Data:** 2026-06-15
**Espelho de:** ADR-0019 do Oikos (perspectiva do AssetBridge)

## Contexto

ADR-0001 definiu o contrato com o Oikos como "REST API versionada, sem banco compartilhado", com duas direções possíveis:

- **(a)** AssetBridge ingere o bruto e entrega posições + IUP ao Oikos.
- **(b)** Oikos ingere com seus próprios parsers e chama AssetBridge apenas para resolver o IUP.

A direção para BTG ficou em aberto no ADR-0001. O Oikos possui `btg_position_xml.py` e `btg_transaction_excel.py` em produção; o AssetBridge tem seu próprio `parser_btg.py` (para operar de forma independente na direção a). A questão é qual direção vale para BTG e qual é o contrato concreto do `POST /resolve-iup`.

## Decisão

### 1. Direção B para BTG — AssetBridge recebe campos estruturados, não XML bruto

Para BTG, o Oikos ingere os arquivos com seus próprios parsers e chama o AssetBridge **apenas para resolver o IUP** — enviando campos estruturados de identidade (ISIN, CNPJ, descrição, classificação CVM), não o XML bruto.

O AssetBridge mantém seu `parser_btg.py` para operar na **direção a** com custodiantes onde o Oikos não tem parser próprio. Para BTG, o `parser_btg.py` do AssetBridge é capacidade de ingestão autônoma — não substitui os parsers do Oikos.

A duplicação de lógica de parsing (Oikos + AssetBridge) é explícita e aceita: ADR-0001 garante que cada produto opera de forma autônoma; parsers distintos são consequência natural.

### 2. Contrato do endpoint `POST /resolve-iup`

O AssetBridge expõe:

```
POST /resolve-iup
Content-Type: application/json

{
  "isin": "BRXYZ...",           // opcional — presente quando disponível
  "cnpj": "12.345.678/0001-99", // opcional
  "description": "CRI OPEA...", // opcional — Camada 1 só roda se faltar campo forte
  "cvm_classification": "CRI"   // opcional — campo estruturado BTG, preferido a Desc
}
```

Resposta (match exato de chave forte — síncrona):
```json
{ "status": "resolved", "iup": "IUP-abc123..." }
```

Resposta (ambíguo / HITL — assíncrona):
```json
{ "status": "pending", "thread_id": "uuid-..." }
```

**Extração condicional:** Camada 1 (regex + LLM) só roda sobre o que faltar. Oikos manda dado estruturado → IUP determinístico, sem LLM. Custodiante novo manda texto bruto → Camada 1 completa.

### 3. Garantias que o AssetBridge deve honrar

| Garantia | Detalhe |
|---|---|
| Timeout tolerável | Oikos define timeout de 5s; AssetBridge deve responder `pending` em < 5s para casos ambíguos — nunca travar esperando HITL |
| Idempotência | Reingestão de ISIN/CNPJ idêntico → mesmo IUP; sem novo cunho |
| `pending` não é erro | Oikos trata `pending` como degradação graciosa — `instrument.iup = null` até backfill |
| Calls por instrumento, não por arquivo | O Oikos não re-chama se `instrument.iup` já está preenchido; AssetBridge não precisa dedupar por chamada — a idempotência é do registro |

### 4. Backfill — pull por re-resolução (decidido)

Quando o AssetBridge resolve um IUP que estava `pending`, o Oikos precisa preencher `instrument.iup`. **Mecanismo decidido: pull por re-resolução**, do lado do Oikos — não há novo endpoint nem push deste lado.

O Oikos (`POST /imports/backfill-iup`) varre seus instrumentos com `iup IS NULL` e chave forte e re-chama este mesmo `POST /resolve-iup`. Como a resolução é idempotente, itens já resolvidos no HITL passam a retornar `resolved`. O AssetBridge **não precisa conhecer a URL/auth do Oikos** nem manter um canal de push — o contrato é o mesmo `/resolve-iup` síncrono.

Implicações para o AssetBridge:
- A idempotência de `/resolve-iup` é o que torna o pull seguro (re-chamar não re-cunha).
- Uma vez resolvida uma pendência no HITL, a próxima chamada de `/resolve-iup` com a mesma chave forte deve retornar `resolved` com o IUP cunhado.

**Push via webhook permanece deferido** — só entra se a latência do pull for insuficiente, e exigiria definir a auth service-to-service e a URL do Oikos.

### 5. Autenticação e versionamento

**Ainda não definidos.** AssetBridge não exige auth no MVP. Quando o Oikos adicionar JWT (ADR-0008 do Oikos — a criar), a auth service-to-service e o versionamento do contrato (`/v1` vs header) são definidos em conjunto. O AssetBridge deve versionar o endpoint quando o primeiro consumidor real entrar em produção.

## Consequências

**Positivo:**
- Oikos e AssetBridge operam 100% autônomos — degradação graciosa em ambas as direções
- AssetBridge recebe campos estruturados limpos em vez de XML — sem acoplamento de formato
- Camada 1 só é invocada quando necessário — leve para o caso BTG estruturado
- `pending` como resposta legítima permite HITL sem travar o ingest do Oikos

**Negativo:**
- Duplicação de parsers BTG (Oikos + AssetBridge) — explícita e aceita
- `instrument.iup` pode ficar null por tempo indeterminado sem backfill definido
- Dois contratos de resposta (sync/pending) exigem lógica de cliente no Oikos

## Relacionados

- **ADR-0001** — contrato REST com o Oikos; IUP como autoridade única
- **ADR-0005** — roteamento três-vias no AssetBridge; `is_instrument` config-driven
- **ADR-0019 (Oikos)** — espelho desta decisão do ponto de vista do Oikos
- **ADR-0015 (Oikos)** — AssetBridge como produto externo; turbinador opcional
