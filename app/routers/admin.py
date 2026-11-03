from fastapi import APIRouter, Depends, HTTPException, Response

from app import models, schemas
from app.database import DbSession
from app.dependencias import Admin, Periodo, exigir_admin, validar_intervalo
from app.services import ausencia_service, fechamento_service, extrato_pdf_service, extrato_service, ponto_service

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
def corrigir_ausencia(dados: schemas.AusenciaCreate, db: DbSession, admin: Admin):
    """Corrige ausências individuais: atestado, falta justificada ou férias."""
    validar_intervalo(dados.inicio, dados.fim)
    try:
        return ausencia_service.corrigir(
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


@router.post("/fechamentos", response_model=list[schemas.FechamentoResponse], status_code=201)
def registrar_fechamento(dados: schemas.FechamentoCreate, db: DbSession, admin: Admin):
    validar_intervalo(dados.inicio, dados.fim)
    try:
        return fechamento_service.registrar(db, admin, dados.inicio, dados.fim, dados.motivo)
    except fechamento_service.ConflitoDeFechamento as erro:
        datas = ", ".join(f"{d:%d/%m/%Y}" for d in erro.datas)
        raise HTTPException(409, f"A clínica já possui fechamento registrado em: {datas}.")


@router.delete("/fechamentos/{fechamento_id}", status_code=204)
def remover_fechamento(fechamento_id: int, db: DbSession):
    try:
        fechamento_service.remover(db, fechamento_id)
    except LookupError:
        raise HTTPException(404, "Fechamento não encontrado.")


@router.post("/marcacoes", response_model=schemas.MarcacaoResponse, status_code=201)
def criar_marcacao_manual(dados: schemas.MarcacaoAdminCreate, db: DbSession, admin: Admin):
    try:
        marcacao, tipo = ponto_service.registrar_marcacao_admin(
            db, dados.usuario_id, dados.momento, dados.tipo, admin.id
        )
    except LookupError:
        raise HTTPException(404, "Funcionário não encontrado.")
    except ponto_service.TipoMarcacaoInvalido as erro:
        raise HTTPException(409, str(erro))
    return schemas.MarcacaoResponse(
        nsr=marcacao.nsr, usuario_id=marcacao.usuario_id, tipo=tipo,
        momento=marcacao.momento, comprovante_url=None,
    )
