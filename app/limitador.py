"""Limite de tentativas erradas de PIN, por funcionário.

Fica na memória do processo: reiniciar o servidor zera os contadores, e com vários
processos cada um conta separado. Para a clínica (1 processo) é suficiente.
"""
import time
from collections import defaultdict, deque

from app import config

_falhas: dict[int, deque[float]] = defaultdict(deque)


def _janela() -> int:
    return config.PIN_BLOQUEIO_MINUTOS * 60


def _falhas_recentes(usuario_id: int, agora: float) -> deque[float]:
    fila = _falhas[usuario_id]
    while fila and agora - fila[0] > _janela():
        fila.popleft()
    return fila


def segundos_de_bloqueio(usuario_id: int, agora: float | None = None) -> int:
    """0 se pode tentar; senão, quantos segundos faltam para liberar."""
    agora = time.monotonic() if agora is None else agora
    fila = _falhas_recentes(usuario_id, agora)
    if len(fila) < config.PIN_MAX_TENTATIVAS:
        return 0
    return int(_janela() - (agora - fila[0])) + 1


def registrar_falha(usuario_id: int, agora: float | None = None) -> None:
    agora = time.monotonic() if agora is None else agora
    _falhas_recentes(usuario_id, agora).append(agora)


def limpar(usuario_id: int) -> None:
    _falhas.pop(usuario_id, None)


def resetar_tudo() -> None:
    _falhas.clear()
