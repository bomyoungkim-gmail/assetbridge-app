from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import LandingRecord


def store_raw(session: Session, custodiante: str, raw: bytes) -> LandingRecord:
    """Guarda o bruto na landing zone por hash de conteúdo (ADR-0006).

    Idempotente: bytes idênticos → no-op, devolve o registro existente.
    É o file-hash (grão de arquivo); a âncora sub-arquivo
    `(extractor_version, source_locator)` é fatia futura.
    """
    content_hash = hashlib.sha256(raw).hexdigest()
    existente = session.scalars(
        select(LandingRecord).where(LandingRecord.content_hash == content_hash)
    ).first()
    if existente is not None:
        return existente

    rec = LandingRecord(content_hash=content_hash, custodiante=custodiante, raw=raw)
    session.add(rec)
    session.flush()
    return rec
