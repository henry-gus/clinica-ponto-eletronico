# Sistema de Ponto Eletrônico (Clínica)

API para controle de jornada de trabalho, feita com FastAPI, SQLAlchemy e PostgreSQL (SQLite em
desenvolvimento), containerizada com Docker. Registra o ponto por QR Code dinâmico e emite o
**Comprovante de Registro de Ponto do Trabalhador** em PDF assinado eletronicamente.

## Como funciona

1. A recepção abre `/recepcao`, que mostra um QR Code renovado a cada 60 segundos.
2. O funcionário escaneia, abre `/bater-ponto`, informa ID e PIN e registra a marcação.
3. A resposta traz um link para o comprovante em PDF dessa marcação (válido por 72h).
4. A qualquer momento, o funcionário abre `/meu-extrato`, entra com ID e PIN, filtra o período e vê (ou
   baixa em PDF) todas as suas marcações, como numa folha de ponto.
5. O administrador abre `/painel` (com o `ADMIN_TOKEN`), vê o resumo de todos os funcionários no período,
   abre o extrato de cada um na tela e baixa os PDFs (um a um ou todos num ZIP).
6. O cadastro de funcionários e as demais consultas continuam pela API (header `X-Admin-Token`).

### Decisões de projeto

- **QR Code dinâmico (JWT com validade curta).** Dificulta que alguém registre o ponto de fora da
  clínica com a foto de um QR antigo. Não elimina: uma foto enviada dentro da janela de validade
  (120s por padrão) ainda funciona. Por isso o funcionário também precisa do PIN.
- **Marcações imutáveis com NSR.** A tabela `marcacoes` só recebe inserções. Entrada ou saída é
  deduzida pela ordem das marcações no dia (fuso da clínica); uma saída esquecida não afeta o dia seguinte.
- **Limite de tentativas de PIN.** Depois de 5 erros (padrão), o funcionário fica bloqueado por 15 min,
  inclusive para o PIN correto. O contador vale para bater ponto e para o extrato. Fica na memória do
  servidor: reiniciar zera, e quem errar de propósito pode travar o acesso de um colega por alguns minutos.
- **Extrato por período.** Lista todos os dias do período (inclusive os sem marcação), pareia as marcações do
  dia (1ª-2ª, 3ª-4ª...) e soma as horas. Marcação sem par aparece como "incompleta" e não soma horas. O saldo é
  o total trabalhado menos (dias com ao menos um par completo x jornada diária).
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

# extratos (datas inclusivas; sem parâmetros = do dia 1º do mês até hoje)
curl "http://localhost:8000/admin/resumo?inicio=2026-10-01&fim=2026-10-31" -H "X-Admin-Token: $ADMIN_TOKEN"
curl "http://localhost:8000/admin/extrato/1/pdf?inicio=2026-10-01&fim=2026-10-31" -H "X-Admin-Token: $ADMIN_TOKEN" -o extrato.pdf
curl "http://localhost:8000/admin/extratos/zip?inicio=2026-10-01&fim=2026-10-31" -H "X-Admin-Token: $ADMIN_TOKEN" -o extratos.zip

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
  limitador.py, dependencias.py
  routers/    usuarios, ponto, comprovantes, funcionario, admin, relatorios, paginas
  services/   ponto_service, relatorio_service, autenticacao_service, extrato_service,
              extrato_pdf_service, comprovante_service, assinatura_service
static/       recepcao, bater-ponto, meu-extrato, painel (HTML + css/js)
scripts/      gerar_certificado_teste.py
tests/
```

## Testes

```bash
pytest
```

## Segurança em uso real

O `/painel` pede o `ADMIN_TOKEN`, que trafega em HTTP puro dentro da rede da clínica. Para uso real, prefira
abrir o painel só no computador da clínica e colocar HTTPS (proxy reverso) na frente do sistema.

## Próximos passos

- Exportação do AFD (Arquivo Fonte de Dados)
- Correção de marcações pelo administrador (ajustes sem alterar a marcação original)
- Cadastro de funcionários pelo painel
