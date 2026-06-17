from __future__ import annotations

import os
from datetime import date
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import DATABASE_URL, HitlDecision, PendingResolution, get_session
from .enrichment import EnrichmentResult
from .graph import build_graph
from .identity import AssetIdentity, rotulo_semantico
from .registry import IupRegistry

router = APIRouter()

# URI psycopg cru p/ o checkpointer (sem o dialeto +psycopg do SQLAlchemy).
_DB_URI = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")


@lru_cache(maxsize=1)
def _checkpointer() -> BaseCheckpointSaver:
    """Checkpointer durável do app (Postgres — system of record, ADR-0001).

    Mantém o estado dos grafos pausados no HITL entre requests E entre restarts
    do processo. Construído lazy (singleton) p/ não abrir conexão no import nem
    nos testes (que injetam `MemorySaver` via override de `get_graph`)."""
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        _DB_URI,
        max_size=10,
        kwargs={"autocommit": True, "row_factory": dict_row},
        open=True,
    )
    cp = PostgresSaver(pool)
    cp.setup()  # cria as tabelas de checkpoint (idempotente)
    return cp


class _NullSource:
    """Fonte de enriquecimento neutra p/ o grafo do HITL (o resume foca em
    cunhar o IUP; enriquecimento real entra pela porta quando configurado)."""

    def buscar(self, ativo: AssetIdentity) -> list[EnrichmentResult]:
        return []


@lru_cache(maxsize=1)
def _enrichment_source():
    """Fonte de enriquecimento do app. Config-gated: com
    `ASSETBRIDGE_CVM_CRI_CACHE_DIR` setado, usa o `CvmCriSource` vivo (baixa/cacheia
    o zip da CVM via `CvmCriCache`); sem env → `_NullSource` (default seguro — sem
    rede em teste). Refresh in-process (re-ler após TTL sem restart) é deferido."""
    cache_dir = os.environ.get("ASSETBRIDGE_CVM_CRI_CACHE_DIR")
    if not cache_dir:
        return _NullSource()
    from .cvm_ops import CvmCriCache

    ttl_days = int(os.environ.get("ASSETBRIDGE_CVM_CRI_TTL_DAYS", "7"))
    return CvmCriCache(
        cache_dir, year=date.today().year, ttl_days=ttl_days
    ).load_source()


@lru_cache(maxsize=1)
def _field_proposer():
    """Extrator fuzzy (LLM) do app. Config-gated, mesmo padrão do
    `_enrichment_source`: com `ASSETBRIDGE_OLLAMA_MODEL` setado, liga o
    `OllamaProposer` real (cliente `ChatOllama` → servidor Ollama em
    `ASSETBRIDGE_OLLAMA_BASE_URL`); sem env → `None` (default seguro — o nó
    `extract` vira passthrough, sem LLM, e os testes não tocam Ollama).

    Construção lazy: `build_ollama_proposer` só importa `langchain_ollama` quando
    chamado. Ativar exige o serviço `ollama` no ar (profile `llm` do compose)."""
    modelo = os.environ.get("ASSETBRIDGE_OLLAMA_MODEL")
    if not modelo:
        return None
    from .proposers import build_ollama_proposer

    base_url = os.environ.get("ASSETBRIDGE_OLLAMA_BASE_URL")
    return build_ollama_proposer(modelo=modelo, base_url=base_url)


def get_graph(session: Session = Depends(get_session)):
    """Grafo do app com o checkpointer durável compartilhado — permite retomar um
    thread pausado no `interrupt_before(["hitl"])` de qualquer request/processo.

    Fonte de enriquecimento = composição (ADR-0011): a fonte estática gated por
    env (CVM CRI) + as fontes-`api` cadastradas no registry (lidas do DB por
    request, podem mudar sem restart), encadeadas best-effort. O extrator fuzzy
    (LLM) entra gated por env (`_field_proposer`); sem env, o `extract` é
    passthrough (só identidade já estruturada)."""
    from .source_registry import ChainEnrichmentSource, build_db_sources

    fonte = ChainEnrichmentSource([_enrichment_source(), *build_db_sources(session)])
    return build_graph(
        session, fonte, proposer=_field_proposer(), checkpointer=_checkpointer()
    )


def _resume_hitl(graph, thread_id: str, decisao: AssetIdentity) -> str:
    """Injeta a decisão humana no estado do thread pausado e retoma o grafo
    (hitl → enrich → deliver). Devolve o IUP cunhado pelo nó `hitl`."""
    cfg = {"configurable": {"thread_id": thread_id}}
    graph.update_state(cfg, {"decisao": decisao})
    out = graph.invoke(None, cfg)
    return out["iup"]


@router.get("/pending")
def listar_pendencias(session: Session = Depends(get_session)):
    """Fila HITL (CONTEXT/Q1): pendências abertas aguardando decisão humana."""
    rows = session.scalars(
        select(PendingResolution).where(PendingResolution.status == "pending")
    ).all()
    return {
        "pending": [
            {
                "id": r.id,
                "chave_provisoria": r.chave_provisoria,
                "motivo": r.motivo,
                "payload": r.payload,
            }
            for r in rows
        ]
    }


@router.get("/status/{thread_id}")
def status_thread(thread_id: str, session: Session = Depends(get_session)):
    """Poll do contrato sync/pending (ADR-0008): o consumidor pergunta pelo
    `thread_id` e backfilla o IUP quando resolvido. Nunca trava — `pending` é
    resposta legítima (IUP nulo), não erro."""
    pend = session.scalars(
        select(PendingResolution).where(PendingResolution.thread_id == thread_id)
    ).first()
    if pend is None:
        raise HTTPException(status_code=404, detail="thread_id desconhecido")
    if pend.status == "resolved":
        dec = session.scalars(
            select(HitlDecision).where(HitlDecision.pending_id == pend.id)
        ).first()
        return {"status": "resolved", "iup": dec.iup if dec else None}
    return {"status": pend.status, "iup": None}


@router.post("/pending/{pending_id}/decision")
def decidir(
    pending_id: int,
    ativo: AssetIdentity,
    session: Session = Depends(get_session),
    graph=Depends(get_graph),
):
    """Decisão humana sobre uma pendência: cunha o IUP e resolve a fila.

    Pegajosa (ADR-0007): se já houver decisão, devolve a mesma — não re-cunha.
    Se a pendência veio do grafo (tem `thread_id`), RETOMA o thread pausado no
    HITL (hitl → enrich → deliver); senão cunha direto via `cunhar_hitl`."""
    pend = session.get(PendingResolution, pending_id)
    if pend is None:
        raise HTTPException(status_code=404, detail="pendência não encontrada")

    ja_decidida = session.scalars(
        select(HitlDecision).where(HitlDecision.pending_id == pending_id)
    ).first()
    if ja_decidida is not None:
        return {"iup": ja_decidida.iup, "novo": False, "status": pend.status}

    if pend.thread_id:
        iup = _resume_hitl(graph, pend.thread_id, ativo)
    else:
        iup = IupRegistry(session).cunhar_hitl(ativo).iup

    pend.status = "resolved"
    session.add(HitlDecision(pending_id=pending_id, iup=iup))
    session.flush()
    return {
        "iup": iup,
        "rotulo_semantico": rotulo_semantico(ativo),
        "status": pend.status,
    }
