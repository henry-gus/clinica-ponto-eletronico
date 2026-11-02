"""Cria um administrador ou promove uma pessoa já cadastrada.

Uso:
    python -m scripts.criar_admin                 # pergunta os dados e cria um administrador novo
    python -m scripts.criar_admin --promover 3    # torna a pessoa de ID 3 administradora

Com Docker:
    docker compose exec api python -m scripts.criar_admin

É assim que nasce o primeiro administrador. Os demais podem ser cadastrados pela tela.
"""
import argparse
import getpass
import re
import sys

from dotenv import load_dotenv

load_dotenv()  # fora do Docker, lê o .env da pasta atual

from pydantic import ValidationError  # noqa: E402

from app import models  # noqa: E402,F401
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.migracoes import migrar_esquema  # noqa: E402
from app.schemas import UsuarioCreate  # noqa: E402
from app.services import usuario_service  # noqa: E402


def promover(db, usuario_id: int) -> models.Usuario:
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise LookupError(f"Não existe cadastro com ID {usuario_id}.")
    usuario.papel = "admin"
    db.commit()
    return usuario


def criar(db, nome: str, cpf: str, cargo: str, pin: str) -> models.Usuario:
    dados = UsuarioCreate(nome=nome, cpf=cpf, cargo=cargo, pin=pin, papel="admin")
    return usuario_service.criar_usuario(db, dados)


def _pedir_pin() -> str:
    while True:
        pin = getpass.getpass("PIN (4 a 6 dígitos): ")
        if not re.fullmatch(r"\d{4,6}", pin):
            print("O PIN deve ter de 4 a 6 dígitos.")
        elif pin != getpass.getpass("Repita o PIN: "):
            print("Os PINs não conferem.")
        else:
            return pin


def main() -> int:
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--promover", type=int, metavar="ID", help="torna administrador quem já está cadastrado")
    dados = argumentos.parse_args()

    migrar_esquema(engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        try:
            if dados.promover is not None:
                usuario = promover(db, dados.promover)
            else:
                nome = input("Nome completo: ").strip()
                cpf = input("CPF: ").strip()
                cargo = input("Cargo [Administrador]: ").strip() or "Administrador"
                usuario = criar(db, nome, cpf, cargo, _pedir_pin())
        except LookupError as erro:
            print(erro)
            return 1
        except ValidationError as erro:
            for problema in erro.errors():
                print(f"{'.'.join(str(p) for p in problema['loc'])}: {problema['msg'].removeprefix('Value error, ')}")
            return 1
        except usuario_service.CpfDuplicado:
            print("Já existe cadastro com este CPF. Use --promover ID para torná-lo administrador.")
            return 1

        # Ainda dentro da sessão: depois do `with` o objeto fica desanexado do banco.
        print(f"Pronto: {usuario.nome} (ID {usuario.id}) agora é administrador. Entre em /extratos com esse ID e o PIN.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
