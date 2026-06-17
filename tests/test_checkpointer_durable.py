import uuid

from langgraph.checkpoint.postgres import PostgresSaver

from assetbridge.db import DATABASE_URL
from assetbridge.graph import build_graph
from assetbridge.identity import AssetIdentity

# URI psycopg cru (sem o dialeto +psycopg do SQLAlchemy).
_URI = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")


class _NoSource:
    def buscar(self, ativo):
        return []


def test_postgressaver_persiste_estado_pausado_entre_instancias(session):
    # Prova a durabilidade: uma instância pausa no HITL; OUTRA instância
    # (simula novo processo após restart) lê o estado e retoma. thread_id único
    # → as linhas de checkpoint commitadas não colidem nem poluem outros testes.
    tid = "pg-" + uuid.uuid4().hex
    cfg = {"configurable": {"thread_id": tid}}
    ambiguo = AssetIdentity(tipo="CRI", data_vencimento="2059-05-15")

    with PostgresSaver.from_conn_string(_URI) as cp1:
        cp1.setup()
        build_graph(session, _NoSource(), checkpointer=cp1).invoke(
            {"ativo": ambiguo}, cfg
        )

    # Nova instância, conexão nova: o estado pausado sobrevive.
    with PostgresSaver.from_conn_string(_URI) as cp2:
        g2 = build_graph(session, _NoSource(), checkpointer=cp2)
        assert g2.get_state(cfg).next == ("hitl",)

        decidido = AssetIdentity(
            tipo="CRI",
            data_vencimento="2059-05-15",
            cnpj_emissor="11222333000181",
            serie_emissao="13S",
        )
        g2.update_state(cfg, {"decisao": decidido})
        out = g2.invoke(None, cfg)

    assert out["iup"].startswith("IUP-")
