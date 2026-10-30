from datetime import datetime, timedelta, timezone
from io import BytesIO

import jwt
import pytest
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pypdf import PdfReader

from app import config, models
from app.cpf import cpf_valido
from app.services import assinatura_service, comprovante_service
from scripts.gerar_certificado_teste import gerar
from tests.conftest import ADMIN


def _bater_ponto(client, usuario):
    token = client.get("/qr-token").json()["token"]
    resposta = client.post(f"/ponto/{usuario['id']}?token={token}", json={"pin": "1234"})
    assert resposta.status_code == 200
    return resposta.json()


def _texto(pdf: bytes) -> str:
    return "\n".join(pagina.extract_text() for pagina in PdfReader(BytesIO(pdf)).pages)


@pytest.fixture
def certificado(tmp_path, monkeypatch):
    caminho = tmp_path / "teste.p12"
    gerar(str(caminho), "senha-teste")
    monkeypatch.setattr(config, "CERT_P12_PATH", str(caminho))
    monkeypatch.setattr(config, "CERT_P12_SENHA", "senha-teste")


def test_resposta_do_ponto_traz_link_do_comprovante(client, usuario):
    marcacao = _bater_ponto(client, usuario)
    assert marcacao["comprovante_url"].startswith(f"/comprovantes/{marcacao['nsr']}?token=")


def test_comprovante_tem_os_campos_do_art_79(client, usuario):
    marcacao = _bater_ponto(client, usuario)

    resposta = client.get(marcacao["comprovante_url"])
    texto = _texto(resposta.content)

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert "Comprovante de Registro de Ponto do Trabalhador" in texto
    assert f"NSR: {marcacao['nsr']}" in texto
    assert "Clínica Exemplo Ltda" in texto and "11.222.333/0001-81" in texto
    assert "Rua das Flores, 100" in texto
    assert "Ana Souza" in texto and "529.982.247-25" in texto
    assert "SEM assinatura" in texto  # sem certificado configurado


def test_horario_do_comprovante_no_fuso_da_clinica():
    momento = datetime(2026, 10, 5, 17, 32, 10, tzinfo=timezone.utc)
    assert comprovante_service.formatar_momento(momento) == "05/10/2026 14:32:10 (UTC-03:00)"


def test_comprovante_assinado_tem_assinatura_integra(client, usuario, certificado):
    marcacao = _bater_ponto(client, usuario)

    pdf = client.get(marcacao["comprovante_url"]).content
    assinaturas = PdfFileReader(BytesIO(pdf)).embedded_signatures
    status = validate_pdf_signature(assinaturas[0])

    assert assinatura_service.configurada()
    assert len(assinaturas) == 1
    assert status.intact and status.valid
    assert not status.trusted  # certificado de teste autoassinado: não é ICP-Brasil
    assert "SEM assinatura" not in _texto(pdf)


def test_alterar_o_pdf_assinado_invalida_a_assinatura(client, usuario, certificado):
    marcacao = _bater_ponto(client, usuario)
    pdf = client.get(marcacao["comprovante_url"]).content

    # O título do documento fica em texto puro no PDF: trocar uma letra mantém o arquivo
    # abrindo normalmente, mas muda os bytes cobertos pela assinatura.
    assert b"Registro de Ponto" in pdf
    adulterado = pdf.replace(b"Registro de Ponto", b"Registro de Ponta", 1)

    assinatura = PdfFileReader(BytesIO(adulterado)).embedded_signatures[0]
    assert not validate_pdf_signature(assinatura).intact


def test_link_invalido_expirado_ou_de_outra_marcacao_e_negado(client, usuario):
    primeira = _bater_ponto(client, usuario)
    segunda = _bater_ponto(client, usuario)
    token_da_primeira = primeira["comprovante_url"].split("token=")[1]

    assert client.get(f"/comprovantes/{primeira['nsr']}").status_code == 403
    assert client.get(f"/comprovantes/{primeira['nsr']}?token=lixo").status_code == 403
    assert client.get(f"/comprovantes/{segunda['nsr']}?token={token_da_primeira}").status_code == 403

    expirado = jwt.encode(
        {"tipo": "comprovante", "nsr": primeira["nsr"],
         "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        config.SECRET_KEY, algorithm="HS256",
    )
    assert client.get(f"/comprovantes/{primeira['nsr']}?token={expirado}").status_code == 403


def test_token_do_qr_nao_serve_como_link_de_comprovante(client, usuario):
    marcacao = _bater_ponto(client, usuario)
    token_qr = client.get("/qr-token").json()["token"]
    assert client.get(f"/comprovantes/{marcacao['nsr']}?token={token_qr}").status_code == 403


def test_admin_baixa_qualquer_comprovante_e_nsr_inexistente_da_404(client, usuario):
    marcacao = _bater_ponto(client, usuario)
    assert client.get(f"/comprovantes/{marcacao['nsr']}", headers=ADMIN).status_code == 200
    assert client.get("/comprovantes/9999", headers=ADMIN).status_code == 404


def test_sem_dados_do_empregador_nao_emite_comprovante(client, usuario, monkeypatch):
    marcacao = _bater_ponto(client, usuario)  # o ponto em si continua funcionando
    monkeypatch.setattr(config, "EMPRESA_CNPJ", "")
    assert client.get(marcacao["comprovante_url"]).status_code == 503


def test_comprovante_regenerado_e_igual_para_a_mesma_marcacao(db, usuario):
    marcacao = models.Marcacao(
        usuario_id=usuario["id"], momento=datetime(2026, 10, 5, 17, 0, tzinfo=timezone.utc)
    )
    db.add(marcacao)
    db.commit()
    assert _texto(comprovante_service.gerar_comprovante(db, marcacao.nsr)) == _texto(
        comprovante_service.gerar_comprovante(db, marcacao.nsr)
    )


def test_cpf_invalido_e_duplicado(client, usuario):
    corpo = {"nome": "Bia", "cpf": "111.111.111-11", "cargo": "Médica", "pin": "4321"}
    assert client.post("/usuarios/", json=corpo, headers=ADMIN).status_code == 422

    corpo["cpf"] = "52998224725"  # o mesmo CPF do fixture, sem pontuação
    assert client.post("/usuarios/", json=corpo, headers=ADMIN).status_code == 409


def test_validacao_de_cpf():
    assert cpf_valido("52998224725")
    assert not cpf_valido("52998224724")
    assert not cpf_valido("00000000000")
    assert not cpf_valido("123")
