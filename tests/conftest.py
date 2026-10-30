import os

os.environ.setdefault("SECRET_KEY", "chave-de-teste-com-mais-de-32-caracteres-ok")
os.environ.setdefault("ADMIN_TOKEN", "admin-teste")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("EMPRESA_NOME", "Clínica Exemplo Ltda")
os.environ.setdefault("EMPRESA_CNPJ", "11.222.333/0001-81")
os.environ.setdefault("EMPRESA_ENDERECO", "Rua das Flores, 100, Centro, Belo Horizonte - MG")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

ADMIN = {"X-Admin-Token": "admin-teste"}


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessao = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield sessao
    finally:
        sessao.close()


@pytest.fixture
def client(db):
    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def usuario(client):
    resposta = client.post(
        "/usuarios/",
        json={
            "nome": "Ana Souza",
            "cpf": "529.982.247-25",
            "cargo": "Recepcionista",
            "carga_horaria_diaria": 8,
            "pin": "1234",
        },
        headers=ADMIN,
    )
    assert resposta.status_code == 200
    return resposta.json()
