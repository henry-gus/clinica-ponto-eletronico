const token = new URLSearchParams(location.search).get("token");
const formulario = document.getElementById("formulario");
const mensagem = document.getElementById("mensagem");
const blocoComprovante = document.getElementById("comprovante");
const linkComprovante = document.getElementById("link-comprovante");

function mostrar(texto, classe) {
  mensagem.textContent = texto;
  mensagem.className = classe;
}

if (!token) {
  formulario.hidden = true;
  mostrar("Escaneie o QR Code da recepção para bater o ponto.", "erro");
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const botao = formulario.querySelector("button");
  botao.disabled = true;
  mostrar("", "");
  blocoComprovante.hidden = true;

  const id = document.getElementById("usuario_id").value.trim();
  const pin = document.getElementById("pin").value;

  try {
    const resposta = await fetch(`/ponto/${encodeURIComponent(id)}?token=${encodeURIComponent(token)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin }),
    });
    const dados = await resposta.json();
    if (!resposta.ok) {
      mostrar(typeof dados.detail === "string" ? dados.detail : "Dados inválidos.", "erro");
      return;
    }
    const horario = new Date(dados.momento).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" });
    const tipo = dados.tipo === "entrada" ? "Entrada" : "Saída";
    mostrar(`${tipo} registrada em ${horario} (NSR ${dados.nsr})`, "ok");
    linkComprovante.href = dados.comprovante_url;
    blocoComprovante.hidden = false;
    document.getElementById("pin").value = "";
  } catch (erro) {
    mostrar("Sem conexão com o servidor.", "erro");
  } finally {
    botao.disabled = false;
  }
});
