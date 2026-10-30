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
