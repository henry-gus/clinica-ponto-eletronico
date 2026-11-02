import os

os.environ.setdefault("SECRET_KEY", "chave-de-teste-com-mais-de-32-caracteres-ok")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("EMPRESA_NOME", "Clínica Exemplo Ltda")
os.environ.setdefault("EMPRESA_CNPJ", "11.222.333/0001-81")
os.environ.setdefault("EMPRESA_ENDERECO", "Rua das Flores, 100, Centro, Belo Horizonte - MG")

from datetime import date, datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import config, limitador, models, security  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import extrato_service  # noqa: E402
from scripts.gerar_certificado_teste import gerar  # noqa: E402

PIN_ADMIN = "9999"
PIN_ANA = "1234"
PERIODO = "inicio=2026-10-01&fim=2026-10-31"


def utc(mes, dia, hora, minuto=0):
    """Instante em UTC. O horário local da clínica é UTC-3."""
    return datetime(2026, mes, dia, hora, minuto, tzinfo=timezone.utc)


def semear(db, usuario_id, momentos):
    db.add_all(models.Marcacao(usuario_id=usuario_id, momento=m) for m in momentos)
    db.commit()


def entrar(client, usuario, pin=PIN_ANA):
    """Faz login e devolve o header Authorization."""
    resposta = client.post("/auth/login", json={"usuario_id": usuario["id"], "pin": pin})
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['token']}"}


def novo_usuario(client, cab_admin, nome, cpf, pin="4321", **extras):
    resposta = client.post(
        "/usuarios/",
        json={"nome": nome, "cpf": cpf, "cargo": "Fisioterapeuta", "carga_horaria_diaria": 8, "pin": pin, **extras},
        headers=cab_admin,
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


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


@pytest.fixture(autouse=True)
def zerar_limitador():
    """O limite de tentativas fica na memória do processo: começa limpo em cada teste."""
    limitador.resetar_tudo()


@pytest.fixture
def hoje_em_novembro(monkeypatch):
    """Fixa 'hoje' em 15/11/2026: outubro inteiro já passou, então as faltas de outubro são determinísticas."""
    monkeypatch.setattr(extrato_service, "hoje_local", lambda: date(2026, 11, 15))


@pytest.fixture
def admin(db):
    """Administrador criado direto no banco (como o script criar_admin faz)."""
    pessoa = models.Usuario(
        nome="Carla Admin", cpf="39053344705", cargo="Administradora",
        pin_hash=security.hash_pin(PIN_ADMIN), papel="admin",
    )
    db.add(pessoa)
    db.commit()
    return {"id": pessoa.id, "nome": pessoa.nome}


@pytest.fixture
def cab_admin(client, admin):
    return entrar(client, admin, PIN_ADMIN)


@pytest.fixture
def usuario(client, cab_admin):
    """Ana Souza, funcionária (segunda a sexta, 8h por dia), cadastrada pelo administrador."""
    return novo_usuario(client, cab_admin, "Ana Souza", "529.982.247-25", pin=PIN_ANA, cargo="Recepcionista")


@pytest.fixture
def cab_ana(client, usuario):
    return entrar(client, usuario)


@pytest.fixture
def certificado(tmp_path, monkeypatch):
    caminho = tmp_path / "teste.p12"
    gerar(str(caminho), "senha-teste")
    monkeypatch.setattr(config, "CERT_P12_PATH", str(caminho))
    monkeypatch.setattr(config, "CERT_P12_SENHA", "senha-teste")
