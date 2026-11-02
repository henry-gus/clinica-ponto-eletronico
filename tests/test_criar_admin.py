import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, security
from app.database import Base
from app.services import usuario_service
from scripts import criar_admin

RAIZ = Path(__file__).resolve().parent.parent


def test_promover_funcionario(db, usuario):
    promovido = criar_admin.promover(db, usuario["id"])
    assert promovido.eh_admin and db.get(models.Usuario, usuario["id"]).papel == "admin"


def test_promover_id_inexistente(db):
    with pytest.raises(LookupError):
        criar_admin.promover(db, 999)


def test_criar_administrador_novo(db):
    novo = criar_admin.criar(db, "Dan Chefe", "111.444.777-35", "Gerente", "5555")
    assert novo.papel == "admin" and novo.cpf == "11144477735"
    assert security.verificar_pin("5555", novo.pin_hash)


def test_criar_valida_os_dados(db, usuario):
    with pytest.raises(ValidationError):
        criar_admin.criar(db, "Dan", "111.111.111-11", "Gerente", "5555")  # CPF inválido
    with pytest.raises(ValidationError):
        criar_admin.criar(db, "Dan", "111.444.777-35", "Gerente", "12")  # PIN curto
    with pytest.raises(usuario_service.CpfDuplicado):
        criar_admin.criar(db, "Dan", "529.982.247-25", "Gerente", "5555")  # CPF da Ana


def _preparar_banco(tmp_path):
    caminho = tmp_path / "cli.db"
    engine = create_engine(f"sqlite:///{caminho}")
    Base.metadata.create_all(bind=engine)
    with sessionmaker(bind=engine)() as db:
        db.add(models.Usuario(nome="Ana", cpf="52998224725", cargo="R", pin_hash=security.hash_pin("1234")))
        db.commit()
    return caminho


def _rodar(caminho, *argumentos):
    ambiente = {**os.environ, "SECRET_KEY": "x" * 40, "DATABASE_URL": f"sqlite:///{caminho}"}
    return subprocess.run(
        [sys.executable, "-m", "scripts.criar_admin", *argumentos],
        cwd=RAIZ, env=ambiente, capture_output=True, text=True, timeout=60,
    )


def test_linha_de_comando_promove(tmp_path):
    caminho = _preparar_banco(tmp_path)

    resultado = _rodar(caminho, "--promover", "1")

    assert resultado.returncode == 0, resultado.stderr
    assert "Ana" in resultado.stdout and "administrador" in resultado.stdout
    with sessionmaker(bind=create_engine(f"sqlite:///{caminho}"))() as db:
        assert db.get(models.Usuario, 1).papel == "admin"


def test_linha_de_comando_com_id_inexistente_falha_com_mensagem(tmp_path):
    resultado = _rodar(_preparar_banco(tmp_path), "--promover", "99")
    assert resultado.returncode == 1 and "99" in resultado.stdout


def test_linha_de_comando_migra_banco_antigo(tmp_path):
    """O script também serve para quem atualiza o código com dados da versão anterior."""
    caminho = tmp_path / "antigo.db"
    engine = create_engine(f"sqlite:///{caminho}")
    with engine.begin() as conexao:
        conexao.exec_driver_sql(
            "CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome VARCHAR NOT NULL, cpf VARCHAR(11) NOT NULL UNIQUE, "
            "cargo VARCHAR NOT NULL, carga_horaria_diaria FLOAT NOT NULL, pin_hash VARCHAR NOT NULL)"
        )
        conexao.exec_driver_sql("INSERT INTO usuarios VALUES (1, 'Ana', '52998224725', 'R', 8.0, 'x:y')")

    assert _rodar(caminho, "--promover", "1").returncode == 0
    with sessionmaker(bind=engine)() as db:
        assert db.get(models.Usuario, 1).papel == "admin"
