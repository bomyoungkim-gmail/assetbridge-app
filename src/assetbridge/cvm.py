from __future__ import annotations

# Classificação por código CVM estruturado (ADR-0005), calibrada na amostra
# real do BTG — ver docs/btg-formato-real.md. Código CVM é o sinal coarse e
# autoritativo; o Desc só refina DENTRO da renda fixa privada (196).
_CVM_CLASSE = {
    "196": "RF_PRIVADA",  # LF / CRI / CDB — domínio do AssetBridge
    "193": "PUBLICO",     # Tesouro + derivativos
    "197": "FUNDO",       # cotas de fundo (FIDC/FII/FIC/FIM/FIA)
    "37": "LISTADO",      # cotas listadas / units
}

# Refino fino dentro de 196 pelo Desc (único sinal disponível; fallback ADR-0005).
_RF_PRIVADA_FINO = ("CRI", "CRA", "CDB", "RDP", "LFSN", "LFN", "LF", "DEB")


def classificar(cvm_code: str, desc: str) -> str:
    """Classe do ativo a partir do código CVM estruturado + Desc (refino).

    196 → refina por Desc (CRI/CRA/CDB/LF…); demais códigos → rótulo coarse;
    sem CVM → fallback pelo Desc (cota self do fundo, ETF). Nunca confia só no
    `desc.split()` como autoridade quando há código CVM (ADR-0005).
    """
    coarse = _CVM_CLASSE.get(cvm_code or "", "")
    primeiro = desc.split()[0].upper() if desc else ""

    if coarse == "RF_PRIVADA":
        for fino in _RF_PRIVADA_FINO:
            if primeiro.startswith(fino):
                return fino
        return "RF_PRIVADA"

    if coarse:
        return coarse

    return primeiro
