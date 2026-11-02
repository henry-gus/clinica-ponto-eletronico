from fastapi import APIRouter, HTTPException, Response

from app import config, schemas, security
from app.database import DbSession
from app.dependencias import Periodo, UsuarioLogado
from app.services import autenticacao_service, extrato_pdf_service, extrato_service

router = APIRouter(prefix="/funcionario", tags=["funcionário"])


@router.post("/login", response_model=schemas.SessaoResponse)
def entrar(dados: schemas.LoginRequest, db: DbSession):
    """ID + PIN -> sessão curta para consultar o próprio extrato."""
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
        "expira_em_segundos": config.SESSAO_FUNCIONARIO_MINUTOS * 60,
    }


@router.get("/extrato", response_model=schemas.ExtratoResponse)
def meu_extrato(usuario: UsuarioLogado, db: DbSession, periodo: Periodo):
    inicio, fim = periodo
    return extrato_service.para_resposta(extrato_service.extrato_do_usuario(db, usuario, inicio, fim))


@router.get("/extrato/pdf")
def meu_extrato_pdf(usuario: UsuarioLogado, db: DbSession, periodo: Periodo):
    inicio, fim = periodo
    extrato = extrato_service.extrato_do_usuario(db, usuario, inicio, fim)
    return Response(
        content=extrato_pdf_service.gerar_pdf(extrato),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{extrato_pdf_service.nome_arquivo(extrato)}"'},
    )
