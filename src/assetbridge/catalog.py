from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import IupRecord, LandingRecord, PositionRecord, get_session

# Acervo (item 4 / browse): superfícies read-only do que já foi injetado —
# IUPs cunhados, projeção de posição e imports na landing zone. Sem mutação;
# visibilidade operacional enquanto não há tela rica (ADR-0009 §5).

router = APIRouter()


@router.get("/assets")
def listar_assets(limit: int = 200, session: Session = Depends(get_session)):
    """IUPs cunhados no registry (autoridade — ADR-0001). Mais recentes primeiro."""
    rows = session.scalars(
        select(IupRecord).order_by(IupRecord.created_at.desc()).limit(limit)
    ).all()
    total = session.scalar(select(func.count()).select_from(IupRecord))
    return {
        "total": total,
        "assets": [
            {
                "id": r.id,
                "iup": r.iup,
                "chave_sintetica": r.chave_sintetica,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/positions")
def listar_positions(limit: int = 200, session: Session = Depends(get_session)):
    """Projeção interna de posição (direção a — Q2/Q6). Time-series por carteira."""
    rows = session.scalars(
        select(PositionRecord)
        .order_by(PositionRecord.asof.desc(), PositionRecord.id.desc())
        .limit(limit)
    ).all()
    total = session.scalar(select(func.count()).select_from(PositionRecord))
    return {
        "total": total,
        "positions": [
            {
                "id": r.id,
                "id_carteira": r.id_carteira,
                "custodiante": r.custodiante,
                "iup": r.iup,
                "asof": r.asof.isoformat() if r.asof else None,
                "quantidade": str(r.quantidade) if r.quantidade is not None else None,
                "pu": str(r.pu) if r.pu is not None else None,
            }
            for r in rows
        ],
    }


@router.get("/imports")
def listar_imports(limit: int = 200, session: Session = Depends(get_session)):
    """Imports na landing zone (bruto imutável por hash — ADR-0006). Nunca
    devolve os bytes brutos, só os metadados de lineage."""
    rows = session.scalars(
        select(LandingRecord).order_by(LandingRecord.created_at.desc()).limit(limit)
    ).all()
    total = session.scalar(select(func.count()).select_from(LandingRecord))
    return {
        "total": total,
        "imports": [
            {
                "id": r.id,
                "custodiante": r.custodiante,
                "content_hash": r.content_hash,
                "tamanho_bytes": len(r.raw) if r.raw is not None else 0,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
