from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import PendingResolution


def enqueue_pending(
    session: Session,
    chave_provisoria: str,
    payload: dict,
    motivo: str,
    thread_id: Optional[str] = None,
) -> Optional[PendingResolution]:
    """Enfileira uma pendência HITL única (fila do Q1). Mecanismo ÚNICO de
    enqueue — `registry` (sem chave forte) e `enrichment` (campo forte sugerido
    pela web) delegam aqui. Dedup por `(chave_provisoria, motivo)` entre as
    abertas: re-resolver o mesmo item com o mesmo motivo não duplica a pendência.
    Nunca grava IUP. Devolve a linha criada, ou `None` se já havia aberta."""
    ja = session.scalars(
        select(PendingResolution).where(
            PendingResolution.chave_provisoria == chave_provisoria,
            PendingResolution.status == "pending",
            PendingResolution.motivo == motivo,
        )
    ).first()
    if ja is not None:
        return None
    pend = PendingResolution(
        chave_provisoria=chave_provisoria,
        payload=payload,
        motivo=motivo,
        status="pending",
        thread_id=thread_id,
    )
    session.add(pend)
    session.flush()
    return pend
