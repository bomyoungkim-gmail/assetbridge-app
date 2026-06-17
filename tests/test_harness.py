from assetbridge.harness import LoadReport, gerar_carteiras_btg, rodar_carga
from assetbridge.parser_btg import parse_position_xml

# Template BTG real (mesma estrutura ISO 20022 dos demais testes): fundo com
# uma sub-posição de CRI com ISIN (chave forte → cunha IUP).
_TEMPLATE = b"""<?xml version="1.0" encoding="utf-8"?>
<PosicaoAtivosCarteira xmlns:ISO="urn:iso:std:iso:20022:tech:xsd:semt.003.001.04">
  <ISO:Document><ISO:SctiesBalAcctgRpt>
    <ISO:StmtGnlDtls><ISO:StmtDtTm><ISO:Dt>2026-06-03</ISO:Dt></ISO:StmtDtTm></ISO:StmtGnlDtls>
    <ISO:SfkpgAcct><ISO:Id>30306294000145</ISO:Id><ISO:Nm>BTG</ISO:Nm></ISO:SfkpgAcct>
    <ISO:BalForAcct>
      <ISO:FinInstrmId><ISO:ISIN>BR0JJ0CTF000</ISO:ISIN>
        <ISO:OthrId><ISO:Id>55064365000171</ISO:Id><ISO:Tp><ISO:Cd>CNPJ</ISO:Cd></ISO:Tp></ISO:OthrId>
        <ISO:Desc>FUNDO X</ISO:Desc></ISO:FinInstrmId>
      <ISO:AggtBal><ISO:Qty><ISO:Qty><ISO:Qty><ISO:Unit>1</ISO:Unit></ISO:Qty></ISO:Qty></ISO:Qty></ISO:AggtBal>
      <ISO:PricDtls><ISO:Val><ISO:Amt>1</ISO:Amt></ISO:Val></ISO:PricDtls>
      <ISO:AcctBaseCcyAmts><ISO:HldgVal><ISO:Amt>1</ISO:Amt><ISO:Sgn>true</ISO:Sgn></ISO:HldgVal></ISO:AcctBaseCcyAmts>
    </ISO:BalForAcct>
    <ISO:SubAcctDtls><ISO:BalForSubAcct>
      <ISO:FinInstrmId><ISO:ISIN>BRIMWLCRI6O9</ISO:ISIN><ISO:Desc>CRI IPCA</ISO:Desc></ISO:FinInstrmId>
      <ISO:FinInstrmAttrbts><ISO:MtrtyDt>2059-05-15</ISO:MtrtyDt><ISO:DnmtnCcy>BRL</ISO:DnmtnCcy></ISO:FinInstrmAttrbts>
      <ISO:AggtBal><ISO:Qty><ISO:Qty><ISO:Qty><ISO:Unit>1000.00</ISO:Unit></ISO:Qty></ISO:Qty></ISO:Qty></ISO:AggtBal>
      <ISO:PricDtls><ISO:Val><ISO:Amt>500.00</ISO:Amt></ISO:Val><ISO:Tp><ISO:Cd>MRKT</ISO:Cd></ISO:Tp></ISO:PricDtls>
      <ISO:AcctBaseCcyAmts><ISO:HldgVal><ISO:Amt>500000.00</ISO:Amt><ISO:Sgn>true</ISO:Sgn></ISO:HldgVal></ISO:AcctBaseCcyAmts>
    </ISO:BalForSubAcct></ISO:SubAcctDtls>
  </ISO:SctiesBalAcctgRpt></ISO:Document>
</PosicaoAtivosCarteira>"""


def test_gera_n_carteiras_btg_distintas():
    # ADR-0012: harness sobre carteiras BTG (não 300 sintéticas). Cada variante
    # tem CNPJ de fundo distinto → id_carteira distinto → hash distinto (sem
    # dedup na landing zone, ADR-0008).
    raws = gerar_carteiras_btg(_TEMPLATE, 10)

    assert len(raws) == 10
    cnpjs = {parse_position_xml(r).fund_cnpj for r in raws}
    assert len(cnpjs) == 10  # todos distintos
    assert len(set(raws)) == 10  # bytes distintos → hashes distintos


def test_rodar_carga_ingere_todas_e_mede_throughput(session):
    # Load test do pipeline ponta-a-ponta sobre carteiras BTG reais.
    raws = gerar_carteiras_btg(_TEMPLATE, 25)
    rep = rodar_carga(session, raws)

    assert isinstance(rep, LoadReport)
    assert rep.carteiras == 25
    assert rep.duplicados == 0
    # cada carteira tem 1 sub-posição com chave forte → 1 posição cunhada, 0 HITL.
    assert rep.posicoes == 25
    assert rep.pendencias == 0
    assert rep.segundos > 0
    assert rep.carteiras_por_seg > 0


def test_carga_reingestao_identica_e_no_op(session):
    # Rodar a MESMA carga 2x: a 2ª é toda duplicada (idempotência, ADR-0008).
    raws = gerar_carteiras_btg(_TEMPLATE, 5)
    rodar_carga(session, raws)
    rep2 = rodar_carga(session, raws)

    assert rep2.duplicados == 5
    assert rep2.posicoes == 0
