from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional, Union

from .sources import CvmCriSource, load_cvm_cri_classe_index

# Zip anual da CVM (informe mensal de CRI). Ver memória reference-cvm-dados-abertos.
_URL_TEMPLATE = (
    "https://dados.cvm.gov.br/dados/SECURIT/DOC/INF_MENSAL_CRI/DADOS/"
    "inf_mensal_cri_{year}.zip"
)


class CvmCriCache:
    """Camada de ops do `CvmCriSource`: baixa o zip anual da CVM, extrai a tabela
    `classe`, cacheia o CSV em disco e reconstrói o índice por ISIN. Refresh por
    TTL (CVM atualiza ~semanalmente) ou `force`. `fetch_zip` é injetável p/ rodar
    sem rede nos testes; em produção baixa via httpx."""

    def __init__(
        self,
        cache_dir: Union[str, Path],
        year: int,
        ttl_days: int = 7,
        fetch_zip: Optional[Callable[[], bytes]] = None,
        url: Optional[str] = None,
    ):
        self._dir = Path(cache_dir)
        self._year = year
        self._ttl = timedelta(days=ttl_days)
        self._url = url or _URL_TEMPLATE.format(year=year)
        self._fetch = fetch_zip or (lambda: _http_get(self._url))
        self._csv = self._dir / f"inf_mensal_cri_classe_{year}.csv"

    def _fresco(self) -> bool:
        if not self._csv.exists():
            return False
        idade = datetime.now() - datetime.fromtimestamp(self._csv.stat().st_mtime)
        return idade < self._ttl

    def classe_csv(self, force: bool = False) -> str:
        """CSV da tabela `classe` (texto decodificado). Serve do cache se fresco;
        senão baixa o zip, extrai, grava e devolve."""
        if not force and self._fresco():
            return self._csv.read_text(encoding="utf-8")
        text = _extrair_classe(self._fetch(), self._year)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._csv.write_text(text, encoding="utf-8")
        return text

    def load_source(self, force: bool = False) -> CvmCriSource:
        return CvmCriSource(load_cvm_cri_classe_index(self.classe_csv(force)))


def _extrair_classe(zip_bytes: bytes, year: int) -> str:
    """Extrai e decodifica o CSV `classe` (latin-1) de dentro do zip da CVM."""
    membro = f"inf_mensal_cri_classe_{year}.csv"
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return zf.read(membro).decode("latin-1")


def _http_get(url: str) -> bytes:
    import httpx

    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.content
