# Sistema de Ponto Eletrônico (Clínica)

API para controle de jornada de trabalho, feita com FastAPI, SQLAlchemy e PostgreSQL (SQLite em
desenvolvimento), containerizada com Docker. Registra o ponto por QR Code dinâmico e emite o
**Comprovante de Registro de Ponto do Trabalhador** em PDF assinado eletronicamente.

## Como funciona

1. A recepção abre `/recepcao`, que mostra um QR Code renovado a cada 60 segundos.
2. O funcionário escaneia, abre `/bater-ponto`, informa ID e PIN e registra a marcação.
3. A resposta traz um link para o comprovante em PDF dessa marcação (válido por 72h).
4. Em `/extratos`, qualquer pessoa entra com ID e PIN. O servidor diz o **perfil** (funcionário ou
   administrador) e a tela mostra só o que aquele perfil pode usar:
   - **Funcionário:** aba *Extratos* com as próprias marcações no período escolhido, em tela ou PDF.
   - **Administrador:** aba *Extratos* com o resumo de todos, o extrato de cada pessoa na tela, PDF por
     pessoa, ZIP com todos e o registro de **atestado, falta justificada e férias**; e aba *Funcionários*,
     para cadastrar e listar pessoas.

## Primeiro administrador

O administrador é uma pessoa cadastrada com perfil `admin`; entra como todos, com ID e PIN. Como ainda não
há ninguém para cadastrá-lo, o primeiro nasce pelo terminal:

```bash
python -m scripts.criar_admin                  # cria um novo (pergunta nome, CPF, cargo e PIN)
python -m scripts.criar_admin --promover 3     # ou promove quem já está cadastrado (ID 3)
docker compose exec api python -m scripts.criar_admin    # com Docker
```

Depois disso, novos administradores podem ser cadastrados pela aba *Funcionários*. O perfil é lido do banco
a cada requisição: promover ou rebaixar vale na hora.

### Decisões de projeto

- **QR Code dinâmico (JWT com validade curta).** Dificulta que alguém registre o ponto de fora da
  clínica com a foto de um QR antigo. Não elimina: uma foto enviada dentro da janela de validade
  (120s por padrão) ainda funciona. Por isso o funcionário também precisa do PIN.
- **Marcações imutáveis com NSR.** A tabela `marcacoes` só recebe inserções. Entrada ou saída é
  deduzida pela ordem das marcações no dia (fuso da clínica); uma saída esquecida não afeta o dia seguinte.
- **Limite de tentativas de PIN.** Depois de 5 erros (padrão), a pessoa fica bloqueada por 15 min,
  inclusive para o PIN correto. O contador vale para bater ponto e para o login. Fica na memória do
  servidor: reiniciar zera, e quem errar de propósito pode travar o acesso de um colega por alguns minutos.
- **Extrato por período.** Lista todos os dias do período (inclusive os sem marcação) e pareia as marcações
  do dia (1ª-2ª, 3ª-4ª...). Regras do saldo:
  - horas trabalhadas = soma dos pares entrada-saída (marcação sem par fica registrada, mas não soma);
  - horas esperadas = jornada x dias de trabalho já encerrados, **menos** os dias com atestado, férias ou
    falta justificada (abonados);
  - dia de trabalho passado, sem marcação e sem ausência = **falta**, que entra no esperado e pesa no saldo;
  - hoje só entra no esperado depois de um par completo; dias futuros nunca entram;
  - cada pessoa tem seus **dias de trabalho** (padrão segunda a sexta) e a data **a partir da qual o ponto é
    cobrado** (o padrão da tela é hoje), para que quem entrou no meio do mês não receba faltas retroativas.
    Trabalho em dia fora da escala conta como hora a mais.
  - **Feriados ainda não são tratados:** um feriado em dia útil aparece como falta. Enquanto isso, registre
    "falta justificada" com a observação "Feriado".
- **Comprovante gerado sob demanda** a partir da marcação, do cadastro e dos dados do empregador.
  Contém os campos do art. 79 da Portaria 671 (título, NSR, empregador, local, trabalhador com CPF,
  data, hora e fuso) e, havendo certificado, é assinado em PAdES.

## Rodando com Docker (PostgreSQL)

```bash
cp .env.example .env     # edite SECRET_KEY, POSTGRES_PASSWORD e os dados da empresa
python -m scripts.gerar_certificado_teste   # opcional: certificado de TESTE para assinar o PDF
docker compose up -d --build
```

Ao atualizar de uma versão anterior, o servidor acrescenta sozinho as colunas novas (perfil, dias de trabalho e
data de início) e cria a tabela de ausências, **sem apagar dados**. Só falta definir o administrador (veja
"Primeiro administrador"). Se a versão antiga tinha tabelas de uma estrutura muito anterior, apague o volume:
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

## Uso da API

Tudo o que a tela faz está na API (documentação interativa em `/docs`, com o botão **Authorize**).

```bash
# 1. login -> token (o campo "papel" diz se é funcionario ou admin)
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"usuario_id": 1, "pin": "1234"}'

# 2. use o token nas demais chamadas
curl "http://localhost:8000/extratos/meu?inicio=2026-10-01&fim=2026-10-31" -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/extratos/meu/pdf?inicio=2026-10-01&fim=2026-10-31" -H "Authorization: Bearer $TOKEN" -o extrato.pdf
```

Só administradores (as demais rotas respondem 403 para funcionários):

```bash
curl -X POST http://localhost:8000/usuarios/ -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"nome": "Ana Souza", "cpf": "529.982.247-25", "cargo": "Recepcionista", "pin": "1234",
       "dias_trabalho": [0, 1, 2, 3, 4], "data_inicio": "2026-10-01", "papel": "funcionario"}'

curl "http://localhost:8000/admin/resumo?inicio=2026-10-01&fim=2026-10-31" -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/admin/extrato/2/pdf?inicio=2026-10-01&fim=2026-10-31" -H "Authorization: Bearer $TOKEN" -o extrato.pdf
curl "http://localhost:8000/admin/extratos/zip?inicio=2026-10-01&fim=2026-10-31" -H "Authorization: Bearer $TOKEN" -o extratos.zip

# atestado, falta_justificada ou ferias (um registro por dia, de inicio a fim)
curl -X POST http://localhost:8000/admin/ausencias -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"usuario_id": 2, "tipo": "atestado", "inicio": "2026-10-08", "fim": "2026-10-09", "observacao": "consulta"}'
curl -X DELETE http://localhost:8000/admin/ausencias/7 -H "Authorization: Bearer $TOKEN"
```

Datas sem parâmetros = do dia 1º do mês até hoje. O comprovante de uma marcação também pode ser baixado por um
administrador logado: `GET /comprovantes/{nsr}`.

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
  main.py, config.py, database.py, migracoes.py, models.py, schemas.py, security.py, cpf.py
  limitador.py, dependencias.py (login, perfis, período)
  routers/    auth, extratos, admin, usuarios, ponto, comprovantes, paginas
  services/   ponto_service, relatorio_service, autenticacao_service, usuario_service,
              ausencia_service, extrato_service, extrato_pdf_service, comprovante_service,
              assinatura_service
static/       recepcao, bater-ponto, extratos (HTML + css/js)
scripts/      criar_admin.py, gerar_certificado_teste.py
tests/
```

## Testes

```bash
pytest
```

## Segurança em uso real

O ID e o PIN do administrador trafegam em HTTP puro dentro da rede da clínica. Para uso real, prefira usar a
conta de administrador só no computador da clínica e colocar HTTPS (proxy reverso) na frente do sistema.
O PIN tem só 4 a 6 dígitos: o bloqueio por tentativas é o que o protege, e ele pode ser provocado de propósito
contra uma conta (o administrador inclusive) por alguns minutos.

## Próximos passos

- Exportação do AFD (Arquivo Fonte de Dados)
- Correção de marcações pelo administrador (ajustes sem alterar a marcação original)
- Feriados e troca de PIN pelo administrador
