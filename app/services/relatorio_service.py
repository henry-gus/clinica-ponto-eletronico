from collections import defaultdict
from datetime import date, datetime

from app import config


def agrupar_por_dia(momentos: list[datetime]) -> dict[date, list[datetime]]:
    """Agrupa marcações pelo dia no fuso da clínica, em ordem cronológica."""
    dias: dict[date, list[datetime]] = defaultdict(list)
    for momento in sorted(momentos):
        dias[momento.astimezone(config.FUSO).date()].append(momento)
    return dias


def parear(marcacoes: list[datetime]) -> tuple[list[tuple[datetime, datetime]], datetime | None]:
    """Pareia as marcações de um dia (1ª-2ª, 3ª-4ª...). Devolve os pares e a marcação sobrando, se houver."""
    pares = [(marcacoes[i], marcacoes[i + 1]) for i in range(0, len(marcacoes) - 1, 2)]
    sobra = marcacoes[-1] if len(marcacoes) % 2 else None
    return pares, sobra


def calcular_relatorio(momentos: list[datetime], carga_horaria_diaria: float) -> dict:
    """Pareia as marcações de cada dia (1ª-2ª, 3ª-4ª...) e soma as horas.

    Marcação sobrando no dia (número ímpar) não entra na soma e o dia é sinalizado
    para correção. Horas esperadas = dias com ao menos um par completo x carga diária.
    """
    total_segundos = 0.0
    dias_trabalhados = 0
    incompletos: list[date] = []

    for dia, marcacoes in sorted(agrupar_por_dia(momentos).items()):
        pares, sobra = parear(marcacoes)
        total_segundos += sum((saida - entrada).total_seconds() for entrada, saida in pares)
        if pares:
            dias_trabalhados += 1
        if sobra is not None:
            incompletos.append(dia)

    total_horas = total_segundos / 3600
    esperadas = dias_trabalhados * carga_horaria_diaria
    return {
        "total_horas_trabalhadas": round(total_horas, 2),
        "horas_extras": round(total_horas - esperadas, 2),
        "dias_com_marcacao_incompleta": incompletos,
    }
