from fastapi import APIRouter, Depends, HTTPException, Response

from app import models, schemas
from app.database import DbSession
from app.dependencias import Admin, Periodo, exigir_admin, validar_intervalo
from app.services import ausencia_service, extrato_pdf_service, extrato_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(exigir_admin)])


def _arquivo(conteudo: bytes, nome: str, tipo: str = "application/pdf") -> Response:
    disposicao = "inline" if tipo == "application/pdf" else "attachment"
    return Response(content=conteudo, media_type=tipo, headers={"Content-Disposition": f'{disposicao}; filename="{nome}"'})


def _usuario(db, usuario_id: int) -> models.Usuario:
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(404, "Funcionário não encontrado.")
    return usuario


@router.get("/resumo", response_model=list[schemas.ResumoResponse])
def resumo(db: DbSession, periodo: Periodo):
    """Uma linha por pessoa cadastrada com os totais do período."""
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
    return _arquivo(extrato_pdf_service.gerar_pdf(dados), extrato_pdf_service.nome_arquivo(dados))


@router.get("/extratos/zip")
def extratos_zip(db: DbSession, periodo: Periodo):
    """Um PDF por pessoa, num único ZIP."""
    inicio, fim = periodo
    todos = extrato_service.extratos_de_todos(db, inicio, fim)
    if not todos:
        raise HTTPException(404, "Nenhum funcionário cadastrado.")
    return _arquivo(
        extrato_pdf_service.gerar_zip(todos),
        f"extratos-{inicio:%Y%m%d}-{fim:%Y%m%d}.zip",
        tipo="application/zip",
    )


@router.post("/ausencias", response_model=list[schemas.AusenciaResponse], status_code=201)
def registrar_ausencia(dados: schemas.AusenciaCreate, db: DbSession, admin: Admin):
    """Atestado, falta justificada ou férias: uma ausência por dia, de `inicio` a `fim`."""
    validar_intervalo(dados.inicio, dados.fim)
    try:
        return ausencia_service.registrar(
            db, admin, dados.usuario_id, dados.tipo, dados.inicio, dados.fim, dados.observacao
        )
    except ausencia_service.UsuarioInexistente:
        raise HTTPException(404, "Funcionário não encontrado.")
    except ausencia_service.ConflitoDeAusencia as erro:
        datas = ", ".join(f"{d:%d/%m/%Y}" for d in erro.datas)
        raise HTTPException(409, f"Já existe ausência registrada em: {datas}. Remova-a antes de registrar de novo.")


@router.delete("/ausencias/{ausencia_id}", status_code=204)
def remover_ausencia(ausencia_id: int, db: DbSession):
    try:
        ausencia_service.remover(db, ausencia_id)
    except ausencia_service.AusenciaInexistente:
        raise HTTPException(404, "Registro de ausência não encontrado.")
