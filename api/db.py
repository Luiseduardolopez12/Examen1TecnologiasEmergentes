"""Acceso de solo lectura al Data Warehouse. La API nunca escribe en la base."""
from sqlalchemy import text

from etl.config import dw_engine


def consultar(sql, params=None):
    """Ejecuta un SELECT y devuelve una lista de diccionarios."""
    with dw_engine().connect() as cn:
        filas = cn.execute(text(sql), params or {}).mappings().all()
    return [dict(f) for f in filas]
