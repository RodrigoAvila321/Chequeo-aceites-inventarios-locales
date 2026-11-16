"""Catálogo de aceites del proyecto «Planificación PM» (repositorio Prueba).

Los lubricantes de ese programa se identifican por N° de parte (LL-0001 a LL-0007) y sus nombres están en
su base de datos PlanificacionPM_datos.db (configuración «consumo» y «diario»). Esa base se abre SIEMPRE en
modo solo lectura: este programa nunca la modifica.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

NOMBRE_DB_PM = "PlanificacionPM_datos.db"

# Respaldo si no se encuentra la base de Planificación PM (nombres editables en Configuración).
CATALOGO_DEFECTO = [
    {"parte": f"LL-000{i}", "nombre": f"Lubricante LL-000{i}" + (" (consumo diario)" if i == 6 else ""),
     "activo": True}
    for i in range(1, 8)
]


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
    diario: set[str] = set()
    for clave in ("consumo", "diario"):
        for f in json.loads(filas.get(clave) or "[]"):
            parte = str(f.get("parte") or "").strip()
            if not parte:
                continue
            if clave == "diario":
                diario.add(parte)
            nom = str(f.get("lubricante") or "").strip()
            if nom and not nombres.get(parte):
                nombres[parte] = nom
            nombres.setdefault(parte, "")
    if not nombres:
        raise ValueError("La base de Planificación PM no tiene lubricantes configurados (Configuración > Consumo).")
    out = []
    for p in sorted(nombres):
        n = nombres[p] or f"Lubricante {p}"
        if p in diario and "diario" not in n.lower():
            n += " (consumo diario)"
        out.append({"parte": p, "nombre": n, "activo": True})
    return out


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
