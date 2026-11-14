"""API del dashboard.

    uvicorn api.main:app --reload --port 8000
Documentación interactiva: http://localhost:8000/docs
"""
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api import consultas, seguridad

app = FastAPI(title="API Analítica de Ventas", version="1.0")

# El dashboard de Angular corre en el puerto 4200
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])


class Credenciales(BaseModel):
    usuario: str
    clave: str


def filtros(desde: Optional[date] = None, hasta: Optional[date] = None,
            grupo: Optional[str] = None, territorio: Optional[str] = None):
    if desde and hasta and desde > hasta:
        raise HTTPException(400, "La fecha 'desde' no puede ser posterior a 'hasta'")
    return {"desde": desde, "hasta": hasta, "grupo": grupo, "territorio": territorio}


@app.post("/auth/login")
def login(c: Credenciales):
    if not seguridad.validar_credenciales(c.usuario, c.clave):
        raise HTTPException(401, "Usuario o clave incorrectos")
    return {"token": seguridad.crear_token(c.usuario)}


@app.get("/salud")
def salud():
    return {"estado": "ok"}


# Todo lo demás exige token
protegido = [Depends(seguridad.usuario_actual)]


@app.get("/api/filtros", dependencies=protegido)
def opciones():
    return consultas.opciones_filtros()


@app.get("/api/ultima-actualizacion", dependencies=protegido)
def actualizacion():
    return consultas.ultima_actualizacion()


@app.get("/api/kpis", dependencies=protegido)
def kpis(f: dict = Depends(filtros)):
    return consultas.kpis(**f)


@app.get("/api/ventas-mensuales", dependencies=protegido)
def ventas_mensuales(f: dict = Depends(filtros)):
    return consultas.ventas_mensuales(**f)


@app.get("/api/top-productos", dependencies=protegido)
def top_productos(limite: int = Query(10, ge=1, le=50), f: dict = Depends(filtros)):
    return consultas.top_productos(limite, **f)


@app.get("/api/top-clientes", dependencies=protegido)
def top_clientes(limite: int = Query(10, ge=1, le=50), f: dict = Depends(filtros)):
    return consultas.top_clientes(limite, **f)


@app.get("/api/ventas-por-territorio", dependencies=protegido)
def por_territorio(f: dict = Depends(filtros)):
    return consultas.ventas_por_territorio(**f)


@app.get("/api/ventas-por-grupo", dependencies=protegido)
def por_grupo(f: dict = Depends(filtros)):
    return consultas.ventas_por_grupo(**f)


@app.get("/api/vendedores", dependencies=protegido)
def vendedores(f: dict = Depends(filtros)):
    return consultas.vendedores(**f)


@app.get("/api/detalle", dependencies=protegido)
def detalle(pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=100),
            f: dict = Depends(filtros)):
    return {"pagina": pagina, "tamano": tamano,
            "total": consultas.total_detalle(**f),
            "filas": consultas.detalle(pagina, tamano, **f)}


@app.get("/api/etl/ejecuciones", dependencies=protegido)
def ejecuciones(limite: int = Query(30, ge=1, le=200)):
    return consultas.ejecuciones_etl(limite)
