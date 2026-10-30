import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

from app import config

ALGORITHM = "HS256"


# --- QR Code rotativo -------------------------------------------------------
def criar_token_qr() -> str:
    expiracao = datetime.now(timezone.utc) + timedelta(seconds=config.QR_VALIDADE_SEGUNDOS)
    return jwt.encode({"tipo": "qr_ponto", "exp": expiracao}, config.SECRET_KEY, algorithm=ALGORITHM)


def validar_token_qr(token: str) -> bool:
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:  # inclui token expirado
        return False
    return payload.get("tipo") == "qr_ponto"


# --- Link do comprovante ----------------------------------------------------
def criar_token_comprovante(nsr: int) -> str:
    """Token que dá acesso a UM comprovante (o da marcação `nsr`)."""
    expiracao = datetime.now(timezone.utc) + timedelta(hours=config.COMPROVANTE_VALIDADE_HORAS)
    return jwt.encode(
        {"tipo": "comprovante", "nsr": nsr, "exp": expiracao}, config.SECRET_KEY, algorithm=ALGORITHM
    )


def validar_token_comprovante(token: str, nsr: int) -> bool:
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return False
    return payload.get("tipo") == "comprovante" and payload.get("nsr") == nsr


# --- PIN do funcionário -----------------------------------------------------
def _scrypt(pin: str, salt: bytes) -> bytes:
    return hashlib.scrypt(pin.encode(), salt=salt, n=2**14, r=8, p=1)


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    return f"{salt.hex()}:{_scrypt(pin, salt).hex()}"


def verificar_pin(pin: str, armazenado: str) -> bool:
    salt_hex, hash_hex = armazenado.split(":")
    return hmac.compare_digest(_scrypt(pin, bytes.fromhex(salt_hex)).hex(), hash_hex)


# --- Administrador ----------------------------------------------------------
def admin_valido(token: str) -> bool:
    return hmac.compare_digest(token.encode(), config.ADMIN_TOKEN.encode())


def exigir_admin(x_admin_token: str = Header(default="")):
    if not admin_valido(x_admin_token):
        raise HTTPException(status_code=401, detail="Token de administrador inválido")
