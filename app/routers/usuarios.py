from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from app import models, schemas, security
from app.database import DbSession

router = APIRouter(prefix="/usuarios", tags=["usuários"], dependencies=[Depends(security.exigir_admin)])


@router.post("/", response_model=schemas.UsuarioResponse)
def criar_usuario(dados: schemas.UsuarioCreate, db: DbSession):
    usuario = models.Usuario(
        nome=dados.nome,
        cpf=dados.cpf,
        cargo=dados.cargo,
        carga_horaria_diaria=dados.carga_horaria_diaria,
        pin_hash=security.hash_pin(dados.pin),
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Já existe um funcionário com este CPF.")
    db.refresh(usuario)
    return usuario
