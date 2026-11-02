"""PDF do extrato de marcações (a "folha de ponto" do período)."""
import re
import unicodedata
import zipfile
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app import config
from app.cpf import formatar_cpf
from app.services import assinatura_service
from app.services.extrato_service import Extrato, formatar_duracao, hora_local

TITULO = "Extrato de Registros de Ponto"

_BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9, leading=11)
_TITULO = ParagraphStyle("titulo", parent=_BASE, fontName="Helvetica-Bold", fontSize=15, leading=18, alignment=TA_CENTER)
_ROTULO = ParagraphStyle("rotulo", parent=_BASE, fontName="Helvetica-Bold", textColor=colors.HexColor("#444444"))
_CABECALHO = ParagraphStyle("cabecalho", parent=_BASE, fontName="Helvetica-Bold")
_NOTA = ParagraphStyle("nota", parent=_BASE, fontSize=7.5, leading=9, textColor=colors.HexColor("#555555"))


def _p(texto: str, estilo: ParagraphStyle = _BASE) -> Paragraph:
    # Todo texto vem de fora (nome da clínica, do funcionário...): "&" e "<" quebrariam o Paragraph.
    return Paragraph(escape(texto), estilo)


def _periodo(extrato: Extrato) -> str:
    return f"{extrato.inicio:%d/%m/%Y} a {extrato.fim:%d/%m/%Y}"


def _texto_marcacoes(dia) -> str:
    partes = [f"{hora_local(e)} - {hora_local(s)}" for e, s in dia.pares]
    if dia.sobra:
        partes.append(f"{hora_local(dia.sobra)} - (sem saída)")
    return " | ".join(partes)


def _rodape(sera_assinado: bool):
    aviso = (
        "Documento assinado eletronicamente. Verifique a assinatura no seu leitor de PDF."
        if sera_assinado
        else "Documento SEM assinatura eletrônica (ambiente de teste, sem certificado configurado)."
    )

    def desenhar(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(documento.leftMargin, 10 * mm, aviso)
        canvas.drawRightString(A4[0] - documento.rightMargin, 10 * mm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    return desenhar


def _historia(extrato: Extrato) -> list:
    usuario = extrato.usuario
    emitido = datetime.now(config.FUSO).strftime("%d/%m/%Y %H:%M")

    identificacao = [
        ("Empregador", f"{config.EMPRESA_NOME} - CNPJ/CPF {config.EMPRESA_CNPJ}"),
        ("Local", config.EMPRESA_ENDERECO),
        ("Trabalhador", f"{usuario.nome} - CPF {formatar_cpf(usuario.cpf)} - {usuario.cargo}"),
        ("Período", _periodo(extrato)),
        ("Jornada diária", f"{formatar_duracao(usuario.carga_horaria_diaria * 3600)} h"),
        ("Emitido em", emitido),
    ]
    quadro_id = Table(
        [[_p(rotulo, _ROTULO), _p(valor)] for rotulo, valor in identificacao],
        colWidths=[28 * mm, 142 * mm],
    )
    quadro_id.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1)]))

    linhas = [[_p(t, _CABECALHO) for t in ("Data", "Dia", "Marcações (entrada - saída)", "Horas", "Observação")]]
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for indice, dia in enumerate(extrato.dias, start=1):
        linhas.append([
            _p(f"{dia.data:%d/%m/%Y}"),
            _p(dia.dia_semana),
            _p(_texto_marcacoes(dia)),
            _p(formatar_duracao(dia.segundos) if dia.pares else ""),
            _p("Marcação incompleta" if dia.incompleto else ""),
        ])
        if dia.data.weekday() >= 5:
            estilo.append(("BACKGROUND", (0, indice), (-1, indice), colors.HexColor("#f3f3f3")))
    tabela = Table(linhas, colWidths=[22 * mm, 12 * mm, 84 * mm, 16 * mm, 36 * mm], repeatRows=1)
    tabela.setStyle(TableStyle(estilo))

    totais = Table(
        [
            [_p("Dias com marcação completa", _ROTULO), _p(str(extrato.dias_trabalhados))],
            [_p("Total de horas trabalhadas", _ROTULO), _p(formatar_duracao(extrato.total_segundos))],
            [_p("Horas esperadas (dias x jornada)", _ROTULO), _p(formatar_duracao(extrato.esperado_segundos))],
            [_p("Saldo do período", _ROTULO), _p(formatar_duracao(extrato.saldo_segundos))],
        ],
        colWidths=[60 * mm, 30 * mm],
        hAlign="LEFT",
    )
    totais.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))

    nota = _p(
        "Extrato informativo, gerado a partir das marcações registradas (horários no fuso da clínica). "
        "Só entram nas horas os pares entrada-saída: uma marcação sem par fica registrada, mas não soma horas.",
        _NOTA,
    )
    return [_p(TITULO, _TITULO), Spacer(1, 6 * mm), quadro_id, Spacer(1, 5 * mm), tabela, Spacer(1, 4 * mm), totais, Spacer(1, 3 * mm), nota]


def gerar_pdf(extrato: Extrato) -> bytes:
    assinar = assinatura_service.configurada()
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
        title=f"{TITULO} - {extrato.usuario.nome}", author=config.EMPRESA_NOME,
    )
    rodape = _rodape(assinar)
    documento.build(_historia(extrato), onFirstPage=rodape, onLaterPages=rodape)
    pdf = buffer.getvalue()
    return assinatura_service.assinar(pdf) if assinar else pdf


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower() or "funcionario"


def nome_arquivo(extrato: Extrato) -> str:
    return f"extrato-{_slug(extrato.usuario.nome)}-{extrato.inicio:%Y%m%d}-{extrato.fim:%Y%m%d}.pdf"


def gerar_zip(extratos: list[Extrato]) -> bytes:
    """Um PDF por funcionário (cada um com a sua assinatura), reunidos num ZIP."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as arquivo:
        for extrato in extratos:
            arquivo.writestr(f"{extrato.usuario.id:03d}-{nome_arquivo(extrato)}", gerar_pdf(extrato))
    return buffer.getvalue()
