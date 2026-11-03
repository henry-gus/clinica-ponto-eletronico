from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models


class ConflitoDeFechamento(Exception):
    def __init__(self, datas: list[date]):
        self.datas = datas


def registrar(db: Session, admin: models.Usuario, inicio: date, fim: date, motivo: str | None):
    existentes = db.query(models.FechamentoClinica.data).filter(
        models.FechamentoClinica.data >= inicio, models.FechamentoClinica.data <= fim
    ).order_by(models.FechamentoClinica.data).all()
    if existentes:
        raise ConflitoDeFechamento([item.data for item in existentes])
    motivo = (motivo or "").strip() or None
    novos = [models.FechamentoClinica(
        data=inicio + timedelta(days=i), motivo=motivo, registrado_por=admin.id
    ) for i in range((fim - inicio).days + 1)]
    db.add_all(novos)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflitoDeFechamento([])
    for item in novos:
        db.refresh(item)
    return novos


def remover(db: Session, fechamento_id: int):
    item = db.get(models.FechamentoClinica, fechamento_id)
    if item is None:
        raise LookupError("Fechamento não encontrado.")
    db.delete(item)
    db.commit()
