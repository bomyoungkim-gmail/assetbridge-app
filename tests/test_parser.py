from decimal import Decimal

from assetbridge.parser_btg import parse_ativos, parse_carteira, parse_position_xml

# XML mínimo mas completo no formato real BTG (ISO 20022 semt.003.001.04 /
# ANBIMA), usado para testar parse_position_xml sem arquivo externo.
_XML_POSICAO = b"""<?xml version="1.0" encoding="utf-8"?>
<PosicaoAtivosCarteira xmlns:ISO="urn:iso:std:iso:20022:tech:xsd:semt.003.001.04">
  <ISO:Document>
    <ISO:SctiesBalAcctgRpt>
      <ISO:StmtGnlDtls>
        <ISO:StmtDtTm><ISO:Dt>2026-06-03</ISO:Dt></ISO:StmtDtTm>
      </ISO:StmtGnlDtls>
      <ISO:SfkpgAcct>
        <ISO:Id>30306294000145</ISO:Id>
        <ISO:Nm>BANCO BTG PACTUAL S A</ISO:Nm>
      </ISO:SfkpgAcct>
      <ISO:BalForAcct>
        <ISO:FinInstrmId>
          <ISO:ISIN>BR0JJ0CTF000</ISO:ISIN>
          <ISO:OthrId>
            <ISO:Id>55064365000171</ISO:Id>
            <ISO:Tp><ISO:Cd>CNPJ</ISO:Cd></ISO:Tp>
          </ISO:OthrId>
          <ISO:Desc>OIKOS G FIC FIM CP</ISO:Desc>
        </ISO:FinInstrmId>
        <ISO:AggtBal>
          <ISO:Qty><ISO:Qty><ISO:Qty><ISO:Unit>26162.54377</ISO:Unit></ISO:Qty></ISO:Qty></ISO:Qty>
        </ISO:AggtBal>
        <ISO:PricDtls>
          <ISO:Val><ISO:Amt>1.338588</ISO:Amt></ISO:Val>
        </ISO:PricDtls>
        <ISO:AcctBaseCcyAmts>
          <ISO:HldgVal><ISO:Amt>35125091.80</ISO:Amt><ISO:Sgn>true</ISO:Sgn></ISO:HldgVal>
        </ISO:AcctBaseCcyAmts>
      </ISO:BalForAcct>
      <ISO:AcctBaseCcyTtlAmts>
        <ISO:TtlHldgsValOfStmt>
          <ISO:Amt>35125091.80</ISO:Amt><ISO:Sgn>true</ISO:Sgn>
        </ISO:TtlHldgsValOfStmt>
      </ISO:AcctBaseCcyTtlAmts>
      <ISO:SubAcctDtls>
        <ISO:BalForSubAcct>
          <ISO:FinInstrmId>
            <ISO:ISIN>BRIMWLCRI6O9</ISO:ISIN>
            <ISO:Desc>CRI IPCA</ISO:Desc>
          </ISO:FinInstrmId>
          <ISO:FinInstrmAttrbts>
            <ISO:MtrtyDt>2059-05-15</ISO:MtrtyDt>
            <ISO:ClssfctnTp>
              <ISO:AltrnClssfctn><ISO:Id>196</ISO:Id></ISO:AltrnClssfctn>
            </ISO:ClssfctnTp>
            <ISO:DnmtnCcy>BRL</ISO:DnmtnCcy>
          </ISO:FinInstrmAttrbts>
          <ISO:AggtBal>
            <ISO:Qty><ISO:Qty><ISO:Qty><ISO:Unit>1000.00</ISO:Unit></ISO:Qty></ISO:Qty></ISO:Qty>
          </ISO:AggtBal>
          <ISO:PricDtls>
            <ISO:Val><ISO:Amt>500.00</ISO:Amt></ISO:Val>
            <ISO:Tp><ISO:Cd>MRKT</ISO:Cd></ISO:Tp>
          </ISO:PricDtls>
          <ISO:AcctBaseCcyAmts>
            <ISO:HldgVal><ISO:Amt>500000.00</ISO:Amt><ISO:Sgn>true</ISO:Sgn></ISO:HldgVal>
          </ISO:AcctBaseCcyAmts>
        </ISO:BalForSubAcct>
      </ISO:SubAcctDtls>
    </ISO:SctiesBalAcctgRpt>
  </ISO:Document>
</PosicaoAtivosCarteira>"""


def test_parse_position_xml_extrai_fundo():
    result = parse_position_xml(_XML_POSICAO)

    assert result.fund_cnpj == "55064365000171"
    assert result.fund_name == "OIKOS G FIC FIM CP"
    assert result.fund_isin == "BR0JJ0CTF000"
    assert result.reference_date.isoformat() == "2026-06-03"
    assert result.custodian_cnpj == "30306294000145"


def test_parse_position_xml_extrai_subposicoes():
    result = parse_position_xml(_XML_POSICAO)

    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.instrument.isin == "BRIMWLCRI6O9"
    assert pos.instrument.cvm_classification == "196"
    assert pos.quantity == Decimal("1000.00")
    assert pos.price == Decimal("500.00")
    assert pos.holding_value == Decimal("500000.00")
    assert pos.price_type == "MRKT"


def test_parse_position_xml_extrai_valores_fundo():
    result = parse_position_xml(_XML_POSICAO)

    assert result.quota_quantity == Decimal("26162.54377")
    assert result.nav == Decimal("1.338588")
    assert result.total_aum_reported == Decimal("35125091.80")

XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:ISO="urn:iso:std:iso:20022:tech:xsd:semt.003.001.04">
  <ISO:BalForSubAcct>
    <ISO:FinInstrmId>
      <ISO:ISIN>BRIMWLCRI6O9</ISO:ISIN>
      <ISO:Desc>CRI IPCA</ISO:Desc>
    </ISO:FinInstrmId>
    <ISO:FinInstrmAttrbts>
      <ISO:MtrtyDt>2059-05-15</ISO:MtrtyDt>
      <ISO:IsseDt>2021-05-11</ISO:IsseDt>
    </ISO:FinInstrmAttrbts>
  </ISO:BalForSubAcct>
</Document>"""


def test_parse_extrai_ativo_de_renda_fixa_do_xml_btg():
    ativos = parse_ativos(XML)

    assert len(ativos) == 1
    a = ativos[0]
    assert a.tipo == "CRI"
    assert a.isin == "BRIMWLCRI6O9"
    assert a.data_vencimento == "2059-05-15"


# ADR-0005: gate não pode ser em `Desc`. Ativo com ISIN mas sem Desc é real
# (ISIN é a chave forte) e NÃO pode sumir; nó sem nenhum conteúdo identificador
# é não-instrumento → exclusão auditada, nunca drop silencioso.
XML_SEM_DESC_E_LIXO = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:ISO="urn:iso:std:iso:20022:tech:xsd:semt.003.001.04">
  <ISO:BalForSubAcct>
    <ISO:FinInstrmId>
      <ISO:ISIN>BRAAAACRI0A0</ISO:ISIN>
    </ISO:FinInstrmId>
    <ISO:FinInstrmAttrbts>
      <ISO:MtrtyDt>2030-01-01</ISO:MtrtyDt>
    </ISO:FinInstrmAttrbts>
  </ISO:BalForSubAcct>
  <ISO:BalForSubAcct>
    <ISO:FinInstrmId></ISO:FinInstrmId>
  </ISO:BalForSubAcct>
</Document>"""


def test_parse_carteira_emite_isin_sem_desc_e_exclui_no_instrumento():
    result = parse_carteira(XML_SEM_DESC_E_LIXO)

    # ISIN presente sem Desc → instrumento real, não dropado
    assert len(result.instrumentos) == 1
    assert result.instrumentos[0].isin == "BRAAAACRI0A0"
    # nó vazio → excluído COM registro (motivo), nunca silencioso
    assert len(result.excluidos) == 1
    assert result.excluidos[0]["motivo"]


# Estrutura real BTG (docs/btg-formato-real.md): classe vem do código CVM em
# FinInstrmAttrbts/ClssfctnTp/AltrnClssfctn/Id, não do Desc.
XML_CVM = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:ISO="urn:iso:std:iso:20022:tech:xsd:semt.003.001.04">
  <ISO:BalForSubAcct>
    <ISO:FinInstrmId>
      <ISO:ISIN>BRSTNCLF1RK7</ISO:ISIN>
      <ISO:Desc>CRI OPEA IGUATEMI</ISO:Desc>
    </ISO:FinInstrmId>
    <ISO:FinInstrmAttrbts>
      <ISO:ClssfctnTp>
        <ISO:AltrnClssfctn>
          <ISO:Id>196</ISO:Id>
          <ISO:Issr>CVM</ISO:Issr>
        </ISO:AltrnClssfctn>
      </ISO:ClssfctnTp>
      <ISO:MtrtyDt>2030-01-01</ISO:MtrtyDt>
    </ISO:FinInstrmAttrbts>
  </ISO:BalForSubAcct>
  <ISO:BalForAcct>
    <ISO:FinInstrmId>
      <ISO:ISIN>BR0DVOCTF006</ISO:ISIN>
      <ISO:Desc>TESOURO SELIC</ISO:Desc>
    </ISO:FinInstrmId>
    <ISO:FinInstrmAttrbts>
      <ISO:ClssfctnTp>
        <ISO:AltrnClssfctn>
          <ISO:Id>193</ISO:Id>
          <ISO:Issr>CVM</ISO:Issr>
        </ISO:AltrnClssfctn>
      </ISO:ClssfctnTp>
    </ISO:FinInstrmAttrbts>
  </ISO:BalForAcct>
</Document>"""


def test_parse_classe_vem_do_codigo_cvm_nao_do_desc():
    result = parse_carteira(XML_CVM)

    # itera BalForSubAcct E BalForAcct
    assert len(result.instrumentos) == 2
    por_isin = {a.isin: a for a in result.instrumentos}
    # CVM=196 + Desc "CRI ..." → CRI (refino)
    assert por_isin["BRSTNCLF1RK7"].tipo == "CRI"
    assert por_isin["BRSTNCLF1RK7"].data_vencimento == "2030-01-01"
    # CVM=193 → PUBLICO (não "TESOURO" do Desc)
    assert por_isin["BR0DVOCTF006"].tipo == "PUBLICO"


# Holding sem ISIN mas com CNPJ em OthrId (Cd=CNPJ) — chave forte via CNPJ.
XML_OTHRID_CNPJ = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:ISO="urn:iso:std:iso:20022:tech:xsd:semt.003.001.04">
  <ISO:BalForAcct>
    <ISO:FinInstrmId>
      <ISO:OthrId>
        <ISO:Id>23781789000160</ISO:Id>
        <ISO:Tp><ISO:Cd>CNPJ</ISO:Cd></ISO:Tp>
      </ISO:OthrId>
      <ISO:Desc>DGO FIM CP</ISO:Desc>
    </ISO:FinInstrmId>
  </ISO:BalForAcct>
  <ISO:BalForSubAcct>
    <ISO:FinInstrmId>
      <ISO:OthrId>
        <ISO:Id>SHAR</ISO:Id>
        <ISO:Tp><ISO:Prtry>TABELA NIVEL 1</ISO:Prtry></ISO:Tp>
      </ISO:OthrId>
      <ISO:Desc>CARAVELA VC2 FIP C</ISO:Desc>
    </ISO:FinInstrmId>
  </ISO:BalForSubAcct>
</Document>"""


def test_parse_extrai_cnpj_de_othrid_e_ignora_nao_cnpj():
    result = parse_carteira(XML_OTHRID_CNPJ)
    por_desc = {a.tipo if a.tipo else a.cnpj_emissor: a for a in result.instrumentos}
    # self-line do fundo: CNPJ em OthrId → chave forte, sem ISIN
    fund = next(a for a in result.instrumentos if a.cnpj_emissor)
    assert fund.cnpj_emissor == "23781789000160"
    assert fund.isin is None
    # OthrId "SHAR" (não-CNPJ) → ignorado, sem chave forte
    keyless = next(a for a in result.instrumentos if not a.cnpj_emissor)
    assert keyless.isin is None
    assert keyless.cnpj_emissor is None


def test_parse_ativos_e_atalho_para_instrumentos():
    assert parse_ativos(XML_SEM_DESC_E_LIXO) == parse_carteira(
        XML_SEM_DESC_E_LIXO
    ).instrumentos
