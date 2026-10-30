from collections import defaultdict
from datetime import date, datetime

from app import config


def agrupar_por_dia(momentos: list[datetime]) -> dict[date, list[datetime]]:
    """Agrupa marcações pelo dia no fuso da clínica, em ordem cronológica."""
    dias: dict[date, list[datetime]] = defaultdict(list)
    for momento in sorted(momentos):
        dias[momento.astimezone(config.FUSO).date()].append(momento)
    return dias


def calcular_relatorio(momentos: list[datetime], carga_horaria_diaria: float) -> dict:
    """Pareia as marcações de cada dia (1ª-2ª, 3ª-4ª...) e soma as horas.

    Marcação sobrando no dia (número ímpar) não entra na soma e o dia é sinalizado
    para correção. Horas esperadas = dias com ao menos um par completo x carga diária.
    """
    total_segundos = 0.0
    dias_trabalhados = 0
    incompletos: list[date] = []

    for dia, marcacoes in sorted(agrupar_por_dia(momentos).items()):
        pares = len(marcacoes) // 2
        for i in range(pares):
            total_segundos += (marcacoes[2 * i + 1] - marcacoes[2 * i]).total_seconds()
        if pares:
            dias_trabalhados += 1
        if len(marcacoes) % 2:
            incompletos.append(dia)

    total_horas = total_segundos / 3600
    esperadas = dias_trabalhados * carga_horaria_diaria
    return {
        "total_horas_trabalhadas": round(total_horas, 2),
        "horas_extras": round(total_horas - esperadas, 2),
        "dias_com_marcacao_incompleta": incompletos,
    }
