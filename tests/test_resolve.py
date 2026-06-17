from assetbridge.identity import AssetIdentity


def _cri(**over):
    base = dict(
        tipo="CRI",
        cnpj_emissor="12345678000199",
        data_vencimento="2059-05-15",
        serie_emissao="13S",
        is_subordinado=False,
    )
    base.update(over)
    return AssetIdentity(**base)


def test_ativo_estruturado_inedito_cunha_iup_novo(registry):
    ativo = AssetIdentity(
        tipo="CRI",
        cnpj_emissor="12345678000199",
        data_vencimento="2059-05-15",
        serie_emissao="13S",
        is_subordinado=False,
    )

    res = registry.resolve(ativo)

    assert res.novo is True
    assert res.iup.startswith("IUP-")
    # IUP é surrogate opaco: não carrega os dados de identidade.
    assert "12345678000199" not in res.iup


def test_reingestao_identica_devolve_mesmo_iup(registry):
    r1 = registry.resolve(_cri())
    r2 = registry.resolve(_cri())

    assert r1.novo is True
    assert r2.novo is False
    assert r2.iup == r1.iup


def test_rotulo_semantico_cri_derivado_por_classe(registry):
    res = registry.resolve(
        _cri(cnpj_emissor="11222333000181", serie_emissao="13S",
             data_vencimento="2059-05-15")
    )

    assert res.rotulo_semantico == "IUP-CRI-11222333000181-SERIE13S-2059-05-15"
    # rótulo é derivado/legível; nunca é a chave canônica opaca.
    assert res.rotulo_semantico != res.iup


def test_rotulo_btg_degrada_para_isin_sem_cnpj(registry):
    # BTG só traz ISIN/classe/venc (ADR-0003): rótulo degrada para ISIN,
    # nunca emite "None" no lugar de CNPJ/série ausentes.
    res = registry.resolve(
        AssetIdentity(tipo="CRI", data_vencimento="2059-05-15", isin="BRIMWLCRI6O9")
    )

    assert res.rotulo_semantico == "IUP-CRI-BRIMWLCRI6O9-2059-05-15"
    assert "None" not in res.rotulo_semantico


def test_registro_pk_surrogate_chave_nullable_sem_rotulo():
    # ADR-0004: PK surrogate, chave_sintetica nullable; rótulo não persistido (Q3).
    from assetbridge.db import IupRecord

    cols = IupRecord.__table__.columns
    assert cols["id"].primary_key is True
    assert cols["chave_sintetica"].primary_key is False
    assert cols["chave_sintetica"].nullable is True
    assert "rotulo_semantico" not in cols


def test_serie_diferente_gera_iup_distinto(registry):
    a = registry.resolve(_cri(serie_emissao="13S"))
    b = registry.resolve(_cri(serie_emissao="14S"))

    assert b.novo is True
    assert b.iup != a.iup


def test_chave_forte_incompleta_vai_para_hitl(registry):
    res = registry.resolve(_cri(cnpj_emissor=None))

    assert res.pending is True
    assert res.iup is None
    assert res.novo is False


def test_pending_persiste_na_fila_e_e_idempotente(registry, session):
    # Q1: sem chave forte → vai para pending_resolution (lastreia GET /pending).
    # Re-resolver o mesmo item não duplica a pendência (dedup por chave provisória).
    from sqlalchemy import func, select

    from assetbridge.db import PendingResolution

    registry.resolve(_cri(cnpj_emissor=None))
    registry.resolve(_cri(cnpj_emissor=None))

    abertas = session.scalar(
        select(func.count())
        .select_from(PendingResolution)
        .where(PendingResolution.status == "pending")
    )
    assert abertas == 1


def test_pending_nunca_guarda_iup(registry, session):
    from sqlalchemy import select

    from assetbridge.db import PendingResolution

    registry.resolve(_cri(cnpj_emissor=None))
    row = session.scalars(select(PendingResolution)).first()

    assert row is not None
    assert not hasattr(row, "iup")
    assert row.motivo is not None


def test_ativo_btg_com_isin_resolve_e_e_idempotente(registry):
    def mk():
        return AssetIdentity(
            tipo="CRI", data_vencimento="2059-05-15", isin="BRIMWLCRI6O9"
        )

    a = registry.resolve(mk())
    b = registry.resolve(mk())

    assert a.pending is False
    assert a.novo is True
    assert a.iup.startswith("IUP-")
    # idempotência pela chave forte ISIN
    assert b.novo is False
    assert b.iup == a.iup


def test_lf_subordinada_nao_funde_com_senior(registry):
    senior = registry.resolve(
        AssetIdentity(
            tipo="LF",
            cnpj_emissor="60746948000112",
            data_vencimento="2030-01-15",
            serie_emissao=None,
            is_subordinado=False,
        )
    )
    sub = registry.resolve(
        AssetIdentity(
            tipo="LF",
            cnpj_emissor="60746948000112",
            data_vencimento="2030-01-15",
            serie_emissao=None,
            is_subordinado=True,
        )
    )

    assert sub.novo is True
    assert sub.iup != senior.iup
