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
