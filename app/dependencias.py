from datetime import date, datetime
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import config, models, security
from app.database import DbSession
from app.services.extrato_service import MAX_DIAS_PERIODO

# Faz o botão "Authorize" aparecer em /docs: cole o token devolvido por POST /auth/login.
_bearer = HTTPBearer(auto_error=False, description="Token devolvido por POST /auth/login")


def sessao_opcional(
    db: DbSession, credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> models.Usuario | None:
    """Quem está logado, ou None. O perfil (funcionário/admin) é sempre lido do banco, nunca do token."""
    if credenciais is None:
        return None
    uid = security.validar_token_sessao(credenciais.credentials)
    return db.get(models.Usuario, uid) if uid is not None else None


def usuario_logado(usuario: Annotated[models.Usuario | None, Depends(sessao_opcional)]) -> models.Usuario:
    if usuario is None:
        raise HTTPException(401, "Sessão expirada. Entre novamente com ID e PIN.")
    return usuario


UsuarioLogado = Annotated[models.Usuario, Depends(usuario_logado)]


def exigir_admin(usuario: UsuarioLogado) -> models.Usuario:
    if not usuario.eh_admin:
        raise HTTPException(403, "Acesso restrito ao administrador.")
    return usuario


Admin = Annotated[models.Usuario, Depends(exigir_admin)]


def validar_intervalo(inicio: date, fim: date) -> None:
    if fim < inicio:
        raise HTTPException(422, "A data final deve ser igual ou posterior à data inicial.")
    if (fim - inicio).days >= MAX_DIAS_PERIODO:
        raise HTTPException(422, f"O período pode ter no máximo {MAX_DIAS_PERIODO} dias.")


def periodo(inicio: date | None = None, fim: date | None = None) -> tuple[date, date]:
    """Período (datas inclusivas, no fuso da clínica). Padrão: do dia 1º do mês até hoje."""
    hoje = datetime.now(config.FUSO).date()
    inicio = inicio or hoje.replace(day=1)
    fim = fim or hoje
    validar_intervalo(inicio, fim)
    return inicio, fim


Periodo = Annotated[tuple[date, date], Depends(periodo)]
