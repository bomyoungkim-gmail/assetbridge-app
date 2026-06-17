from __future__ import annotations

from typing import Optional, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from .enrichment import EnrichmentSource, enrich_route
from .extraction import (
    FieldProposal,
    FieldProposer,
    montar_identidade,
    registrar_extracao,
)
from .identity import AssetIdentity
from .registry import IupRegistry

# Orquestração agêntica (ADR-0010): grafo extract → resolve_identity → enrich →
# deliver. Nesta fatia os nós envolvem as funções determinísticas que já
# existem; LLM/extração de texto caótico entra por fatia (ADR-0002).


class IngestState(TypedDict, total=False):
    raw: str
    ativo: AssetIdentity
    proposals: list[FieldProposal]  # proposals fuzzy do LLM (proveniência, ADR-0007)
    decisao: AssetIdentity  # identidade resolvida pelo humano (resume do HITL)
    iup: Optional[str]
    pending: bool
    enriched: list[str]


def build_graph(
    session: Session,
    source: EnrichmentSource,
    proposer: Optional[FieldProposer] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
):
    """Compila o grafo de ingestão com sessão + portas injetadas.

    `source` = porta `EnrichmentSource`; `proposer` = porta do extrator fuzzy
    (LLM). Com `checkpointer`, o grafo ganha HITL no fluxo: pausa
    (`interrupt_before` em `hitl`) antes de gravar o IUP de itens ambíguos,
    persiste o estado por `thread_id` e retoma com a decisão humana (ADR-0007).
    `enrich` é best-effort: nunca derruba a entrega (ADR-0010)."""
    registry = IupRegistry(session)

    def extract(state: IngestState) -> dict:
        # Identidade já estruturada (BTG direção b) → passthrough. Texto bruto
        # não-BTG → Camada 1 (regex + LLM proposer), fronteira do ADR-0007.
        if state.get("ativo") is not None:
            return {}
        raw = state.get("raw")
        if raw is None or proposer is None:
            return {}
        # Chama o LLM UMA vez; guarda as proposals p/ a proveniência no deliver.
        proposals = proposer.propor(raw)
        return {"ativo": montar_identidade(raw, proposals), "proposals": proposals}

    def resolve_identity(state: IngestState, config) -> dict:
        # Auto-cunha só em chave forte; ambíguo → pending (ADR-0007). O
        # thread_id do checkpoint vira coluna da pendência (rastreio do HITL).
        thread_id = (config or {}).get("configurable", {}).get("thread_id")
        res = registry.resolve(state["ativo"], thread_id=thread_id)
        return {"iup": res.iup, "pending": res.pending}

    def hitl(state: IngestState) -> dict:
        # Só executa após o humano decidir (resume). `interrupt_before` garante
        # que o grafo PAUSA aqui antes de cunhar qualquer IUP de item ambíguo.
        decisao = state.get("decisao")
        if decisao is None:
            return {"pending": True}
        res = registry.cunhar_hitl(decisao)
        return {"iup": res.iup, "pending": False}

    def enrich(state: IngestState) -> dict:
        # Turbinador opcional: falha da fonte → segue sem enriquecimento.
        try:
            results = source.buscar(state["ativo"])
        except Exception:
            return {"enriched": []}
        gravados = enrich_route(
            session, state["ativo"], state.get("iup"), results
        )
        return {"enriched": gravados}

    def deliver(state: IngestState) -> dict:
        # Persiste a proveniência da extração versionada (ADR-0007), atada ao IUP
        # cunhado — base do reprocessamento em massa quando o modelo melhora.
        # Só no path de texto bruto (proposals presentes); BTG estruturado não tem.
        raw = state.get("raw")
        proposals = state.get("proposals")
        if raw and proposals:
            registrar_extracao(session, raw, state.get("iup"), proposals)
        # Ponto de entrega (posição + IUP + enrichment) ao Oikos — direção a.
        return {}

    def _rota(state: IngestState) -> str:
        return "hitl" if state.get("pending") else "enrich"

    g = StateGraph(IngestState)
    g.add_node("extract", extract)
    g.add_node("resolve_identity", resolve_identity)
    g.add_node("hitl", hitl)
    g.add_node("enrich", enrich)
    g.add_node("deliver", deliver)
    g.add_edge(START, "extract")
    g.add_edge("extract", "resolve_identity")
    g.add_conditional_edges(
        "resolve_identity", _rota, {"hitl": "hitl", "enrich": "enrich"}
    )
    g.add_edge("hitl", "enrich")
    g.add_edge("enrich", "deliver")
    g.add_edge("deliver", END)

    # interrupt_before só faz sentido com checkpointer (estado durável p/ retomar).
    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer, interrupt_before=["hitl"])
    return g.compile()
