"""Monta o extrato de marcações de um período (a "folha de ponto")."""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import config, models
from app.services import relatorio_service

DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MAX_DIAS_PERIODO = 366


def formatar_duracao(segundos: float) -> str:
    """Segundos em HH:MM (arredondado ao minuto), com sinal se negativo."""
    minutos = int(abs(segundos) / 60 + 0.5)  # arredonda meio minuto para cima
    sinal = "-" if segundos < 0 and minutos else ""
    return f"{sinal}{minutos // 60:02d}:{minutos % 60:02d}"


def hora_local(momento: datetime) -> str:
    return momento.astimezone(config.FUSO).strftime("%H:%M")


@dataclass
class DiaExtrato:
    data: date
    pares: list[tuple[datetime, datetime]] = field(default_factory=list)
    sobra: datetime | None = None  # entrada sem saída

    @property
    def segundos(self) -> float:
        return sum((saida - entrada).total_seconds() for entrada, saida in self.pares)

    @property
    def dia_semana(self) -> str:
        return DIAS_SEMANA[self.data.weekday()]

    @property
    def incompleto(self) -> bool:
        return self.sobra is not None

    @property
    def tem_marcacao(self) -> bool:
        return bool(self.pares) or self.sobra is not None


@dataclass
class Extrato:
    usuario: models.Usuario
    inicio: date
    fim: date
    dias: list[DiaExtrato]

    @property
    def total_segundos(self) -> float:
        return sum(dia.segundos for dia in self.dias)

    @property
    def dias_trabalhados(self) -> int:
        return sum(1 for dia in self.dias if dia.pares)

    @property
    def dias_incompletos(self) -> int:
        return sum(1 for dia in self.dias if dia.incompleto)

    @property
    def esperado_segundos(self) -> float:
        return self.dias_trabalhados * self.usuario.carga_horaria_diaria * 3600

    @property
    def saldo_segundos(self) -> float:
        return self.total_segundos - self.esperado_segundos


def limites_utc(inicio: date, fim: date) -> tuple[datetime, datetime]:
    """Do começo do dia `inicio` ao fim do dia `fim` (inclusive), no fuso da clínica, em UTC."""
    de = datetime(inicio.year, inicio.month, inicio.day, tzinfo=config.FUSO)
    ate = datetime(fim.year, fim.month, fim.day, tzinfo=config.FUSO) + timedelta(days=1)
    return de.astimezone(timezone.utc), ate.astimezone(timezone.utc)


def buscar_momentos(db: Session, inicio: date, fim: date, usuario_id: int | None = None) -> dict[int, list[datetime]]:
    """Marcações do período, agrupadas por funcionário (uma consulta só)."""
    de, ate = limites_utc(inicio, fim)
    consulta = db.query(models.Marcacao).filter(
        models.Marcacao.momento >= de, models.Marcacao.momento < ate
    )
    if usuario_id is not None:
        consulta = consulta.filter(models.Marcacao.usuario_id == usuario_id)

    por_usuario: dict[int, list[datetime]] = {}
    for marcacao in consulta.order_by(models.Marcacao.nsr):
        por_usuario.setdefault(marcacao.usuario_id, []).append(marcacao.momento)
    return por_usuario


def montar_extrato(usuario: models.Usuario, momentos: list[datetime], inicio: date, fim: date) -> Extrato:
    """Um item por dia do período (inclusive dias sem marcação), como numa folha de ponto."""
    por_dia = relatorio_service.agrupar_por_dia(momentos)
    dias = []
    for deslocamento in range((fim - inicio).days + 1):
        data = inicio + timedelta(days=deslocamento)
        pares, sobra = relatorio_service.parear(por_dia.get(data, []))
        dias.append(DiaExtrato(data=data, pares=pares, sobra=sobra))
    return Extrato(usuario=usuario, inicio=inicio, fim=fim, dias=dias)


def extrato_do_usuario(db: Session, usuario: models.Usuario, inicio: date, fim: date) -> Extrato:
    momentos = buscar_momentos(db, inicio, fim, usuario.id).get(usuario.id, [])
    return montar_extrato(usuario, momentos, inicio, fim)


def extratos_de_todos(db: Session, inicio: date, fim: date) -> list[Extrato]:
    """Extrato de cada funcionário cadastrado, em ordem alfabética (2 consultas no total)."""
    usuarios = db.query(models.Usuario).order_by(models.Usuario.nome, models.Usuario.id).all()
    momentos = buscar_momentos(db, inicio, fim)
    return [montar_extrato(u, momentos.get(u.id, []), inicio, fim) for u in usuarios]


def para_resposta(extrato: Extrato) -> dict:
    usuario = extrato.usuario
    return {
        "usuario_id": usuario.id,
        "nome": usuario.nome,
        "cargo": usuario.cargo,
        "cpf": usuario.cpf,
        "carga_horaria_diaria": usuario.carga_horaria_diaria,
        "inicio": extrato.inicio,
        "fim": extrato.fim,
        "dias": [
            {
                "data": dia.data,
                "dia_semana": dia.dia_semana,
                "pares": [
                    {"entrada": hora_local(e), "saida": hora_local(s)} for e, s in dia.pares
                ]
                + ([{"entrada": hora_local(dia.sobra), "saida": None}] if dia.sobra else []),
                "horas": formatar_duracao(dia.segundos) if dia.pares else "",
                "incompleto": dia.incompleto,
            }
            for dia in extrato.dias
        ],
        "total_horas": formatar_duracao(extrato.total_segundos),
        "horas_esperadas": formatar_duracao(extrato.esperado_segundos),
        "saldo": formatar_duracao(extrato.saldo_segundos),
        "dias_trabalhados": extrato.dias_trabalhados,
        "dias_incompletos": extrato.dias_incompletos,
    }


def para_resumo(extrato: Extrato) -> dict:
    return {
        "usuario_id": extrato.usuario.id,
        "nome": extrato.usuario.nome,
        "cargo": extrato.usuario.cargo,
        "dias_trabalhados": extrato.dias_trabalhados,
        "total_horas": formatar_duracao(extrato.total_segundos),
        "saldo": formatar_duracao(extrato.saldo_segundos),
        "dias_incompletos": extrato.dias_incompletos,
    }
