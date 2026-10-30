# Sistema de Ponto Eletrônico (Clínica)

API para controle de jornada de trabalho, feita com FastAPI, SQLAlchemy e PostgreSQL (SQLite em
desenvolvimento), containerizada com Docker. Registra o ponto por QR Code dinâmico e emite o
**Comprovante de Registro de Ponto do Trabalhador** em PDF assinado eletronicamente.

## Como funciona

1. A recepção abre `/recepcao`, que mostra um QR Code renovado a cada 60 segundos.
2. O funcionário escaneia, abre `/bater-ponto`, informa ID e PIN e registra a marcação.
3. A resposta traz um link para o comprovante em PDF dessa marcação (válido por 72h).
4. O administrador cadastra funcionários e consulta relatórios pela API (header `X-Admin-Token`).

### Decisões de projeto

- **QR Code dinâmico (JWT com validade curta).** Dificulta que alguém registre o ponto de fora da
  clínica com a foto de um QR antigo. Não elimina: uma foto enviada dentro da janela de validade
  (120s por padrão) ainda funciona. Por isso o funcionário também precisa do PIN.
- **Marcações imutáveis com NSR.** A tabela `marcacoes` só recebe inserções. Entrada ou saída é
  deduzida pela ordem das marcações no dia (fuso da clínica); uma saída esquecida não afeta o dia seguinte.
- **Comprovante gerado sob demanda** a partir da marcação, do cadastro e dos dados do empregador.
  Contém os campos do art. 79 da Portaria 671 (título, NSR, empregador, local, trabalhador com CPF,
  data, hora e fuso) e, havendo certificado, é assinado em PAdES.

## Rodando com Docker (PostgreSQL)

```bash
cp .env.example .env     # edite SECRET_KEY, ADMIN_TOKEN, POSTGRES_PASSWORD e os dados da empresa
python -m scripts.gerar_certificado_teste   # opcional: certificado de TESTE para assinar o PDF
docker compose up -d --build
```

Se você já tinha subido a versão anterior, apague o volume antigo (o esquema do banco mudou):
`docker compose down -v`.

- API e documentação: `http://localhost:8000/docs`
- Recepção: `http://localhost:8000/recepcao` (abra pelo IP da máquina na rede, não por `localhost`,
  para o QR funcionar no celular, ou defina `BASE_URL` no `.env`)

Para usar o certificado de teste, descomente `CERT_P12_PATH` e `CERT_P12_SENHA` no `.env`.

## Rodando sem Docker (SQLite)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --env-file .env --host 0.0.0.0
```

## Uso da API (administrador)

```bash
curl -X POST http://localhost:8000/usuarios/ \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"nome": "Ana Souza", "cpf": "529.982.247-25", "cargo": "Recepcionista",
       "carga_horaria_diaria": 8, "pin": "1234"}'

curl "http://localhost:8000/relatorio/1?mes=10&ano=2026" -H "X-Admin-Token: $ADMIN_TOKEN"

# comprovante de qualquer marcação (o trabalhador usa o link devolvido ao bater o ponto)
curl http://localhost:8000/comprovantes/1 -H "X-Admin-Token: $ADMIN_TOKEN" -o comprovante.pdf
```

## Assinatura do comprovante

A Portaria 671 exige PDF assinado eletronicamente. Em produção isso significa certificado
**ICP-Brasil**, que deve ser configurado em `CERT_P12_PATH`/`CERT_P12_SENHA`. O certificado gerado por
`scripts/gerar_certificado_teste.py` é autoassinado, não tem validade legal e serve só para
desenvolvimento e demonstração. Sem certificado configurado, o PDF sai sem assinatura e avisa isso no rodapé.

Estar em conformidade com a portaria também exige o registro do programa no INPI e o Atestado
Técnico e Termo de Responsabilidade, que não são questões de código.

## Estrutura

```
app/
  main.py, config.py, database.py, models.py, schemas.py, security.py, cpf.py
  routers/    usuarios, ponto, comprovantes, relatorios, paginas
  services/   ponto_service, relatorio_service, comprovante_service, assinatura_service
static/       recepcao, bater-ponto (HTML + css/js)
scripts/      gerar_certificado_teste.py
tests/
```

## Testes

```bash
pytest
```

## Próximos passos

- Exportação do AFD (Arquivo Fonte de Dados)
- Tela de administração (funcionários e relatório)
- Limite de tentativas de PIN e consulta dos comprovantes das últimas 48h com ID e PIN
