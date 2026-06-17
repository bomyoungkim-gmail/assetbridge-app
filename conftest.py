import warnings

# Deprecation de terceiros (starlette.testclient usa httpx legado), emitida no
# import de fastapi.testclient — fora do nosso controle; suprimida antes do
# import que a dispara para manter a suite com zero warnings.
warnings.filterwarnings(
    "ignore",
    message=r"Using `httpx` with `starlette\.testclient` is deprecated",
)

# Dispara o import de fastapi.testclient aqui, sob o filtro acima, antes da
# coleta (onde o catch_warnings do pytest sobreporia o filtro runtime).
from fastapi.testclient import TestClient  # noqa: E402,F401

import pytest
from sqlalchemy.orm import Session

from assetbridge.db import Base, engine
from assetbridge.registry import IupRegistry


@pytest.fixture(scope="session", autouse=True)
def _schema():
    # DB do container é efêmero; cria o schema (sem drop).
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def session():
    # Isolamento por rollback de transação — sem TRUNCATE/DELETE/DROP.
    conn = engine.connect()
    trans = conn.begin()
    s = Session(bind=conn)
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def registry(session):
    return IupRegistry(session)
