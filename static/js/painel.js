const CHAVE_ADMIN = "ponto_admin_token";
const telaLogin = document.getElementById("tela-login");
const telaPainel = document.getElementById("tela-painel");
const mensagem = document.getElementById("mensagem");
const campoInicio = document.getElementById("inicio");
const campoFim = document.getElementById("fim");
const corpoResumo = document.getElementById("corpo-resumo");
const blocoDetalhe = document.getElementById("detalhe-bloco");

let token = sessionStorage.getItem(CHAVE_ADMIN);
let funcionarioAberto = null;

function mostrar(texto) {
  mensagem.textContent = texto;
  mensagem.className = texto ? "erro" : "";
}

function consulta() {
  return `inicio=${encodeURIComponent(campoInicio.value)}&fim=${encodeURIComponent(campoFim.value)}`;
}

function buscar(caminho) {
  const separador = caminho.includes("?") ? "&" : "?";
  return fetch(`${caminho}${separador}${consulta()}`, { headers: { "X-Admin-Token": token } });
}

function sair(aviso = "") {
  token = null;
  funcionarioAberto = null;
  sessionStorage.removeItem(CHAVE_ADMIN);
  telaPainel.hidden = true;
  telaLogin.hidden = false;
  mostrar(aviso);
}

async function baixar(caminho, nomePadrao) {
  mostrar("");
  const resposta = await buscar(caminho);
  if (resposta.status === 401) return sair("Token inválido ou expirado.");
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, await resposta.json()));
  await baixarArquivo(resposta, nomePadrao);
}

async function verFuncionario(id) {
  mostrar("");
  const resposta = await buscar(`/admin/extrato/${id}`);
  if (resposta.status === 401) return sair("Token inválido ou expirado.");
  const dados = await resposta.json();
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, dados));
  funcionarioAberto = id;
  renderizarExtrato(document.getElementById("detalhe"), dados);
  blocoDetalhe.hidden = false;
  blocoDetalhe.scrollIntoView({ behavior: "smooth" });
}

function linhaResumo(item) {
  const botaoVer = el("button", { type: "button", class: "mini", text: "Ver" });
  botaoVer.addEventListener("click", () => verFuncionario(item.usuario_id));
  const botaoPdf = el("button", { type: "button", class: "mini secundario", text: "PDF" });
  botaoPdf.addEventListener("click", () => baixar(`/admin/extrato/${item.usuario_id}/pdf`, "extrato.pdf"));

  return el("tr", { class: item.dias_incompletos ? "incompleto" : "" },
    el("td", { text: item.nome }),
    el("td", { text: item.cargo }),
    el("td", { text: String(item.dias_trabalhados) }),
    el("td", { text: item.total_horas }),
    el("td", { text: item.saldo }),
    el("td", { text: String(item.dias_incompletos) }),
    el("td", { class: "acoes" }, botaoVer, botaoPdf),
  );
}

async function carregarResumo() {
  mostrar("");
  const resposta = await buscar("/admin/resumo");
  if (resposta.status === 401) return sair("Token inválido ou expirado.");
  const dados = await resposta.json();
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, dados));
  corpoResumo.replaceChildren(...dados.map(linhaResumo));
  document.getElementById("vazio").hidden = dados.length > 0;
  if (funcionarioAberto !== null) verFuncionario(funcionarioAberto);
}

document.getElementById("form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  mostrar("");
  const candidato = document.getElementById("token").value;
  try {
    const resposta = await fetch("/usuarios/", { headers: { "X-Admin-Token": candidato } });
    if (!resposta.ok) return mostrar("Token de administrador inválido.");
  } catch (erro) {
    return mostrar("Sem conexão com o servidor.");
  }
  token = candidato;
  sessionStorage.setItem(CHAVE_ADMIN, token);
  document.getElementById("token").value = "";
  abrirPainel();
});

function abrirPainel() {
  telaLogin.hidden = true;
  telaPainel.hidden = false;
  carregarResumo();
}

document.getElementById("form-periodo").addEventListener("submit", (evento) => {
  evento.preventDefault();
  carregarResumo();
});
document.getElementById("baixar-zip").addEventListener("click", () => baixar("/admin/extratos/zip", "extratos.zip"));
document.getElementById("baixar-detalhe").addEventListener("click", () => {
  if (funcionarioAberto !== null) baixar(`/admin/extrato/${funcionarioAberto}/pdf`, "extrato.pdf");
});
document.getElementById("sair").addEventListener("click", () => sair());

const padrao = periodoPadrao();
campoInicio.value = padrao.inicio;
campoFim.value = padrao.fim;
if (token) abrirPainel();
