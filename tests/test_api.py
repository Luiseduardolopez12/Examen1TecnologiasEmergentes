"""Pruebas de la API con una base falsa (no necesitan SQL Server)."""
import pytest
from fastapi.testclient import TestClient

from api import consultas
from api.main import app

cliente = TestClient(app)
LLAMADAS = []


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setenv("API_USER", "admin")
    monkeypatch.setenv("API_PASSWORD", "clave123")
    monkeypatch.setenv("API_SECRET", "secreto-de-prueba")
    LLAMADAS.clear()

    def falsa(sql, params=None):
        LLAMADAS.append((sql, params or {}))
        if "SUM(f.NetSales), 0)     AS ventas_netas" in sql:
            return [{"ventas_netas": 1000, "ganancia": 250, "unidades": 40, "facturas": 8, "clientes": 5}]
        if "COUNT(*) AS total" in sql:
            return [{"total": 45}]
        return []

    monkeypatch.setattr(consultas, "consultar", falsa)


def _token():
    r = cliente.post("/auth/login", json={"usuario": "admin", "clave": "clave123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_login_con_clave_mala_da_401():
    r = cliente.post("/auth/login", json={"usuario": "admin", "clave": "mala"})
    assert r.status_code == 401


def test_endpoints_sin_token_dan_401():
    assert cliente.get("/api/kpis").status_code == 401
    assert cliente.get("/api/kpis", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_token_alterado_se_rechaza():
    cuerpo, firma = _token()["Authorization"][7:].split(".")
    malo = {"Authorization": f"Bearer {cuerpo}.{'0' * len(firma)}"}
    assert cliente.get("/api/kpis", headers=malo).status_code == 401


def test_kpis_calculan_ratios_sobre_totales():
    r = cliente.get("/api/kpis", headers=_token())
    assert r.status_code == 200
    d = r.json()
    assert d["margen_pct"] == 25.0          # 250 / 1000
    assert d["ticket_promedio"] == 125.0    # 1000 / 8


def test_filtros_viajan_como_parametros_y_no_en_el_texto_del_sql():
    ataque = "x'; DROP TABLE dw.FactSales;--"
    cliente.get("/api/kpis", params={"grupo": ataque, "desde": "2016-01-01"}, headers=_token())
    sql, params = LLAMADAS[-1]
    assert params["grupo"] == ataque
    assert "DROP TABLE" not in sql
    assert ":grupo" in sql and ":desde" in sql


def test_fecha_desde_mayor_que_hasta_da_400():
    r = cliente.get("/api/kpis", params={"desde": "2016-05-01", "hasta": "2016-01-01"}, headers=_token())
    assert r.status_code == 400


def test_detalle_pagina_correctamente():
    r = cliente.get("/api/detalle", params={"pagina": 3, "tamano": 20}, headers=_token())
    assert r.status_code == 200
    assert r.json()["total"] == 45
    assert LLAMADAS[-1][1]["salto"] == 40   # (3 - 1) * 20


def test_limites_invalidos_dan_422():
    assert cliente.get("/api/top-productos", params={"limite": 0}, headers=_token()).status_code == 422
    assert cliente.get("/api/detalle", params={"tamano": 5000}, headers=_token()).status_code == 422


def test_token_pegado_con_comillas_o_con_bearer_repetido_tambien_sirve():
    token = _token()["Authorization"][7:]
    for pegado in (f'"{token}"', f"Bearer {token}", f"  {token}  "):
        r = cliente.get("/api/kpis", headers={"Authorization": f"Bearer {pegado}"})
        assert r.status_code == 200, pegado


def test_pronostico_sin_tabla_o_sin_filas_responde_no_disponible(monkeypatch):
    monkeypatch.setattr(consultas, "consultar", lambda sql, params=None: [{"o": None}])
    assert cliente.get("/api/pronostico", headers=_token()).json() == {"disponible": False}
    monkeypatch.setattr(consultas, "consultar",
                        lambda sql, params=None: [{"o": 1, "r": None}])
    assert cliente.get("/api/pronostico", headers=_token()).json() == {"disponible": False}


def test_pronostico_devuelve_prediccion_metricas_e_historial(monkeypatch):
    def falsa(sql, params=None):
        if "OBJECT_ID" in sql:
            return [{"o": 99}]
        if "MAX(ml_run_id)" in sql:
            return [{"r": 7}]
        if "FROM dw.PronosticoVentas" in sql:
            assert params == {"run": 7}
            return [{"mes": "2016-06", "horizonte_mes": 1, "valor": 4.5, "inferior": 4.0, "superior": 5.0,
                     "modelo": "tendencia_lineal", "version": "v1", "base_hasta": "2016-05", "generado_en": "2026-11-14"}]
        if "audit.ml_metricas" in sql:
            return [{"modelo": "tendencia_lineal", "es_baseline": 0, "ganador": 1, "mae_validacion": 1, "rmse_validacion": 1,
                     "mape_validacion": 1, "mae_prueba": 1, "rmse_prueba": 1, "mape_prueba": 1}]
        return [{"mes": "2016-05", "ventas_netas": 4.1, "ganancia": 2.0}]      # historial

    monkeypatch.setattr(consultas, "consultar", falsa)
    d = cliente.get("/api/pronostico", headers=_token()).json()
    assert d["disponible"] and d["modelo"] == "tendencia_lineal" and d["base_hasta"] == "2016-05"
    assert d["metricas"][0]["ganador"] is True and d["metricas"][0]["es_baseline"] is False
    assert d["pronostico"][0]["mes"] == "2016-06" and d["historial"][0]["mes"] == "2016-05"


def test_pronostico_exige_token():
    assert cliente.get("/api/pronostico").status_code == 401
