"""Pruebas del modelo de pronóstico con series inventadas (no necesitan SQL Server)."""
import joblib
import numpy as np
import pandas as pd
import pytest

from ml import modelos as M


def _serie(n=41, base=4e6, tendencia=0.0, estacional=0.0, ruido=0.0, semilla=1, inicio="2013-01"):
    rng = np.random.default_rng(semilla)
    idx = pd.period_range(inicio, periods=n, freq="M")
    t = np.arange(n)
    mes = np.array([p.month for p in idx])
    y = base * (1 + tendencia * t + estacional * np.sin(2 * np.pi * mes / 12)) * (1 + ruido * rng.standard_normal(n))
    return pd.Series(y, index=idx)


def test_modelos_basicos_dan_lo_esperado():
    y = pd.Series([10.0, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140],
                  index=pd.period_range("2015-01", periods=14, freq="M"))
    assert list(M.UltimoValor().fit(y).predict(3)) == [140, 140, 140]
    assert M.MediaMovil(3).fit(y).predict(2)[0] == pytest.approx(130)
    # el mes siguiente a 2016-02 es marzo; hace un año fue 2015-03 = 30
    assert M.MismoMesAnioPasado().fit(y).predict(2)[0] == 30
    # una recta perfecta se extrapola exacta
    assert M.Tendencia().fit(y).predict(2) == pytest.approx([150, 160])


def test_estacional_aprende_un_patron_claro():
    y = _serie(n=36, estacional=0.3, ruido=0.0)
    pred = M.TendenciaEstacional().fit(y.iloc[:-6]).predict(6)
    assert np.mean(np.abs(pred - y.iloc[-6:].values) / y.iloc[-6:].values) < 0.05


def test_con_estacionalidad_fuerte_gana_un_modelo_estacional():
    y = _serie(n=41, estacional=0.35, ruido=0.02)
    r = M.entrenar_y_pronosticar(y)
    assert r["ganador"] in ("tendencia_estacional", "mismo_mes_anio_pasado")


def test_con_tendencia_clara_el_baseline_no_gana():
    y = _serie(n=41, tendencia=0.03, ruido=0.01)
    r = M.entrenar_y_pronosticar(y)
    assert r["ganador"] in ("tendencia_lineal", "tendencia_estacional")


def test_el_baseline_siempre_se_reporta_y_hay_un_solo_ganador():
    r = M.entrenar_y_pronosticar(_serie(ruido=0.1))
    assert sum(m["es_baseline"] for m in r["metricas"]) == 1
    assert sum(m["ganador"] for m in r["metricas"]) == 1


def test_pronostico_tiene_horizonte_meses_correctos_y_rangos_ordenados():
    y = _serie(ruido=0.05)
    r = M.entrenar_y_pronosticar(y, horizonte=6)
    p = r["pronostico"]
    assert len(p) == 6
    assert p[0]["mes"] == str(y.index[-1] + 1) and p[-1]["mes"] == str(y.index[-1] + 6)
    for fila in p:
        assert 0 <= fila["inferior"] <= fila["valor"] <= fila["superior"]


def test_la_prueba_son_los_ultimos_meses_y_no_se_usa_para_elegir():
    """Si se cambian SOLO los meses de prueba, el ganador y las métricas de validación no cambian."""
    y = _serie(ruido=0.05)
    r1 = M.entrenar_y_pronosticar(y)
    y2 = y.copy()
    y2.iloc[-6:] = y2.iloc[-6:] * 3
    r2 = M.entrenar_y_pronosticar(y2)
    assert r1["ganador"] == r2["ganador"]
    for a, b in zip(r1["metricas"], r2["metricas"]):
        assert a["mae_validacion"] == pytest.approx(b["mae_validacion"])
        assert a["mae_prueba"] != pytest.approx(b["mae_prueba"])


def test_validacion_nunca_usa_el_futuro():
    """Una serie que cambia de nivel al final no puede 'filtrarse' hacia pliegues anteriores."""
    y = pd.Series(np.r_[np.full(30, 100.0), np.full(11, 1000.0)],
                  index=pd.period_range("2013-01", periods=41, freq="M"))
    cv = M.validacion_cruzada(y.iloc[:30], [M.UltimoValor()], horizonte=6, origen_min=18)
    assert cv["ultimo_valor"]["mae"] == 0       # dentro de los primeros 30 meses todo vale 100


def test_pocos_meses_no_prometen_pronostico():
    with pytest.raises(ValueError, match="No se promete"):
        M.entrenar_y_pronosticar(_serie(n=20))


def test_preparar_serie_descarta_mes_incompleto_y_rechaza_huecos():
    df = pd.DataFrame({"mes": ["2016-03", "2016-04", "2016-05"], "ventas": [1, 2, 3]})
    assert len(M.preparar_serie(df, "2016-05-31")) == 3          # mayo completo
    assert len(M.preparar_serie(df, "2016-05-17")) == 2          # mayo incompleto: se descarta
    hueco = pd.DataFrame({"mes": ["2016-01", "2016-03"], "ventas": [1, 2]})
    with pytest.raises(ValueError, match="Faltan meses"):
        M.preparar_serie(hueco, "2016-03-31")


def test_el_modelo_guardado_se_puede_recargar_y_predice_igual(tmp_path):
    r = M.entrenar_y_pronosticar(_serie(ruido=0.05))
    archivo = tmp_path / "m.joblib"
    joblib.dump(r["modelo_final"], archivo)
    recargado = joblib.load(archivo)
    assert recargado.predict(6) == pytest.approx([p["valor"] for p in r["pronostico"]])
