// Funções compartilhadas pelas telas de extrato (funcionário e painel do admin).
// Todo texto vindo do servidor entra via textContent: nunca innerHTML.

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

function mensagemDeErro(resposta, dados) {
  if (resposta.status === 429) {
    const minutos = Math.ceil(Number(resposta.headers.get("Retry-After") || 0) / 60);
    return `Muitas tentativas com PIN errado. Tente de novo em ${minutos || 15} min.`;
  }
  return typeof dados?.detail === "string" ? dados.detail : "Dados inválidos.";
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

function renderizarExtrato(alvo, extrato) {
  alvo.replaceChildren();

  const cabecalho = ["Data", "Dia", "Marcações (entrada - saída)", "Horas", "Obs."];
  const corpo = el("tbody");
  for (const dia of extrato.dias) {
    const marcacoes = dia.pares.map((p) => `${p.entrada} - ${p.saida ?? "(sem saída)"}`).join(" | ");
    const classes = [["Sáb", "Dom"].includes(dia.dia_semana) ? "fds" : "", dia.incompleto ? "incompleto" : ""];
    corpo.append(
      el("tr", { class: classes.join(" ").trim() },
        el("td", { text: dataBR(dia.data) }),
        el("td", { text: dia.dia_semana }),
        el("td", { text: marcacoes }),
        el("td", { text: dia.horas }),
        el("td", { text: dia.incompleto ? "Incompleta" : "" }),
      ),
    );
  }
  const tabela = el("table", { class: "extrato" },
    el("thead", {}, el("tr", {}, ...cabecalho.map((titulo) => el("th", { text: titulo })))),
    corpo,
  );

  const totais = [
    ["Dias com marcação completa", String(extrato.dias_trabalhados)],
    ["Total de horas trabalhadas", extrato.total_horas],
    [`Horas esperadas (jornada de ${extrato.carga_horaria_diaria} h)`, extrato.horas_esperadas],
    ["Saldo do período", extrato.saldo],
  ];
  if (extrato.dias_incompletos) totais.push(["Dias com marcação incompleta", String(extrato.dias_incompletos)]);

  alvo.append(
    el("h2", { text: extrato.nome }),
    el("p", { class: "sub", text: `${extrato.cargo} · ${dataBR(extrato.inicio)} a ${dataBR(extrato.fim)}` }),
    el("div", { class: "tabela-rolagem" }, tabela),
    el("dl", { class: "totais" }, ...totais.flatMap(([rotulo, valor]) => [el("dt", { text: rotulo }), el("dd", { text: valor })])),
  );
}
