from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app import cpf as cpf_util


DIAS_PADRAO = [0, 1, 2, 3, 4]  # segunda a sexta


class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=1)
    cpf: str
    cargo: str = Field(min_length=1)
    carga_horaria_diaria: float = Field(8.0, gt=0, le=24)
    pin: str = Field(pattern=r"^\d{4,6}$")
    papel: Literal["funcionario", "admin"] = "funcionario"
    dias_trabalho: list[int] = Field(default_factory=lambda: list(DIAS_PADRAO), min_length=1)
    data_inicio: date | None = None  # vazio = o ponto é cobrado desde sempre

    @field_validator("cpf")
    @classmethod
    def validar_cpf(cls, valor: str) -> str:
        digitos = cpf_util.somente_digitos(valor)
        if not cpf_util.cpf_valido(digitos):
            raise ValueError("CPF inválido")
        return digitos

    @field_validator("dias_trabalho")
    @classmethod
    def validar_dias(cls, valor: list[int]) -> list[int]:
        if any(dia < 0 or dia > 6 for dia in valor):
            raise ValueError("Dias da semana vão de 0 (segunda) a 6 (domingo)")
        return sorted(set(valor))


class UsuarioResponse(BaseModel):
    id: int
    nome: str
    cpf: str
    cargo: str
    carga_horaria_diaria: float
    papel: str
    dias_trabalho: list[int] = Field(validation_alias="dias_trabalho_lista")
    data_inicio: date | None

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
    papel: str
    expira_em_segundos: int


class EuResponse(BaseModel):
    usuario_id: int
    nome: str
    papel: str


class ParResponse(BaseModel):
    entrada: str  # HH:MM no horário da clínica
    saida: str | None  # None = entrada sem saída


class DiaResponse(BaseModel):
    data: date
    dia_semana: str
    dia_de_trabalho: bool  # False = folga (fim de semana, dia fora da escala ou antes do início)
    pares: list[ParResponse]
    horas: str  # HH:MM; vazio se o dia não tem par completo
    situacao: str  # "", "falta", "incompleta" ou o tipo da ausência
    situacao_texto: str
    ausencia_id: int | None
    observacao: str | None


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
    faltas: int
    ausencias: dict[str, int]  # tipo -> quantidade de dias


class ResumoResponse(BaseModel):
    usuario_id: int
    nome: str
    cargo: str
    dias_trabalhados: int
    total_horas: str
    saldo: str
    dias_incompletos: int
    faltas: int
    ausencias: int


class AusenciaCreate(BaseModel):
    usuario_id: int
    tipo: Literal["atestado", "falta_justificada", "ferias"]
    inicio: date
    fim: date
    observacao: str | None = Field(None, max_length=200)


class AusenciaResponse(BaseModel):
    id: int
    usuario_id: int
    data: date
    tipo: str
    observacao: str | None

    model_config = {"from_attributes": True}
