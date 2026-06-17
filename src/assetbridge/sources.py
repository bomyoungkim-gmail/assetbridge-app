from __future__ import annotations

import csv
import io
from typing import Any, Optional

import httpx

from .enrichment import EnrichmentResult, EnrichmentSource
from .identity import AssetIdentity


class HttpEnrichmentSource:
    """Conector de enriquecimento sobre HTTP — registro oficial (CVM/B3/ANBIMA).

    Implementa a porta `EnrichmentSource` (ADR-0010). Mapeia a resposta do
    registro para `EnrichmentResult` via `field_map` (config — o contrato real do
    endpoint é plugado aqui, o conector independe dele). `fonte="oficial"` →
    confiança alta. Degrada gracioso: sem chave, 404 ou erro de rede → `[]`
    (enriquecimento é turbinador, nunca bloqueia a entrega)."""

    def __init__(
        self,
        client: httpx.Client,
        path: str,
        field_map: dict[str, str],
        param: str = "isin",
        fonte: str = "oficial",
        confianca: float = 0.95,
    ):
        self._client = client
        self._path = path
        self._field_map = field_map
        self._param = param
        self._fonte = fonte
        self._confianca = confianca

    def buscar(self, ativo: AssetIdentity) -> list[EnrichmentResult]:
        chave = ativo.isin or ativo.cnpj_emissor
        if not chave:
            return []  # sem chave de consulta → não chama rede
        try:
            resp = self._client.get(self._path, params={self._param: chave})
            resp.raise_for_status()
            registro = _registro(resp.json())
        except Exception:
            return []  # 404 / rede / payload inválido → degrada gracioso
        if not registro:
            return []

        url = str(resp.request.url)
        return [
            EnrichmentResult(
                campo=campo,
                valor=str(registro[chave_resp]),
                fonte=self._fonte,
                fonte_url=url,
                confianca=self._confianca,
                query=chave,
                snapshot=registro,
            )
            for chave_resp, campo in self._field_map.items()
            if registro.get(chave_resp) is not None
        ]


class HybridEnrichmentSource:
    """Composição oficial→web (ADR-0010). Tenta o registro oficial primeiro;
    a web aberta entra só nas **lacunas** (campos que o oficial não cobriu) e com
    a confiança **rebaixada ao teto** `cap_web` (fonte menos confiável). Degrada
    gracioso: se a web falha, devolve só o oficial."""

    def __init__(
        self,
        oficial: EnrichmentSource,
        web: EnrichmentSource,
        cap_web: float = 0.7,
    ):
        self._oficial = oficial
        self._web = web
        self._cap = cap_web

    def buscar(self, ativo: AssetIdentity) -> list[EnrichmentResult]:
        try:
            oficial = self._oficial.buscar(ativo)
        except Exception:
            oficial = []
        cobertos = {r.campo for r in oficial}

        try:
            web = self._web.buscar(ativo)
        except Exception:
            web = []
        web_lacunas = [
            r.model_copy(update={"confianca": min(r.confianca, self._cap)})
            for r in web
            if r.campo not in cobertos
        ]
        return oficial + web_lacunas


def _registro(data: Any) -> Optional[dict]:
    """Normaliza o corpo da resposta para um registro (dict).

    Aceita o registro direto, uma lista (pega o primeiro) ou um envelope comum
    (`results`/`data`). Formato exato do registro oficial é deferido ao acesso."""
    if isinstance(data, dict):
        for chave in ("results", "data", "items"):
            if isinstance(data.get(chave), list):
                return data[chave][0] if data[chave] else None
        return data
    if isinstance(data, list):
        return data[0] if data else None
    return None


# --- CVM: informe mensal de CRI (dados abertos), tabela `classe` ---
#
# Derivado EMPIRICAMENTE do dataset securit-doc-inf_mensal_cri (verificado
# 2026-06-17): a tabela `classe` traz a coluna `Codigo_ISIN`, então **joina
# direto pelo ISIN do BTG**. Campos abaixo são características (não-identidade);
# `Data_Vencimento`/`Numero_Serie` ficam de fora de propósito (identidade sai do
# parser/HITL, não da web). CSV real: latin-1, separador `;`, decimal vírgula.
CVM_CRI_CLASSE_FIELD_MAP = {
    "Classificacao_Risco_Atual": "rating",
    "Nivel_Subordinacao": "subordinacao",
    "Taxas_Indexadores": "indexador",
    "Situacao": "situacao",
    "Classe": "classe_cvm",
}
_CVM_CRI_DATASET_URL = (
    "https://dados.cvm.gov.br/dataset/securit-doc-inf_mensal_cri"
)


class CvmCriSource:
    """`EnrichmentSource` real: informe mensal de CRI da CVM, chaveado por ISIN.

    Recebe um índice já carregado (`isin → linha`) p/ ser testável sem rede; o
    download/cache do zip e a montagem do índice vivem em `load_cvm_cri_classe_index`
    + camada de ops. `fonte="oficial"` (confiança alta), snapshot da linha.

    Limite conhecido: o `Codigo_ISIN` da CVM é irregular (alguns códigos não são
    ISIN 12-char), então o match depende da qualidade do dado — sem ISIN ou ISIN
    fora do índice → `[]` (degrada gracioso)."""

    def __init__(
        self,
        index: dict[str, dict],
        field_map: Optional[dict[str, str]] = None,
        fonte: str = "oficial",
        confianca: float = 0.95,
    ):
        self._index = index
        self._field_map = field_map or CVM_CRI_CLASSE_FIELD_MAP
        self._fonte = fonte
        self._confianca = confianca

    def buscar(self, ativo: AssetIdentity) -> list[EnrichmentResult]:
        if not ativo.isin:
            return []
        row = self._index.get(ativo.isin.strip().upper())
        if not row:
            return []
        return [
            EnrichmentResult(
                campo=campo,
                valor=str(row[col]).strip(),
                fonte=self._fonte,
                fonte_url=_CVM_CRI_DATASET_URL,
                confianca=self._confianca,
                query=ativo.isin,
                snapshot=row,
            )
            for col, campo in self._field_map.items()
            if str(row.get(col, "")).strip()
        ]


def load_cvm_cri_classe_index(text: str) -> dict[str, dict]:
    """Indexa o CSV `inf_mensal_cri_classe` por `Codigo_ISIN`, mantendo a linha
    de `Data_Referencia`/`Versao` mais recente (a tabela é histórica). `text` já
    deve vir decodificado (o arquivo da CVM é latin-1)."""
    index: dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        isin = (row.get("Codigo_ISIN") or "").strip().upper()
        if not isin:
            continue
        atual = index.get(isin)
        if atual is None or _versao_key(row) >= _versao_key(atual):
            index[isin] = row
    return index


def _versao_key(row: dict) -> tuple:
    try:
        versao = int(row.get("Versao") or 0)
    except ValueError:
        versao = 0
    return (row.get("Data_Referencia") or "", versao)
