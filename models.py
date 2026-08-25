from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    cargo = Column(String) 
    carga_horaria_diaria = Column(Float, default=8.0) 

class RegistroPonto(Base):
    __tablename__ = "registros_ponto"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    # Salva o tempo absoluto em UTC
    entrada = Column(DateTime, default=lambda: datetime.now(timezone.utc)) 
    saida = Column(DateTime, nullable=True) #Fica nulo até registrar a saída