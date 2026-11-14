"""Bitácora de preguntas al asistente (audit.asistente_consultas). Si falla, no rompe la respuesta."""
import json

from sqlalchemy import text

from etl.config import dw_engine


def guardar(pregunta, resultado=None, error=None):
    try:
        resultado = resultado or {}
        with dw_engine().begin() as cn:
            cn.execute(text("""
                INSERT INTO audit.asistente_consultas
                    (pregunta, herramientas, respuesta, respondida, modelo, duracion_ms, error)
                VALUES (:p, :h, :r, :ok, :m, :d, :e)"""),
                {"p": pregunta[:500], "h": json.dumps(resultado.get("fuentes", []), ensure_ascii=False, default=str)[:1000],
                 "r": resultado.get("respuesta"), "ok": 1 if resultado.get("respondida") else 0,
                 "m": resultado.get("modelo"), "d": resultado.get("duracion_ms"),
                 "e": (error or "")[:500] or None})
    except Exception:
        pass
