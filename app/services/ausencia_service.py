from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models


class UsuarioInexistente(LookupError):
    pass


class AusenciaInexistente(LookupError):
    pass


class ConflitoDeAusencia(Exception):
    """Já existe ausência em algum dos dias pedidos."""

    def __init__(self, datas: list[date]):
        super().__init__(datas)
        self.datas = datas


def corrigir(
    db: Session, admin: models.Usuario, usuario_id: int, tipo: str, inicio: date, fim: date, observacao: str | None
) -> list[models.Ausencia]:
    """Uma ausência por dia do intervalo (inclusive fins de semana: férias e atestados contam dias corridos).

    Se algum dia já tiver ausência, nada é gravado: o administrador remove a antiga e registra de novo.
    """
    if db.get(models.Usuario, usuario_id) is None:
        raise UsuarioInexistente(usuario_id)

    existentes = (
        db.query(models.Ausencia.data)
        .filter(models.Ausencia.usuario_id == usuario_id, models.Ausencia.data >= inicio, models.Ausencia.data <= fim)
        .order_by(models.Ausencia.data)
        .all()
    )
    if existentes:
        raise ConflitoDeAusencia([linha.data for linha in existentes])

    novas = [
        models.Ausencia(
            usuario_id=usuario_id,
            data=inicio + timedelta(days=i),
            tipo=tipo,
            observacao=(observacao or "").strip() or None,
            registrado_por=admin.id,
        )
        for i in range((fim - inicio).days + 1)
    ]
    db.add_all(novas)
    try:
        db.commit()
    except IntegrityError:  # duas requisições ao mesmo tempo
        db.rollback()
        raise ConflitoDeAusencia([])
    for ausencia in novas:
        db.refresh(ausencia)
    return novas


def remover(db: Session, ausencia_id: int) -> None:
    ausencia = db.get(models.Ausencia, ausencia_id)
    if ausencia is None:
        raise AusenciaInexistente(ausencia_id)
    db.delete(ausencia)
    db.commit()
