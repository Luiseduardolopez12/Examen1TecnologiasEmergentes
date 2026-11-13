"""Configuración: lee el .env y entrega las conexiones a SQL Server."""
import os
from functools import lru_cache
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

SOURCE_DB = os.getenv("SOURCE_DB", "WideWorldImporters")
DW_DB = os.getenv("DW_DB", "DW_Ventas")
OVERLAP_HOURS = int(os.getenv("OVERLAP_HOURS", "24"))


def _cadena_odbc(base):
    servidor = os.getenv("SQL_SERVER", "localhost")
    driver = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    usuario = os.getenv("SQL_USER", "")
    clave = os.getenv("SQL_PASSWORD", "")

    # sin usuario -> autenticación de Windows
    if usuario:
        acceso = f"UID={usuario};PWD={clave};"
    else:
        acceso = "Trusted_Connection=yes;"

    return (f"DRIVER={{{driver}}};SERVER={servidor};DATABASE={base};"
            f"{acceso}TrustServerCertificate=yes;")


@lru_cache(maxsize=None)
def get_engine(base):
    url = "mssql+pyodbc:///?odbc_connect=" + quote_plus(_cadena_odbc(base))
    return create_engine(url, fast_executemany=True)


def source_engine():
    return get_engine(SOURCE_DB)


def dw_engine():
    return get_engine(DW_DB)
