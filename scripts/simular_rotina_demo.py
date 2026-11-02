
import argparse
from datetime import date, datetime, time, timedelta

from dotenv import load_dotenv

# Carrega as configurações do .env antes de importar o projeto.
load_dotenv()

from sqlalchemy import delete

from app import config, models, security
from app.database import Base, SessionLocal, engine


PIN_DEMO = "1234"


def gerar_cpf(base: str) -> str:
    """Gera um CPF fictício com dígitos verificadores válidos."""
    cpf = base

    for posicao in (9, 10):
        soma = sum(
            int(cpf[i]) * (posicao + 1 - i)
            for i in range(posicao)
        )
        digito = (soma * 10) % 11 % 10
        cpf += str(digito)

    return cpf


def ultimos_dias_uteis(quantidade=10):
    """Retorna os últimos dez dias úteis completos."""
    atual = datetime.now(config.FUSO).date() - timedelta(days=1)
    dias = []

    while len(dias) < quantidade:
        if atual.weekday() < 5:
            dias.append(atual)

        atual -= timedelta(days=1)

    return sorted(dias)


def criar_funcionario(db, nome, cpf_base, cargo, jornada):
    usuario = models.Usuario(
        nome=nome,
        cpf=gerar_cpf(cpf_base),
        cargo=cargo,
        carga_horaria_diaria=jornada,
        pin_hash=security.hash_pin(PIN_DEMO),
    )

    db.add(usuario)
    db.flush()

    print(f"Funcionário: {nome}")
    print(f"ID: {usuario.id} | PIN: {PIN_DEMO}\n")

    return usuario


def registrar_horarios(db, usuario, dia, horarios):
    """Insere as marcações respeitando o fuso da clínica."""
    for horario in horarios:
        momento = datetime.combine(
            dia,
            horario,
            tzinfo=config.FUSO,
        )

        db.add(
            models.Marcacao(
                usuario_id=usuario.id,
                momento=momento,
            )
        )


def simular(db, dias):
    # -------------------------------------------------
    # FUNCIONÁRIOS
    # -------------------------------------------------

    fisio_manha = criar_funcionario(
        db,
        "Fisioterapeuta - Manhã",
        "900000001",
        "Fisioterapeuta",
        4.0,
    )

    fisio_tarde = criar_funcionario(
        db,
        "Fisioterapeuta - Tarde",
        "900000002",
        "Fisioterapeuta",
        5.0,
    )

    recepcionista = criar_funcionario(
        db,
        "Recepcionista",
        "900000003",
        "Recepcionista",
        8.8,
    )

    # Uma quarta-feira terá hora extra no turno da manhã.
    dia_extra = next(
        dia for dia in reversed(dias)
        if dia.weekday() == 2
    )

    # -------------------------------------------------
    # MARCAÇÕES
    # -------------------------------------------------

    for dia in dias:
        semana = dia.weekday()

        # FISIOTERAPEUTA - MANHÃ
        if dia == dia_extra:
            # Entrada: 06:30
            # Pausa: 10:00 até 10:15
            # Saída: 11:00
            horarios = [
                time(6, 30),
                time(10, 0),
                time(10, 15),
                time(11, 0),
            ]
        else:
            horarios = [
                time(6, 30),
                time(10, 30),
            ]

        registrar_horarios(
            db, fisio_manha, dia, horarios
        )

        # FISIOTERAPEUTA - TARDE
        if semana in (0, 2):
            # Segunda e quarta
            horarios = [
                time(15, 30),
                time(19, 0),
                time(19, 15),
                time(20, 45),
            ]

        elif semana in (1, 3):
            # Terça e quinta
            horarios = [
                time(16, 0),
                time(18, 30),
                time(18, 45),
                time(21, 15),
            ]

        else:
            # Sexta-feira: sem expediente informado.
            horarios = []

        if horarios:
            registrar_horarios(
                db, fisio_tarde, dia, horarios
            )

        # RECEPCIONISTA
        if semana <= 3:
            # Segunda a quinta
            horarios = [
                time(7, 30),
                time(13, 0),
                time(14, 0),
                time(17, 30),
            ]

        else:
            # Sexta-feira
            # Almoço considerado das 13:00 às 14:00.
            horarios = [
                time(7, 30),
                time(13, 0),
                time(14, 0),
                time(16, 30),
            ]

        registrar_horarios(
            db, recepcionista, dia, horarios
        )

    print(f"Dia de hora extra: {dia_extra}")
    print("Todas as marcações foram preparadas.")


def main():
    parser = argparse.ArgumentParser(
        description="Recria os dados da demonstração."
    )

    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Confirma a exclusão dos dados existentes.",
    )

    args = parser.parse_args()

    if not args.confirmar:
        print(
            "ATENÇÃO: este script apaga TODOS os funcionários "
            "e TODAS as marcações do banco configurado."
        )
        print(
            "Faça um backup e execute novamente com --confirmar."
        )
        return

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # Limpa primeiro as marcações por causa da chave estrangeira.
        # A exclusão em lote é intencional e não utiliza o DELETE
        # individual bloqueado pelo modelo Marcacao.
        db.execute(delete(models.Marcacao))
        db.execute(delete(models.Usuario))

        dias = ultimos_dias_uteis(10)

        simular(db, dias)

        db.commit()

        print("\nSIMULAÇÃO CONCLUÍDA!")
        print(f"Período: {dias[0]} até {dias[-1]}")
        print("PIN de todos os funcionários:", PIN_DEMO)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
