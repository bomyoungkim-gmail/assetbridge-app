from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel


class AssetIdentity(BaseModel):
    """Campos FORTES de identidade de um ativo de renda fixa privada.

    Só campos determinísticos entram aqui (ver ADR-0001): o que define o IUP.
    Enriquecimento (nome do emissor, lastro) NÃO entra na identidade.
    """

    tipo: str
    data_vencimento: str
    isin: Optional[str] = None
    cnpj_emissor: Optional[str] = None
    serie_emissao: Optional[str] = None
    is_subordinado: bool = False


def tem_chave_forte(ativo: AssetIdentity) -> bool:
    """Há chave forte se houver ISIN (BTG) ou CNPJ do emissor (texto)."""
    return bool(ativo.isin or ativo.cnpj_emissor)


def chave_sintetica(ativo: AssetIdentity) -> str:
    """Hash dos campos de identidade. NÃO é o IUP — é o balde de match.

    ISIN, quando presente, é globalmente único e basta como chave forte.
    Sem ISIN, compõe pelos campos fortes do texto (CNPJ/venc/série/subord.).
    """
    if ativo.isin:
        base = "ISIN|" + ativo.isin
    else:
        base = "|".join(
            [
                ativo.tipo,
                ativo.cnpj_emissor or "",
                ativo.data_vencimento,
                ativo.serie_emissao or "",
                str(ativo.is_subordinado),
            ]
        )
    return "sint_" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _rotulo_isin(a: AssetIdentity) -> str:
    """Fallback legível quando faltam campos do texto (caso BTG: só ISIN)."""
    chave = a.isin or "SEMCHAVE"
    return f"IUP-{a.tipo.upper()}-{chave}-{a.data_vencimento}"


def _rotulo_cri(a: AssetIdentity) -> str:
    # Degrada para ISIN quando CNPJ/série ausentes (ADR-0003); nunca emite "None".
    if a.cnpj_emissor and a.serie_emissao:
        return (
            f"IUP-{a.tipo.upper()}-{a.cnpj_emissor}"
            f"-SERIE{a.serie_emissao}-{a.data_vencimento}"
        )
    return _rotulo_isin(a)


def _rotulo_default(a: AssetIdentity) -> str:
    if a.cnpj_emissor:
        return f"IUP-{a.tipo.upper()}-{a.cnpj_emissor}-{a.data_vencimento}"
    return _rotulo_isin(a)


# Regras por classe config-driven (ver decisão ClassRules / ADR-0001).
# Promover a Strategy/polimorfismo só se a lógica por classe crescer.
_ROTULO_POR_CLASSE = {
    "CRI": _rotulo_cri,
    "CRA": _rotulo_cri,
}


def rotulo_semantico(ativo: AssetIdentity) -> str:
    """Rótulo legível derivado por classe. NÃO é a identidade — é exibição."""
    builder = _ROTULO_POR_CLASSE.get(ativo.tipo.upper(), _rotulo_default)
    return builder(ativo)


@dataclass
class Resolution:
    """Resultado da resolução de identidade.

    resolved: iup + rotulo, novo indica se foi cunhado agora.
    pending: aguardando HITL (sem iup).
    """

    novo: bool = False
    iup: Optional[str] = None
    rotulo_semantico: Optional[str] = None
    pending: bool = False
    motivo: Optional[str] = None
