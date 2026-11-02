from sqlalchemy.orm import Session

from app import limitador, models, security


class CredenciaisInvalidas(Exception):
    pass


class TentativasEsgotadas(Exception):
    def __init__(self, segundos: int):
        super().__init__(segundos)
        self.segundos = segundos


def autenticar(db: Session, usuario_id: int, pin: str) -> models.Usuario:
    """Confere ID e PIN, respeitando o limite de tentativas.

    Enquanto o funcionário estiver bloqueado, nem o PIN correto é aceito.
    """
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise CredenciaisInvalidas()

    espera = limitador.segundos_de_bloqueio(usuario_id)
    if espera:
        raise TentativasEsgotadas(espera)

    if not security.verificar_pin(pin, usuario.pin_hash):
        limitador.registrar_falha(usuario_id)
        raise CredenciaisInvalidas()

    limitador.limpar(usuario_id)
    return usuario
