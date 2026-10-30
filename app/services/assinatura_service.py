"""Assinatura eletrônica de PDFs (PAdES) com certificado .p12/.pfx."""
from functools import lru_cache
from io import BytesIO

from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers
from pyhanko.sign.fields import SigSeedSubFilter

from app import config


def configurada() -> bool:
    return bool(config.CERT_P12_PATH)


@lru_cache(maxsize=4)
def _carregar_signer(caminho: str, senha: str) -> signers.SimpleSigner:
    return signers.SimpleSigner.load_pkcs12(
        pfx_file=caminho, passphrase=senha.encode() if senha else None
    )


def assinar(pdf: bytes) -> bytes:
    signer = _carregar_signer(config.CERT_P12_PATH, config.CERT_P12_SENHA)
    metadados = signers.PdfSignatureMetadata(
        field_name="AssinaturaComprovante",
        subfilter=SigSeedSubFilter.PADES,
        reason="Comprovante de Registro de Ponto do Trabalhador",
    )
    escritor = IncrementalPdfFileWriter(BytesIO(pdf))
    return signers.sign_pdf(escritor, metadados, signer=signer).getvalue()
