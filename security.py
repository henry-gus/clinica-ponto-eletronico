from datetime import datetime, timedelta, timezone

import jwt

# ATENÇÃO: Em produção, essa chave deve vir de um arquivo .env
# Nunca compartilhe essa chave, ela é o que garante que ninguém falsifique o token
SECRET_KEY = "chave_super_secreta_da_clinica" 
ALGORITHM = "HS256"

def criar_token_qr() -> str:
    # Define que o token só vale por 60 segundos a partir de agora
    expiracao = datetime.now(timezone.utc) + timedelta(seconds=60)
    
    payload = {
        "tipo": "qr_ponto",
        "exp": expiracao
    }
    
    # Gera a string codificada
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def validar_token_qr(token: str) -> bool:
    try:
        # Tenta decodificar. O pyjwt verifica a validade e a expiração automaticamente
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        tipo = payload.get("tipo")
        
        return tipo == "qr_ponto"
    except jwt.ExpiredSignatureError:
        # Cai aqui se já tiver passado dos 30 segundos
        return False 
    except jwt.InvalidTokenError:
        # Cai aqui se tentarem inventar um token falso
        return False