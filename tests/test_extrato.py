import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

import jwt
import pytest
from pypdf import PdfReader
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature

from app import config, models, security
from app.services.extrato_service import formatar_duracao
from tests.conftest import ADMIN

PERIODO = "inicio=2026-10-01&fim=2026-10-31"


def utc(mes, dia, hora, minuto=0):
    return datetime(2026, mes, dia, hora, minuto, tzinfo=timezone.utc)


def semear(db, usuario_id, momentos):
    db.add_all(models.Marcacao(usuario_id=usuario_id, momento=m) for m in momentos)
    db.commit()


# Horário local = UTC-3. Ana: 01/10 8h-12h e 13h-18h (9h); 02/10 8h-17h (9h); 03/10 só entrada.
@pytest.fixture
def ana(db, usuario):
    semear(db, usuario["id"], [
        utc(9, 30, 11), utc(9, 30, 20),                       # fora do período (setembro)
        utc(10, 1, 11), utc(10, 1, 15), utc(10, 1, 16), utc(10, 1, 21),
        utc(10, 2, 11), utc(10, 2, 20),
        utc(10, 3, 11),                                       # entrada sem saída
        utc(11, 1, 2, 30),                                    # 31/10 23:30 local: ainda é outubro
        utc(11, 2, 11), utc(11, 2, 20),                       # fora do período (novembro)
    ])
    return usuario


def entrar(client, usuario, pin="1234"):
    resposta = client.post("/funcionario/login", json={"usuario_id": usuario["id"], "pin": pin})
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['token']}"}


def novo_usuario(client, nome, cpf, pin="4321"):
    resposta = client.post(
        "/usuarios/",
        json={"nome": nome, "cpf": cpf, "cargo": "Fisioterapeuta", "carga_horaria_diaria": 6, "pin": pin},
        headers=ADMIN,
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def texto_pdf(conteudo: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(BytesIO(conteudo)).pages)


# --------------------------------------------------------------- formatação
@pytest.mark.parametrize("segundos, esperado", [
    (0, "00:00"), (9 * 3600, "09:00"), (-4500, "-01:15"), (29, "00:00"), (30, "00:01"), (-20, "00:00"),
])
def test_formatar_duracao(segundos, esperado):
    assert formatar_duracao(segundos) == esperado


# ------------------------------------------------------------------- sessão
def test_login_devolve_sessao(client, usuario):
    resposta = client.post("/funcionario/login", json={"usuario_id": usuario["id"], "pin": "1234"})
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Ana Souza"
    assert resposta.json()["expira_em_segundos"] == config.SESSAO_FUNCIONARIO_MINUTOS * 60


def test_login_com_pin_errado_ou_id_inexistente(client, usuario):
    assert client.post("/funcionario/login", json={"usuario_id": usuario["id"], "pin": "0000"}).status_code == 403
    assert client.post("/funcionario/login", json={"usuario_id": 999, "pin": "1234"}).status_code == 403


def test_extrato_exige_sessao_valida(client, usuario):
    expirada = jwt.encode(
        {"tipo": "sessao_funcionario", "uid": usuario["id"], "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        config.SECRET_KEY, algorithm="HS256",
    )
    de_usuario_inexistente = security.criar_token_sessao(999)
    token_qr = client.get("/qr-token").json()["token"]
    token_comprovante = security.criar_token_comprovante(1)

    for cabecalho in ({}, {"Authorization": "Bearer lixo"}, {"Authorization": "Basic abc"},
                      *({"Authorization": f"Bearer {t}"} for t in
                        (expirada, de_usuario_inexistente, token_qr, token_comprovante))):
        for rota in ("/funcionario/extrato", "/funcionario/extrato/pdf"):
            assert client.get(f"{rota}?{PERIODO}", headers=cabecalho).status_code == 401


# --------------------------------------------------- limite de tentativas
def test_cinco_erros_bloqueiam_ate_o_pin_correto(client, usuario):
    dados = {"usuario_id": usuario["id"], "pin": "0000"}
    for _ in range(config.PIN_MAX_TENTATIVAS):
        assert client.post("/funcionario/login", json=dados).status_code == 403

    bloqueado = client.post("/funcionario/login", json={"usuario_id": usuario["id"], "pin": "1234"})
    assert bloqueado.status_code == 429
    assert int(bloqueado.headers["Retry-After"]) > 0


def test_acerto_zera_o_contador(client, usuario):
    errado = {"usuario_id": usuario["id"], "pin": "0000"}
    for _ in range(config.PIN_MAX_TENTATIVAS - 1):
        client.post("/funcionario/login", json=errado)
    entrar(client, usuario)  # acerta: zera
    for _ in range(config.PIN_MAX_TENTATIVAS - 1):
        assert client.post("/funcionario/login", json=errado).status_code == 403


def test_bloqueio_vale_tambem_para_bater_ponto(client, usuario):
    token = client.get("/qr-token").json()["token"]
    for _ in range(config.PIN_MAX_TENTATIVAS):
        assert client.post(f"/ponto/{usuario['id']}?token={token}", json={"pin": "0000"}).status_code == 403

    assert client.post(f"/ponto/{usuario['id']}?token={token}", json={"pin": "1234"}).status_code == 429
    assert client.post("/funcionario/login", json={"usuario_id": usuario["id"], "pin": "1234"}).status_code == 429


def test_bloqueio_de_um_funcionario_nao_afeta_outro(client, usuario):
    outro = novo_usuario(client, "Bia Lima", "111.444.777-35")
    for _ in range(config.PIN_MAX_TENTATIVAS):
        client.post("/funcionario/login", json={"usuario_id": usuario["id"], "pin": "0000"})
    entrar(client, outro, pin="4321")


# ---------------------------------------------------------- extrato (JSON)
def test_extrato_do_funcionario(client, ana):
    resposta = client.get(f"/funcionario/extrato?{PERIODO}", headers=entrar(client, ana))
    dados = resposta.json()
    dias = {d["data"]: d for d in dados["dias"]}

    assert resposta.status_code == 200
    assert len(dados["dias"]) == 31  # todos os dias do período, como numa folha de ponto
    assert dias["2026-10-01"]["pares"] == [
        {"entrada": "08:00", "saida": "12:00"}, {"entrada": "13:00", "saida": "18:00"},
    ]
    assert dias["2026-10-01"]["horas"] == "09:00" and dias["2026-10-02"]["horas"] == "09:00"
    assert dias["2026-10-03"]["pares"] == [{"entrada": "08:00", "saida": None}]
    assert dias["2026-10-03"]["incompleto"] and dias["2026-10-03"]["horas"] == ""
    assert dias["2026-10-04"]["pares"] == [] and dias["2026-10-04"]["horas"] == ""
    assert dias["2026-10-31"]["pares"] == [{"entrada": "23:30", "saida": None}]  # horário local
    assert (dados["total_horas"], dados["horas_esperadas"], dados["saldo"]) == ("18:00", "16:00", "02:00")
    assert (dados["dias_trabalhados"], dados["dias_incompletos"]) == (2, 2)


def test_filtro_de_periodo_restringe_os_dias(client, ana):
    resposta = client.get("/funcionario/extrato?inicio=2026-10-02&fim=2026-10-03", headers=entrar(client, ana))
    dados = resposta.json()
    assert [d["data"] for d in dados["dias"]] == ["2026-10-02", "2026-10-03"]
    assert dados["total_horas"] == "09:00"


def test_funcionario_ve_somente_o_proprio_extrato(client, db, ana):
    bia = novo_usuario(client, "Bia Lima", "111.444.777-35")
    semear(db, bia["id"], [utc(10, 5, 12), utc(10, 5, 16)])  # 09:00-13:00 de Bia

    dados = client.get(f"/funcionario/extrato?{PERIODO}", headers=entrar(client, ana)).json()
    assert dados["nome"] == "Ana Souza"
    assert "05" not in [d["data"][-2:] for d in dados["dias"] if d["pares"]]

    dados_bia = client.get(f"/funcionario/extrato?{PERIODO}", headers=entrar(client, bia, "4321")).json()
    assert dados_bia["nome"] == "Bia Lima" and dados_bia["total_horas"] == "04:00"


def test_periodo_padrao_e_validacoes(client, usuario):
    cabecalho = entrar(client, usuario)
    hoje = datetime.now(config.FUSO).date()

    padrao = client.get("/funcionario/extrato", headers=cabecalho)
    assert padrao.status_code == 200 and len(padrao.json()["dias"]) == hoje.day

    assert client.get("/funcionario/extrato?inicio=2026-10-10&fim=2026-10-01", headers=cabecalho).status_code == 422
    assert client.get("/funcionario/extrato?inicio=2025-01-01&fim=2026-10-01", headers=cabecalho).status_code == 422
    assert client.get("/funcionario/extrato?inicio=nao-e-data", headers=cabecalho).status_code == 422


# ----------------------------------------------------------------- PDF
def test_pdf_do_funcionario(client, ana, monkeypatch):
    monkeypatch.setattr(config, "EMPRESA_NOME", "LABELLE PILATES&FISIOTERAPIA LTDA")  # "&" quebraria o PDF sem escape
    resposta = client.get(f"/funcionario/extrato/pdf?{PERIODO}", headers=entrar(client, ana))
    texto = texto_pdf(resposta.content)

    assert resposta.status_code == 200 and resposta.headers["content-type"] == "application/pdf"
    assert "extrato-ana-souza-20261001-20261031.pdf" in resposta.headers["content-disposition"]
    for esperado in ("Extrato de Registros de Ponto", "LABELLE PILATES&FISIOTERAPIA LTDA", "Ana Souza",
                     "529.982.247-25", "01/10/2026 a 31/10/2026", "08:00 - 12:00", "13:00 - 18:00",
                     "08:00 - (sem saída)", "Marcação incompleta", "18:00", "16:00", "02:00"):
        assert esperado in texto, esperado
    assert "SEM assinatura" in texto


def test_pdf_com_o_mes_inteiro_cabe_em_duas_paginas_no_maximo(client, ana):
    pdf = client.get(f"/funcionario/extrato/pdf?{PERIODO}", headers=entrar(client, ana)).content
    assert len(PdfReader(BytesIO(pdf)).pages) <= 2


def test_pdf_de_periodo_longo_pagina_e_repete_o_cabecalho(client, ana):
    pdf = client.get("/funcionario/extrato/pdf?inicio=2026-01-01&fim=2026-12-31", headers=entrar(client, ana)).content
    paginas = PdfReader(BytesIO(pdf)).pages
    assert len(paginas) > 2
    assert all("Marcações (entrada - saída)" in p.extract_text() for p in paginas)


def test_pdf_do_extrato_pode_ser_assinado(client, ana, certificado):
    pdf = client.get(f"/funcionario/extrato/pdf?{PERIODO}", headers=entrar(client, ana)).content
    assinaturas = PdfFileReader(BytesIO(pdf)).embedded_signatures
    status = validate_pdf_signature(assinaturas[0])

    assert len(assinaturas) == 1 and status.intact and status.valid
    assert "SEM assinatura" not in texto_pdf(pdf)


# --------------------------------------------------------------- admin
ROTAS_ADMIN = [
    f"/admin/resumo?{PERIODO}", f"/admin/extrato/1?{PERIODO}", f"/admin/extrato/1/pdf?{PERIODO}",
    f"/admin/extratos/zip?{PERIODO}", "/usuarios/",
]


@pytest.mark.parametrize("rota", ROTAS_ADMIN)
def test_rotas_do_admin_exigem_token(client, ana, rota):
    assert client.get(rota).status_code == 401
    assert client.get(rota, headers={"X-Admin-Token": "errado"}).status_code == 401
    assert client.get(rota, headers=entrar(client, ana)).status_code == 401  # sessão de funcionário não vale


def test_admin_lista_funcionarios(client, ana):
    novo_usuario(client, "Bia Lima", "111.444.777-35")
    nomes = [u["nome"] for u in client.get("/usuarios/", headers=ADMIN).json()]
    assert nomes == ["Ana Souza", "Bia Lima"]


def test_resumo_de_todos_os_funcionarios(client, ana):
    novo_usuario(client, "Bia Lima", "111.444.777-35")  # sem marcações
    resumo = client.get(f"/admin/resumo?{PERIODO}", headers=ADMIN).json()

    assert [r["nome"] for r in resumo] == ["Ana Souza", "Bia Lima"]
    assert (resumo[0]["total_horas"], resumo[0]["saldo"], resumo[0]["dias_incompletos"]) == ("18:00", "02:00", 2)
    assert (resumo[1]["total_horas"], resumo[1]["dias_trabalhados"]) == ("00:00", 0)


def test_admin_ve_o_extrato_de_qualquer_funcionario(client, ana):
    dados = client.get(f"/admin/extrato/{ana['id']}?{PERIODO}", headers=ADMIN).json()
    assert dados["nome"] == "Ana Souza" and dados["total_horas"] == "18:00" and len(dados["dias"]) == 31

    pdf = client.get(f"/admin/extrato/{ana['id']}/pdf?{PERIODO}", headers=ADMIN)
    assert pdf.status_code == 200 and "Ana Souza" in texto_pdf(pdf.content)

    assert client.get(f"/admin/extrato/999?{PERIODO}", headers=ADMIN).status_code == 404
    assert client.get(f"/admin/extrato/999/pdf?{PERIODO}", headers=ADMIN).status_code == 404


def test_zip_com_um_pdf_por_funcionario(client, db, ana, certificado):
    bia = novo_usuario(client, "Bia Lima", "111.444.777-35")
    semear(db, bia["id"], [utc(10, 5, 12), utc(10, 5, 16)])

    resposta = client.get(f"/admin/extratos/zip?{PERIODO}", headers=ADMIN)
    arquivo = zipfile.ZipFile(BytesIO(resposta.content))

    assert resposta.status_code == 200 and resposta.headers["content-type"] == "application/zip"
    assert "extratos-20261001-20261031.zip" in resposta.headers["content-disposition"]
    assert arquivo.namelist() == [
        f"{ana['id']:03d}-extrato-ana-souza-20261001-20261031.pdf",
        f"{bia['id']:03d}-extrato-bia-lima-20261001-20261031.pdf",
    ]
    textos = [texto_pdf(arquivo.read(nome)) for nome in arquivo.namelist()]
    assert "Ana Souza" in textos[0] and "Bia Lima" not in textos[0]
    assert "Bia Lima" in textos[1] and "04:00" in textos[1]
    assert all(len(PdfFileReader(BytesIO(arquivo.read(n))).embedded_signatures) == 1 for n in arquivo.namelist())


def test_paginas_estaticas(client):
    for caminho in ("/meu-extrato", "/painel", "/static/js/extrato-ui.js"):
        assert client.get(caminho).status_code == 200
