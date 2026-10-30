from fastapi import APIRouter, Header, HTTPException, Response

from app import security
from app.database import DbSession
from app.services import comprovante_service

router = APIRouter(prefix="/comprovantes", tags=["comprovantes"])


@router.get("/{nsr}")
def baixar_comprovante(
    nsr: int,
    db: DbSession,
    token: str = "",
    x_admin_token: str = Header(default=""),
):
    """PDF do comprovante da marcação `nsr`. Acesso pelo link do trabalhador ou pelo admin."""
    if not (security.validar_token_comprovante(token, nsr) or security.admin_valido(x_admin_token)):
        raise HTTPException(403, "Link do comprovante inválido ou expirado.")

    try:
        pdf = comprovante_service.gerar_comprovante(db, nsr)
    except comprovante_service.MarcacaoNaoEncontrada:
        raise HTTPException(404, "Marcação não encontrada.")
    except comprovante_service.DadosEmpregadorIncompletos as erro:
        raise HTTPException(503, str(erro))

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="comprovante-nsr-{nsr}.pdf"'},
    )
