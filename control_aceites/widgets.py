"""Componentes gráficos: franja de seguridad, pasos del control, indicadores, gráfico de litros y tablas."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import tema
from .tema import (AMARILLO, AZUL, BORDE, FONDO, FUENTE, NAVY, NAVY2, SUAVE, TARJETA, TEXTO, VERDE, ACENTO)
from .util import fmt_num


class FranjaSeguridad(tk.Canvas):
    """Franja diagonal amarilla/negra (señalética de mantención)."""

    def __init__(self, master, alto=8, **kw):
        super().__init__(master, height=alto, highlightthickness=0, bd=0, background=AMARILLO, **kw)
        self.bind("<Configure>", self._dibujar)

    def _dibujar(self, _=None):
        self.delete("all")
        w, h = self.winfo_width(), int(self["height"])
        paso = 18
        for x in range(-h, w + paso, paso):
            self.create_polygon(x, h, x + h, 0, x + h + paso / 2, 0, x + paso / 2, h, fill=NAVY, outline="")


class Pasos(tk.Canvas):
    """Indicador del avance del control: 1 Stock inicial → … → 5 Reporte."""
    ETAPAS = ("Stock inicial", "Consumos semana", "Sobrante calculado", "Stock entregado", "Reporte")

    def __init__(self, master, **kw):
        super().__init__(master, height=74, highlightthickness=0, bd=0, background=TARJETA, **kw)
        self.actual = 0
        self.bind("<Configure>", lambda e: self._dibujar())

    def fijar(self, completadas: int):
        self.actual = completadas
        self._dibujar()

    def _dibujar(self):
        self.delete("all")
        w = max(self.winfo_width(), 400)
        n = len(self.ETAPAS)
        m = 70
        xs = [m + i * (w - 2 * m) / (n - 1) for i in range(n)]
        y, r = 26, 15
        for i in range(n - 1):
            col = VERDE if i + 1 < self.actual else BORDE
            self.create_line(xs[i] + r, y, xs[i + 1] - r, y, fill=col, width=4)
        for i, (x, nom) in enumerate(zip(xs, self.ETAPAS)):
            hecho = i < self.actual
            activo = i == self.actual
            fill = VERDE if hecho else (ACENTO if activo else "#E6EBF1")
            self.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline="")
            self.create_text(x, y, text="✔" if hecho else str(i + 1),
                             fill="#FFFFFF" if (hecho or activo) else SUAVE, font=(FUENTE, 10, "bold"))
            self.create_text(x, y + r + 14, text=nom, fill=NAVY if (hecho or activo) else SUAVE,
                             font=(FUENTE, 9, "bold" if activo else "normal"))


class Indicador(tk.Frame):
    """Tarjeta con ícono, título, valor grande y detalle."""

    def __init__(self, master, titulo: str, icono: str, color: str):
        super().__init__(master, background=TARJETA, highlightthickness=1, highlightbackground=BORDE)
        tk.Frame(self, background=color, width=5).pack(side="left", fill="y")
        cuerpo = tk.Frame(self, background=TARJETA)
        cuerpo.pack(side="left", fill="both", expand=True, padx=(10, 10), pady=8)
        cab = tk.Frame(cuerpo, background=TARJETA)
        cab.pack(fill="x")
        self._img = tema.icono(self, icono, 18, color)
        tk.Label(cab, image=self._img, background=TARJETA).pack(side="left")
        tk.Label(cab, text=titulo, background=TARJETA, foreground=SUAVE, font=(FUENTE, 9, "bold")).pack(
            side="left", padx=6)
        self.valor = tk.Label(cuerpo, text="—", background=TARJETA, foreground=NAVY, font=(FUENTE, 17, "bold"),
                              anchor="w")
        self.valor.pack(fill="x")
        self.detalle = tk.Label(cuerpo, text="", background=TARJETA, foreground=SUAVE, font=(FUENTE, 8), anchor="w")
        self.detalle.pack(fill="x")

    def fijar(self, valor: str, detalle: str = "", color: str | None = None):
        self.valor.configure(text=valor, foreground=color or NAVY)
        self.detalle.configure(text=detalle)


class GraficoLitros(tk.Canvas):
    """Barras por aceite: stock inicial, sobrante calculado y stock entregado (litros)."""
    SERIES = (("Stock inicial", NAVY2), ("Sobrante calculado", tema.AMBAR), ("Stock entregado", VERDE))

    def __init__(self, master, **kw):
        super().__init__(master, height=210, highlightthickness=0, bd=0, background=TARJETA, **kw)
        self.datos: list[tuple[str, list[float | None]]] = []
        self.bind("<Configure>", lambda e: self._dibujar())

    def fijar(self, datos):
        self.datos = datos
        self._dibujar()

    def _dibujar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        izq, der, arr, aba = 58, 12, 26, 34
        # leyenda
        x = izq
        for nom, col in self.SERIES:
            self.create_rectangle(x, 8, x + 12, 18, fill=col, outline="")
            self.create_text(x + 17, 13, text=nom, anchor="w", fill=TEXTO, font=(FUENTE, 8))
            x += 30 + len(nom) * 6
        if not self.datos:
            self.create_text(w / 2, h / 2, text="Ingrese el stock inicial para ver el gráfico",
                             fill=SUAVE, font=(FUENTE, 9))
            return
        vals = [v for _, s in self.datos for v in s if v is not None]
        vmax = max([1.0] + vals)
        vmin = min([0.0] + vals)
        alto = h - arr - aba
        esc = alto / (vmax - vmin)
        y0 = arr + vmax * esc
        # grilla
        for k in range(5):
            v = vmin + (vmax - vmin) * k / 4
            y = y0 - v * esc
            self.create_line(izq, y, w - der, y, fill="#EEF1F5")
            self.create_text(izq - 6, y, text=fmt_num(v, 0), anchor="e", fill=SUAVE, font=(FUENTE, 7))
        self.create_line(izq, y0, w - der, y0, fill=BORDE)
        n = len(self.datos)
        ancho_g = (w - izq - der) / n
        ancho_b = min(22, ancho_g / 4.2)
        for i, (nom, serie) in enumerate(self.datos):
            cx = izq + ancho_g * (i + 0.5)
            for j, v in enumerate(serie):
                if v is None:
                    continue
                x0 = cx + (j - 1.5) * ancho_b + j * 2
                y = y0 - v * esc
                self.create_rectangle(x0, min(y, y0), x0 + ancho_b, max(y, y0), fill=self.SERIES[j][1], outline="")
            self.create_text(cx, h - aba + 12, text=nom, fill=TEXTO, font=(FUENTE, 8, "bold"))
        self.create_text(12, arr - 12, text="L", anchor="w", fill=SUAVE, font=(FUENTE, 8, "bold"))


class Desplazable(ttk.Frame):
    """Marco con barra de desplazamiento vertical (rueda del mouse incluida)."""

    def __init__(self, master, fondo=TARJETA, **kw):
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, background=fondo)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.interior = tk.Frame(self.canvas, background=fondo)
        self._win = self.canvas.create_window(0, 0, window=self.interior, anchor="nw")
        self.canvas.configure(yscrollcommand=self.barra.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.barra.pack(side="right", fill="y")
        self.interior.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._rueda))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _rueda(self, e):
        if self.canvas.yview() != (0.0, 1.0):
            self.canvas.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")


def tabla(master, columnas, alto=10) -> ttk.Treeview:
    """columnas: [(id, título, ancho, alineación)]."""
    marco = ttk.Frame(master)
    tv = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings", height=alto)
    for cid, tit, ancho, al in columnas:
        tv.heading(cid, text=tit, anchor="center")
        tv.column(cid, width=ancho, minwidth=40, anchor=al, stretch=True)
    lineas = max(t.count("\n") + 1 for _, t, _, _ in columnas)
    if lineas > 1:
        # El alto del encabezado lo fija la columna oculta #0: así los títulos de 2 líneas no se recortan.
        tv.heading("#0", text="\n".join(" " * lineas))
    sy = ttk.Scrollbar(marco, orient="vertical", command=tv.yview)
    sx = ttk.Scrollbar(marco, orient="horizontal", command=tv.xview)
    tv.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    tv.grid(row=0, column=0, sticky="nsew")
    sy.grid(row=0, column=1, sticky="ns")
    sx.grid(row=1, column=0, sticky="ew")
    marco.rowconfigure(0, weight=1)
    marco.columnconfigure(0, weight=1)
    tv.marco = marco
    for est, col in tema.FONDO_ESTADO.items():
        tv.tag_configure(est, background=col)
    tv.tag_configure("total", background="#E8EDF3", font=(FUENTE, 9, "bold"))
    tv.tag_configure("par", background="#F7F9FB")
    return tv


def tarjeta(master, titulo: str | None = None, icono: str | None = None) -> tk.Frame:
    """Tarjeta blanca con borde y título opcional. Devuelve el marco interior."""
    ext = tk.Frame(master, background=TARJETA, highlightthickness=1, highlightbackground=BORDE)
    if titulo:
        cab = tk.Frame(ext, background=TARJETA)
        cab.pack(fill="x", padx=14, pady=(10, 2))
        if icono:
            img = tema.icono(ext, icono, 16, NAVY)
            lb = tk.Label(cab, image=img, background=TARJETA)
            lb.image = img
            lb.pack(side="left", padx=(0, 6))
        tk.Label(cab, text=titulo, background=TARJETA, foreground=NAVY, font=(FUENTE, 11, "bold")).pack(side="left")
        ext.cab = cab
    inner = tk.Frame(ext, background=TARJETA)
    inner.pack(fill="both", expand=True, padx=14, pady=(4, 12))
    ext.inner = inner
    return ext


__all__ = ["FranjaSeguridad", "Pasos", "Indicador", "GraficoLitros", "Desplazable", "tabla", "tarjeta",
           "AZUL", "FONDO"]
