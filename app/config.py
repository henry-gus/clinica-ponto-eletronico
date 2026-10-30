"""Configurações lidas de variáveis de ambiente (veja .env.example)."""
import os
from zoneinfo import ZoneInfo


def _exigir(nome: str) -> str:
    valor = os.getenv(nome)
    if not valor:
        raise RuntimeError(f"Variável de ambiente {nome} não definida. Veja o .env.example.")
    return valor


SECRET_KEY = _exigir("SECRET_KEY")
ADMIN_TOKEN = _exigir("ADMIN_TOKEN")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ponto.db")

# URL pública usada dentro do QR Code. Se vazia, usa o endereço pelo qual a recepção foi aberta.
BASE_URL = os.getenv("BASE_URL", "")

# Fuso da clínica: define o que conta como "dia" e "mês" nos relatórios e nos comprovantes.
FUSO = ZoneInfo(os.getenv("TZ_CLINICA", "America/Sao_Paulo"))

# O QR é renovado a cada 60s na recepção; 120s dá tempo de abrir a página e digitar ID e PIN.
QR_VALIDADE_SEGUNDOS = int(os.getenv("QR_VALIDADE_SEGUNDOS", "120"))

# --- Comprovante de registro de ponto (Portaria 671, arts. 79 e 80) ---------
# Dados do empregador impressos em todo comprovante.
EMPRESA_NOME = os.getenv("EMPRESA_NOME", "")
EMPRESA_CNPJ = os.getenv("EMPRESA_CNPJ", "")  # ou CPF, se o empregador for pessoa física
EMPRESA_REGISTRO_ADICIONAL = os.getenv("EMPRESA_CEI_CAEPF_CNO", "")  # opcional
EMPRESA_ENDERECO = os.getenv("EMPRESA_ENDERECO", "")  # local da prestação do serviço

# O link do comprovante entregue ao trabalhador vale por este tempo (mínimo legal: 48h).
COMPROVANTE_VALIDADE_HORAS = int(os.getenv("COMPROVANTE_VALIDADE_HORAS", "72"))

# Certificado digital (.p12/.pfx) para assinar o PDF. Vazio = comprovante sem assinatura.
CERT_P12_PATH = os.getenv("CERT_P12_PATH", "")
CERT_P12_SENHA = os.getenv("CERT_P12_SENHA", "")
