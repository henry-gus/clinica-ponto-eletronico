from datetime import date, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app import config, models, security
from app.database import DbSession
from app.services.extrato_service import MAX_DIAS_PERIODO


def usuario_logado(db: DbSession, authorization: str = Header(default="")) -> models.Usuario:
    """Funcionário identificado pela sessão (header `Authorization: Bearer <token>`)."""
    esquema, _, token = authorization.partition(" ")
    uid = security.validar_token_sessao(token) if esquema.lower() == "bearer" else None
    usuario = db.get(models.Usuario, uid) if uid is not None else None
    if usuario is None:
        raise HTTPException(401, "Sessão expirada. Entre novamente com ID e PIN.")
    return usuario


UsuarioLogado = Annotated[models.Usuario, Depends(usuario_logado)]


def periodo(inicio: date | None = None, fim: date | None = None) -> tuple[date, date]:
    """Período (datas inclusivas, no fuso da clínica). Padrão: do dia 1º do mês até hoje."""
    hoje = datetime.now(config.FUSO).date()
    inicio = inicio or hoje.replace(day=1)
    fim = fim or hoje
    if fim < inicio:
        raise HTTPException(422, "A data final deve ser igual ou posterior à data inicial.")
    if (fim - inicio).days >= MAX_DIAS_PERIODO:
        raise HTTPException(422, f"O período pode ter no máximo {MAX_DIAS_PERIODO} dias.")
    return inicio, fim


Periodo = Annotated[tuple[date, date], Depends(periodo)]
