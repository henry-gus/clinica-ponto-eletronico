import pytest

from app import models
from tests.conftest import novo_usuario

SEMANA = "inicio=2026-10-01&fim=2026-10-09"


def registrar(client, cab, usuario_id, tipo="atestado", inicio="2026-10-05", fim="2026-10-06", observacao=None):
    return client.post(
        "/admin/ausencias",
        json={"usuario_id": usuario_id, "tipo": tipo, "inicio": inicio, "fim": fim, "observacao": observacao},
        headers=cab,
    )


def test_registra_um_dia_por_data_do_intervalo(client, db, usuario, admin, cab_admin):
    resposta = registrar(client, cab_admin, usuario["id"], "ferias", "2026-10-02", "2026-10-06", "  férias de outubro  ")

    assert resposta.status_code == 201
    dias = resposta.json()
    assert [d["data"] for d in dias] == ["2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06"]  # inclui fim de semana
    assert all(d["tipo"] == "ferias" and d["observacao"] == "férias de outubro" for d in dias)
    # fica registrado quem lançou
    assert {a.registrado_por for a in db.query(models.Ausencia).all()} == {admin["id"]}


def test_observacao_vazia_vira_nulo(client, usuario, cab_admin):
    assert registrar(client, cab_admin, usuario["id"], observacao="   ").json()[0]["observacao"] is None


def test_conflito_nao_grava_nada(client, db, usuario, cab_admin):
    registrar(client, cab_admin, usuario["id"], "atestado", "2026-10-06", "2026-10-07")
    antes = db.query(models.Ausencia).count()

    resposta = registrar(client, cab_admin, usuario["id"], "ferias", "2026-10-05", "2026-10-08")

    assert resposta.status_code == 409
    assert "06/10/2026, 07/10/2026" in resposta.json()["detail"]
    assert db.query(models.Ausencia).count() == antes  # nem o dia 05 nem o 08 entraram


def test_mesmo_dia_para_pessoas_diferentes_nao_conflita(client, usuario, cab_admin):
    bia = novo_usuario(client, cab_admin, "Bia Lima", "111.444.777-35")
    assert registrar(client, cab_admin, usuario["id"]).status_code == 201
    assert registrar(client, cab_admin, bia["id"]).status_code == 201


@pytest.mark.parametrize("corpo, status", [
    ({"inicio": "2026-10-06", "fim": "2026-10-05"}, 422),            # fim antes do início
    ({"inicio": "2025-01-01", "fim": "2026-10-05"}, 422),            # mais de 366 dias
    ({"tipo": "folga"}, 422),                                        # tipo desconhecido
    ({"observacao": "x" * 201}, 422),
    ({"inicio": "ontem"}, 422),
    ({"usuario_id": 999}, 404),
])
def test_pedidos_invalidos(client, usuario, cab_admin, corpo, status):
    base = {"usuario_id": usuario["id"], "tipo": "atestado", "inicio": "2026-10-05", "fim": "2026-10-06"}
    assert client.post("/admin/ausencias", json={**base, **corpo}, headers=cab_admin).status_code == status


def test_remover_devolve_o_dia_a_falta(client, usuario, cab_ana, cab_admin, hoje_em_novembro):
    ausencias = registrar(client, cab_admin, usuario["id"], "atestado", "2026-10-05", "2026-10-05").json()

    # Ana não tem marcação alguma: dias de trabalho 01, 02, 05, 06, 07, 08, 09. O atestado abona o dia 05.
    antes = client.get(f"/extratos/meu?{SEMANA}", headers=cab_ana).json()
    assert (antes["faltas"], antes["ausencias"]) == (6, {"atestado": 1})

    assert client.delete(f"/admin/ausencias/{ausencias[0]['id']}", headers=cab_admin).status_code == 204
    depois = client.get(f"/extratos/meu?{SEMANA}", headers=cab_ana).json()
    assert (depois["faltas"], depois["ausencias"]) == (7, {})

    assert client.delete(f"/admin/ausencias/{ausencias[0]['id']}", headers=cab_admin).status_code == 404


def test_apos_remover_da_para_registrar_de_novo(client, usuario, cab_admin):
    primeira = registrar(client, cab_admin, usuario["id"]).json()
    for ausencia in primeira:
        client.delete(f"/admin/ausencias/{ausencia['id']}", headers=cab_admin)
    assert registrar(client, cab_admin, usuario["id"], "ferias").status_code == 201


def test_funcionario_ve_as_proprias_ausencias_mas_nao_altera(client, usuario, cab_ana, cab_admin, hoje_em_novembro):
    ausencia = registrar(client, cab_admin, usuario["id"], "falta_justificada", "2026-10-05", "2026-10-05", "mudança").json()[0]

    dados = client.get(f"/extratos/meu?{SEMANA}", headers=cab_ana).json()
    dia = next(d for d in dados["dias"] if d["data"] == "2026-10-05")
    assert (dia["situacao_texto"], dia["observacao"]) == ("Falta justificada", "mudança")

    assert client.delete(f"/admin/ausencias/{ausencia['id']}", headers=cab_ana).status_code == 403
    assert registrar(client, cab_ana, usuario["id"], inicio="2026-10-08", fim="2026-10-08").status_code == 403
