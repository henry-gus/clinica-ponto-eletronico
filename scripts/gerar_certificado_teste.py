"""Gera um certificado AUTOASSINADO de teste (.p12) para assinar os comprovantes.

ATENÇÃO: não é ICP-Brasil e não tem validade legal. Serve para desenvolvimento e demonstração.
Uso: python -m scripts.gerar_certificado_teste [--saida certs/teste.p12] [--senha teste]
"""
import argparse
import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


def gerar(caminho: str, senha: str) -> None:
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Clinica Ponto - CERTIFICADO DE TESTE (nao ICP-Brasil)")]
    )
    agora = datetime.datetime.now(datetime.timezone.utc)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - datetime.timedelta(minutes=5))
        .not_valid_after(agora + datetime.timedelta(days=365))
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=True, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(chave, hashes.SHA256())
    )
    conteudo = pkcs12.serialize_key_and_certificates(
        b"clinica-ponto-teste", chave, certificado, None,
        serialization.BestAvailableEncryption(senha.encode()),
    )
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--saida", default="certs/teste.p12")
    argumentos.add_argument("--senha", default="teste")
    dados = argumentos.parse_args()
    gerar(dados.saida, dados.senha)
    print(f"Certificado de teste gerado em {dados.saida}")
