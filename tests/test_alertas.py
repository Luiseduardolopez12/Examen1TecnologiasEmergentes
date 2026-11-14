"""Pruebas de las reglas de alerta (números inventados, sin base de datos)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from alertas import acciones
from alertas.evaluar import sin_duplicar
from alertas.reglas import comprobar, desplazar_mes, ultimo_mes_completo, variacion_pct
from api import consultas
from api.main import app

cliente = TestClient(app)


def _serie(**meses):
    return {k.replace("_", "-"): v for k, v in meses.items()}


def _caida_mensual(c):
    return next(x for x in c if x["regla"] == "caida_mensual")


# ---- reglas ----
def test_caida_mayor_al_umbral_dispara():
    c = comprobar(_serie(**{"2016_03": 100.0, "2016_04": 80.0}), "2016-04")
    mensual = _caida_mensual(c)
    assert mensual["dispara"] and mensual["variacion_pct"] == -20.0
    assert mensual["severidad"] == "MEDIA" and "2016-04" in mensual["mensaje"]


def test_caida_menor_al_umbral_no_dispara():
    c = comprobar(_serie(**{"2016_03": 100.0, "2016_04": 90.0}), "2016-04")
    assert not _caida_mensual(c)["dispara"]


def test_justo_en_el_umbral_no_dispara_y_un_poco_mas_si():
    assert not _caida_mensual(comprobar(_serie(**{"2016_03": 100.0, "2016_04": 85.0}), "2016-04"))["dispara"]
    assert _caida_mensual(comprobar(_serie(**{"2016_03": 100.0, "2016_04": 84.9}), "2016-04"))["dispara"]


def test_crecimiento_no_dispara():
    assert not _caida_mensual(comprobar(_serie(**{"2016_03": 100.0, "2016_04": 150.0}), "2016-04"))["dispara"]


def test_severidad_alta_desde_30_por_ciento():
    c = comprobar(_serie(**{"2016_03": 100.0, "2016_04": 70.0}), "2016-04")
    assert _caida_mensual(c)["severidad"] == "ALTA"


def test_interanual_compara_con_el_mismo_mes_del_anio_pasado():
    serie = {"2015-04": 200.0, "2015-05": 100.0, "2016-04": 100.0, "2016-05": 150.0}
    c = comprobar(serie, "2016-04")           # contra 2016-03 no hay dato; contra 2015-04 cae 50 %
    assert [x["regla"] for x in c] == ["caida_interanual"]
    assert c[0]["dispara"] and c[0]["referencia_mes"] == "2015-04"


def test_sin_mes_de_referencia_no_inventa_datos():
    assert comprobar({"2013-01": 100.0}, "2013-01") == []          # primer mes de la historia
    assert comprobar({"2013-01": 100.0}, "2013-05") == []          # mes que no existe
    assert comprobar({"2016-03": 0.0, "2016-04": 5.0}, "2016-04") == []   # referencia cero


def test_umbral_configurable():
    serie = _serie(**{"2016_03": 100.0, "2016_04": 90.0})
    assert _caida_mensual(comprobar(serie, "2016-04", umbral=5))["dispara"]


def test_aritmetica_de_meses():
    assert desplazar_mes("2016-03", 1) == "2016-02"
    assert desplazar_mes("2016-01", 1) == "2015-12"
    assert desplazar_mes("2016-03", 12) == "2015-03"
    assert variacion_pct(80, 100) == -20 and variacion_pct(1, None) is None


def test_ultimo_mes_completo_ignora_el_mes_a_medias():
    meses = ["2016-03", "2016-04", "2016-05"]
    assert ultimo_mes_completo(meses, date(2016, 5, 31)) == "2016-05"
    assert ultimo_mes_completo(meses, date(2016, 5, 17)) == "2016-04"
    assert ultimo_mes_completo([], date(2016, 5, 31)) is None


# ---- sin duplicados ----
def test_no_se_duplican_alertas_ya_registradas():
    a = {"regla": "caida_mensual", "periodo": "2016-04", "ambito": "Global"}
    b = {"regla": "caida_interanual", "periodo": "2016-04", "ambito": "Global"}
    existentes = {("caida_mensual", "2016-04", "Global")}
    nuevas, repetidas = sin_duplicar([a, b], existentes)
    assert nuevas == [b] and repetidas == 1
    assert sin_duplicar([a, b], {("caida_mensual", "2016-04", "Global"),
                                 ("caida_interanual", "2016-04", "Global")}) == ([], 2)


# ---- API ----
@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setenv("API_USER", "admin")
    monkeypatch.setenv("API_PASSWORD", "clave123")
    monkeypatch.setenv("API_SECRET", "secreto-de-prueba")


def _token():
    r = cliente.post("/auth/login", json={"usuario": "admin", "clave": "clave123"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_alertas_sin_tabla_devuelve_lista_vacia(monkeypatch):
    monkeypatch.setattr(consultas, "consultar", lambda sql, params=None: [{"o": None}])
    assert cliente.get("/api/alertas", headers=_token()).json() == []


def test_alertas_filtra_por_estado_con_parametros(monkeypatch):
    llamadas = []

    def falsa(sql, params=None):
        llamadas.append((sql, params))
        return [{"o": 5}] if "OBJECT_ID" in sql else [{"alerta_id": 1}]
    monkeypatch.setattr(consultas, "consultar", falsa)
    r = cliente.get("/api/alertas", params={"estado": "NUEVA"}, headers=_token())
    assert r.json() == [{"alerta_id": 1}]
    sql, params = llamadas[-1]
    assert params["estado"] == "NUEVA" and ":estado" in sql
    assert cliente.get("/api/alertas", params={"estado": "x'; DROP TABLE a;--"}, headers=_token()).status_code == 422


def test_revisar_alerta(monkeypatch):
    monkeypatch.setattr(acciones, "marcar_revisada", lambda i: i == 7)
    assert cliente.post("/api/alertas/7/revisar", headers=_token()).json()["estado"] == "REVISADA"
    assert cliente.post("/api/alertas/8/revisar", headers=_token()).status_code == 404


def test_alertas_exigen_token():
    assert cliente.get("/api/alertas").status_code == 401
    assert cliente.post("/api/alertas/1/revisar").status_code == 401
