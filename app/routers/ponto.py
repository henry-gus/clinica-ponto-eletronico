from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from app import config, models, schemas, security
from app.database import DbSession
from app.services import autenticacao_service, ponto_service

router = APIRouter(tags=["ponto"])


@router.get("/qr-token")
def gerar_qr_token(request: Request):
    token = security.criar_token_qr()
    base = (config.BASE_URL or str(request.base_url)).rstrip("/")
    return {"token": token, "url": f"{base}/bater-ponto?token={token}"}


@router.post("/ponto/{usuario_id}", response_model=schemas.MarcacaoResponse)
def registrar_ponto(
    usuario_id: int,
    dados: schemas.PontoRequest,
    token: Annotated[str, Query()],
    db: DbSession,
):
    if not security.validar_token_qr(token):
        raise HTTPException(403, "QR Code inválido ou expirado. Escaneie o código atual na recepção.")

    try:
        autenticacao_service.autenticar(db, usuario_id, dados.pin)
    except autenticacao_service.CredenciaisInvalidas:
        # Mesma mensagem para ID inexistente e PIN errado, para não revelar quais IDs existem.
        raise HTTPException(403, "ID ou PIN inválido.")
    except autenticacao_service.TentativasEsgotadas as erro:
        raise HTTPException(
            429,
            "Muitas tentativas com PIN errado. Aguarde alguns minutos.",
            headers={"Retry-After": str(erro.segundos)},
        )

    usuario = db.get(models.Usuario, usuario_id)
    if usuario is not None and usuario.eh_admin:
        raise HTTPException(403, "Administradores não registram ponto.")

    marcacao, tipo = ponto_service.registrar_marcacao(db, usuario_id)
    token = security.criar_token_comprovante(marcacao.nsr)
    return schemas.MarcacaoResponse(
        nsr=marcacao.nsr,
        usuario_id=usuario_id,
        tipo=tipo,
        momento=marcacao.momento,
        comprovante_url=f"/comprovantes/{marcacao.nsr}?token={token}",
    )
