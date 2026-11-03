from datetime import date, datetime, timedelta, timezone

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


class TipoMarcacaoInvalido(Exception):
    pass


def registrar_marcacao_admin(
    db: Session, usuario_id: int, momento: datetime, tipo: str, admin_id: int
) -> tuple[models.Marcacao, str]:
    """Registra uma marcação retroativa lançada pelo administrador, mantendo a ordem entrada/saída."""
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None or usuario.eh_admin:
        raise LookupError("Funcionário não encontrado.")
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=config.FUSO)
    momento = momento.astimezone(timezone.utc)
    inicio, fim = _limites_do_dia_local(momento)
    existentes = db.query(models.Marcacao).filter(
        models.Marcacao.usuario_id == usuario_id,
        models.Marcacao.momento >= inicio,
        models.Marcacao.momento < fim,
    ).all()
    candidato = (momento, max((m.nsr for m in existentes), default=0) + 1)
    ordenadas = sorted([(m.momento, m.nsr) for m in existentes] + [candidato])
    indice = ordenadas.index(candidato)
    tipo_esperado = "entrada" if indice % 2 == 0 else "saida"
    if tipo != tipo_esperado:
        raise TipoMarcacaoInvalido(f"A próxima marcação nesta posição deve ser uma {tipo_esperado}.")

    marcacao = models.Marcacao(
        usuario_id=usuario_id, momento=momento, manual=1, registrado_por=admin_id
    )
    db.add(marcacao)
    db.commit()
    db.refresh(marcacao)
    return marcacao, tipo
