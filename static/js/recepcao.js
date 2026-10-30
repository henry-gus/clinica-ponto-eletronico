const INTERVALO_SEGUNDOS = 60;
const contador = document.getElementById("contador");
const areaQr = document.getElementById("qrcode");
let restante = INTERVALO_SEGUNDOS;

async function atualizarQR() {
  try {
    const resposta = await fetch("/qr-token");
    const { url } = await resposta.json();
    areaQr.innerHTML = "";
    new QRCode(areaQr, { text: url, width: 220, height: 220 });
    restante = INTERVALO_SEGUNDOS;
  } catch (erro) {
    console.error("Falha ao atualizar o QR Code", erro);
  }
}

setInterval(() => {
  restante -= 1;
  if (restante <= 0) atualizarQR();
  contador.textContent = Math.max(restante, 0);
}, 1000);

atualizarQR();
