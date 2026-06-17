from assetbridge.cvm import classificar


def test_196_refina_para_classe_fina_por_desc():
    # CVM=196 é renda fixa privada; Desc refina CRI/CDB/LF (ADR-0005).
    assert classificar("196", "CRI OPEA LASTRO X") == "CRI"
    assert classificar("196", "CDB BANCO ITAU") == "CDB"
    assert classificar("196", "LF SUBORDINADA") == "LF"


def test_codigos_coarse_mapeiam_classe():
    assert classificar("193", "LFT REF") == "PUBLICO"
    assert classificar("197", "CSHG LOGISTICA FII") == "FUNDO"
    assert classificar("37", "BPAC11") == "LISTADO"


def test_sem_cvm_cai_no_fallback_desc():
    # cota self do fundo / ETF não traz ClssfctnTp → fallback pelo Desc
    assert classificar("", "BOVA11 ETF") == "BOVA11"
    assert classificar("", "") == ""
