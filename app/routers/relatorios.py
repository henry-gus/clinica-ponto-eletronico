from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app import config, models, schemas, security
from app.database import DbSession
from app.services import relatorio_service

router = APIRouter(tags=["relatórios"], dependencies=[Depends(security.exigir_admin)])


@router.get("/relatorio/{usuario_id}", response_model=schemas.RelatorioResponse)
def relatorio_mensal(
    usuario_id: int,
    db: DbSession,
    mes: int = Query(ge=1, le=12),
    ano: int = Query(ge=2000, le=2100),
):
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(404, "Usuário não encontrado")

    # O mês é delimitado no fuso da clínica e convertido para UTC só para consultar.
    inicio = datetime(ano, mes, 1, tzinfo=config.FUSO)
    fim = datetime(ano + (mes == 12), mes % 12 + 1, 1, tzinfo=config.FUSO)
    marcacoes = (
        db.query(models.Marcacao)
        .filter(
            models.Marcacao.usuario_id == usuario_id,
            models.Marcacao.momento >= inicio.astimezone(timezone.utc),
            models.Marcacao.momento < fim.astimezone(timezone.utc),
        )
        .order_by(models.Marcacao.nsr)
        .all()
    )
    resumo = relatorio_service.calcular_relatorio(
        [m.momento for m in marcacoes], usuario.carga_horaria_diaria
    )
    return {"usuario_id": usuario_id, "mes": mes, "ano": ano, **resumo}
