"""Registro de ejecuciones, watermarks y filas rechazadas en el esquema audit."""
from contextlib import contextmanager

import pandas as pd
from sqlalchemy import text

from etl.config import dw_engine


class Ejecucion:
    """Contadores de una corrida; se guardan en audit.etl_runs al terminar."""

    def __init__(self, execution_id):
        self.id = execution_id
        self.rows_read = 0
        self.rows_inserted = 0
        self.rows_updated = 0
        self.rows_rejected = 0
        self.watermark_start = None
        self.watermark_end = None


@contextmanager
def ejecucion(pipeline, origen, destino):
    eng = dw_engine()
    with eng.begin() as cn:
        run_id = cn.execute(text("""
            INSERT audit.etl_runs (pipeline_name, source_object, target_object)
            OUTPUT inserted.execution_id
            VALUES (:p, :o, :d)"""), {"p": pipeline, "o": origen, "d": destino}).scalar()

    run = Ejecucion(run_id)
    estado, error = "SUCCESS", None
    try:
        yield run
    except Exception as e:
        estado, error = "FAILED", str(e)[:4000]
        raise
    finally:
        with eng.begin() as cn:
            cn.execute(text("""
                UPDATE audit.etl_runs
                SET end_time = SYSDATETIME(), status = :st, error_detail = :err,
                    rows_read = :r, rows_inserted = :i, rows_updated = :u, rows_rejected = :x,
                    watermark_start = :ws, watermark_end = :we
                WHERE execution_id = :id"""), {
                "st": estado, "err": error, "r": run.rows_read, "i": run.rows_inserted,
                "u": run.rows_updated, "x": run.rows_rejected,
                "ws": run.watermark_start, "we": run.watermark_end, "id": run.id})
        print(f"[{pipeline}] {estado} | leídas={run.rows_read} insertadas={run.rows_inserted} "
              f"actualizadas={run.rows_updated} rechazadas={run.rows_rejected} (exec {run.id})")


def leer_watermark(objeto):
    with dw_engine().connect() as cn:
        return cn.execute(text(
            "SELECT watermark_value FROM audit.watermarks WHERE source_object = :o"),
            {"o": objeto}).scalar()


def guardar_watermark(objeto, valor):
    with dw_engine().begin() as cn:
        cn.execute(text("""
            MERGE audit.watermarks AS t
            USING (SELECT :o AS source_object, :v AS watermark_value) AS s
               ON t.source_object = s.source_object
            WHEN MATCHED THEN UPDATE SET watermark_value = s.watermark_value, updated_at = SYSDATETIME()
            WHEN NOT MATCHED THEN INSERT (source_object, watermark_value)
                 VALUES (s.source_object, s.watermark_value);"""), {"o": objeto, "v": valor})


def guardar_rechazos(rechazos, execution_id):
    if rechazos.empty:
        return
    rechazos = rechazos.assign(execution_id=execution_id)
    rechazos.to_sql("rejected_rows", dw_engine(), schema="audit", if_exists="append",
                    index=False, chunksize=2000)
