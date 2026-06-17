from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from lxml import etree as lxml_et

from .cvm import classificar
from .identity import AssetIdentity

# --- Rich position types (parse_position_xml) ---

_NS_ISO = "urn:iso:std:iso:20022:tech:xsd:semt.003.001.04"
_I = f"{{{_NS_ISO}}}"


@dataclass
class ParsedInstrument:
    isin: str | None
    cnpj: str | None
    description: str | None
    cvm_classification: str | None
    currency: str


@dataclass
class ParsedPosition:
    instrument: ParsedInstrument
    quantity: Decimal
    price: Decimal
    holding_value: Decimal
    price_type: str | None


@dataclass
class ParsedBalanceBreakdown:
    scope: str
    source: str
    parent_id: str | None
    parent_name: str | None
    id: str | None
    name: str | None
    amount: Decimal
    additional_details: str | None
    position_identifier: str | None = None


@dataclass
class ParsedFundPosition:
    reference_date: date
    fund_cnpj: str
    fund_isin: str | None
    fund_name: str
    custodian_cnpj: str
    custodian_name: str
    nav: Decimal | None
    quota_quantity: Decimal | None
    total_holding_value: Decimal | None
    total_aum_reported: Decimal | None
    payables: Decimal | None
    receivables: Decimal | None
    positions: list[ParsedPosition] = field(default_factory=list)
    balance_breakdowns: list[ParsedBalanceBreakdown] = field(default_factory=list)


def _lxml_text(el, path: str) -> str | None:
    if el is None:
        return None
    found = el.find(path)
    return found.text.strip() if found is not None and found.text else None


def _lxml_decimal(el, path: str) -> Decimal | None:
    v = _lxml_text(el, path)
    return Decimal(v) if v else None


def _signed_amount(el, path: str) -> Decimal | None:
    if el is None:
        return None
    container = el.find(path)
    if container is None:
        return None
    amount = _lxml_decimal(container, f"{_I}Amt")
    if amount is None:
        return None
    sign = _lxml_text(container, f"{_I}Sgn")
    return -amount if sign == "false" else amount


def _balance_type_id(el) -> str | None:
    return (
        _lxml_text(el, f"{_I}Prtry/{_I}Id")
        or _lxml_text(el, f"{_I}Cd")
        or _lxml_text(el, f"{_I}Prtry")
    )


def _balance_type_name(el) -> str | None:
    return _lxml_text(el, f"{_I}Prtry/{_I}SchmeNm")


def _balance_quantity(el) -> Decimal:
    return (
        _lxml_decimal(el, f"{_I}Qty/{_I}Qty/{_I}FaceAmt")
        or _lxml_decimal(el, f"{_I}Qty/{_I}Qty/{_I}Unit")
        or _lxml_decimal(el, f"{_I}Qty/{_I}Qty/{_I}Qty/{_I}Unit")
        or Decimal("0")
    )


def _pos_identifier(isin: str | None, cnpj: str | None, desc: str | None) -> str:
    return isin or cnpj or desc or "?"


def _parse_balance_detail(
    detail,
    *,
    scope: str,
    source: str,
    parent_id: str | None,
    parent_name: str | None,
    position_identifier: str | None = None,
) -> ParsedBalanceBreakdown:
    sub_bal_type = detail.find(f"{_I}SubBalTp")
    return ParsedBalanceBreakdown(
        scope=scope,
        source=source,
        parent_id=parent_id,
        parent_name=parent_name,
        id=_balance_type_id(sub_bal_type),
        name=_balance_type_name(sub_bal_type),
        amount=_balance_quantity(detail),
        additional_details=_lxml_text(detail, f"{_I}SubBalAddtlDtls"),
        position_identifier=position_identifier,
    )


def parse_position_xml(xml_bytes: bytes) -> ParsedFundPosition:
    """Extrai posição completa do XML BTG (ISO 20022 semt.003.001.04).

    Retorna dados do fundo (CNPJ, nome, NAV, AUM) + sub-posições + breakdowns.
    Espelha o parser do oikos-testes (ADR-0019); ambos devem divergir apenas
    por falha — toda mudança aqui deve ser refletida lá.
    """
    root = lxml_et.fromstring(xml_bytes)
    rpt = root.find(f"{_I}Document/{_I}SctiesBalAcctgRpt")
    if rpt is None:
        raise ValueError("BTG position XML: SctiesBalAcctgRpt não encontrado")

    reference_date_text = _lxml_text(rpt, f"{_I}StmtGnlDtls/{_I}StmtDtTm/{_I}Dt")
    if not reference_date_text:
        raise ValueError("BTG position XML: data de referência ausente")
    reference_date = date.fromisoformat(reference_date_text)

    custodian_cnpj = _lxml_text(rpt, f"{_I}SfkpgAcct/{_I}Id") or ""
    custodian_name = _lxml_text(rpt, f"{_I}SfkpgAcct/{_I}Nm") or ""

    bal = rpt.find(f"{_I}BalForAcct")
    if bal is None:
        raise ValueError("BTG position XML: BalForAcct (fundo) não encontrado")

    fund_isin = _lxml_text(bal, f"{_I}FinInstrmId/{_I}ISIN")
    fund_name = _lxml_text(bal, f"{_I}FinInstrmId/{_I}Desc") or ""

    # CNPJ do fundo em OthrId[Tp/Cd=CNPJ] — AcctOwnr é o gestor (mesmo CNPJ
    # para toda a carteira), conforme CONTEXT.md e ADR-0019.
    fund_cnpj = ""
    for other in bal.findall(f"{_I}FinInstrmId/{_I}OthrId"):
        if _lxml_text(other, f"{_I}Tp/{_I}Cd") == "CNPJ":
            fund_cnpj = _lxml_text(other, f"{_I}Id") or ""
            break

    nav = _lxml_decimal(bal, f"{_I}PricDtls/{_I}Val/{_I}Amt")
    quota_quantity = _lxml_decimal(bal, f"{_I}AggtBal/{_I}Qty/{_I}Qty/{_I}Qty/{_I}Unit")
    total_holding_value = _signed_amount(bal, f"{_I}AcctBaseCcyAmts/{_I}HldgVal")
    total_aum_reported = _signed_amount(rpt, f"{_I}AcctBaseCcyTtlAmts/{_I}TtlHldgsValOfStmt")

    payables = Decimal("0")
    receivables = Decimal("0")
    balance_breakdowns: list[ParsedBalanceBreakdown] = []
    for breakdown in bal.findall(f"{_I}BalBrkdwn"):
        sub_type = breakdown.find(f"{_I}SubBalTp")
        sub_id = _balance_type_id(sub_type)
        sub_name = _balance_type_name(sub_type)
        qty_el = breakdown.find(f"{_I}Qty/{_I}Qty/{_I}FaceAmt")
        if qty_el is not None and qty_el.text:
            amt = Decimal(qty_el.text.strip())
            if sub_id == "PAYA":
                payables += amt
            elif sub_id == "RECE":
                receivables += amt
        for detail in breakdown.findall(f"{_I}AddtlBalBrkdwnDtls"):
            balance_breakdowns.append(_parse_balance_detail(
                detail,
                scope="fund",
                source="BalBrkdwn/AddtlBalBrkdwnDtls",
                parent_id=sub_id,
                parent_name=sub_name,
            ))

    positions: list[ParsedPosition] = []
    for sub_acct in rpt.findall(f"{_I}SubAcctDtls"):
        for pos_el in sub_acct.findall(f"{_I}BalForSubAcct"):
            fin = pos_el.find(f"{_I}FinInstrmId")
            isin = _lxml_text(fin, f"{_I}ISIN")
            cnpj = None
            if fin is not None:
                for other in fin.findall(f"{_I}OthrId"):
                    if _lxml_text(other, f"{_I}Tp/{_I}Cd") == "CNPJ":
                        cnpj = _lxml_text(other, f"{_I}Id")

            description = _lxml_text(fin, f"{_I}Desc")
            pos_id = _pos_identifier(isin, cnpj, description)

            attrs = pos_el.find(f"{_I}FinInstrmAttrbts")
            cvm_class = (
                _lxml_text(attrs, f"{_I}ClssfctnTp/{_I}AltrnClssfctn/{_I}Id")
                if attrs is not None
                else None
            )
            currency = (_lxml_text(attrs, f"{_I}DnmtnCcy") if attrs is not None else None) or "BRL"

            quantity = _lxml_decimal(pos_el, f"{_I}AggtBal/{_I}Qty/{_I}Qty/{_I}Qty/{_I}Unit") or Decimal("0")
            price = _lxml_decimal(pos_el, f"{_I}PricDtls/{_I}Val/{_I}Amt") or Decimal("0")
            holding_value = _signed_amount(pos_el, f"{_I}AcctBaseCcyAmts/{_I}HldgVal") or Decimal("0")
            price_type = _lxml_text(pos_el, f"{_I}PricDtls/{_I}Tp/{_I}Cd")

            for breakdown in pos_el.findall(f"{_I}BalBrkdwn"):
                sub_type = breakdown.find(f"{_I}SubBalTp")
                sub_id = _balance_type_id(sub_type)
                sub_name = _balance_type_name(sub_type)
                for detail in breakdown.findall(f"{_I}AddtlBalBrkdwnDtls"):
                    balance_breakdowns.append(_parse_balance_detail(
                        detail,
                        scope="position",
                        source="BalForSubAcct/BalBrkdwn/AddtlBalBrkdwnDtls",
                        parent_id=sub_id,
                        parent_name=sub_name,
                        position_identifier=pos_id,
                    ))
            for detail in pos_el.findall(f"{_I}AddtlBalBrkdwn"):
                balance_breakdowns.append(_parse_balance_detail(
                    detail,
                    scope="position",
                    source="BalForSubAcct/AddtlBalBrkdwn",
                    parent_id=None,
                    parent_name=None,
                    position_identifier=pos_id,
                ))

            positions.append(ParsedPosition(
                instrument=ParsedInstrument(
                    isin=isin,
                    cnpj=cnpj,
                    description=description,
                    cvm_classification=cvm_class,
                    currency=currency,
                ),
                quantity=quantity,
                price=price,
                holding_value=holding_value,
                price_type=price_type,
            ))

    # MARGEM no BTG: embutida na soma das sub-posições; persistida como ajuste
    # negativo explícito para que o AUM reconcilie (ADR-0005, oikos CONTEXT §fontes).
    for detail in balance_breakdowns:
        if detail.scope != "fund":
            continue
        if (detail.name or "").upper() != "MARGEM":
            continue
        positions.append(ParsedPosition(
            instrument=ParsedInstrument(
                isin=None,
                cnpj=None,
                description=detail.name,
                cvm_classification=detail.parent_name,
                currency="BRL",
            ),
            quantity=Decimal("1"),
            price=-detail.amount,
            holding_value=-detail.amount,
            price_type="BBDN",
        ))

    return ParsedFundPosition(
        reference_date=reference_date,
        fund_cnpj=fund_cnpj,
        fund_isin=fund_isin,
        fund_name=fund_name,
        custodian_cnpj=custodian_cnpj,
        custodian_name=custodian_name,
        nav=nav,
        quota_quantity=quota_quantity,
        total_holding_value=total_holding_value,
        total_aum_reported=total_aum_reported,
        payables=payables,
        receivables=receivables,
        positions=positions,
        balance_breakdowns=balance_breakdowns,
    )

_NS = {"ISO": "urn:iso:std:iso:20022:tech:xsd:semt.003.001.04"}
_ISIN_PLACEHOLDER = "BR0000000000"


def _texto(el, path: str) -> str:
    return (el.findtext(path, default="", namespaces=_NS) or "").strip()


@dataclass
class ParseResult:
    """Resultado do parse de uma carteira BTG, roteado em três vias (ADR-0005).

    instrumentos: nós que são instrumentos → vão para resolução (forte→IUP,
    fraco→HITL via registry). excluidos: nós não-instrumento → exclusão
    AUDITADA (motivo registrado), nunca drop silencioso.
    """

    instrumentos: list[AssetIdentity] = field(default_factory=list)
    excluidos: list[dict[str, Any]] = field(default_factory=list)


def _is_instrumento(isin: str, desc: str, venc: str) -> bool:
    """Teste estrutural de instrumento para o BTG (ADR-0005).

    NÃO usa presença de chave forte — só conteúdo identificador estrutural.
    Um nó sem ISIN, sem Desc e sem vencimento é controle/lixo, não ativo.
    (`is_instrument` config por custodiante é fatia futura; aqui é o do BTG.)
    """
    return bool(isin or desc or venc)


def parse_carteira(xml: bytes) -> ParseResult:
    """Extrai a carteira do XML BTG (ISO 20022 semt.003.001.04), roteando.

    Gate é estrutural (`_is_instrumento`), nunca em `Desc` nem em chave forte:
    ativo com ISIN sem Desc é real e não some; nó vazio vira exclusão auditada.
    """
    root = ET.fromstring(xml)
    pais = {filho: pai for pai in root.iter() for filho in pai}

    result = ParseResult()
    for fin_id in root.iter(f"{{{_NS['ISO']}}}FinInstrmId"):
        desc = _texto(fin_id, "ISO:Desc")

        isin = _texto(fin_id, "ISO:ISIN")
        if isin == _ISIN_PLACEHOLDER:
            isin = ""

        # CNPJ em OthrId (Tp/Cd=CNPJ) é chave forte quando não há ISIN — ex.
        # linha self do fundo. OthrId não-CNPJ (ex. "SHAR"/TABELA NIVEL 1) é
        # ignorado → sem chave forte → HITL (confirmado na amostra real).
        cnpj = ""
        for othr in fin_id.findall("ISO:OthrId", _NS):
            if _texto(othr, "ISO:Tp/ISO:Cd") == "CNPJ":
                cnpj = _texto(othr, "ISO:Id")
                break

        venc = ""
        cvm_code = ""
        holding = pais.get(fin_id)
        if holding is not None:
            attr = holding.find("ISO:FinInstrmAttrbts", _NS)
            if attr is not None:
                venc = _texto(attr, "ISO:MtrtyDt")
                # Classe CVM estruturada (ADR-0005): autoridade sobre o Desc.
                cvm_code = _texto(
                    attr, "ISO:ClssfctnTp/ISO:AltrnClssfctn/ISO:Id"
                )

        if not _is_instrumento(isin, desc, venc):
            result.excluidos.append(
                {
                    "isin": isin or None,
                    "desc": desc or None,
                    "venc": venc or None,
                    "motivo": "nó sem conteúdo identificador (não-instrumento)",
                }
            )
            continue

        result.instrumentos.append(
            AssetIdentity(
                # Classe pelo código CVM estruturado + refino por Desc (ADR-0005),
                # nunca `desc.split()` como autoridade.
                tipo=classificar(cvm_code, desc),
                data_vencimento=venc,
                isin=isin or None,
                cnpj_emissor=cnpj or None,
            )
        )

    return result


def parse_ativos(xml: bytes) -> list[AssetIdentity]:
    """Atalho de compatibilidade: só os instrumentos da carteira."""
    return parse_carteira(xml).instrumentos
