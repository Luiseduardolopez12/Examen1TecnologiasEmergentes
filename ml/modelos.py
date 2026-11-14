"""Modelos de pronóstico mensual y la forma de evaluarlos.

Problema: predecir las ventas netas de los próximos 6 meses a partir de las ventas mensuales.
Decisión que apoya: cuánto inventario comprar y qué meta de ventas fijar.

Todos los modelos tienen la misma interfaz: fit(serie) y predict(h). La serie es un
pandas.Series con índice mensual (PeriodIndex).
"""
import copy

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge

Z_80 = 1.2816   # para un intervalo de 80 % si los errores son aproximadamente normales


# --------------------------------------------------------------------------- preparación

def preparar_serie(df, fecha_max):
    """df con columnas mes ('2016-05') y ventas. Devuelve la serie lista para modelar.

    - Si el último mes está incompleto (los datos no llegan a fin de mes) se descarta,
      porque compararlo con meses completos haría creer que las ventas se desploman.
    - Si falta algún mes en el medio se lanza un error: no se inventan datos.
    """
    y = pd.Series(df["ventas"].astype(float).values,
                  index=pd.PeriodIndex(df["mes"], freq="M")).sort_index()
    ultimo = y.index[-1]
    if pd.Timestamp(fecha_max).normalize() < ultimo.end_time.normalize():
        y = y.iloc[:-1]
    esperado = pd.period_range(y.index[0], y.index[-1], freq="M")
    if len(esperado) != len(y):
        faltan = [str(p) for p in esperado.difference(y.index)]
        raise ValueError(f"Faltan meses en la serie: {faltan}")
    return y


# --------------------------------------------------------------------------- modelos

class Modelo:
    nombre = ""
    descripcion = ""
    es_baseline = False

    def fit(self, y):
        raise NotImplementedError

    def predict(self, h):
        raise NotImplementedError

    def parametros(self):
        return {}


class UltimoValor(Modelo):
    """Baseline: el próximo mes vale lo mismo que el último observado."""
    nombre = "ultimo_valor"
    descripcion = "Repite el último mes observado"
    es_baseline = True

    def fit(self, y):
        self.ultimo_ = float(y.iloc[-1])
        return self

    def predict(self, h):
        return np.full(h, self.ultimo_)


class MediaMovil(Modelo):
    descripcion = "Promedio de los últimos meses, sin tendencia ni estacionalidad"

    def __init__(self, ventana=3):
        self.ventana = ventana
        self.nombre = f"media_movil_{ventana}"

    def fit(self, y):
        self.media_ = float(y.iloc[-self.ventana:].mean())
        return self

    def predict(self, h):
        return np.full(h, self.media_)

    def parametros(self):
        return {"ventana": self.ventana}


class MismoMesAnioPasado(Modelo):
    """Cada mes se predice con el mismo mes del año anterior (necesita 12 meses de historia)."""
    nombre = "mismo_mes_anio_pasado"
    descripcion = "Repite lo que se vendió el mismo mes un año antes"

    def fit(self, y):
        if len(y) < 12:
            raise ValueError("Se necesitan al menos 12 meses")
        self.ultimos_ = y.iloc[-12:].values.astype(float)
        return self

    def predict(self, h):
        return np.array([self.ultimos_[i % 12] for i in range(h)])


class Tendencia(Modelo):
    nombre = "tendencia_lineal"
    descripcion = "Recta ajustada al paso del tiempo (regresión lineal)"

    def fit(self, y):
        self.n_ = len(y)
        self.modelo_ = LinearRegression().fit(np.arange(self.n_).reshape(-1, 1), y.values)
        return self

    def predict(self, h):
        return self.modelo_.predict(np.arange(self.n_, self.n_ + h).reshape(-1, 1))


class TendenciaEstacional(Modelo):
    """Tendencia + un efecto por mes del año. Ridge evita que los efectos se disparen con tan pocos datos.

    El alpha es fijo y se eligió por razonamiento, no probando: cada mes aparece unas 3 veces en
    la historia, y Ridge encoge su efecto por un factor n / (n + alpha). Con alpha = 1 el efecto
    perdía ~30 %; con 0.1 pierde ~4 %. No se ajusta con los datos para no sobreajustar 41 puntos."""
    nombre = "tendencia_estacional"
    descripcion = "Tendencia lineal más un ajuste por mes del año (Ridge)"

    def __init__(self, alpha=0.1):
        self.alpha = alpha

    def _x(self, t, meses):
        dummies = np.zeros((len(t), 11))
        for i, m in enumerate(meses):
            if m > 1:
                dummies[i, m - 2] = 1
        return np.column_stack([(np.asarray(t) - self.mu_) / self.sd_, dummies])

    def fit(self, y):
        n = len(y)
        t = np.arange(n)
        self.mu_, self.sd_ = t.mean(), t.std() or 1.0
        self.escala_ = float(y.mean())          # se trabaja en "veces el promedio"
        self.n_, self.ultimo_ = n, y.index[-1]
        self.modelo_ = Ridge(alpha=self.alpha).fit(
            self._x(t, [p.month for p in y.index]), y.values / self.escala_)
        return self

    def predict(self, h):
        t = np.arange(self.n_, self.n_ + h)
        meses = [(self.ultimo_ + i).month for i in range(1, h + 1)]
        return self.modelo_.predict(self._x(t, meses)) * self.escala_

    def parametros(self):
        return {"alpha": self.alpha}


def candidatos():
    return [UltimoValor(), MediaMovil(3), MismoMesAnioPasado(), Tendencia(), TendenciaEstacional()]


# --------------------------------------------------------------------------- evaluación

def metricas(real, pred):
    real, pred = np.asarray(real, float), np.asarray(pred, float)
    e = pred - real
    return {"mae": float(np.mean(np.abs(e))),
            "rmse": float(np.sqrt(np.mean(e ** 2))),
            "mape": float(np.mean(np.abs(e) / real) * 100)}


def validacion_cruzada(y, modelos, horizonte, origen_min):
    """Validación hacia adelante: entrena con los primeros `o` meses y predice los siguientes
    `horizonte`, moviendo `o` de a un mes. Nunca se entrena con meses posteriores a los que se predicen."""
    resultado = {m.nombre: {"reales": [], "preds": []} for m in modelos}
    pliegues = 0
    for o in range(origen_min, len(y) - horizonte + 1):
        entrenamiento, real = y.iloc[:o], y.iloc[o:o + horizonte].values
        for m in modelos:
            pred = copy.deepcopy(m).fit(entrenamiento).predict(horizonte)
            resultado[m.nombre]["reales"].extend(real)
            resultado[m.nombre]["preds"].extend(pred)
        pliegues += 1
    if pliegues == 0:
        raise ValueError("No hay suficientes meses para validar")
    for nombre, r in resultado.items():
        r.update(metricas(r["reales"], r["preds"]))
        r["errores"] = np.array(r["preds"]) - np.array(r["reales"])
        r["pliegues"] = pliegues
    return resultado


def entrenar_y_pronosticar(y, horizonte=6, origen_min=18):
    """Flujo completo:
    1. Se aparta la PRUEBA: los últimos `horizonte` meses. No se toca hasta el final.
    2. Con lo demás se compara cada modelo por validación hacia adelante y se elige el de menor MAE.
    3. Recién entonces se mide en la prueba (modelo reentrenado con todo menos la prueba).
    4. El ganador se reentrena con todos los datos y predice los próximos `horizonte` meses.
    """
    if len(y) < origen_min + 2 * horizonte:
        raise ValueError(f"Solo hay {len(y)} meses; se necesitan al menos {origen_min + 2 * horizonte} "
                         "para entrenar, validar y probar. No se promete un pronóstico.")
    modelos = candidatos()
    entrenamiento, prueba = y.iloc[:-horizonte], y.iloc[-horizonte:]

    cv = validacion_cruzada(entrenamiento, modelos, horizonte, origen_min)
    ganador = min(modelos, key=lambda m: cv[m.nombre]["mae"])    # empate: gana el más simple (va primero)

    filas = []
    for m in modelos:
        en_prueba = metricas(prueba.values, copy.deepcopy(m).fit(entrenamiento).predict(horizonte))
        filas.append({
            "modelo": m.nombre, "descripcion": m.descripcion, "es_baseline": m.es_baseline,
            "ganador": m is ganador, "parametros": m.parametros(),
            **{f"{k}_validacion": cv[m.nombre][k] for k in ("mae", "rmse", "mape")},
            **{f"{k}_prueba": v for k, v in en_prueba.items()},
        })

    final = copy.deepcopy(ganador).fit(y)
    pred = final.predict(horizonte)
    sigma = cv[ganador.nombre]["rmse"]            # error típico observado al validar
    meses = [str(y.index[-1] + i) for i in range(1, horizonte + 1)]
    pronostico = [{"mes": mes, "horizonte_mes": i + 1, "valor": float(v),
                   "inferior": float(max(v - Z_80 * sigma, 0)), "superior": float(v + Z_80 * sigma)}
                  for i, (mes, v) in enumerate(zip(meses, pred))]

    return {"modelo_final": final, "ganador": ganador.nombre, "metricas": filas,
            "pronostico": pronostico, "base_hasta": str(y.index[-1]),
            "meses_entrenamiento": len(entrenamiento), "meses_prueba": len(prueba),
            "pliegues": cv[ganador.nombre]["pliegues"], "horizonte": horizonte}
