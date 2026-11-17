"""Pruebas del cálculo de sobrante, cuadratura en litros y análisis de inconsistencias."""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from control_aceites.calculo import (CUADRADO, FALTANTE, SOBRANTE, TRASPASO, analizar_entrega,  # noqa: E402
                                     calcular_sobrante, conclusion, resultado)
from control_aceites.catalogo import fusionar, leer_catalogo_pm  # noqa: E402
from control_aceites.db import Repositorio  # noqa: E402
from control_aceites.util import fmt_num, parse_entero, parse_fecha, parse_num  # noqa: E402

LT = 208.0


def test_parseo_y_formato():
    assert parse_num("1.234,5") == 1234.5 and parse_num("120,5") == 120.5 and parse_num("120.5") == 120.5
    assert parse_num("1.234") == 1234 and parse_num("0.208") == 0.208 and parse_num("") == 0
    assert parse_num("abc") is None and parse_entero("2,5") is None and parse_entero("3") == 3
    assert fmt_num(1234.5) == "1.234,5" and fmt_num(15073) == "15.073" and fmt_num(-0.0001) == "0"
    assert parse_fecha("16-11-2026").isoformat() == "2026-11-16" and parse_fecha("31-02-2026") is None


def test_sobrante_sin_rellenos():
    c = calcular_sobrante(5, 300, 120, 0, LT)
    assert c["total_ini"] == 5 * 208 + 300
    assert c["tarros"] == 5 and c["camion"] == 180 and c["total"] == 5 * 208 + 180
    assert c["cuadra"] and not c["avisos"]


def test_rellenos_cuadran_en_litros():
    c = calcular_sobrante(5, 100, 350, 2, LT)
    # 2 tarros al camión: tarros 3, camión 100 + 416 − 350 = 166
    assert c["tarros"] == 3 and c["camion"] == 166
    assert c["litros_rellenos"] == 416
    assert c["total"] == c["total_ini"] - 350 and c["cuadra"]


def test_consumo_mayor_que_camion_descuenta_tarros():
    c = calcular_sobrante(4, 50, 300, 0, LT)
    # faltan 250 L en el camión: se descuentan 2 tarros (416 L): camión 166, tarros 2
    assert c["rellenos_implicitos"] == 2 and c["tarros"] == 2 and c["camion"] == 166
    assert c["total"] == 4 * 208 + 50 - 300 and c["avisos"][0][0] == "aviso"


def test_consumo_mayor_que_stock_total():
    c = calcular_sobrante(1, 10, 500, 0, LT)
    assert c["tarros"] == 0 and c["camion"] == pytest.approx(10 + 208 - 500)
    assert any(n == "error" for n, _ in c["avisos"])


def test_entrega_cuadrada():
    c = calcular_sobrante(5, 300, 120, 0, LT)
    a = analizar_entrega(c, 5, 180, LT)
    assert a["estado"] == CUADRADO and not a["inconsistente"] and a["dif_total"] == 0


def test_tarros_pasados_al_camion_no_son_perdida():
    c = calcular_sobrante(5, 300, 120, 0, LT)       # calculado: 5 tarros + 180 L
    a = analizar_entrega(c, 3, 180 + 416, LT)       # 2 tarros aparecen como litros en el camión
    assert a["estado"] == TRASPASO and a["traspaso"] == 2 and a["dif_total"] == 0 and a["inconsistente"]


def test_traspaso_con_faltante():
    c = calcular_sobrante(5, 300, 120, 0, LT)
    a = analizar_entrega(c, 4, 180 + 208 - 30, LT)  # 1 tarro al camión, pero faltan 30 L
    assert a["traspaso"] == 1 and a["estado"] == FALTANTE and a["dif_total"] == -30
    assert a["camion_sin_explicar"] == -30 and a["tarros_sin_explicar"] == 0


def test_tarro_desaparecido():
    c = calcular_sobrante(5, 300, 120, 0, LT)
    a = analizar_entrega(c, 4, 180, LT)
    assert a["estado"] == FALTANTE and a["traspaso"] == 0 and a["tarros_sin_explicar"] == -1
    assert a["dif_total"] == -208


def test_sobrante_en_camion():
    c = calcular_sobrante(5, 300, 120, 0, LT)
    a = analizar_entrega(c, 5, 190.5, LT)
    assert a["estado"] == SOBRANTE and a["dif_total"] == 10.5


def test_relleno_registrado_no_realizado():
    c = calcular_sobrante(5, 100, 50, 1, LT)        # calculado: 4 tarros + 258 L
    a = analizar_entrega(c, 5, 50, LT)              # el tarro sigue lleno y el camión no lo recibió
    assert a["inverso"] == 1 and a["estado"] == TRASPASO


def _control():
    return {"id": 1, "litros_tarro": LT,
            "aceites": [{"parte": "LL-0001", "nombre": "Motor"}, {"parte": "LL-0002", "nombre": "Hidráulico"}],
            "inicial": {"turno": "Turno A", "fecha": "2026-11-16", "persona": "J. Pérez", "obs": "",
                        "items": {"LL-0001": {"tarros": 5, "camion": 300}, "LL-0002": {"tarros": 3, "camion": 50}}},
            "consumos": {"desde": "2026-11-16", "hasta": "2026-11-22", "obs": "",
                         "items": {"LL-0001": {"consumo": 120, "rellenos": 0},
                                   "LL-0002": {"consumo": 200, "rellenos": 1}}},
            "entrega": {"turno": "Turno B", "fecha": "2026-11-23", "persona": "M. Soto", "obs": "",
                        "items": {"LL-0001": {"tarros": 3, "camion": 596},
                                  "LL-0002": {"tarros": 2, "camion": 40}}}}


def test_resultado_control_y_reporte(tmp_path):
    ctl = _control()
    res = resultado(ctl)
    t = res["totales"]
    assert t["ini"] == 8 * 208 + 350 and t["consumo"] == 320 and t["calc"] == t["ini"] - 320
    f1, f2 = res["filas"]
    assert f1["entrega"]["estado"] == TRASPASO and f1["entrega"]["traspaso"] == 2
    assert f2["calc"]["camion"] == 58 and f2["entrega"]["estado"] == FALTANTE and f2["entrega"]["dif_total"] == -18
    assert res["inconsistencias"] == 2 and res["cuadratura_ok"]
    assert "Faltante total: 18 L" in conclusion(res)

    from control_aceites.reporte_pdf import exportar_reporte
    ruta = tmp_path / "r.pdf"
    exportar_reporte(ctl, str(ruta))
    assert ruta.read_bytes()[:4] == b"%PDF" and ruta.stat().st_size > 3000
    # control abierto (sin entrega) también genera reporte
    ctl.pop("entrega")
    exportar_reporte(ctl, str(tmp_path / "r2.pdf"))


def test_repositorio(tmp_path):
    r = Repositorio(tmp_path / "c.db")
    ctl = _control()
    ctl.pop("id")
    cid = r.guardar_control(ctl)
    assert r.control(cid)["inicial"]["turno"] == "Turno A"
    ctl["consumos"]["obs"] = "x"
    r.guardar_control(ctl)
    assert len(r.controles()) == 1 and r.control(cid)["consumos"]["obs"] == "x"
    r.respaldar(tmp_path / "resp.db")
    assert Repositorio(tmp_path / "resp.db").control(cid)
    r.borrar_control(cid)
    assert r.controles() == []


def test_catalogo_planificacion_pm_solo_lectura(tmp_path):
    ruta = tmp_path / "PlanificacionPM_datos.db"
    cx = sqlite3.connect(ruta)
    cx.execute("CREATE TABLE config (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)")
    cx.execute("INSERT INTO config VALUES('consumo', ?)", (json.dumps([
        {"modelo": "DI650i", "parte": "LL-0001", "lubricante": "Aceite motor 15W40"},
        {"modelo": "DR412i", "parte": "LL-0001", "lubricante": "Aceite motor 15W40"},
        {"modelo": "DI650i", "parte": "LL-0002", "lubricante": "Aceite hidráulico"}]),))
    cx.execute("INSERT INTO config VALUES('diario', ?)", (json.dumps([
        {"equipo": "D10", "parte": "LL-0006", "lubricante": "Aceite perforación", "litros_dia": 4}]),))
    cx.commit()
    cx.close()
    antes = hashlib.sha256(ruta.read_bytes()).hexdigest()
    cat = leer_catalogo_pm(ruta)
    assert [c["parte"] for c in cat] == ["LL-0001", "LL-0002", "LL-0006"]
    assert cat[2]["nombre"] == "Aceite perforación"
    assert hashlib.sha256(ruta.read_bytes()).hexdigest() == antes   # no se modificó
    f = fusionar([{"parte": "LL-0002", "nombre": "x", "activo": False}, {"parte": "X-1", "nombre": "y"}], cat)
    assert [a["parte"] for a in f] == ["LL-0001", "LL-0002", "LL-0006", "X-1"] and f[1]["activo"] is False


# ------------------------------------------------------------- recepciones
def test_recepcion_suma_tarros_al_sobrante():
    c = calcular_sobrante(2, 100, 50, 0, LT, recibidos=3)
    assert c["tarros"] == 5 and c["camion"] == 50 and c["litros_recibidos"] == 624
    assert c["total"] == 2 * 208 + 100 + 624 - 50 and c["cuadra"] and not c["avisos"]


def test_tarros_recibidos_pueden_rellenarse_al_camion():
    c = calcular_sobrante(0, 20, 300, 2, LT, recibidos=2)   # sin tarros iniciales: se rellena con lo recibido
    assert c["tarros"] == 0 and c["camion"] == 20 + 416 - 300 and not c["avisos"] and c["cuadra"]
    c = calcular_sobrante(1, 0, 0, 3, LT, recibidos=1)
    assert c["rellenos"] == 2 and c["avisos"][0][0] == "error"


def test_recepcion_no_registrada_se_sugiere():
    c = calcular_sobrante(2, 100, 50, 0, LT)
    a = analizar_entrega(c, 3, 50, LT)                    # aparece un tarro lleno más
    assert a["estado"] == SOBRANTE and a["dif_total"] == 208
    assert any("recepción" in m for _, m in a["hallazgos"])


def test_control_con_recepciones(tmp_path):
    ctl = _control()
    ctl["recepciones"] = [{"fecha": "2026-11-18", "turno": "Turno A", "obs": "Guía ok", "items": {"LL-0002": 2}},
                          {"fecha": "2026-11-20", "turno": "Turno B", "obs": "", "items": {"LL-0001": 1, "LL-0002": 1}}]
    ctl["entrega"]["items"]["LL-0001"] = {"tarros": 4, "camion": 596}   # 4 = 5 + 1 recibido − 2 al camión
    ctl["entrega"]["items"]["LL-0002"] = {"tarros": 5, "camion": 58}    # 3 − 1 relleno + 3 recibidos
    res = resultado(ctl)
    t = res["totales"]
    assert t["rec_tarros"] == 4 and t["recibido"] == 832
    assert t["calc"] == t["ini"] + 832 - t["consumo"] and res["cuadratura_ok"]
    ctl2 = _control()
    ctl2["recepciones"] = [{"fecha": "2026-11-18", "turno": "Turno A", "obs": "", "items": {"LL-0002": 2}}]
    f2b = resultado(ctl2)["filas"][1]["entrega"]                       # los 2 tarros recibidos no están
    assert f2b["tarros_sin_explicar"] == -2 and any("recepción registrada" in m for _, m in f2b["hallazgos"])
    f1, f2 = res["filas"]
    assert f1["calc"]["tarros"] == 6 and f1["entrega"]["estado"] == TRASPASO and f1["entrega"]["traspaso"] == 2
    assert f2["calc"]["tarros"] == 5 and f2["entrega"]["estado"] == CUADRADO

    from control_aceites.reporte_pdf import exportar_reporte
    ruta = tmp_path / "rec.pdf"
    exportar_reporte(ctl, str(ruta))
    assert ruta.stat().st_size > 3000


def test_control_antiguo_sin_recepciones():
    ctl = _control()
    ctl.pop("recepciones", None)
    assert resultado(ctl)["totales"]["recibido"] == 0
    ctl["recepciones"] = None
    assert resultado(ctl)["totales"]["rec_tarros"] == 0



# ------------------------------------------------------------ nombres reales
def test_catalogo_por_defecto_con_nombres_reales():
    from control_aceites.catalogo import CATALOGO_DEFECTO, es_nombre_generico
    nombres = {a["parte"]: a["nombre"] for a in CATALOGO_DEFECTO}
    assert list(nombres) == [f"LL-000{i}" for i in range(1, 8)]
    assert nombres["LL-0001"] == "Mobil Delvac MX 15W40" and nombres["LL-0006"] == "Mobil Almo 529"
    assert nombres["LL-0007"] == "Mobil Mining Coolant 50%"
    assert es_nombre_generico("Lubricante LL-0006 (consumo diario)") and not es_nombre_generico("Mobil Almo 529")


def test_leer_nombres_desde_excel(tmp_path):
    import openpyxl
    from control_aceites.catalogo import leer_catalogo
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Configuración"
    ws.append(["Modelo", "Sistema", "Lubricante", "N° parte", "Litros"])
    ws.append(["DI650i", "Motor", "Mobil Delvac MX 15W40", "LL-0001", 40])
    ws.append(["DR412i", "Motor", "Mobil Delvac MX 15W40", "LL-0001", 50])
    ws.append(["DI650i", "Hidráulico", "Mobil DTE 10 Excel 46", "LL-0004", 300])
    ws.append([])
    ws.append(["Equipo", "D10", "Mobil Almo 529", "LL-0006", 4])
    wb.save(tmp_path / "Planificacion_PM.xlsx")
    antes = (tmp_path / "Planificacion_PM.xlsx").read_bytes()
    cat = leer_catalogo(tmp_path / "Planificacion_PM.xlsx")
    assert [(a["parte"], a["nombre"]) for a in cat] == [("LL-0001", "Mobil Delvac MX 15W40"),
                                                         ("LL-0004", "Mobil DTE 10 Excel 46"),
                                                         ("LL-0006", "Mobil Almo 529")]
    assert (tmp_path / "Planificacion_PM.xlsx").read_bytes() == antes      # solo lectura
