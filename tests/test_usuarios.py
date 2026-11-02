from datetime import date

import pytest

from app.cpf import cpf_valido
from tests.conftest import PIN_ADMIN, entrar, novo_usuario


def test_cadastro_com_valores_padrao(client, cab_admin):
    pessoa = novo_usuario(client, cab_admin, "Bia Lima", "111.444.777-35")
    assert pessoa["papel"] == "funcionario"
    assert pessoa["dias_trabalho"] == [0, 1, 2, 3, 4]  # segunda a sexta
    assert pessoa["data_inicio"] is None
    assert pessoa["cpf"] == "11144477735"  # só dígitos


def test_cadastro_com_escala_e_inicio(client, cab_admin):
    pessoa = novo_usuario(client, cab_admin, "Caio Reis", "529.982.247-25", dias_trabalho=[5, 6, 5], data_inicio="2026-10-08")
    assert pessoa["dias_trabalho"] == [5, 6]
    assert pessoa["data_inicio"] == "2026-10-08"


def test_administrador_cadastrado_pela_tela_consegue_entrar_como_admin(client, cab_admin):
    novo = novo_usuario(client, cab_admin, "Dan Chefe", "111.444.777-35", pin="5555", papel="admin")
    assert novo["papel"] == "admin"
    assert client.get("/usuarios/", headers=entrar(client, novo, "5555")).status_code == 200


@pytest.mark.parametrize("campo, valor", [
    ("dias_trabalho", [7]), ("dias_trabalho", [-1]), ("dias_trabalho", []),
    ("papel", "root"), ("cpf", "111.111.111-11"), ("cpf", "123"), ("pin", "12"), ("pin", "abcd"),
    ("carga_horaria_diaria", 0), ("carga_horaria_diaria", 25), ("data_inicio", "ontem"),
])
def test_cadastro_invalido(client, cab_admin, campo, valor):
    corpo = {"nome": "X", "cpf": "111.444.777-35", "cargo": "Y", "pin": "4321", campo: valor}
    assert client.post("/usuarios/", json=corpo, headers=cab_admin).status_code == 422


def test_cpf_duplicado(client, cab_admin, usuario):
    corpo = {"nome": "Outra", "cpf": "52998224725", "cargo": "Y", "pin": "4321"}  # o mesmo CPF da Ana, sem pontuação
    assert client.post("/usuarios/", json=corpo, headers=cab_admin).status_code == 409


def test_listagem_em_ordem_alfabetica(client, cab_admin, usuario):
    novo_usuario(client, cab_admin, "Bia Lima", "111.444.777-35")
    lista = client.get("/usuarios/", headers=cab_admin).json()
    assert [u["nome"] for u in lista] == ["Ana Souza", "Bia Lima", "Carla Admin"]
    assert lista[2]["papel"] == "admin" and "pin_hash" not in lista[0]


def test_validacao_de_cpf():
    assert cpf_valido("52998224725")
    assert not cpf_valido("52998224724")
    assert not cpf_valido("00000000000")
    assert not cpf_valido("123")
