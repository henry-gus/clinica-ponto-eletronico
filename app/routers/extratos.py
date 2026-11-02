from fastapi import APIRouter, Response

from app.database import DbSession
from app.dependencias import Periodo, UsuarioLogado
from app.schemas import ExtratoResponse
from app.services import extrato_pdf_service, extrato_service

router = APIRouter(prefix="/extratos", tags=["extratos"])


@router.get("/meu", response_model=ExtratoResponse)
def meu_extrato(usuario: UsuarioLogado, db: DbSession, periodo: Periodo):
    """Extrato de quem está logado (qualquer perfil)."""
    inicio, fim = periodo
    return extrato_service.para_resposta(extrato_service.extrato_do_usuario(db, usuario, inicio, fim))


@router.get("/meu/pdf")
def meu_extrato_pdf(usuario: UsuarioLogado, db: DbSession, periodo: Periodo):
    inicio, fim = periodo
    extrato = extrato_service.extrato_do_usuario(db, usuario, inicio, fim)
    return Response(
        content=extrato_pdf_service.gerar_pdf(extrato),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{extrato_pdf_service.nome_arquivo(extrato)}"'},
    )
