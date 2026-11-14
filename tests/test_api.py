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
