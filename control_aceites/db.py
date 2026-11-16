"""Base de datos local (SQLite): configuración, catálogo de aceites y controles semanales."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

from .util import ahora_iso

NOMBRE_DB = "ControlAceites_datos.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS config (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS controles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turno TEXT, fecha TEXT, datos TEXT NOT NULL,
    creado TEXT, actualizado TEXT
);
"""


def carpeta_datos() -> Path:
    """Si junto al ejecutable ya existe la base de datos, se usa esa (modo portátil).
    Si no, Documentos\\ControlAceites."""
    junto = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    if (junto / NOMBRE_DB).exists():
        return junto
    docs = Path.home() / "Documents"
    if not docs.exists():
        docs = Path.home()
    destino = docs / "ControlAceites"
    try:
        destino.mkdir(parents=True, exist_ok=True)
        return destino
    except OSError:
        alt = Path(os.environ.get("APPDATA") or Path.home()) / "ControlAceites"
        alt.mkdir(parents=True, exist_ok=True)
        return alt


class Repositorio:
    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.cx = sqlite3.connect(str(self.ruta))
        self.cx.row_factory = sqlite3.Row
        self.cx.executescript(ESQUEMA)
        self.cx.commit()

    def cerrar(self):
        self.cx.close()

    # ---------------------------------------------------------------- config
    def get(self, clave: str, defecto=None):
        r = self.cx.execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
        return json.loads(r[0]) if r else defecto

    def set(self, clave: str, valor):
        self.cx.execute("INSERT OR REPLACE INTO config(clave, valor) VALUES(?,?)",
                        (clave, json.dumps(valor, ensure_ascii=False)))
        self.cx.commit()

    def catalogo(self) -> list[dict]:
        return self.get("catalogo", [])

    def aceites_activos(self) -> list[dict]:
        return [{"parte": a["parte"], "nombre": a["nombre"]} for a in self.catalogo() if a.get("activo", True)]

    def litros_tarro(self) -> float:
        return float(self.get("litros_tarro", 208.0))

    # --------------------------------------------------------------- controles
    def controles(self) -> list[dict]:
        out = []
        for r in self.cx.execute("SELECT * FROM controles ORDER BY id DESC"):
            d = json.loads(r["datos"])
            d.update(id=r["id"], creado=r["creado"], actualizado=r["actualizado"])
            out.append(d)
        return out

    def control(self, cid: int | None) -> dict | None:
        if cid is None:
            return None
        r = self.cx.execute("SELECT * FROM controles WHERE id=?", (cid,)).fetchone()
        if not r:
            return None
        d = json.loads(r["datos"])
        d.update(id=r["id"], creado=r["creado"], actualizado=r["actualizado"])
        return d

    def guardar_control(self, control: dict) -> int:
        datos = {k: v for k, v in control.items() if k not in ("id", "creado", "actualizado")}
        ini = control.get("inicial") or {}
        txt = json.dumps(datos, ensure_ascii=False)
        ahora = ahora_iso()
        if control.get("id"):
            self.cx.execute("UPDATE controles SET turno=?, fecha=?, datos=?, actualizado=? WHERE id=?",
                            (ini.get("turno"), ini.get("fecha"), txt, ahora, control["id"]))
            cid = control["id"]
        else:
            cur = self.cx.execute("INSERT INTO controles(turno, fecha, datos, creado, actualizado) VALUES(?,?,?,?,?)",
                                  (ini.get("turno"), ini.get("fecha"), txt, ahora, ahora))
            cid = cur.lastrowid
            control["id"] = cid
        self.cx.commit()
        return cid

    def borrar_control(self, cid: int):
        self.cx.execute("DELETE FROM controles WHERE id=?", (cid,))
        self.cx.commit()
        if self.get("control_actual") == cid:
            self.set("control_actual", None)

    def respaldar(self, destino: str | Path):
        dst = sqlite3.connect(str(destino))
        try:
            self.cx.backup(dst)
        finally:
            dst.close()
