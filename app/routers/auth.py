from fastapi import APIRouter, HTTPException

from app import config, schemas, security
from app.database import DbSession
from app.dependencias import UsuarioLogado
from app.services import autenticacao_service

router = APIRouter(prefix="/auth", tags=["autenticação"])


@router.post("/login", response_model=schemas.SessaoResponse)
def entrar(dados: schemas.LoginRequest, db: DbSession):
    """ID + PIN -> sessão. A resposta diz o perfil (`funcionario` ou `admin`)."""
    try:
        usuario = autenticacao_service.autenticar(db, dados.usuario_id, dados.pin)
    except autenticacao_service.CredenciaisInvalidas:
        raise HTTPException(403, "ID ou PIN inválido.")
    except autenticacao_service.TentativasEsgotadas as erro:
        raise HTTPException(
            429,
            "Muitas tentativas com PIN errado. Aguarde alguns minutos.",
            headers={"Retry-After": str(erro.segundos)},
        )
    return {
        "token": security.criar_token_sessao(usuario.id),
        "nome": usuario.nome,
        "papel": usuario.papel,
        "expira_em_segundos": config.SESSAO_MINUTOS * 60,
    }


@router.get("/eu", response_model=schemas.EuResponse)
def quem_sou_eu(usuario: UsuarioLogado):
    """Confere a sessão e devolve quem está logado (a tela usa isso ao recarregar)."""
    return {"usuario_id": usuario.id, "nome": usuario.nome, "papel": usuario.papel}
