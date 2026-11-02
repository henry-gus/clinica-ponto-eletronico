from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app import cpf as cpf_util


class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=1)
    cpf: str
    cargo: str = Field(min_length=1)
    carga_horaria_diaria: float = Field(8.0, gt=0, le=24)
    pin: str = Field(pattern=r"^\d{4,6}$")

    @field_validator("cpf")
    @classmethod
    def validar_cpf(cls, valor: str) -> str:
        digitos = cpf_util.somente_digitos(valor)
        if not cpf_util.cpf_valido(digitos):
            raise ValueError("CPF inválido")
        return digitos


class UsuarioResponse(BaseModel):
    id: int
    nome: str
    cpf: str
    cargo: str
    carga_horaria_diaria: float

    model_config = {"from_attributes": True}


class PontoRequest(BaseModel):
    pin: str


class MarcacaoResponse(BaseModel):
    nsr: int
    usuario_id: int
    tipo: Literal["entrada", "saida"]
    momento: datetime  # UTC; o frontend converte para o horário local
    comprovante_url: str  # link do PDF, válido por COMPROVANTE_VALIDADE_HORAS


class RelatorioResponse(BaseModel):
    usuario_id: int
    mes: int
    ano: int
    total_horas_trabalhadas: float
    horas_extras: float
    dias_com_marcacao_incompleta: list[date]


# --- Extrato (folha de ponto) ---
class LoginRequest(BaseModel):
    usuario_id: int
    pin: str


class SessaoResponse(BaseModel):
    token: str
    nome: str
    expira_em_segundos: int


class ParResponse(BaseModel):
    entrada: str  # HH:MM no horário da clínica
    saida: str | None  # None = entrada sem saída


class DiaResponse(BaseModel):
    data: date
    dia_semana: str
    pares: list[ParResponse]
    horas: str  # HH:MM; vazio se o dia não tem par completo
    incompleto: bool


class ExtratoResponse(BaseModel):
    usuario_id: int
    nome: str
    cargo: str
    cpf: str
    carga_horaria_diaria: float
    inicio: date
    fim: date
    dias: list[DiaResponse]
    total_horas: str
    horas_esperadas: str
    saldo: str
    dias_trabalhados: int
    dias_incompletos: int


class ResumoResponse(BaseModel):
    usuario_id: int
    nome: str
    cargo: str
    dias_trabalhados: int
    total_horas: str
    saldo: str
    dias_incompletos: int
