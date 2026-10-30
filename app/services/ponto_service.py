from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import config, models


def _limites_do_dia_local(agora: datetime) -> tuple[datetime, datetime]:
    """Início e fim (em UTC) do dia local em que `agora` cai."""
    inicio_local = agora.astimezone(config.FUSO).replace(hour=0, minute=0, second=0, microsecond=0)
    fim_local = inicio_local + timedelta(days=1)
    return inicio_local.astimezone(timezone.utc), fim_local.astimezone(timezone.utc)


def registrar_marcacao(
    db: Session, usuario_id: int, agora: datetime | None = None
) -> tuple[models.Marcacao, str]:
    """Insere uma marcação e diz se foi entrada ou saída.

    A 1ª marcação do dia local é entrada, a 2ª saída, a 3ª entrada... Como a contagem
    é por dia, uma saída esquecida não contamina o dia seguinte.
    """
    agora = agora or datetime.now(timezone.utc)
    inicio, fim = _limites_do_dia_local(agora)
    anteriores = (
        db.query(models.Marcacao)
        .filter(
            models.Marcacao.usuario_id == usuario_id,
            models.Marcacao.momento >= inicio,
            models.Marcacao.momento < fim,
        )
        .count()
    )
    tipo = "entrada" if anteriores % 2 == 0 else "saida"

    marcacao = models.Marcacao(usuario_id=usuario_id, momento=agora)
    db.add(marcacao)
    db.commit()
    db.refresh(marcacao)
    return marcacao, tipo
