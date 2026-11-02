// Funções compartilhadas pela tela de extratos.
// Todo texto vindo do servidor entra via textContent: nunca innerHTML.

const ROTULOS_AUSENCIA = { atestado: "Atestado", falta_justificada: "Falta justificada", ferias: "Férias" };

function el(tag, props = {}, ...filhos) {
  const no = document.createElement(tag);
  for (const [chave, valor] of Object.entries(props)) {
    if (chave === "class") no.className = valor;
    else if (chave === "text") no.textContent = valor;
    else no.setAttribute(chave, valor);
  }
  no.append(...filhos);
  return no;
}

function dataBR(iso) {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function isoLocal(data) {
  const dois = (n) => String(n).padStart(2, "0");
  return `${data.getFullYear()}-${dois(data.getMonth() + 1)}-${dois(data.getDate())}`;
}

function periodoPadrao() {
  const hoje = new Date();
  return { inicio: isoLocal(new Date(hoje.getFullYear(), hoje.getMonth(), 1)), fim: isoLocal(hoje) };
}

function formatarCpf(cpf) {
  return `${cpf.slice(0, 3)}.${cpf.slice(3, 6)}.${cpf.slice(6, 9)}-${cpf.slice(9)}`;
}

function mensagemDeErro(resposta, dados) {
  if (resposta.status === 429) {
    const minutos = Math.ceil(Number(resposta.headers.get("Retry-After") || 0) / 60);
    return `Muitas tentativas com PIN errado. Tente de novo em ${minutos || 15} min.`;
  }
  const detalhe = dados?.detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe) && detalhe.length) {
    return detalhe.map((erro) => String(erro.msg).replace(/^Value error, /, "")).join("; ");
  }
  return "Dados inválidos.";
}

async function baixarArquivo(resposta, nomePadrao) {
  const blob = await resposta.blob();
  const url = URL.createObjectURL(blob);
  const cabecalho = resposta.headers.get("Content-Disposition") || "";
  const nome = (cabecalho.match(/filename="([^"]+)"/) || [])[1] || nomePadrao;
  const link = el("a", { href: url, download: nome });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

// opcoes.aoRemoverAusencia(id): quando informada, a tabela ganha a coluna de ações (modo administrador).
function renderizarExtrato(alvo, extrato, opcoes = {}) {
  alvo.replaceChildren();

  const cabecalho = ["Data", "Dia", "Marcações (entrada - saída)", "Horas", "Situação"];
  if (opcoes.aoRemoverAusencia) cabecalho.push("");

  const corpo = el("tbody");
  for (const dia of extrato.dias) {
    const marcacoes = dia.pares.map((p) => `${p.entrada} - ${p.saida ?? "(sem saída)"}`).join(" | ");
    const situacao = dia.situacao_texto + (dia.observacao ? ` - ${dia.observacao}` : "");

    const classes = [];
    if (!dia.dia_de_trabalho) classes.push("folga");
    if (dia.situacao === "falta") classes.push("falta");
    if (dia.situacao === "incompleta") classes.push("incompleto");
    if (dia.ausencia_id !== null) classes.push("ausencia");

    const linha = el("tr", { class: classes.join(" ") },
      el("td", { text: dataBR(dia.data) }),
      el("td", { text: dia.dia_semana }),
      el("td", { text: marcacoes }),
      el("td", { text: dia.horas }),
      el("td", { text: situacao }),
    );
    if (opcoes.aoRemoverAusencia) {
      const celula = el("td");
      if (dia.ausencia_id !== null) {
        const remover = el("button", { type: "button", class: "mini secundario", text: "Remover" });
        remover.addEventListener("click", () => opcoes.aoRemoverAusencia(dia.ausencia_id));
        celula.append(remover);
      }
      linha.append(celula);
    }
    corpo.append(linha);
  }

  const tabela = el("table", { class: "extrato" },
    el("thead", {}, el("tr", {}, ...cabecalho.map((titulo) => el("th", { text: titulo })))),
    corpo,
  );

  const totais = [
    ["Dias com marcação completa", String(extrato.dias_trabalhados)],
    ["Total de horas trabalhadas", extrato.total_horas],
    ["Horas esperadas", extrato.horas_esperadas],
    ["Saldo do período", extrato.saldo],
    ["Faltas não justificadas", String(extrato.faltas)],
  ];
  for (const [tipo, quantidade] of Object.entries(extrato.ausencias)) {
    totais.push([`${ROTULOS_AUSENCIA[tipo] || tipo} (dias)`, String(quantidade)]);
  }
  if (extrato.dias_incompletos) totais.push(["Dias com marcação incompleta", String(extrato.dias_incompletos)]);

  alvo.append(
    el("h2", { text: extrato.nome }),
    el("p", { class: "sub", text: `${extrato.cargo} · ${dataBR(extrato.inicio)} a ${dataBR(extrato.fim)}` }),
    el("div", { class: "tabela-rolagem" }, tabela),
    el("dl", { class: "totais" }, ...totais.flatMap(([rotulo, valor]) => [el("dt", { text: rotulo }), el("dd", { text: valor })])),
  );
}
