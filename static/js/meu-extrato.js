const CHAVE_SESSAO = "ponto_sessao";
const telaLogin = document.getElementById("tela-login");
const telaExtrato = document.getElementById("tela-extrato");
const mensagem = document.getElementById("mensagem");
const campoInicio = document.getElementById("inicio");
const campoFim = document.getElementById("fim");

let token = sessionStorage.getItem(CHAVE_SESSAO);

function mostrar(texto, classe = "erro") {
  mensagem.textContent = texto;
  mensagem.className = texto ? classe : "";
}

function consulta() {
  return `inicio=${encodeURIComponent(campoInicio.value)}&fim=${encodeURIComponent(campoFim.value)}`;
}

function buscar(caminho) {
  return fetch(`${caminho}?${consulta()}`, { headers: { Authorization: `Bearer ${token}` } });
}

function sair(aviso = "") {
  token = null;
  sessionStorage.removeItem(CHAVE_SESSAO);
  telaExtrato.hidden = true;
  telaLogin.hidden = false;
  mostrar(aviso);
}

async function carregarExtrato() {
  mostrar("");
  const resposta = await buscar("/funcionario/extrato");
  if (resposta.status === 401) return sair("Sessão expirada. Entre novamente.");
  const dados = await resposta.json();
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, dados));
  renderizarExtrato(document.getElementById("extrato"), dados);
}

function abrirExtrato(nome) {
  document.getElementById("nome-usuario").textContent = nome;
  telaLogin.hidden = true;
  telaExtrato.hidden = false;
  carregarExtrato();
}

document.getElementById("form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  mostrar("");
  const botao = evento.target.querySelector("button");
  botao.disabled = true;
  try {
    const resposta = await fetch("/funcionario/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usuario_id: Number(document.getElementById("usuario_id").value),
        pin: document.getElementById("pin").value,
      }),
    });
    const dados = await resposta.json();
    if (!resposta.ok) return mostrar(mensagemDeErro(resposta, dados));
    token = dados.token;
    sessionStorage.setItem(CHAVE_SESSAO, token);
    sessionStorage.setItem(`${CHAVE_SESSAO}_nome`, dados.nome);
    document.getElementById("pin").value = "";
    abrirExtrato(dados.nome);
  } catch (erro) {
    mostrar("Sem conexão com o servidor.");
  } finally {
    botao.disabled = false;
  }
});

document.getElementById("form-periodo").addEventListener("submit", (evento) => {
  evento.preventDefault();
  carregarExtrato();
});

document.getElementById("baixar-pdf").addEventListener("click", async () => {
  mostrar("");
  const resposta = await buscar("/funcionario/extrato/pdf");
  if (resposta.status === 401) return sair("Sessão expirada. Entre novamente.");
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, await resposta.json()));
  await baixarArquivo(resposta, "extrato.pdf");
});

document.getElementById("sair").addEventListener("click", () => sair());

const padrao = periodoPadrao();
campoInicio.value = padrao.inicio;
campoFim.value = padrao.fim;
if (token) abrirExtrato(sessionStorage.getItem(`${CHAVE_SESSAO}_nome`) || "");
