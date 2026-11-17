"""Catálogo de aceites del proyecto «Planificación PM» (repositorio Prueba).

Los lubricantes de ese programa se identifican por N° de parte (LL-0001 a LL-0007) y sus nombres están en
su base de datos PlanificacionPM_datos.db (configuración «consumo» y «diario»). Esa base se abre SIEMPRE en
modo solo lectura: este programa nunca la modifica.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

NOMBRE_DB_PM = "PlanificacionPM_datos.db"

# Nombres reales de los lubricantes de Planificación PM (Configuración > columna «Lubricante»).
# El código LL-000X es el código de compra. Editables en Configuración.
NOMBRES_REALES = {
    "LL-0001": "Mobil Delvac MX 15W40",
    "LL-0002": "M. Lube HD Plus 75W90",
    "LL-0003": "Mobil SHC Rarus 46",
    "LL-0004": "Mobil DTE 10 Excel 46",
    "LL-0005": "Mobil SHC Gear 320",
    "LL-0006": "Mobil Almo 529",
    "LL-0007": "Mobil Mining Coolant 50%",
}
CATALOGO_DEFECTO = [{"parte": p, "nombre": n, "activo": True} for p, n in sorted(NOMBRES_REALES.items())]
_GENERICO = re.compile(r"^Lubricante [A-Z]{2}-\d{4}( \(consumo diario\))?$")


def es_nombre_generico(nombre: str) -> bool:
    """Nombres provisorios de las versiones 1.0 y 1.1 («Lubricante LL-0001»)."""
    return bool(_GENERICO.match(nombre or ""))


def candidatos_db_pm() -> list[Path]:
    home = Path.home()
    rutas = []
    if getattr(sys, "frozen", False):
        rutas.append(Path(sys.executable).parent / NOMBRE_DB_PM)
    for docs in (home / "Documents", home / "Documentos", home / "OneDrive" / "Documents",
                 home / "OneDrive" / "Documentos"):
        rutas.append(docs / "PlanificacionPM" / NOMBRE_DB_PM)
    if os.environ.get("APPDATA"):
        rutas.append(Path(os.environ["APPDATA"]) / "PlanificacionPM" / NOMBRE_DB_PM)
    return rutas


def buscar_db_pm() -> Path | None:
    for r in candidatos_db_pm():
        if r.is_file():
            return r
    return None


def leer_catalogo_pm(ruta: str | Path) -> list[dict]:
    """Lee los lubricantes (N° de parte + nombre) de una base de Planificación PM, en modo solo lectura."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ValueError(f"No existe el archivo {ruta}.")
    uri = ruta.resolve().as_uri() + "?mode=ro"
    try:
        cx = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as ex:
        raise ValueError(f"No se pudo abrir la base de datos ({ex}).") from ex
    try:
        try:
            filas = dict(cx.execute("SELECT clave, valor FROM config WHERE clave IN ('consumo','diario')").fetchall())
        except sqlite3.DatabaseError as ex:
            raise ValueError("El archivo no es una base de datos de Planificación PM.") from ex
    finally:
        cx.close()
    nombres: dict[str, str] = {}
    for clave in ("consumo", "diario"):
        for f in json.loads(filas.get(clave) or "[]"):
            parte = str(f.get("parte") or "").strip()
            if not parte:
                continue
            nom = str(f.get("lubricante") or "").strip()
            if nom and not nombres.get(parte):
                nombres[parte] = nom
            nombres.setdefault(parte, "")
    if not nombres:
        raise ValueError("La base de Planificación PM no tiene lubricantes configurados (Configuración > Consumo).")
    return [{"parte": p, "nombre": nombres[p] or NOMBRES_REALES.get(p, p), "activo": True} for p in sorted(nombres)]


_CODIGO = re.compile(r"^[A-Z]{2}-\d{4}$")
_EQUIPO = re.compile(r"^[A-Z]{1,3}-?\d{1,3}$")


def _nombre_valido(v) -> bool:
    if not isinstance(v, str):
        return False
    v = v.strip()
    return len(v) > 4 and any(c.isalpha() for c in v) and not _CODIGO.match(v) and not _EQUIPO.match(v)


def leer_catalogo_xlsm(ruta: str | Path) -> list[dict]:
    """Lee código de compra y nombre de los lubricantes del libro Planificacion_PM (.xlsm / .xlsx), en solo
    lectura. Busca en la hoja «Configuración» cada código LL-0000 y toma el nombre de la celda vecina
    (columna «Lubricante»)."""
    try:
        import openpyxl
    except ImportError as ex:  # pragma: no cover
        raise ValueError("Falta el módulo openpyxl para leer archivos Excel.") from ex
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ValueError(f"No existe el archivo {ruta}.")
    try:
        wb = openpyxl.load_workbook(str(ruta), read_only=True, data_only=True)
    except Exception as ex:  # noqa: BLE001 - archivo dañado o con otro formato
        raise ValueError(f"No se pudo abrir el libro Excel ({ex}).") from ex
    try:
        hojas = [wb[n] for n in wb.sheetnames if n.strip().lower() in ("configuración", "configuracion")] \
            or list(wb.worksheets)
        nombres: dict[str, str] = {}
        for ws in hojas:
            for fila in ws.iter_rows(values_only=True):
                for i, v in enumerate(fila):
                    if not (isinstance(v, str) and _CODIGO.match(v.strip())):
                        continue
                    cod = v.strip()
                    izq = fila[i - 1] if i > 0 else None
                    der = fila[i + 1] if i + 1 < len(fila) else None
                    nom = izq if _nombre_valido(izq) else der if _nombre_valido(der) else None
                    if nom and cod not in nombres:
                        nombres[cod] = str(nom).strip()
    finally:
        wb.close()
    if not nombres:
        raise ValueError("No se encontraron lubricantes (códigos LL-0000 con su nombre) en el libro Excel.")
    return [{"parte": p, "nombre": nombres[p], "activo": True} for p in sorted(nombres)]


def leer_catalogo(ruta: str | Path) -> list[dict]:
    """Lee el catálogo desde una base .db o un libro Excel de Planificación PM."""
    if Path(ruta).suffix.lower() in (".xlsm", ".xlsx"):
        return leer_catalogo_xlsm(ruta)
    return leer_catalogo_pm(ruta)


def fusionar(actual: list[dict], nuevo: list[dict]) -> list[dict]:
    """Actualiza nombres desde Planificación PM manteniendo el estado «activo» y los aceites agregados a mano."""
    previo = {a["parte"]: a for a in actual}
    out = []
    for a in nuevo:
        b = dict(a)
        if a["parte"] in previo:
            b["activo"] = previo[a["parte"]].get("activo", True)
        out.append(b)
    vistos = {a["parte"] for a in nuevo}
    out += [a for a in actual if a["parte"] not in vistos]
    return out
