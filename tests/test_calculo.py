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
    assert cat[2]["nombre"] == "Aceite perforación (consumo diario)"
    assert hashlib.sha256(ruta.read_bytes()).hexdigest() == antes   # no se modificó
    f = fusionar([{"parte": "LL-0002", "nombre": "x", "activo": False}, {"parte": "X-1", "nombre": "y"}], cat)
    assert [a["parte"] for a in f] == ["LL-0001", "LL-0002", "LL-0006", "X-1"] and f[1]["activo"] is False
