import zipfile
from datetime import date
from io import BytesIO

import pytest
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pypdf import PdfReader

from app import config
from app.services import extrato_service
from app.services.extrato_service import formatar_duracao
from tests.conftest import PERIODO, entrar, novo_usuario, semear, utc

SEMANA = "inicio=2026-10-01&fim=2026-10-09"  # qui 01, sex 02, sáb 03, dom 04, seg 05 ... sex 09


def texto_pdf(conteudo: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(BytesIO(conteudo)).pages)


def registrar(client, cab_admin, usuario_id, tipo, inicio, fim, observacao=None):
    resposta = client.post(
        "/admin/ausencias",
        json={"usuario_id": usuario_id, "tipo": tipo, "inicio": inicio, "fim": fim, "observacao": observacao},
        headers=cab_admin,
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


# Horário local = UTC-3. Ana: 01/10 8h-12h e 13h-18h (9h); 02/10 8h-17h (9h); 03/10 (sáb) só entrada.
@pytest.fixture
def ana(db, usuario):
    semear(db, usuario["id"], [
        utc(9, 30, 11), utc(9, 30, 20),                       # fora do período (setembro)
        utc(10, 1, 11), utc(10, 1, 15), utc(10, 1, 16), utc(10, 1, 21),
        utc(10, 2, 11), utc(10, 2, 20),
        utc(10, 3, 11),                                       # sábado, entrada sem saída
        utc(11, 1, 2, 30),                                    # 31/10 23:30 local: ainda é outubro
        utc(11, 2, 11), utc(11, 2, 20),                       # fora do período (novembro)
    ])
    return usuario


@pytest.mark.parametrize("segundos, esperado", [
    (0, "00:00"), (9 * 3600, "09:00"), (-4500, "-01:15"), (29, "00:00"), (30, "00:01"), (-20, "00:00"),
])
def test_formatar_duracao(segundos, esperado):
    assert formatar_duracao(segundos) == esperado


# ------------------------------------------------------------ regras do saldo
def test_extrato_com_faltas(client, ana, cab_ana, hoje_em_novembro):
    dados = client.get(f"/extratos/meu?{SEMANA}", headers=cab_ana).json()
    dias = {d["data"]: d for d in dados["dias"]}

    assert len(dados["dias"]) == 9
    assert dias["2026-10-01"]["pares"] == [{"entrada": "08:00", "saida": "12:00"}, {"entrada": "13:00", "saida": "18:00"}]
    assert dias["2026-10-01"]["horas"] == "09:00" and dias["2026-10-01"]["situacao"] == ""
    assert dias["2026-10-03"]["pares"] == [{"entrada": "08:00", "saida": None}]
    assert dias["2026-10-03"]["situacao"] == "incompleta" and dias["2026-10-03"]["dia_de_trabalho"] is False
    assert dias["2026-10-04"]["situacao"] == "" and dias["2026-10-04"]["dia_de_trabalho"] is False  # domingo: folga
    assert dias["2026-10-05"]["situacao"] == "falta" and dias["2026-10-05"]["situacao_texto"] == "Falta"

    # dias de trabalho: 01, 02, 05, 06, 07, 08, 09 = 7 x 8h
    assert (dados["total_horas"], dados["horas_esperadas"], dados["saldo"]) == ("18:00", "56:00", "-38:00")
    assert (dados["faltas"], dados["dias_incompletos"], dados["dias_trabalhados"]) == (5, 1, 2)
    assert dados["ausencias"] == {}


def test_ausencias_abonam_as_horas_esperadas(client, ana, cab_ana, cab_admin, hoje_em_novembro):
    registrar(client, cab_admin, ana["id"], "atestado", "2026-10-05", "2026-10-06", "consulta")
    registrar(client, cab_admin, ana["id"], "ferias", "2026-10-07", "2026-10-07")

    dados = client.get(f"/extratos/meu?{SEMANA}", headers=cab_ana).json()
    dias = {d["data"]: d for d in dados["dias"]}

    assert dias["2026-10-05"]["situacao"] == "atestado" and dias["2026-10-05"]["observacao"] == "consulta"
    assert dias["2026-10-05"]["ausencia_id"] is not None
    assert dias["2026-10-07"]["situacao"] == "ferias" and dias["2026-10-07"]["situacao_texto"] == "Férias"
    # sobram como dias de trabalho esperados: 01, 02, 08, 09 = 4 x 8h; faltas só 08 e 09
    assert (dados["horas_esperadas"], dados["saldo"], dados["faltas"]) == ("32:00", "-14:00", 2)
    assert dados["ausencias"] == {"atestado": 2, "ferias": 1}


def test_hoje_e_dias_futuros_nao_geram_falta(client, db, ana, cab_ana, monkeypatch):
    monkeypatch.setattr(extrato_service, "hoje_local", lambda: date(2026, 10, 5))  # segunda

    dados = client.get(f"/extratos/meu?{SEMANA}", headers=cab_ana).json()
    assert (dados["horas_esperadas"], dados["saldo"], dados["faltas"]) == ("16:00", "02:00", 0)  # só 01 e 02

    semear(db, ana["id"], [utc(10, 5, 11)])  # hoje: entrou e ainda não saiu
    dados = client.get(f"/extratos/meu?{SEMANA}", headers=cab_ana).json()
    assert dados["horas_esperadas"] == "16:00"

    semear(db, ana["id"], [utc(10, 5, 15)])  # hoje: saiu (4h trabalhadas) -> o dia passa a contar
    dados = client.get(f"/extratos/meu?{SEMANA}", headers=cab_ana).json()
    assert (dados["total_horas"], dados["horas_esperadas"], dados["saldo"]) == ("22:00", "24:00", "-02:00")


def test_dias_antes_do_inicio_nao_geram_falta(client, cab_admin, hoje_em_novembro):
    caio = novo_usuario(client, cab_admin, "Caio Reis", "111.444.777-35", data_inicio="2026-10-08")
    dados = client.get(f"/admin/extrato/{caio['id']}?{SEMANA}", headers=cab_admin).json()
    dias = {d["data"]: d for d in dados["dias"]}

    assert dias["2026-10-07"]["dia_de_trabalho"] is False and dias["2026-10-07"]["situacao"] == ""
    assert dias["2026-10-08"]["situacao"] == "falta"
    assert (dados["faltas"], dados["horas_esperadas"]) == (2, "16:00")  # só 08 e 09


def test_escala_propria_do_funcionario(client, db, cab_admin, hoje_em_novembro):
    """Bia trabalha só aos sábados: dia trabalhado fora da escala conta como hora a mais."""
    bia = novo_usuario(client, cab_admin, "Bia Lima", "111.444.777-35", dias_trabalho=[5])
    semear(db, bia["id"], [utc(10, 5, 12), utc(10, 5, 18)])  # segunda 09:00-15:00 (6h)

    dados = client.get(f"/admin/extrato/{bia['id']}?{SEMANA}", headers=cab_admin).json()
    dias = {d["data"]: d for d in dados["dias"]}

    assert dias["2026-10-05"]["horas"] == "06:00" and dias["2026-10-05"]["situacao"] == ""
    assert dias["2026-10-03"]["situacao"] == "falta"  # o único dia da escala no período
    assert (dados["total_horas"], dados["horas_esperadas"], dados["saldo"], dados["faltas"]) == ("06:00", "08:00", "-02:00", 1)


# ------------------------------------------------------------- período e dono
def test_extrato_do_mes_inclui_todos_os_dias_no_horario_local(client, ana, cab_ana, hoje_em_novembro):
    dados = client.get(f"/extratos/meu?{PERIODO}", headers=cab_ana).json()
    dias = {d["data"]: d for d in dados["dias"]}
    assert len(dados["dias"]) == 31
    assert dias["2026-10-31"]["pares"] == [{"entrada": "23:30", "saida": None}]  # 02:30Z de 01/11
    assert dados["dias_incompletos"] == 2


def test_filtro_de_periodo_restringe_os_dias(client, ana, cab_ana, hoje_em_novembro):
    dados = client.get("/extratos/meu?inicio=2026-10-02&fim=2026-10-03", headers=cab_ana).json()
    assert [d["data"] for d in dados["dias"]] == ["2026-10-02", "2026-10-03"]
    assert dados["total_horas"] == "09:00"


def test_funcionario_ve_somente_o_proprio_extrato(client, db, ana, cab_ana, cab_admin, hoje_em_novembro):
    bia = novo_usuario(client, cab_admin, "Bia Lima", "111.444.777-35")
    semear(db, bia["id"], [utc(10, 5, 12), utc(10, 5, 16)])  # 09:00-13:00 de Bia

    dados_ana = client.get(f"/extratos/meu?{SEMANA}", headers=cab_ana).json()
    assert dados_ana["nome"] == "Ana Souza" and dados_ana["total_horas"] == "18:00"

    dados_bia = client.get(f"/extratos/meu?{SEMANA}", headers=entrar(client, bia, "4321")).json()
    assert dados_bia["nome"] == "Bia Lima" and dados_bia["total_horas"] == "04:00"


def test_administrador_tem_o_proprio_extrato_em_extratos_meu(client, admin, cab_admin):
    assert client.get(f"/extratos/meu?{SEMANA}", headers=cab_admin).json()["nome"] == "Carla Admin"


def test_periodo_padrao_e_validacoes(client, cab_ana):
    padrao = client.get("/extratos/meu", headers=cab_ana)
    assert padrao.status_code == 200 and len(padrao.json()["dias"]) == extrato_service.hoje_local().day

    assert client.get("/extratos/meu?inicio=2026-10-10&fim=2026-10-01", headers=cab_ana).status_code == 422
    assert client.get("/extratos/meu?inicio=2025-01-01&fim=2026-10-01", headers=cab_ana).status_code == 422
    assert client.get("/extratos/meu?inicio=nao-e-data", headers=cab_ana).status_code == 422


# ----------------------------------------------------------------------- PDF
def test_pdf_do_funcionario(client, ana, cab_ana, cab_admin, monkeypatch, hoje_em_novembro):
    monkeypatch.setattr(config, "EMPRESA_NOME", "LABELLE PILATES&FISIOTERAPIA LTDA")  # "&" quebraria o PDF sem escape
    registrar(client, cab_admin, ana["id"], "atestado", "2026-10-05", "2026-10-05", "consulta A&B")

    resposta = client.get(f"/extratos/meu/pdf?{SEMANA}", headers=cab_ana)
    texto = texto_pdf(resposta.content)

    assert resposta.status_code == 200 and resposta.headers["content-type"] == "application/pdf"
    assert "extrato-ana-souza-20261001-20261009.pdf" in resposta.headers["content-disposition"]
    for esperado in ("Extrato de Registros de Ponto", "LABELLE PILATES&FISIOTERAPIA LTDA", "Ana Souza",
                     "529.982.247-25", "01/10/2026 a 09/10/2026", "08:00 - 12:00 | 13:00 - 18:00",
                     "08:00 - (sem saída)", "Marcação incompleta", "Atestado - consulta A&B",
                     "Falta", "Faltas não justificadas", "Atestado (dias)", "18:00", "48:00", "-30:00"):
        assert esperado in texto, esperado
    assert "SEM assinatura" in texto


def test_pdf_do_mes_cabe_em_duas_paginas_no_maximo(client, ana, cab_ana, hoje_em_novembro):
    pdf = client.get(f"/extratos/meu/pdf?{PERIODO}", headers=cab_ana).content
    assert len(PdfReader(BytesIO(pdf)).pages) <= 2


def test_pdf_de_periodo_longo_pagina_e_repete_o_cabecalho(client, ana, cab_ana):
    pdf = client.get("/extratos/meu/pdf?inicio=2026-01-01&fim=2026-12-31", headers=cab_ana).content
    paginas = PdfReader(BytesIO(pdf)).pages
    assert len(paginas) > 2
    assert all("Marcações (entrada - saída)" in p.extract_text() for p in paginas)


def test_pdf_do_extrato_pode_ser_assinado(client, ana, cab_ana, certificado):
    pdf = client.get(f"/extratos/meu/pdf?{PERIODO}", headers=cab_ana).content
    assinaturas = PdfFileReader(BytesIO(pdf)).embedded_signatures
    status = validate_pdf_signature(assinaturas[0])

    assert len(assinaturas) == 1 and status.intact and status.valid
    assert "SEM assinatura" not in texto_pdf(pdf)


# --------------------------------------------------------------------- admin
def test_resumo_de_todos(client, ana, cab_admin, hoje_em_novembro):
    registrar(client, cab_admin, ana["id"], "ferias", "2026-10-05", "2026-10-07")
    novo_usuario(client, cab_admin, "Bia Lima", "111.444.777-35")  # sem marcações
    resumo = {r["nome"]: r for r in client.get(f"/admin/resumo?{SEMANA}", headers=cab_admin).json()}

    assert list(resumo) == ["Ana Souza", "Bia Lima"]  # administradores não entram no controle de horas
    ana_resumo = resumo["Ana Souza"]
    assert (ana_resumo["total_horas"], ana_resumo["saldo"], ana_resumo["faltas"], ana_resumo["ausencias"]) == ("18:00", "-14:00", 2, 3)
    assert ana_resumo["dias_incompletos"] == 1
    assert (resumo["Bia Lima"]["total_horas"], resumo["Bia Lima"]["faltas"]) == ("00:00", 7)


def test_admin_ve_o_extrato_de_qualquer_pessoa(client, ana, cab_admin, hoje_em_novembro):
    dados = client.get(f"/admin/extrato/{ana['id']}?{PERIODO}", headers=cab_admin).json()
    assert dados["nome"] == "Ana Souza" and dados["total_horas"] == "18:00" and len(dados["dias"]) == 31

    pdf = client.get(f"/admin/extrato/{ana['id']}/pdf?{PERIODO}", headers=cab_admin)
    assert pdf.status_code == 200 and "Ana Souza" in texto_pdf(pdf.content)

    assert client.get(f"/admin/extrato/999?{PERIODO}", headers=cab_admin).status_code == 404
    assert client.get(f"/admin/extrato/999/pdf?{PERIODO}", headers=cab_admin).status_code == 404


def test_zip_com_um_pdf_por_pessoa(client, db, ana, admin, cab_admin, certificado, hoje_em_novembro):
    bia = novo_usuario(client, cab_admin, "Bia Lima", "111.444.777-35")
    semear(db, bia["id"], [utc(10, 5, 12), utc(10, 5, 16)])

    resposta = client.get(f"/admin/extratos/zip?{PERIODO}", headers=cab_admin)
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
    for caminho in ("/extratos", "/static/js/extrato-ui.js"):
        assert client.get(caminho).status_code == 200
    assert client.get("/painel").status_code == 404 and client.get("/meu-extrato").status_code == 404


def test_fechamento_da_clinica_abona_todos_os_funcionarios(client, ana, cab_ana, cab_admin, hoje_em_novembro):
    resposta = client.post("/admin/fechamentos", json={
        "inicio": "2026-10-05", "fim": "2026-10-06", "motivo": "Feriado municipal"
    }, headers=cab_admin)
    assert resposta.status_code == 201 and len(resposta.json()) == 2
    dados = client.get(f"/extratos/meu?{SEMANA}", headers=cab_ana).json()
    dias = {d["data"]: d for d in dados["dias"]}
    assert dias["2026-10-05"]["situacao"] == "clinica_fechada"
    assert dias["2026-10-05"]["situacao_texto"] == "Clínica fechada"
    assert dias["2026-10-05"]["observacao"] == "Feriado municipal"
    assert (dados["horas_esperadas"], dados["faltas"]) == ("40:00", 3)
    assert client.delete(f"/admin/fechamentos/{resposta.json()[0]['id']}", headers=cab_admin).status_code == 204


def test_marcacao_manual_admin_completa_entrada_e_saida(client, usuario, cab_admin):
    entrada = client.post("/admin/marcacoes", json={
        "usuario_id": usuario["id"], "momento": "2026-10-05T08:00:00", "tipo": "entrada"
    }, headers=cab_admin)
    saida = client.post("/admin/marcacoes", json={
        "usuario_id": usuario["id"], "momento": "2026-10-05T17:00:00", "tipo": "saida"
    }, headers=cab_admin)
    assert entrada.status_code == 201, entrada.text
    assert saida.status_code == 201, saida.text
    assert entrada.json()["tipo"] == "entrada" and saida.json()["tipo"] == "saida"


def test_marcacao_manual_valida_sequencia_e_nao_permite_admin(client, usuario, admin, cab_admin):
    errada = client.post("/admin/marcacoes", json={
        "usuario_id": usuario["id"], "momento": "2026-10-05T08:00:00", "tipo": "saida"
    }, headers=cab_admin)
    admin_mark = client.post("/admin/marcacoes", json={
        "usuario_id": admin["id"], "momento": "2026-10-05T08:00:00", "tipo": "entrada"
    }, headers=cab_admin)
    assert errada.status_code == 409
    assert admin_mark.status_code == 404


def test_saldo_inicial_e_zero_por_padrao(client, cab_admin):
    pessoa = novo_usuario(client, cab_admin, "Bia Lima", "111.444.777-35")
    assert pessoa["saldo_inicial"] == 0


def test_saldo_inicial_compõe_saldo_do_extrato(client, cab_admin, hoje_em_novembro):
    pessoa = novo_usuario(client, cab_admin, "Bia Lima", "111.444.777-35", saldo_inicial=2.5)
    cab = entrar(client, pessoa, "4321")
    dados = client.get(f"/extratos/meu?{SEMANA}", headers=cab).json()
    assert dados["saldo_inicial"] == "02:30"
    assert dados["saldo"] == "-53:30"
