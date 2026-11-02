from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, event
from sqlalchemy.types import TypeDecorator

from app.database import Base


class UTCDateTime(TypeDecorator):
    """Guarda sempre em UTC e devolve datetime com fuso (o SQLite perde o fuso)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("datetime precisa ter fuso horário")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=timezone.utc)


# Ausências que o administrador pode registrar para um dia (código -> texto exibido).
TIPOS_AUSENCIA = {
    "atestado": "Atestado",
    "falta_justificada": "Falta justificada",
    "ferias": "Férias",
}


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True, nullable=False)
    cpf = Column(String(11), unique=True, nullable=False)  # só dígitos
    cargo = Column(String, nullable=False)
    carga_horaria_diaria = Column(Float, default=8.0, nullable=False)
    pin_hash = Column(String, nullable=False)
    papel = Column(String, nullable=False, default="funcionario", server_default="funcionario")
    # Dias da semana em que a pessoa trabalha, como números separados por vírgula (0 = segunda ... 6 = domingo).
    dias_trabalho = Column(String, nullable=False, default="0,1,2,3,4", server_default="0,1,2,3,4")
    # A partir de quando o ponto é cobrado. Antes disso não há falta. Vazio = sem limite.
    data_inicio = Column(Date, nullable=True)

    @property
    def eh_admin(self) -> bool:
        return self.papel == "admin"

    @property
    def dias_trabalho_lista(self) -> list[int]:
        return [int(dia) for dia in self.dias_trabalho.split(",") if dia != ""]


class Marcacao(Base):
    """Uma batida de ponto. Só recebe INSERT: nunca é editada nem apagada.

    O NSR (número sequencial de registro) é a chave primária; sqlite_autoincrement
    impede que um número seja reaproveitado.
    Entrada/saída não é gravada: é deduzida pela ordem das marcações no dia.
    """

    __tablename__ = "marcacoes"
    __table_args__ = {"sqlite_autoincrement": True}

    nsr = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    momento = Column(UTCDateTime, nullable=False, index=True)


@event.listens_for(Marcacao, "before_update")
@event.listens_for(Marcacao, "before_delete")
def _bloquear_alteracao(mapper, connection, target):
    # Proteção na camada da aplicação. Em produção, reforce no banco (trigger/permissões).
    raise RuntimeError("Marcações são imutáveis: não podem ser alteradas nem apagadas.")


class Ausencia(Base):
    """Um dia justificado (atestado, falta justificada ou férias), registrado pelo administrador."""

    __tablename__ = "ausencias"
    __table_args__ = (UniqueConstraint("usuario_id", "data", name="uq_ausencia_usuario_data"),)

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    data = Column(Date, nullable=False, index=True)
    tipo = Column(String, nullable=False)
    observacao = Column(String, nullable=True)
    registrado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    criado_em = Column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
