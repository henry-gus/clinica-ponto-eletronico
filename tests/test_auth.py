from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app import config, models, security
from tests.conftest import PERIODO, PIN_ADMIN, entrar


# ------------------------------------------------------------ login e perfil
def test_login_informa_o_perfil(client, usuario, admin):
    como_admin = client.post("/auth/login", json={"usuario_id": admin["id"], "pin": PIN_ADMIN}).json()
    como_ana = client.post("/auth/login", json={"usuario_id": usuario["id"], "pin": "1234"}).json()

    assert (como_admin["papel"], como_admin["nome"]) == ("admin", "Carla Admin")
    assert (como_ana["papel"], como_ana["nome"]) == ("funcionario", "Ana Souza")
    assert como_ana["expira_em_segundos"] == config.SESSAO_MINUTOS * 60


def test_auth_eu_devolve_quem_esta_logado(client, usuario, cab_ana):
    assert client.get("/auth/eu", headers=cab_ana).json() == {
        "usuario_id": usuario["id"], "nome": "Ana Souza", "papel": "funcionario",
    }
    assert client.get("/auth/eu").status_code == 401


def test_login_com_pin_errado_ou_id_inexistente(client, usuario):
    assert client.post("/auth/login", json={"usuario_id": usuario["id"], "pin": "0000"}).status_code == 403
    assert client.post("/auth/login", json={"usuario_id": 999, "pin": "1234"}).status_code == 403


def test_sessao_invalida_nao_entra(client, usuario):
    expirada = jwt.encode(
        {"tipo": "sessao", "uid": usuario["id"], "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        config.SECRET_KEY, algorithm="HS256",
    )
    tokens_de_outros_tipos = [
        client.get("/qr-token").json()["token"],
        security.criar_token_comprovante(1),
    ]
    candidatos = [expirada, "lixo", security.criar_token_sessao(999), *tokens_de_outros_tipos]

    assert client.get("/auth/eu", headers={"Authorization": "Basic abc"}).status_code == 401
    for token in candidatos:
        assert client.get("/auth/eu", headers={"Authorization": f"Bearer {token}"}).status_code == 401, token


# ------------------------------------------------------ quem pode o quê
ROTAS_ADMIN = [
    ("get", f"/admin/resumo?{PERIODO}"),
    ("get", f"/admin/extrato/1?{PERIODO}"),
    ("get", f"/admin/extrato/1/pdf?{PERIODO}"),
    ("get", f"/admin/extratos/zip?{PERIODO}"),
    ("get", "/usuarios/"),
    ("post", "/usuarios/"),
    ("post", "/admin/ausencias"),
    ("delete", "/admin/ausencias/1"),
]


@pytest.mark.parametrize("metodo, rota", ROTAS_ADMIN)
def test_rotas_do_admin_exigem_login_e_perfil(client, usuario, cab_ana, metodo, rota):
    chamar = getattr(client, metodo)
    assert chamar(rota).status_code == 401  # sem login
    assert chamar(rota, headers={"Authorization": "Bearer lixo"}).status_code == 401
    assert chamar(rota, headers=cab_ana).status_code == 403  # logada, mas funcionária


def test_perfil_e_lido_do_banco_a_cada_requisicao(client, db, usuario, cab_ana):
    """Promover ou rebaixar vale na hora, sem esperar a sessão expirar."""
    assert client.get("/usuarios/", headers=cab_ana).status_code == 403

    db.get(models.Usuario, usuario["id"]).papel = "admin"
    db.commit()
    assert client.get("/usuarios/", headers=cab_ana).status_code == 200

    db.get(models.Usuario, usuario["id"]).papel = "funcionario"
    db.commit()
    assert client.get("/usuarios/", headers=cab_ana).status_code == 403


# --------------------------------------------------- limite de tentativas
def test_cinco_erros_bloqueiam_ate_o_pin_correto(client, usuario):
    dados = {"usuario_id": usuario["id"], "pin": "0000"}
    for _ in range(config.PIN_MAX_TENTATIVAS):
        assert client.post("/auth/login", json=dados).status_code == 403

    bloqueado = client.post("/auth/login", json={"usuario_id": usuario["id"], "pin": "1234"})
    assert bloqueado.status_code == 429
    assert int(bloqueado.headers["Retry-After"]) > 0


def test_acerto_zera_o_contador(client, usuario):
    errado = {"usuario_id": usuario["id"], "pin": "0000"}
    for _ in range(config.PIN_MAX_TENTATIVAS - 1):
        client.post("/auth/login", json=errado)
    entrar(client, usuario)  # acerta: zera
    for _ in range(config.PIN_MAX_TENTATIVAS - 1):
        assert client.post("/auth/login", json=errado).status_code == 403


def test_bloqueio_vale_tambem_para_bater_ponto(client, usuario):
    token = client.get("/qr-token").json()["token"]
    for _ in range(config.PIN_MAX_TENTATIVAS):
        assert client.post(f"/ponto/{usuario['id']}?token={token}", json={"pin": "0000"}).status_code == 403

    assert client.post(f"/ponto/{usuario['id']}?token={token}", json={"pin": "1234"}).status_code == 429
    assert client.post("/auth/login", json={"usuario_id": usuario["id"], "pin": "1234"}).status_code == 429


def test_bloqueio_de_um_nao_afeta_outro(client, usuario, admin):
    for _ in range(config.PIN_MAX_TENTATIVAS):
        client.post("/auth/login", json={"usuario_id": usuario["id"], "pin": "0000"})
    entrar(client, admin, PIN_ADMIN)
