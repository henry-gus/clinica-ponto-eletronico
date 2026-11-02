from fastapi import APIRouter, Depends, HTTPException

from app import models, schemas
from app.database import DbSession
from app.dependencias import exigir_admin
from app.services import usuario_service

router = APIRouter(prefix="/usuarios", tags=["usuários"], dependencies=[Depends(exigir_admin)])


@router.post("/", response_model=schemas.UsuarioResponse)
def criar_usuario(dados: schemas.UsuarioCreate, db: DbSession):
    try:
        return usuario_service.criar_usuario(db, dados)
    except usuario_service.CpfDuplicado:
        raise HTTPException(409, "Já existe um funcionário com este CPF.")


@router.get("/", response_model=list[schemas.UsuarioResponse])
def listar_usuarios(db: DbSession):
    return db.query(models.Usuario).order_by(models.Usuario.nome, models.Usuario.id).all()
