# Usa uma versão leve do Python
FROM python:3.10-slim

# Define a pasta de trabalho dentro do container
WORKDIR /app

# Copia e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# O código em si será mapeado pelo docker-compose para permitir atualização em tempo real