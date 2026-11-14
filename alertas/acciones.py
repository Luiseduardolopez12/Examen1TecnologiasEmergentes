"""Única escritura que hace la API sobre las alertas: marcarlas como revisadas."""
from sqlalchemy import text

from etl.config import dw_engine


def marcar_revisada(alerta_id):
    """Devuelve True si la alerta existía."""
    with dw_engine().begin() as cn:
        n = cn.execute(text("""
            UPDATE audit.alertas
            SET estado = 'REVISADA', revisada_en = COALESCE(revisada_en, SYSDATETIME())
            WHERE alerta_id = :id"""), {"id": alerta_id}).rowcount
    return n > 0
