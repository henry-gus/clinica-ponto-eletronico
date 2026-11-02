from fastapi import APIRouter, Depends, HTTPException, Response

from app import models, schemas, security
from app.database import DbSession
from app.dependencias import Periodo
from app.services import extrato_pdf_service, extrato_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(security.exigir_admin)])


def _pdf(conteudo: bytes, nome: str, tipo: str = "application/pdf") -> Response:
    disposicao = "inline" if tipo == "application/pdf" else "attachment"
    return Response(content=conteudo, media_type=tipo, headers={"Content-Disposition": f'{disposicao}; filename="{nome}"'})


def _usuario(db, usuario_id: int) -> models.Usuario:
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(404, "Funcionário não encontrado.")
    return usuario


@router.get("/resumo", response_model=list[schemas.ResumoResponse])
def resumo(db: DbSession, periodo: Periodo):
    """Uma linha por funcionário com os totais do período."""
    inicio, fim = periodo
    return [extrato_service.para_resumo(e) for e in extrato_service.extratos_de_todos(db, inicio, fim)]


@router.get("/extrato/{usuario_id}", response_model=schemas.ExtratoResponse)
def extrato(usuario_id: int, db: DbSession, periodo: Periodo):
    inicio, fim = periodo
    return extrato_service.para_resposta(
        extrato_service.extrato_do_usuario(db, _usuario(db, usuario_id), inicio, fim)
    )


@router.get("/extrato/{usuario_id}/pdf")
def extrato_pdf(usuario_id: int, db: DbSession, periodo: Periodo):
    inicio, fim = periodo
    dados = extrato_service.extrato_do_usuario(db, _usuario(db, usuario_id), inicio, fim)
    return _pdf(extrato_pdf_service.gerar_pdf(dados), extrato_pdf_service.nome_arquivo(dados))


@router.get("/extratos/zip")
def extratos_zip(db: DbSession, periodo: Periodo):
    """Um PDF por funcionário, num único ZIP."""
    inicio, fim = periodo
    todos = extrato_service.extratos_de_todos(db, inicio, fim)
    if not todos:
        raise HTTPException(404, "Nenhum funcionário cadastrado.")
    return _pdf(
        extrato_pdf_service.gerar_zip(todos),
        f"extratos-{inicio:%Y%m%d}-{fim:%Y%m%d}.zip",
        tipo="application/zip",
    )
