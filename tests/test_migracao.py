from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migracoes import migrar_esquema


def _banco_da_versao_anterior(tmp_path):
    """Tabela `usuarios` como era antes de existirem perfil, escala e data de início."""
    engine = create_engine(f"sqlite:///{tmp_path / 'antigo.db'}")
    with engine.begin() as conexao:
        conexao.execute(text(
            "CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome VARCHAR NOT NULL, cpf VARCHAR(11) NOT NULL UNIQUE, "
            "cargo VARCHAR NOT NULL, carga_horaria_diaria FLOAT NOT NULL, pin_hash VARCHAR NOT NULL)"
        ))
        conexao.execute(text(
            "INSERT INTO usuarios (nome, cpf, cargo, carga_horaria_diaria, pin_hash) "
            "VALUES ('Ana Souza', '52998224725', 'Recepcionista', 8.0, 'x:y')"
        ))
    return engine


def test_acrescenta_as_colunas_novas_sem_perder_os_dados(tmp_path):
    engine = _banco_da_versao_anterior(tmp_path)

    acrescentadas = migrar_esquema(engine)
    Base.metadata.create_all(bind=engine)  # cria a tabela de ausências

    assert sorted(acrescentadas) == ["usuarios.data_inicio", "usuarios.dias_trabalho", "usuarios.papel"]
    assert "ausencias" in inspect(engine).get_table_names()
    with sessionmaker(bind=engine)() as db:
        ana = db.query(models.Usuario).one()
        assert (ana.nome, ana.papel, ana.dias_trabalho_lista, ana.data_inicio) == ("Ana Souza", "funcionario", [0, 1, 2, 3, 4], None)
        assert not ana.eh_admin


def test_rodar_de_novo_nao_faz_nada(tmp_path):
    engine = _banco_da_versao_anterior(tmp_path)
    migrar_esquema(engine)
    assert migrar_esquema(engine) == []


def test_banco_novo_ja_esta_em_dia(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'novo.db'}")
    Base.metadata.create_all(bind=engine)
    assert migrar_esquema(engine) == []


def test_banco_vazio_nao_quebra(tmp_path):
    assert migrar_esquema(create_engine(f"sqlite:///{tmp_path / 'vazio.db'}")) == []
