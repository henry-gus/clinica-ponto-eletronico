from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app import config
from app.services import ponto_service
from tests.conftest import entrar


def _token(client):
    return client.get("/qr-token").json()["token"]


def test_entrada_e_saida_com_nsr_sequencial(client, usuario):
    url = f"/ponto/{usuario['id']}?token={_token(client)}"

    primeira = client.post(url, json={"pin": "1234"}).json()
    segunda = client.post(url, json={"pin": "1234"}).json()

    assert (primeira["tipo"], segunda["tipo"]) == ("entrada", "saida")
    assert segunda["nsr"] == primeira["nsr"] + 1


def test_qr_url_usa_o_endereco_da_requisicao(client):
    url = client.get("/qr-token").json()["url"]
    assert url.startswith("http://testserver/bater-ponto?token=")


def test_token_invalido_e_expirado(client, usuario):
    corpo = {"pin": "1234"}
    assert client.post(f"/ponto/{usuario['id']}?token=lixo", json=corpo).status_code == 403

    expirado = jwt.encode(
        {"tipo": "qr_ponto", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        config.SECRET_KEY,
        algorithm="HS256",
    )
    assert client.post(f"/ponto/{usuario['id']}?token={expirado}", json=corpo).status_code == 403


def test_pin_errado_e_id_inexistente_tem_a_mesma_resposta(client, usuario):
    token = _token(client)
    pin_errado = client.post(f"/ponto/{usuario['id']}?token={token}", json={"pin": "0000"})
    sem_usuario = client.post(f"/ponto/999?token={token}", json={"pin": "1234"})
    assert pin_errado.status_code == sem_usuario.status_code == 403
    assert pin_errado.json() == sem_usuario.json()


def test_marcacao_e_imutavel(db, usuario):
    marcacao, _ = ponto_service.registrar_marcacao(db, usuario["id"])

    marcacao.momento = marcacao.momento + timedelta(hours=1)
    with pytest.raises(RuntimeError):
        db.commit()
    db.rollback()

    db.delete(marcacao)
    with pytest.raises(RuntimeError):
        db.commit()


def test_saida_esquecida_nao_contamina_o_dia_seguinte(db, usuario):
    # 23:50 de 04/10 no horário local (UTC-3) e 00:10 de 05/10: dias locais diferentes.
    noite = datetime(2026, 10, 5, 2, 50, tzinfo=timezone.utc)
    madrugada = datetime(2026, 10, 5, 3, 10, tzinfo=timezone.utc)

    _, tipo1 = ponto_service.registrar_marcacao(db, usuario["id"], agora=noite)
    _, tipo2 = ponto_service.registrar_marcacao(db, usuario["id"], agora=madrugada)

    assert (tipo1, tipo2) == ("entrada", "entrada")


def test_administrador_tambem_pode_bater_ponto(client, admin):
    resposta = client.post(f"/ponto/{admin['id']}?token={_token(client)}", json={"pin": "9999"})
    assert resposta.status_code == 200 and resposta.json()["tipo"] == "entrada"
