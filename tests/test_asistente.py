"""Pruebas del asistente con un Gemini y una base falsos (no gastan cuota ni necesitan SQL Server)."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from api import consultas
from api.main import app
from ia import asistente, gemini, herramientas

cliente = TestClient(app)
OPCIONES = {"grupos": ["Clothing", "Toys"], "territorios": ["Southeast", "Plains"],
            "rango": {"desde": "2013-01-01", "hasta": "2016-05-31"}}


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setenv("API_USER", "admin")
    monkeypatch.setenv("API_PASSWORD", "clave123")
    monkeypatch.setenv("API_SECRET", "secreto-de-prueba")
    monkeypatch.setattr(consultas, "opciones_filtros", lambda: OPCIONES)


class FalsoGemini:
    """Responde primero el plan y luego la redacción; guarda lo que se le pidió."""
    def __init__(self, plan):
        self.plan, self.llamadas = plan, []

    def __call__(self, prompt, sistema, como_json=False, **_):
        self.llamadas.append((prompt, como_json))
        if como_json:
            return (self.plan if isinstance(self.plan, str) else json.dumps(self.plan)), "modelo-falso"
        return "Respuesta redactada con los datos.", "modelo-falso"


@pytest.fixture
def sql(monkeypatch):
    """Cuenta las consultas reales que se intentaron ejecutar."""
    llamadas = []

    def falsa(nombre, valor):
        def f(*a, **k):
            llamadas.append((nombre, a, k))
            return valor
        return f
    for nombre, valor, usa_limite in [("kpis", {"ventas_netas": 100.0}, False),
                                      ("top_productos", [{"producto": "A", "ventas_netas": 5.0}], True),
                                      ("ventas_por_grupo", [{"grupo": "Toys", "ventas_netas": 9.0}], False)]:
        desc = herramientas.CATALOGO[nombre][0]
        monkeypatch.setitem(herramientas.CATALOGO, nombre, (desc, falsa(nombre, valor), usa_limite))
    return llamadas


def _plan(*consultas_):
    return {"consultas": [{"herramienta": h, "parametros": p} for h, p in consultas_]}


def test_pregunta_con_datos_ejecuta_la_herramienta_y_redacta(monkeypatch, sql):
    falso = FalsoGemini(_plan(("top_productos", {"limite": 3, "grupo": "Toys", "desde": "2016-01-01"})))
    monkeypatch.setattr(asistente, "generar", falso)
    r = asistente.responder("¿Cuáles son los 3 productos de juguetes más vendidos este año?")
    assert r["respondida"] and r["fuentes"][0]["herramienta"] == "top_productos"
    nombre, args, kwargs = sql[0]
    assert args == (3,) and kwargs["grupo"] == "Toys" and str(kwargs["desde"]) == "2016-01-01"
    assert len(falso.llamadas) == 2                       # planificar + redactar
    assert '"ventas_netas": 5.0' in falso.llamadas[1][0]  # la redacción recibió los datos reales


def test_sin_consultas_responde_no_tengo_el_dato_sin_llamar_a_la_ia_otra_vez(monkeypatch, sql):
    falso = FalsoGemini(_plan())
    monkeypatch.setattr(asistente, "generar", falso)
    r = asistente.responder("¿Cuántos empleados tiene la empresa?")
    assert not r["respondida"] and r["respuesta"] == asistente.SIN_DATO
    assert sql == [] and len(falso.llamadas) == 1


def test_herramienta_inventada_no_se_ejecuta(monkeypatch, sql):
    monkeypatch.setattr(asistente, "generar", FalsoGemini(_plan(("ejecutar_sql", {"consulta": "DROP TABLE dw.FactSales"}))))
    r = asistente.responder("borra todo")
    assert not r["respondida"] and sql == []
    assert "no existe" in r["respuesta"]


def test_grupo_inexistente_o_malicioso_se_rechaza(monkeypatch, sql):
    ataque = "x'; DROP TABLE dw.FactSales;--"
    monkeypatch.setattr(asistente, "generar", FalsoGemini(_plan(("kpis", {"grupo": ataque}))))
    r = asistente.responder("ventas del grupo raro")
    assert not r["respondida"] and sql == []
    assert "Grupos válidos" in r["respuesta"]


def test_fecha_mal_formada_o_invertida_se_rechaza():
    with pytest.raises(ValueError):
        herramientas.ejecutar("kpis", {"desde": "ayer"})
    with pytest.raises(ValueError):
        herramientas.ejecutar("kpis", {"desde": "2016-05-01", "hasta": "2016-01-01"})


def test_limite_se_acota(sql):
    herramientas.ejecutar("top_productos", {"limite": 999})
    assert sql[-1][1] == (20,)
    herramientas.ejecutar("top_productos", {"limite": -4})
    assert sql[-1][1] == (1,)


def test_una_consulta_buena_y_una_mala_responde_con_lo_que_se_pudo(monkeypatch, sql):
    falso = FalsoGemini(_plan(("kpis", {"hasta": "2016-05-31"}), ("kpis", {"territorio": "Marte"})))
    monkeypatch.setattr(asistente, "generar", falso)
    r = asistente.responder("compara con Marte")
    assert r["respondida"] and len(r["fuentes"]) == 1
    assert "Territorios válidos" in falso.llamadas[1][0]   # el modelo sabe qué no se pudo consultar


def test_el_plan_puede_venir_con_bloque_de_codigo(monkeypatch, sql):
    plan = "```json\n" + json.dumps(_plan(("kpis", {}))) + "\n```"
    monkeypatch.setattr(asistente, "generar", FalsoGemini(plan))
    assert asistente.responder("totales")["respondida"]


def test_plan_que_no_es_json_da_error_controlado(monkeypatch):
    monkeypatch.setattr(asistente, "generar", FalsoGemini("lo siento, no entiendo"))
    with pytest.raises(gemini.ErrorIA):
        asistente.responder("hola")


def test_pronostico_no_arrastra_el_historial(monkeypatch):
    monkeypatch.setattr(consultas, "pronostico", lambda: {"disponible": True, "historial": [1] * 60, "pronostico": []})
    datos, _ = herramientas.ejecutar("pronostico", {})
    assert "pronostico" in datos
    falso = FalsoGemini(_plan(("pronostico", {})))
    monkeypatch.setattr(asistente, "generar", falso)
    asistente.responder("¿cuánto venderemos?")
    assert "historial" not in falso.llamadas[1][0]


# ---- endpoint ----
def _token():
    r = cliente.post("/auth/login", json={"usuario": "admin", "clave": "clave123"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_endpoint_exige_token_y_valida_la_pregunta():
    assert cliente.post("/api/asistente", json={"pregunta": "hola"}).status_code == 401
    assert cliente.post("/api/asistente", json={"pregunta": "a"}, headers=_token()).status_code == 422
    assert cliente.post("/api/asistente", json={"pregunta": "x" * 501}, headers=_token()).status_code == 422


def test_endpoint_responde_y_registra(monkeypatch, sql):
    guardados = []
    monkeypatch.setattr("api.main.registro.guardar", lambda p, r=None, error=None: guardados.append((p, r, error)))
    monkeypatch.setattr(asistente, "generar", FalsoGemini(_plan(("kpis", {}))))
    r = cliente.post("/api/asistente", json={"pregunta": "¿cuánto vendimos?"}, headers=_token())
    assert r.status_code == 200 and r.json()["respondida"]
    assert guardados[0][0] == "¿cuánto vendimos?" and guardados[0][2] is None


def test_endpoint_da_503_amable_si_gemini_no_responde(monkeypatch):
    guardados = []
    monkeypatch.setattr("api.main.registro.guardar", lambda p, r=None, error=None: guardados.append(error))

    def cae(*a, **k):
        raise gemini.ErrorIA("todo caído")
    monkeypatch.setattr(asistente, "generar", cae)
    r = cliente.post("/api/asistente", json={"pregunta": "¿cuánto vendimos?"}, headers=_token())
    assert r.status_code == 503 and "no está disponible" in r.json()["detail"]
    assert guardados == ["todo caído"]


# ---- cliente de Gemini: reintento y respaldo ----
class Resp:
    def __init__(self, codigo, cuerpo=None):
        self.status_code, self._c = codigo, cuerpo or {}

    def json(self):
        return self._c


def _ok(texto):
    return Resp(200, {"candidates": [{"content": {"parts": [{"text": texto}]}}]})


@pytest.fixture
def gem(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave")
    monkeypatch.setenv("GEMINI_MODEL", "principal")
    monkeypatch.setenv("GEMINI_MODEL_RESPALDO", "respaldo")
    monkeypatch.setattr(gemini.time, "sleep", lambda s: None)


def test_gemini_cambia_al_respaldo_cuando_el_principal_da_503(monkeypatch, gem):
    usados = []

    def post(url, **k):
        usados.append(url.split("/models/")[1].split(":")[0])
        return Resp(503) if "principal" in url else _ok("hola")
    monkeypatch.setattr(gemini.httpx, "post", post)
    assert gemini.generar("p", "s") == ("hola", "respaldo")
    assert usados == ["principal", "principal", "respaldo"]     # 2 intentos y luego el respaldo


def test_gemini_no_reintenta_un_404_pero_si_prueba_el_respaldo(monkeypatch, gem):
    usados = []

    def post(url, **k):
        usados.append("principal" in url)
        return Resp(404) if "principal" in url else _ok("ok")
    monkeypatch.setattr(gemini.httpx, "post", post)
    assert gemini.generar("p", "s")[1] == "respaldo" and usados == [True, False]


def test_gemini_tolera_timeouts_y_falla_con_error_claro(monkeypatch, gem):
    def post(url, **k):
        raise httpx.ReadTimeout("lento")
    monkeypatch.setattr(gemini.httpx, "post", post)
    with pytest.raises(gemini.ErrorIA) as e:
        gemini.generar("p", "s")
    assert "ReadTimeout" in str(e.value)


def test_gemini_sin_clave_da_error_claro(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(gemini.ErrorIA):
        gemini.generar("p", "s")
