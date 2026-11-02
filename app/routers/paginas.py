from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

router = APIRouter(include_in_schema=False)


@router.get("/recepcao")
def tela_recepcao():
    return FileResponse(STATIC_DIR / "recepcao.html")


@router.get("/bater-ponto")
def tela_funcionario():
    return FileResponse(STATIC_DIR / "bater-ponto.html")


@router.get("/meu-extrato")
def tela_extrato_funcionario():
    return FileResponse(STATIC_DIR / "meu-extrato.html")


@router.get("/painel")
def tela_painel_admin():
    return FileResponse(STATIC_DIR / "painel.html")
