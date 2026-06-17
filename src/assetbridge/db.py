from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    create_engine,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://ab:ab@db:5432/assetbridge"
)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, future=True)


def get_session():
    """Dependência FastAPI: sessão por request, commit no fim (compartilhada
    por api.py e hitl.py). Em teste é sobrescrita pela sessão com rollback."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    finally:
        s.close()


class Base(DeclarativeBase):
    pass


class IupRecord(Base):
    """Registro autoritativo do IUP (system of record — ver ADR-0001).

    PK surrogate `id` (ADR-0004): a `chave_sintetica` é nullable e dedupa por
    índice único parcial (só quando presente). IUP de HITL fica com chave NULL
    e só é alcançável por surrogate/alias. O `rotulo_semantico` NÃO é coluna —
    é derivado/recalculável on read (Q3), nunca persistido.
    """

    __tablename__ = "iup_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave_sintetica: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    iup: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_iup_registry_chave_sintetica",
            "chave_sintetica",
            unique=True,
            postgresql_where=text("chave_sintetica IS NOT NULL"),
        ),
    )


class LandingRecord(Base):
    """Landing zone imutável (ADR-0006): bruto do custodiante por hash de
    conteúdo. Idempotência de reingestão exata + base de re-extração."""

    __tablename__ = "landing_zone"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    custodiante: Mapped[str] = mapped_column(String, nullable=False)
    raw: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class HitlDecision(Base):
    """Decisão humana persistida (ADR-0007): liga uma pendência ao IUP cunhado.

    Mantém a `pending_resolution` pura (sem IUP); a decisão é pegajosa — re-run
    reaproveita, não re-pergunta nem re-cunha."""

    __tablename__ = "hitl_decision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pending_id: Mapped[int] = mapped_column(
        ForeignKey("pending_resolution.id"), nullable=False, index=True
    )
    iup: Mapped[str] = mapped_column(String, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PositionRecord(Base):
    """Projeção interna de posição (Q2/Q6), time-series por carteira.

    Chaveada por `(id_carteira, custodiante, iup, asof)`; o ingest faz
    delete+replace por `(id_carteira, custodiante, asof)` — espelha a regra de
    dia do Oikos no grão de carteira (Carteira ≠ fundo). `iup` é nullable:
    posição de ativo pendente (HITL) carrega IUP nulo e é backfillada depois."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_carteira: Mapped[str] = mapped_column(String, nullable=False)
    custodiante: Mapped[str] = mapped_column(String, nullable=False)
    iup: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    asof: Mapped[Date] = mapped_column(Date, nullable=False)
    quantidade: Mapped[object] = mapped_column(Numeric(28, 8), nullable=False)
    pu: Mapped[Optional[object]] = mapped_column(Numeric(28, 8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "id_carteira", "custodiante", "iup", "asof", name="uq_position"
        ),
    )


class ExcludedRecord(Base):
    """Exclusão auditada de nó não-instrumento na ingestão (ADR-0005).

    Nada some por `continue` silencioso: linhas de controle/saldo/header/lixo
    ficam aqui com motivo, contáveis e revisáveis."""

    __tablename__ = "excluded_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    custodiante: Mapped[str] = mapped_column(String, nullable=False)
    motivo: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EnrichmentRecord(Base):
    """Característica enriquecida por fonte externa (ADR-0010). NÃO-autoritativa:
    nunca escreve em `iup_registry`; alimenta exibição + aid do HITL.

    Plano de proveniência próprio (≠ landing zone, que é bruto do custodiante):
    guarda `fonte`/`fonte_url`/`confianca`/`query` e o `snapshot` do que foi
    buscado (web não é reproduzível). Atada ao IUP por valor (não FK)."""

    __tablename__ = "enrichment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iup: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    campo: Mapped[str] = mapped_column(String, nullable=False)
    valor: Mapped[str] = mapped_column(String, nullable=False)
    fonte: Mapped[str] = mapped_column(String, nullable=False)  # oficial | web
    fonte_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confianca: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    query: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SourceConfig(Base):
    """Fonte de enriquecimento cadastrada pelo operador (ADR-0011).

    Registry de fontes (api/csv/scraping) que o `_enrichment_source()` lê em
    runtime — operador cadastra fonte-api nova pela UI sem mexer em env/código.
    NÃO-autoritativa (como toda fonte, ADR-0010): só enriquece característica.

    `tipo='api'` liga vivo no grafo (vira `HttpEnrichmentSource` por linha);
    `csv`/`scraping` ficam catalogados mas com execução DEFERIDA (bloqueada por
    amostra, ADR-0010) — visíveis no GET, ignorados na composição viva."""

    __tablename__ = "source_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)  # api | csv | scraping
    base_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    param: Mapped[str] = mapped_column(String, nullable=False, server_default="isin")
    field_map: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    confianca: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.9")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExtractionRecord(Base):
    """Proveniência da extração fuzzy do LLM (ADR-0007). Extração VERSIONADA:
    guarda `modelo` + `confianca` por campo proposto, atado ao bruto por
    `raw_hash` (mesma filosofia da landing zone, ADR-0006).

    Só campos FUZZY entram (classe/série/subordinação); campo forte vem de regex
    determinístico e nunca do LLM. NÃO-autoritativo: alimenta auditoria e o
    reprocessamento em massa quando o modelo melhora — uma extração nova versiona
    (coexiste), não sobrescreve a anterior. `iup` nullable (pode preceder o IUP)."""

    __tablename__ = "extraction_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    iup: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    campo: Mapped[str] = mapped_column(String, nullable=False)
    valor: Mapped[str] = mapped_column(String, nullable=False)
    confianca: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    modelo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # Eixo de versão = modelo: 1 linha por (bruto, campo, modelo). Re-extração
        # com o MESMO modelo sobrescreve (mais recente vence — cobre não-determinismo
        # do LLM e backfill do iup pós-HITL); modelo NOVO versiona (linha nova).
        UniqueConstraint("raw_hash", "campo", "modelo", name="uq_extraction_versao"),
    )


class PendingResolution(Base):
    """Fila de pendências HITL (Q1). Store SEPARADO que NUNCA guarda IUP —
    só a chave provisória, o payload bruto extraído, motivo e status.
    Lastreia GET /pending. `thread_id` (LangGraph) entra depois como coluna."""

    __tablename__ = "pending_resolution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave_provisoria: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="pending"
    )
    # Liga a pendência ao checkpoint do grafo (LangGraph) que pausou no HITL.
    thread_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
