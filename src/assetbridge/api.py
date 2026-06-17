from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import Depends, FastAPI, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import catalog, hitl, source_registry
from .cvm import classificar
from .db import Base, engine, get_session
from .identity import AssetIdentity
from .ingest import ingest_btg
from .registry import IupRegistry


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Schema via create_all (idempotente, checkfirst) — sem Alembic ainda
    # (CONTEXT.md). Testes criam o schema pelo conftest; aqui é p/ o serviço real.
    Base.metadata.create_all(engine)
    # Aquece o checkpointer durável (cria as tabelas de checkpoint). Só no
    # serviço real — os testes não disparam o lifespan (TestClient sem `with`).
    hitl._checkpointer()
    yield


app = FastAPI(title="AssetBridge", lifespan=lifespan)
app.include_router(hitl.router)
app.include_router(source_registry.router)
app.include_router(catalog.router)


def _jsonable(value):
    if is_dataclass(value):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


class ResolveIupRequest(BaseModel):
    """Contrato de integração com o Oikos (ADR-0008 / ADR-0019 do Oikos).

    O consumidor manda campos ESTRUTURADOS de identidade — nunca o XML bruto.
    A classe (`tipo`) é derivada da classificação CVM (refino por descrição),
    nunca de `description.split()` (ADR-0005). `data_vencimento` não vem nesse
    contrato: para BTG o ISIN é a chave forte e basta para resolver."""

    isin: Optional[str] = None
    cnpj: Optional[str] = None
    description: Optional[str] = None
    cvm_classification: Optional[str] = None


@app.post("/resolve-iup")
def resolve_iup(req: ResolveIupRequest, session: Session = Depends(get_session)):
    ativo = AssetIdentity(
        tipo=classificar(req.cvm_classification or "", req.description or ""),
        data_vencimento="",
        isin=req.isin,
        cnpj_emissor=req.cnpj,
    )
    res = IupRegistry(session).resolve(ativo)
    return {
        # `status` é o campo do contrato (resolved|pending); os demais são
        # detalhe rico do standalone — superset compatível.
        "status": "pending" if res.pending else "resolved",
        "iup": res.iup,
        "rotulo_semantico": res.rotulo_semantico,
        "novo": res.novo,
        "pending": res.pending,
        "motivo": res.motivo,
    }


@app.post("/ingest")
async def ingest(
    request: Request,
    x_file_name: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    """Ingestão de XML BTG (ISO 20022 semt.003.001.04) — modo standalone (direção a).

    Ciclo completo (ADR-0005/0006/0008, ver `ingest_btg`): bruto na landing zone
    (no-op se duplicado), roteamento três-vias das posições (chave forte → cunha
    IUP; fraca → HITL; sintética → exclusão auditada) e projeção de posição com
    delete+replace. Retorna os contadores do ciclo + a posição parseada."""
    xml = await request.body()
    res = ingest_btg(session, xml)
    return {
        "source": "btg_position_xml",
        "file_name": x_file_name,
        "status": res.status,
        "id_carteira": res.id_carteira,
        "asof": res.asof,
        "posicoes": res.posicoes,
        "pendencias": res.pendencias,
        "excluidos": res.excluidos,
        "parsed": _jsonable(res.parsed),
    }
