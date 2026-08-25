from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, field_serializer


def formatar_data_ptbr(dt: datetime | None) -> str | None:
    if not dt:
        return None
        
    # 1. Garante que o Python entenda que esse horário veio em UTC do banco
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        
    # 2. Converte matematicamente para o fuso do Brasil
    dt_brasil = dt.astimezone(ZoneInfo("America/Sao_Paulo"))

    # 3. Formata o texto final
    dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    dia_semana = dias[dt_brasil.weekday()]
    mes = meses[dt_brasil.month - 1]
    
    hora_formatada = dt_brasil.strftime("%H:%M:%S")
    return f"{dia_semana}, {dt_brasil.day:02d} {mes} {dt_brasil.year} {hora_formatada} BRT"

# --- Schemas de Usuário ---
class UsuarioBase(BaseModel):
    nome: str
    cargo: str
    carga_horaria_diaria: float = 8.0

class UsuarioCreate(UsuarioBase):
    pass

class UsuarioResponse(UsuarioBase):
    id: int

    class Config:
        from_attributes = True

# --- Schemas de Ponto ---
class RegistroPontoResponse(BaseModel):
    id: int
    usuario_id: int
    entrada: datetime
    saida: datetime | None = None

    @field_serializer('entrada', 'saida')
    def serializar_datas(self, dt: datetime | None, _info):
        return formatar_data_ptbr(dt)

    class Config:
        from_attributes = True

class RelatorioHorasResponse(BaseModel):
    usuario_id: int
    mes: int
    ano: int
    total_horas_trabalhadas: float
    horas_extras: float

    class Config:
        from_attributes = True