"""Consultas del dashboard sobre el modelo estrella.

Todas comparten el mismo FROM y los mismos filtros. Los valores del usuario van siempre
como parámetros (:desde, :grupo...), nunca pegados al texto del SQL.
"""
from api.db import consultar

FROM = """
FROM dw.FactSales f
JOIN dw.DimDate        d ON d.DateKey        = f.DateKey
JOIN dw.DimCustomer    c ON c.CustomerKey    = f.CustomerKey
JOIN dw.DimProduct     p ON p.ProductKey     = f.ProductKey
JOIN dw.DimSalesperson v ON v.SalespersonKey = f.SalespersonKey
"""


def _filtros(desde=None, hasta=None, grupo=None, territorio=None):
    condiciones, params = [], {}
    if desde:
        condiciones.append("d.FullDate >= :desde")
        params["desde"] = desde
    if hasta:
        condiciones.append("d.FullDate <= :hasta")
        params["hasta"] = hasta
    if grupo:
        condiciones.append("p.GroupName = :grupo")
        params["grupo"] = grupo
    if territorio:
        condiciones.append("c.SalesTerritory = :territorio")
        params["territorio"] = territorio
    donde = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return donde, params


def kpis(**filtros):
    donde, params = _filtros(**filtros)
    fila = consultar(f"""
        SELECT ISNULL(SUM(f.NetSales), 0)     AS ventas_netas,
               ISNULL(SUM(f.LineProfit), 0)   AS ganancia,
               ISNULL(SUM(f.Quantity), 0)     AS unidades,
               COUNT(DISTINCT f.InvoiceID)    AS facturas,
               COUNT(DISTINCT c.CustomerID)   AS clientes
        {FROM} {donde}""", params)[0]
    ventas, ganancia, facturas = float(fila["ventas_netas"]), float(fila["ganancia"]), fila["facturas"]
    return {
        "ventas_netas": round(ventas, 2),
        "ganancia": round(ganancia, 2),
        "unidades": int(fila["unidades"]),
        "facturas": facturas,
        "clientes": fila["clientes"],
        # ratios: se calculan sobre los totales, nunca promediando promedios
        "margen_pct": round(ganancia / ventas * 100, 2) if ventas else 0,
        "ticket_promedio": round(ventas / facturas, 2) if facturas else 0,
    }


def ventas_mensuales(**filtros):
    donde, params = _filtros(**filtros)
    return consultar(f"""
        SELECT d.YearMonth AS mes,
               CAST(SUM(f.NetSales) AS FLOAT)   AS ventas_netas,
               CAST(SUM(f.LineProfit) AS FLOAT) AS ganancia
        {FROM} {donde}
        GROUP BY d.YearMonth ORDER BY d.YearMonth""", params)


def top_productos(limite=10, **filtros):
    donde, params = _filtros(**filtros)
    return consultar(f"""
        SELECT TOP (:limite) p.StockItemName AS producto, p.GroupName AS grupo,
               CAST(SUM(f.NetSales) AS FLOAT) AS ventas_netas,
               SUM(f.Quantity) AS unidades
        {FROM} {donde}
        GROUP BY p.StockItemName, p.GroupName
        ORDER BY SUM(f.NetSales) DESC""", {**params, "limite": limite})


def top_clientes(limite=10, **filtros):
    donde, params = _filtros(**filtros)
    return consultar(f"""
        SELECT TOP (:limite) c.CustomerName AS cliente,
               CAST(SUM(f.NetSales) AS FLOAT) AS ventas_netas,
               COUNT(DISTINCT f.InvoiceID) AS facturas
        {FROM} {donde}
        GROUP BY c.CustomerID, c.CustomerName
        ORDER BY SUM(f.NetSales) DESC""", {**params, "limite": limite})


def ventas_por_territorio(**filtros):
    donde, params = _filtros(**filtros)
    return consultar(f"""
        SELECT c.SalesTerritory AS territorio, CAST(SUM(f.NetSales) AS FLOAT) AS ventas_netas
        {FROM} {donde}
        GROUP BY c.SalesTerritory ORDER BY SUM(f.NetSales) DESC""", params)


def ventas_por_grupo(**filtros):
    donde, params = _filtros(**filtros)
    return consultar(f"""
        SELECT p.GroupName AS grupo, CAST(SUM(f.NetSales) AS FLOAT) AS ventas_netas
        {FROM} {donde}
        GROUP BY p.GroupName ORDER BY SUM(f.NetSales) DESC""", params)


def vendedores(**filtros):
    donde, params = _filtros(**filtros)
    return consultar(f"""
        SELECT v.FullName AS vendedor, CAST(SUM(f.NetSales) AS FLOAT) AS ventas_netas,
               CAST(SUM(f.LineProfit) AS FLOAT) AS ganancia
        {FROM} {donde}
        GROUP BY v.PersonID, v.FullName ORDER BY SUM(f.NetSales) DESC""", params)


def detalle(pagina=1, tamano=20, **filtros):
    """Tabla paginada de líneas de venta (lo más reciente primero)."""
    donde, params = _filtros(**filtros)
    return consultar(f"""
        SELECT d.FullDate AS fecha, f.InvoiceID AS factura, c.CustomerName AS cliente,
               p.StockItemName AS producto, v.FullName AS vendedor,
               f.Quantity AS cantidad, CAST(f.NetSales AS FLOAT) AS venta_neta,
               CAST(f.LineProfit AS FLOAT) AS ganancia
        {FROM} {donde}
        ORDER BY d.FullDate DESC, f.InvoiceLineID DESC
        OFFSET :salto ROWS FETCH NEXT :tamano ROWS ONLY""",
                     {**params, "salto": (pagina - 1) * tamano, "tamano": tamano})


def total_detalle(**filtros):
    donde, params = _filtros(**filtros)
    return consultar(f"SELECT COUNT(*) AS total {FROM} {donde}", params)[0]["total"]


def opciones_filtros():
    return {
        "grupos": [r["g"] for r in consultar(
            "SELECT DISTINCT GroupName AS g FROM dw.DimProduct WHERE ProductKey <> -1 ORDER BY 1")],
        "territorios": [r["t"] for r in consultar(
            "SELECT DISTINCT SalesTerritory AS t FROM dw.DimCustomer WHERE CustomerKey <> -1 ORDER BY 1")],
        "rango": consultar(
            "SELECT MIN(d.FullDate) AS desde, MAX(d.FullDate) AS hasta "
            "FROM dw.FactSales f JOIN dw.DimDate d ON d.DateKey = f.DateKey")[0],
    }


def ultima_actualizacion():
    """Cuándo se cargó el DW por última vez y hasta qué fecha llegan los datos."""
    corrida = consultar("""
        SELECT TOP 1 end_time AS ultima_carga, rows_inserted, rows_updated
        FROM audit.etl_runs WHERE pipeline_name = 'dw_load' AND status = 'SUCCESS'
        ORDER BY execution_id DESC""")
    datos = consultar("""
        SELECT MAX(d.FullDate) AS datos_hasta
        FROM dw.FactSales f JOIN dw.DimDate d ON d.DateKey = f.DateKey""")[0]
    return {**(corrida[0] if corrida else {"ultima_carga": None}), **datos}


def ejecuciones_etl(limite=30):
    return consultar("""
        SELECT TOP (:limite) execution_id, pipeline_name, status, rows_read, rows_inserted,
               rows_updated, rows_rejected, start_time, end_time, error_detail
        FROM audit.etl_runs ORDER BY execution_id DESC""", {"limite": limite})
