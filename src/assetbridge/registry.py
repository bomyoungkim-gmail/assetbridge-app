from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import IupRecord, PendingResolution
from .identity import (
    AssetIdentity,
    Resolution,
    chave_sintetica,
    rotulo_semantico,
    tem_chave_forte,
)


class IupRegistry:
    """Autoridade única do IUP. Resolve uma identidade estruturada para o IUP
    canônico (surrogate opaco imutável), cunhando se inédito. Ver ADR-0001."""

    def __init__(self, session: Session):
        self._session = session

    def resolve(self, ativo: AssetIdentity, thread_id: str | None = None) -> Resolution:
        # Gatilho HITL conservador: sem chave forte não cunha IUP (ADR-0007).
        if not tem_chave_forte(ativo):
            motivo = "sem chave forte (ISIN ou CNPJ)"
            self._enqueue_pending(ativo, motivo, thread_id)
            return Resolution(pending=True, motivo=motivo)

        chave = chave_sintetica(ativo)

        # PK é surrogate (ADR-0004): lookup pela chave forte, não por PK.
        existente = self._session.scalars(
            select(IupRecord).where(IupRecord.chave_sintetica == chave)
        ).first()
        # Rótulo é sempre recalculado do ativo em mãos (Q3): nunca persistido.
        rotulo = rotulo_semantico(ativo)
        if existente is not None:
            return Resolution(novo=False, iup=existente.iup, rotulo_semantico=rotulo)

        iup = f"IUP-{uuid.uuid4().hex}"
        self._session.add(IupRecord(chave_sintetica=chave, iup=iup))
        self._session.flush()
        return Resolution(novo=True, iup=iup, rotulo_semantico=rotulo)

    def cunhar_hitl(self, ativo: AssetIdentity) -> Resolution:
        """Cunha IUP a partir de decisão humana (HITL).

        Se a identidade decidida tem chave forte, usa-a (dedupe normal pelo
        unique parcial); senão cunha surrogate com `chave_sintetica=NULL`
        (ADR-0004): o IUP de HITL só é alcançável por surrogate/alias."""
        rotulo = rotulo_semantico(ativo)
        chave = chave_sintetica(ativo) if tem_chave_forte(ativo) else None

        if chave is not None:
            existente = self._session.scalars(
                select(IupRecord).where(IupRecord.chave_sintetica == chave)
            ).first()
            if existente is not None:
                return Resolution(
                    novo=False, iup=existente.iup, rotulo_semantico=rotulo
                )

        iup = f"IUP-{uuid.uuid4().hex}"
        self._session.add(IupRecord(chave_sintetica=chave, iup=iup))
        self._session.flush()
        return Resolution(novo=True, iup=iup, rotulo_semantico=rotulo)

    def _enqueue_pending(
        self, ativo: AssetIdentity, motivo: str, thread_id: str | None = None
    ) -> None:
        """Persiste a pendência na fila HITL (Q1). Dedup por chave provisória:
        re-resolver o mesmo item não duplica a pendência aberta. Nunca grava IUP."""
        chave = chave_sintetica(ativo)
        ja_aberta = self._session.scalars(
            select(PendingResolution).where(
                PendingResolution.chave_provisoria == chave,
                PendingResolution.status == "pending",
            )
        ).first()
        if ja_aberta is not None:
            return

        self._session.add(
            PendingResolution(
                chave_provisoria=chave,
                payload=ativo.model_dump(),
                motivo=motivo,
                status="pending",
                thread_id=thread_id,
            )
        )
        self._session.flush()
