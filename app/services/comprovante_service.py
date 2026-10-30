"""Comprovante de Registro de Ponto do Trabalhador (Portaria 671, arts. 79 e 80).

O PDF é gerado sob demanda a partir da marcação (imutável), do cadastro do trabalhador
e dos dados do empregador em config. Se houver certificado configurado, é assinado.
"""
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app import config, models
from app.cpf import formatar_cpf
from app.services import assinatura_service

TITULO = "Comprovante de Registro de Ponto do Trabalhador"


class MarcacaoNaoEncontrada(LookupError):
    pass


class DadosEmpregadorIncompletos(RuntimeError):
    pass


def formatar_momento(momento: datetime) -> str:
    """Data, hora e fuso da marcação no horário da clínica. Ex.: 05/10/2026 14:32:10 (UTC-03:00)."""
    local = momento.astimezone(config.FUSO)
    deslocamento = local.strftime("%z")  # -0300
    return f"{local:%d/%m/%Y %H:%M:%S} (UTC{deslocamento[:3]}:{deslocamento[3:]})"


def _desenhar(marcacao: models.Marcacao, usuario: models.Usuario, sera_assinado: bool) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(TITULO)
    pdf.setAuthor(config.EMPRESA_NOME)

    largura, altura = A4
    margem = 20 * mm
    largura_texto = largura - 2 * margem
    y = altura - margem

    def texto(conteudo: str, fonte: str = "Helvetica", tamanho: int = 11, espaco: int = 5):
        nonlocal y
        for linha in simpleSplit(conteudo, fonte, tamanho, largura_texto):
            pdf.setFont(fonte, tamanho)
            pdf.drawString(margem, y, linha)
            y -= tamanho + espaco

    def secao(nome: str):
        nonlocal y
        y -= 12
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(margem, y, nome.upper())
        pdf.setLineWidth(0.4)
        pdf.line(margem, y - 4, largura - margem, y - 4)
        y -= 20  # linha de base do primeiro texto da seção, abaixo do traço

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(largura / 2, y - 6, TITULO)
    y -= 40

    texto(f"NSR: {marcacao.nsr}", "Helvetica-Bold", 14, 6)

    secao("Empregador")
    texto(config.EMPRESA_NOME)
    texto(f"CNPJ/CPF: {config.EMPRESA_CNPJ}")
    if config.EMPRESA_REGISTRO_ADICIONAL:
        texto(f"CEI/CAEPF/CNO: {config.EMPRESA_REGISTRO_ADICIONAL}")

    secao("Local da prestação do serviço")
    texto(config.EMPRESA_ENDERECO)

    secao("Trabalhador")
    texto(usuario.nome)
    texto(f"CPF: {formatar_cpf(usuario.cpf)}")

    secao("Marcação")
    texto(f"Data e horário: {formatar_momento(marcacao.momento)}")

    rodape = (
        "Documento assinado eletronicamente. Verifique a assinatura no seu leitor de PDF."
        if sera_assinado
        else "Documento SEM assinatura eletrônica (ambiente de teste, sem certificado configurado)."
    )
    pdf.setFont("Helvetica", 8)
    pdf.drawString(margem, margem, rodape)

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def gerar_comprovante(db: Session, nsr: int) -> bytes:
    if not (config.EMPRESA_NOME and config.EMPRESA_CNPJ and config.EMPRESA_ENDERECO):
        raise DadosEmpregadorIncompletos(
            "Configure EMPRESA_NOME, EMPRESA_CNPJ e EMPRESA_ENDERECO para emitir comprovantes."
        )
    marcacao = db.get(models.Marcacao, nsr)
    if marcacao is None:
        raise MarcacaoNaoEncontrada(nsr)
    usuario = db.get(models.Usuario, marcacao.usuario_id)

    assinar = assinatura_service.configurada()
    pdf = _desenhar(marcacao, usuario, sera_assinado=assinar)
    return assinatura_service.assinar(pdf) if assinar else pdf
