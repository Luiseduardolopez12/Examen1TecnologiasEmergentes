"""Carga a staging: raw (solo agrega) y clean (upsert con MERGE)."""
from datetime import datetime

import pandas as pd
from sqlalchemy import text, types

from etl.config import dw_engine


def _tipos(df):
    # Sin esto pandas crea VARCHAR(max) y se pierden acentos y caracteres especiales.
    # is_string_dtype sirve tanto en pandas 2 (object) como en pandas 3 (str)
    return {c: types.NVARCHAR() for c in df.columns if pd.api.types.is_string_dtype(df[c])}


def cargar_raw(df, nombre, execution_id, reiniciar=False):
    """Guarda lo que llegó de la fuente sin tocarlo. En carga full se vacía primero."""
    eng = dw_engine()
    tabla = f"raw_{nombre}"
    if reiniciar:
        with eng.begin() as cn:
            cn.execute(text(f"IF OBJECT_ID('stg.{tabla}') IS NOT NULL TRUNCATE TABLE stg.{tabla}"))
    if df.empty:
        return
    crudo = df.assign(_execution_id=execution_id, _extracted_at=datetime.now())
    crudo.to_sql(tabla, eng, schema="stg", if_exists="append", index=False,
                 chunksize=5000, dtype=_tipos(crudo))


def upsert_clean(df, tabla, clave):
    """MERGE de df contra stg.<tabla>. Devuelve (insertadas, actualizadas).
    Solo cuenta como actualizada una fila si algún valor realmente cambió."""
    if df.empty:
        return 0, 0
    eng = dw_engine()
    tmp = f"tmp_{tabla}"
    df.to_sql(tmp, eng, schema="stg", if_exists="replace", index=False,
              chunksize=5000, dtype=_tipos(df))

    cols = list(df.columns)
    otras = [c for c in cols if c != clave]
    s_otras = ", ".join(f"s.[{c}]" for c in otras)
    t_otras = ", ".join(f"t.[{c}]" for c in otras)
    asignar = ", ".join(f"t.[{c}] = s.[{c}]" for c in otras)
    lista = ", ".join(f"[{c}]" for c in cols)
    valores = ", ".join(f"s.[{c}]" for c in cols)

    sql = f"""
        MERGE stg.{tabla} AS t
        USING stg.{tmp} AS s ON t.[{clave}] = s.[{clave}]
        WHEN MATCHED AND EXISTS (SELECT {s_otras} EXCEPT SELECT {t_otras}) THEN
            UPDATE SET {asignar}
        WHEN NOT MATCHED THEN
            INSERT ({lista}) VALUES ({valores})
        OUTPUT $action;"""

    with eng.begin() as cn:
        acciones = [fila[0] for fila in cn.execute(text(sql)).fetchall()]
        cn.execute(text(f"DROP TABLE stg.{tmp}"))
    return acciones.count("INSERT"), acciones.count("UPDATE")
