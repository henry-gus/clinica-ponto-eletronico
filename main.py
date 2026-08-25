from datetime import datetime, timezone
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,  # Para pegar o token da URL
)
from fastapi.responses import HTMLResponse
from sqlalchemy import extract
from sqlalchemy.orm import Session

import models
import schemas
import security
from database import SessionLocal, engine

# Cria as tabelas
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ponto Eletrônico Clínica")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DbSession = Annotated[Session, Depends(get_db)]

@app.post("/usuarios/", response_model=schemas.UsuarioResponse)
def criar_usuario(usuario: schemas.UsuarioCreate, db: DbSession):
    novo_usuario = models.Usuario(
        nome=usuario.nome, 
        cargo=usuario.cargo, 
        carga_horaria_diaria=usuario.carga_horaria_diaria
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario

@app.get("/qr-token")
def gerar_qr_token():
    token = security.criar_token_qr()
    # Atualizado para a URL local que o FastAPI está rodando
    url_ponto = f"http://192.168.18.183:8000/bater-ponto?token={token}"
    return {"token": token, "url": url_ponto}

@app.post("/ponto/{usuario_id}", response_model=schemas.RegistroPontoResponse)
def registrar_ponto(
    usuario_id: int, 
    token: Annotated[str, Query(...)], # Usamos Annotated para o Query
    db: DbSession                      # Deixamos apenas o DbSession limpo
):
    # 0. Nova etapa: Validação de Segurança
    if not security.validar_token_qr(token):
        raise HTTPException(
            status_code=403, 
            detail="QR Code inválido ou expirado. Volte à recepção e escaneie o código atual."
        )
    
    # 1. Verifica se o usuário existe
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # 2. Busca se há um ponto ABERTO (entrada registrada, mas sem saída)
    ponto_aberto = db.query(models.RegistroPonto).filter(
        models.RegistroPonto.usuario_id == usuario_id,
        models.RegistroPonto.saida.is_(None)
    ).first()

    # 3. Lógica inteligente: Bate a saída se estiver aberto, senão cria nova entrada
    if ponto_aberto:
        ponto_aberto.saida = datetime.now(timezone.utc)
        db.commit()
        db.refresh(ponto_aberto)
        return ponto_aberto
    else:
        novo_ponto = models.RegistroPonto(usuario_id=usuario_id)
        db.add(novo_ponto)
        db.commit()
        db.refresh(novo_ponto)
        return novo_ponto

@app.get("/relatorio/{usuario_id}", response_model=schemas.RelatorioHorasResponse)
def relatorio_mensal(usuario_id: int, mes: int, ano: int, db: DbSession):
    # 1. Verifica se o usuário existe
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # 2. Busca todos os registros do usuário no mês/ano que já têm "saída"
    registros = db.query(models.RegistroPonto).filter(
        models.RegistroPonto.usuario_id == usuario_id,
        extract('month', models.RegistroPonto.entrada) == mes,
        extract('year', models.RegistroPonto.entrada) == ano,
        models.RegistroPonto.saida.isnot(None) # Ignora pontos esquecidos abertos
    ).all()

    total_segundos = 0
    dias_trabalhados = set() # Usamos um 'set' para não contar o mesmo dia duas vezes

    # 3. Faz a matemática de tempo
    for registro in registros:
        # Subtrai a saída da entrada para pegar a duração
        delta = registro.saida - registro.entrada
        total_segundos += delta.total_seconds()
        
        # Adiciona o dia no 'set' para saber quantos dias únicos ele trabalhou
        dias_trabalhados.add(registro.entrada.date())

    # 4. Converte os totais
    total_horas = total_segundos / 3600
    horas_esperadas = len(dias_trabalhados) * usuario.carga_horaria_diaria
    horas_extras = total_horas - horas_esperadas

    return {
        "usuario_id": usuario_id,
        "mes": mes,
        "ano": ano,
        "total_horas_trabalhadas": round(total_horas, 2),
        "horas_extras": round(horas_extras, 2)
    }

@app.get("/recepcao", response_class=HTMLResponse)
def tela_recepcao():
    html_content = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Ponto Eletrônico - Recepção</title>
        <!-- Biblioteca leve para desenhar o QR Code -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <style>
            body {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
                font-family: Arial, sans-serif;
                background-color: #f4f4f9;
            }
            h1 { color: #333; }
            #qrcode {
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                margin-top: 20px;
            }
            #timer { margin-top: 15px; color: #666; font-size: 14px; }
        </style>
    </head>
    <body>
        <h1>Registre seu Ponto</h1>
        <p>Escaneie o código abaixo com a câmera do celular.</p>
        
        <div id="qrcode"></div>
        <div id="timer">Atualizando em: <span id="contador">60</span>s</div>

        <script>
            const qrContainer = document.getElementById("qrcode");
            const contadorSpan = document.getElementById("contador");
            
            // Inicializa o gerador de QR Code vazio
            let qrcode = new QRCode(qrContainer, {
                width: 300,
                height: 300,
                colorDark : "#000000",
                colorLight : "#ffffff",
                correctLevel : QRCode.CorrectLevel.H
            });

            let tempoRestante = 60;

            async function atualizarQR() {
                try {
                    // Busca um token novo na nossa API
                    const response = await fetch("/qr-token");
                    const data = await response.json();
                    
                    // Atualiza a imagem do QR Code com a nova URL
                    qrcode.makeCode(data.url);
                    
                    // Reseta o contador
                    tempoRestante = 60;
                } catch (error) {
                    console.error("Erro ao buscar token:", error);
                }
            }

            // Função que faz a contagem regressiva na tela
            function atualizarCronometro() {
                tempoRestante--;
                contadorSpan.innerText = tempoRestante;
                
                // Faltando 1 segundo, já pede o próximo token para não haver gap
                if (tempoRestante <= 1) {
                    atualizarQR();
                }
            }

            // Chama a primeira vez imediatamente
            atualizarQR();
            
            // Configura o relógio para rodar a cada 1 segundo (1000 milissegundos)
            setInterval(atualizarCronometro, 1000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/bater-ponto", response_class=HTMLResponse)
def tela_funcionario():
    html_content = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <!-- Tag essencial para o layout se adaptar perfeitamente a telas de celulares -->
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Registrar Ponto</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: #f0f2f5;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
                padding: 20px;
                box-sizing: border-box;
            }
            .card {
                background: white;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                width: 100%;
                max-width: 350px;
                text-align: center;
            }
            h2 { margin-top: 0; color: #1a1a1a; }
            input {
                width: 100%;
                padding: 12px;
                margin: 15px 0;
                border: 1px solid #ccc;
                border-radius: 8px;
                box-sizing: border-box;
                font-size: 16px;
            }
            button {
                width: 100%;
                padding: 14px;
                background-color: #0066cc;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
            }
            button:active { background-color: #0052a3; }
            #mensagem {
                margin-top: 20px;
                font-weight: bold;
                font-size: 14px;
            }
            .sucesso { color: #28a745; }
            .erro { color: #dc3545; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Bater Ponto</h2>
            <p>Confirme seu ID para registrar o horário.</p>
            
            <input type="number" id="userId" placeholder="Seu ID de funcionário" required>
            <button onclick="enviarPonto()">Registrar Agora</button>
            
            <div id="mensagem"></div>
        </div>

        <script>
            async function enviarPonto() {
                const userId = document.getElementById("userId").value;
                const mensagemDiv = document.getElementById("mensagem");
                
                if (!userId) {
                    mensagemDiv.className = "erro";
                    mensagemDiv.innerText = "Por favor, digite seu ID.";
                    return;
                }

                // Pega a URL atual do navegador e extrai o parâmetro ?token=...
                const urlParams = new URLSearchParams(window.location.search);
                const token = urlParams.get("token");

                if (!token) {
                    mensagemDiv.className = "erro";
                    mensagemDiv.innerText = "Nenhum token encontrado. Escaneie o QR Code novamente.";
                    return;
                }

                mensagemDiv.innerText = "Processando...";
                mensagemDiv.className = "";

                try {
                    // Faz a requisição POST para a sua API passando o token na URL
                    const response = await fetch(`/ponto/${userId}?token=${token}`, {
                        method: "POST",
                        headers: {
                            "Accept": "application/json"
                        }
                    });

                    const data = await response.json();

                    if (response.ok) {
                        mensagemDiv.className = "sucesso";
                        // Verifica se bateu entrada ou saída para mostrar uma mensagem bonita
                        if (data.saida) {
                            mensagemDiv.innerText = `Saída registrada com sucesso!\\n${data.saida}`;
                        } else {
                            mensagemDiv.innerText = `Entrada registrada com sucesso!\\n${data.entrada}`;
                        }
                    } else {
                        mensagemDiv.className = "erro";
                        // Mostra a mensagem de erro que vem do backend (ex: token expirado)
                        mensagemDiv.innerText = data.detail || "Erro ao registrar o ponto.";
                    }
                } catch (error) {
                    mensagemDiv.className = "erro";
                    mensagemDiv.innerText = "Erro de conexão com o servidor.";
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)