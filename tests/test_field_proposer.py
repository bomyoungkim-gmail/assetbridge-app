import assetbridge.hitl as hitl


def test_sem_env_proposer_e_none(monkeypatch):
    # Default seguro: sem ASSETBRIDGE_OLLAMA_MODEL → None (extract vira passthrough,
    # testes não tocam Ollama).
    monkeypatch.delenv("ASSETBRIDGE_OLLAMA_MODEL", raising=False)
    hitl._field_proposer.cache_clear()
    assert hitl._field_proposer() is None


def test_com_env_constroi_proposer_real_com_modelo_e_base_url(monkeypatch):
    # Gated por env: MODEL setado → build_ollama_proposer com modelo + base_url.
    # build_ollama_proposer é monkeypatchado p/ não tocar langchain_ollama/rede.
    capturado = {}

    def _fake_build(modelo, base_url=None):
        capturado["modelo"] = modelo
        capturado["base_url"] = base_url
        return "PROPOSER"

    monkeypatch.setattr("assetbridge.proposers.build_ollama_proposer", _fake_build)
    monkeypatch.setenv("ASSETBRIDGE_OLLAMA_MODEL", "qwen3:8b")
    monkeypatch.setenv("ASSETBRIDGE_OLLAMA_BASE_URL", "http://ollama:11434")
    hitl._field_proposer.cache_clear()

    assert hitl._field_proposer() == "PROPOSER"
    assert capturado == {"modelo": "qwen3:8b", "base_url": "http://ollama:11434"}
    hitl._field_proposer.cache_clear()
