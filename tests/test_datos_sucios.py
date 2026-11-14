"Comprueba que las reglas atrapan exactamente lo que fabricamos sucio (sin usar la base)"
from tests.datos_sucios import correr_reglas


def test_cada_tabla_rechaza_lo_esperado():
    resultados, esperado = correr_reglas()
    for nombre, (limpio, rechazos) in resultados.items():
        rech_esp, limp_esp = esperado[nombre]
        assert len(rechazos) == rech_esp, nombre
        assert len(limpio) == limp_esp, nombre


def test_se_usan_todas_las_reglas_de_lineas_y_facturas():
    resultados, _ = correr_reglas()
    reglas_lineas = set(resultados["invoice_lines"][1]["rule_name"])
    assert reglas_lineas == {"cantidad_no_positiva", "precio_negativo",
                             "campo_obligatorio_nulo", "factura_inexistente", "duplicado"}
    reglas_facturas = set(resultados["invoices"][1]["rule_name"])
    assert reglas_facturas == {"fecha_nula", "fecha_futura", "llave_nula", "duplicado"}
