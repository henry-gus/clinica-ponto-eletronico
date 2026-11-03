from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas, security


class CpfDuplicado(Exception):
    pass


def criar_usuario(db: Session, dados: schemas.UsuarioCreate) -> models.Usuario:
    usuario = models.Usuario(
        nome=dados.nome,
        cpf=dados.cpf,
        cargo=dados.cargo,
        carga_horaria_diaria=dados.carga_horaria_diaria,
        pin_hash=security.hash_pin(dados.pin),
        papel=dados.papel,
        dias_trabalho=",".join(str(dia) for dia in dados.dias_trabalho),
        data_inicio=dados.data_inicio,
        saldo_inicial=dados.saldo_inicial,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise CpfDuplicado()
    db.refresh(usuario)
    return usuario
