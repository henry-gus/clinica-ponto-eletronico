const CHAVE_TOKEN = "ponto_token";
const $ = (id) => document.getElementById(id);
const ROTULOS_PAPEL = { admin: "Administrador", funcionario: "Funcionário" };
const NOMES_DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

let sessao = null;       // { token, nome, papel }
let selecionado = null;  // administrador: id da pessoa aberta no detalhe

const ehAdmin = () => sessao !== null && sessao.papel === "admin";

function mostrar(texto, classe = "erro") {
  $("mensagem").textContent = texto;
  $("mensagem").className = texto ? classe : "";
}

function sair(aviso = "") {
  sessao = null;
  selecionado = null;
  sessionStorage.removeItem(CHAVE_TOKEN);
  $("tela-app").hidden = true;
  $("tela-login").hidden = false;
  mostrar(aviso);
}

// Chamada autenticada. Se a sessão expirou, volta ao login e devolve null.
async function chamar(caminho, opcoes = {}) {
  const resposta = await fetch(caminho, {
    ...opcoes,
    headers: { ...(opcoes.headers || {}), Authorization: `Bearer ${sessao.token}` },
  });
  if (resposta.status === 401) {
    sair("Sessão expirada. Entre novamente.");
    return null;
  }
  return resposta;
}

async function lerJson(resposta) {
  try {
    return await resposta.json();
  } catch (erro) {
    return null;
  }
}

const consulta = () => `inicio=${encodeURIComponent($("inicio").value)}&fim=${encodeURIComponent($("fim").value)}`;

// ------------------------------------------------------------------ abas
function abrirAba(nome) {
  document.querySelectorAll(".aba").forEach((botao) => botao.classList.toggle("ativa", botao.dataset.aba === nome));
  $("painel-extratos").hidden = nome !== "extratos";
  $("painel-funcionarios").hidden = nome !== "funcionarios";
  mostrar("");
  if (nome === "funcionarios") carregarFuncionarios();
}

// ----------------------------------------------------------------- extratos
async function carregarExtratos() {
  mostrar("");
  if (ehAdmin()) return carregarResumo();

  const resposta = await chamar(`/extratos/meu?${consulta()}`);
  if (!resposta) return;
  const dados = await lerJson(resposta);
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, dados));
  renderizarExtrato($("detalhe"), dados);
}

function linhaResumo(item) {
  const ver = el("button", { type: "button", class: "mini", text: "Ver" });
  ver.addEventListener("click", () => verPessoa(item.usuario_id));

  const classe = item.dias_incompletos ? "incompleto" : item.faltas ? "falta" : "";
  return el("tr", { class: classe },
    el("td", { text: item.nome }),
    el("td", { text: item.cargo }),
    el("td", { text: String(item.dias_trabalhados) }),
    el("td", { text: item.total_horas }),
    el("td", { text: item.saldo }),
    el("td", { text: String(item.faltas) }),
    el("td", { text: String(item.ausencias) }),
    el("td", { text: String(item.dias_incompletos) }),
    el("td", {}, ver),
  );
}

async function carregarResumo() {
  const resposta = await chamar(`/admin/resumo?${consulta()}`);
  if (!resposta) return;
  const dados = await lerJson(resposta);
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, dados));

  $("corpo-resumo").replaceChildren(...dados.map(linhaResumo));
  $("resumo-vazio").hidden = dados.length > 0;
  if (selecionado !== null) await verPessoa(selecionado);
}

async function verPessoa(id) {
  const resposta = await chamar(`/admin/extrato/${id}?${consulta()}`);
  if (!resposta) return;
  const dados = await lerJson(resposta);
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, dados));

  selecionado = id;
  renderizarExtrato($("detalhe"), dados, { aoRemoverAusencia: removerAusencia });
  $("bloco-detalhe").hidden = false;
  $("form-ausencia").hidden = false;
  $("baixar-pdf").disabled = false;
  $("bloco-detalhe").scrollIntoView({ behavior: "smooth" });
}

async function baixarPdf() {
  mostrar("");
  const caminho = ehAdmin() ? `/admin/extrato/${selecionado}/pdf` : "/extratos/meu/pdf";
  const resposta = await chamar(`${caminho}?${consulta()}`);
  if (!resposta) return;
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, await lerJson(resposta)));
  await baixarArquivo(resposta, "extrato.pdf");
}

async function baixarZip() {
  mostrar("");
  const resposta = await chamar(`/admin/extratos/zip?${consulta()}`);
  if (!resposta) return;
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, await lerJson(resposta)));
  await baixarArquivo(resposta, "extratos.zip");
}

// --------------------------------------------------------------- ausências
async function registrarAusencia(evento) {
  evento.preventDefault();
  if (selecionado === null) return;
  const resposta = await chamar("/admin/ausencias", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      usuario_id: selecionado,
      tipo: $("aus-tipo").value,
      inicio: $("aus-inicio").value,
      fim: $("aus-fim").value,
      observacao: $("aus-obs").value.trim() || null,
    }),
  });
  if (!resposta) return;
  const dados = await lerJson(resposta);
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, dados));

  $("aus-obs").value = "";
  await carregarResumo();
  mostrar(`${dados.length} dia(s) registrado(s).`, "ok");
}

async function removerAusencia(id) {
  if (!window.confirm("Remover este registro de ausência?")) return;
  const resposta = await chamar(`/admin/ausencias/${id}`, { method: "DELETE" });
  if (!resposta) return;
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, await lerJson(resposta)));
  await carregarResumo();
  mostrar("Registro removido.", "ok");
}

// ------------------------------------------------------------ funcionários
async function carregarFuncionarios() {
  const resposta = await chamar("/usuarios/");
  if (!resposta) return;
  const dados = await lerJson(resposta);
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, dados));

  $("corpo-funcionarios").replaceChildren(...dados.map((pessoa) => el("tr", {},
    el("td", { text: String(pessoa.id) }),
    el("td", { text: pessoa.nome }),
    el("td", { text: formatarCpf(pessoa.cpf) }),
    el("td", { text: pessoa.cargo }),
    el("td", { text: `${pessoa.carga_horaria_diaria} h` }),
    el("td", { text: pessoa.dias_trabalho.map((d) => NOMES_DIAS[d]).join(" ") }),
    el("td", { text: pessoa.data_inicio ? dataBR(pessoa.data_inicio) : "sempre" }),
    el("td", { text: ROTULOS_PAPEL[pessoa.papel] || pessoa.papel }),
  )));
}

async function cadastrarPessoa(evento) {
  evento.preventDefault();
  const dias = [...document.querySelectorAll("input[name=dia]:checked")].map((caixa) => Number(caixa.value));
  if (dias.length === 0) return mostrar("Marque ao menos um dia de trabalho.");

  const resposta = await chamar("/usuarios/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nome: $("f-nome").value.trim(),
      cpf: $("f-cpf").value.trim(),
      cargo: $("f-cargo").value.trim(),
      carga_horaria_diaria: Number($("f-jornada").value),
      pin: $("f-pin").value,
      papel: $("f-papel").value,
      dias_trabalho: dias,
      data_inicio: $("f-inicio").value || null,
    }),
  });
  if (!resposta) return;
  const dados = await lerJson(resposta);
  if (!resposta.ok) return mostrar(mensagemDeErro(resposta, dados));

  for (const campo of ["f-nome", "f-cpf", "f-cargo", "f-pin"]) $(campo).value = "";
  await carregarFuncionarios();
  mostrar(`${dados.nome} cadastrado(a) com o ID ${dados.id}.`, "ok");
}

// ------------------------------------------------------------------ sessão
function iniciarSessao() {
  const admin = ehAdmin();
  $("nome-usuario").textContent = sessao.nome;
  $("papel-usuario").textContent = `(${ROTULOS_PAPEL[sessao.papel] || sessao.papel})`;

  // O servidor é quem manda: estas linhas só escondem o que o perfil não usa.
  $("aba-funcionarios").hidden = !admin;
  $("bloco-resumo").hidden = !admin;
  $("baixar-zip").hidden = !admin;
  $("form-ausencia").hidden = true;
  $("bloco-detalhe").hidden = admin;   // administrador: aparece depois de "Ver"
  $("baixar-pdf").disabled = admin;    // administrador: habilita depois de escolher alguém
  $("detalhe").replaceChildren();
  selecionado = null;

  $("tela-login").hidden = true;
  $("tela-app").hidden = false;
  abrirAba("extratos");
  carregarExtratos();
}

$("form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  mostrar("");
  const botao = evento.target.querySelector("button");
  botao.disabled = true;
  try {
    const resposta = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario_id: Number($("usuario_id").value), pin: $("pin").value }),
    });
    const dados = await lerJson(resposta);
    if (!resposta.ok) return mostrar(mensagemDeErro(resposta, dados));
    sessao = { token: dados.token, nome: dados.nome, papel: dados.papel };
    sessionStorage.setItem(CHAVE_TOKEN, dados.token);
    $("pin").value = "";
    iniciarSessao();
  } catch (erro) {
    mostrar("Sem conexão com o servidor.");
  } finally {
    botao.disabled = false;
  }
});

document.querySelectorAll(".aba").forEach((botao) => botao.addEventListener("click", () => abrirAba(botao.dataset.aba)));
$("form-periodo").addEventListener("submit", (evento) => { evento.preventDefault(); carregarExtratos(); });
$("baixar-pdf").addEventListener("click", baixarPdf);
$("baixar-zip").addEventListener("click", baixarZip);
$("form-ausencia").addEventListener("submit", registrarAusencia);
$("form-funcionario").addEventListener("submit", cadastrarPessoa);
$("sair").addEventListener("click", () => sair());

const padrao = periodoPadrao();
$("inicio").value = padrao.inicio;
$("fim").value = padrao.fim;
$("aus-inicio").value = padrao.fim;
$("aus-fim").value = padrao.fim;
$("f-inicio").value = padrao.fim;

// Ao recarregar a página, retoma a sessão se o token ainda valer.
(async () => {
  const token = sessionStorage.getItem(CHAVE_TOKEN);
  if (!token) return;
  try {
    const resposta = await fetch("/auth/eu", { headers: { Authorization: `Bearer ${token}` } });
    if (!resposta.ok) return sessionStorage.removeItem(CHAVE_TOKEN);
    const dados = await resposta.json();
    sessao = { token, nome: dados.nome, papel: dados.papel };
    iniciarSessao();
  } catch (erro) {
    sessionStorage.removeItem(CHAVE_TOKEN);
  }
})();
