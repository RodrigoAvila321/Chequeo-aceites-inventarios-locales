"""Ventanas de ingreso: turno, stock (inicial / entregado), consumos de la semana y sobrante calculado."""
from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import messagebox, ttk

from . import TITULO, tema
from .calculo import TURNOS, calcular_sobrante, etiqueta
from .tema import (ACENTO, AZUL, BORDE, FUENTE, MORADO, NAVY, ROJO, SUAVE, TARJETA, TEXTO, TITULO_C, VERDE)
from .util import fmt_fecha, fmt_l, fmt_num, parse_entero, parse_fecha, parse_num
from .widgets import Desplazable, FranjaSeguridad, tabla


class Dialogo(tk.Toplevel):
    """Ventana modal con encabezado navy y franja de seguridad."""

    def __init__(self, master, titulo: str, subtitulo: str = "", icono: str = "gota", ancho=900, alto=None):
        super().__init__(master)
        self.withdraw()
        self.title(f"{titulo} - {TITULO}")
        self.configure(background=TARJETA)
        self.transient(master.winfo_toplevel())
        self.resizable(True, True)
        self.resultado = None
        cab = tk.Frame(self, background=NAVY)
        cab.pack(fill="x")
        self._ico = tema.icono(self, icono, 30, ACENTO)
        tk.Label(cab, image=self._ico, background=NAVY).pack(side="left", padx=(18, 10), pady=12)
        txt = tk.Frame(cab, background=NAVY)
        txt.pack(side="left", fill="x", pady=10)
        tk.Label(txt, text=titulo, background=NAVY, foreground="#FFFFFF", font=(FUENTE, 14, "bold"),
                 anchor="w").pack(fill="x")
        if subtitulo:
            tk.Label(txt, text=subtitulo, background=NAVY, foreground="#B9C4D3", font=(FUENTE, 9),
                     anchor="w", justify="left").pack(fill="x")
        FranjaSeguridad(self, alto=6).pack(fill="x")
        self.cuerpo = tk.Frame(self, background=TARJETA)
        self.cuerpo.pack(fill="both", expand=True, padx=18, pady=12)
        self.pie = tk.Frame(self, background=TARJETA)
        self.pie.pack(fill="x", padx=18, pady=(0, 14))
        self.error = tk.Label(self.pie, text="", background=TARJETA, foreground=ROJO, font=(FUENTE, 9, "bold"),
                              anchor="w", justify="left", wraplength=ancho - 320)
        self.error.pack(side="left", fill="x", expand=True)
        self._geom = (ancho, alto)
        self.bind("<Escape>", lambda e: self.cancelar())
        self.protocol("WM_DELETE_WINDOW", self.cancelar)

    def boton(self, texto, estilo, cmd):
        b = ttk.Button(self.pie, text=texto, style=f"{estilo}.TButton", command=cmd)
        b.pack(side="right", padx=(8, 0))
        return b

    def mostrar(self):
        self.update_idletasks()
        w, h = self._geom
        h = h or self.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(w, sw - 40), min(h, sh - 80)
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 20)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.lift()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()
        self.wait_window()
        return self.resultado

    def cancelar(self):
        self.resultado = None
        self.destroy()


# ------------------------------------------------------------------- turno
class PreguntaTurno(Dialogo):
    def __init__(self, master, pregunta: str, actual: str | None = None):
        super().__init__(master, "Turno", pregunta, icono="historial", ancho=520)
        tk.Label(self.cuerpo, text=pregunta, background=TARJETA, foreground=TEXTO, font=(FUENTE, 11),
                 wraplength=460, justify="left").pack(anchor="w", pady=(4, 14))
        fila = tk.Frame(self.cuerpo, background=TARJETA)
        fila.pack(fill="x")
        for i, t in enumerate(TURNOS):
            b = ttk.Button(fila, text=t, style=("Naranja" if t == actual else "Navy") + "Grande.TButton",
                           command=lambda t=t: self._elegir(t))
            b.grid(row=0, column=i, sticky="ew", padx=6)
            fila.columnconfigure(i, weight=1)
        self.boton("Cancelar", "Gris", self.cancelar)

    def _elegir(self, t):
        self.resultado = t
        self.destroy()


# -------------------------------------------------------------- cabecera
def _campo(master, fila, col, etiqueta, var, ancho=18, combo=None):
    ttk.Label(master, text=etiqueta, style="Cab.TLabel").grid(row=fila, column=col, sticky="w", padx=(0, 6), pady=3)
    if combo:
        w = ttk.Combobox(master, textvariable=var, values=combo, state="readonly", width=ancho)
    else:
        w = ttk.Entry(master, textvariable=var, width=ancho)
    w.grid(row=fila, column=col + 1, sticky="ew", padx=(0, 18), pady=3)
    return w


# ------------------------------------------------------------------- stock
class FormularioStock(Dialogo):
    """Stock en tarros llenos y en el camión lubricador, por aceite (modo «inicial» o «entrega»)."""

    def __init__(self, master, modo: str, aceites: list[dict], lt: float, turno: str,
                 previo: dict | None = None):
        self.modo = modo
        self.lt = lt
        self.aceites = aceites
        previo = previo or {}
        items = previo.get("items", {})
        if modo == "inicial":
            tit = "Stock inicial de aceites"
            sub = (f"Stock existente indicado por el jefe de operaciones. Tarros llenos de {fmt_num(lt, 0)} L "
                   f"y litros en el camión lubricador.")
            persona = "Jefe de operaciones"
        else:
            tit = "Stock entregado al finalizar el turno"
            sub = ("Conteo físico que entrega el turno. Se compara contra el sobrante calculado; los tarros que "
                   "pasaron al camión se cuadran en litros.")
            persona = "Responsable entrega"
        super().__init__(master, tit, sub, icono="tarro" if modo == "inicial" else "entrega", ancho=920, alto=640)

        cab = tk.Frame(self.cuerpo, background=TARJETA)
        cab.pack(fill="x", pady=(0, 10))
        self.v_turno = tk.StringVar(value=turno)
        self.v_fecha = tk.StringVar(value=fmt_fecha(previo.get("fecha")) or f"{dt.date.today():%d-%m-%Y}")
        self.v_persona = tk.StringVar(value=previo.get("persona", ""))
        self.v_obs = tk.StringVar(value=previo.get("obs", ""))
        _campo(cab, 0, 0, "Turno", self.v_turno, 12, combo=TURNOS)
        _campo(cab, 0, 2, "Fecha (dd-mm-aaaa)", self.v_fecha, 12)
        _campo(cab, 0, 4, persona, self.v_persona, 22)
        ttk.Label(cab, text="Observaciones", style="Cab.TLabel").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(cab, textvariable=self.v_obs).grid(row=1, column=1, columnspan=5, sticky="ew", pady=3)
        cab.columnconfigure(5, weight=1)

        cols = ("Aceite", "Código", f"Tarros llenos\n(× {fmt_num(lt, 0)} L)", "Litros en\ntarros",
                "Camión lubricador\n(litros)", "Total\n(litros)")
        tabla_f = tk.Frame(self.cuerpo, background=TARJETA, highlightthickness=1, highlightbackground=BORDE)
        tabla_f.pack(fill="both", expand=True)
        enc = tk.Frame(tabla_f, background=tema.NAVY2)
        enc.pack(fill="x")
        anchos = (34, 10, 14, 12, 16, 12)
        for i, (t, a) in enumerate(zip(cols, anchos)):
            tk.Label(enc, text=t, background=tema.NAVY2, foreground=tema.ACENTO, font=(FUENTE, 9, "bold"),
                     width=a, justify="center").grid(row=0, column=i, padx=2, pady=4, sticky="ew")
            enc.columnconfigure(i, weight=3 if i == 0 else 1)
        desp = Desplazable(tabla_f)
        desp.pack(fill="both", expand=True)
        cuerpo = desp.interior
        self.filas = []
        for r, a in enumerate(aceites):
            bg = TARJETA if r % 2 == 0 else tema.ALT
            it = items.get(a["parte"], {})
            vt = tk.StringVar(value=str(it.get("tarros", 0)))
            vc = tk.StringVar(value=fmt_num(it.get("camion", 0), 2) if it else "0")
            tk.Label(cuerpo, text=a["nombre"], background=bg, anchor="w", width=34, font=(FUENTE, 9, "bold"),
                     foreground=TEXTO).grid(row=r, column=0, sticky="ew", padx=2, ipady=6)
            tk.Label(cuerpo, text=a["parte"], background=bg, width=10, foreground=SUAVE).grid(
                row=r, column=1, sticky="ew", padx=2, ipady=6)
            sp = ttk.Spinbox(cuerpo, from_=0, to=9999, increment=1, textvariable=vt, width=8, justify="center")
            sp.grid(row=r, column=2, padx=8, pady=3)
            lt_lbl = tk.Label(cuerpo, text="", background=bg, width=12, foreground=SUAVE)
            lt_lbl.grid(row=r, column=3, sticky="ew", padx=2, ipady=6)
            en = ttk.Entry(cuerpo, textvariable=vc, width=12, justify="right")
            en.grid(row=r, column=4, padx=8, pady=3)
            tot = tk.Label(cuerpo, text="", background=bg, width=12, foreground=TITULO_C, font=(FUENTE, 9, "bold"))
            tot.grid(row=r, column=5, sticky="ew", padx=2, ipady=6)
            for v in (vt, vc):
                v.trace_add("write", lambda *_: self._actualizar())
            self.filas.append(dict(aceite=a, vt=vt, vc=vc, lt_lbl=lt_lbl, tot=tot, sp=sp))
        for i, a in enumerate(anchos):
            cuerpo.columnconfigure(i, weight=3 if i == 0 else 1)
        pie = tk.Frame(tabla_f, background=tema.TOTAL_BG)
        pie.pack(fill="x")
        self.lbl_total = tk.Label(pie, text="", background=tema.TOTAL_BG, foreground=TITULO_C, font=(FUENTE, 10, "bold"),
                                  anchor="e")
        self.lbl_total.pack(fill="x", padx=12, pady=6)

        self.boton("Guardar", "Verde", self.guardar)
        self.boton("Cancelar", "Gris", self.cancelar)
        self.bind("<Return>", lambda e: self.guardar())
        self._actualizar()
        if self.filas:
            self.after(50, lambda: self.filas[0]["sp"].focus_set())

    def _leer(self, f):
        return parse_entero(f["vt"].get()), parse_num(f["vc"].get())

    def _actualizar(self):
        tt = tc = 0.0
        nt = 0
        for f in self.filas:
            t, c = self._leer(f)
            ok = t is not None and c is not None and t >= 0 and c >= 0
            if ok:
                f["lt_lbl"].configure(text=fmt_num(t * self.lt, 0))
                f["tot"].configure(text=fmt_num(t * self.lt + c, 1), foreground=TITULO_C)
                tt += t * self.lt
                tc += c
                nt += t
            else:
                f["lt_lbl"].configure(text="—")
                f["tot"].configure(text="revisar", foreground=ROJO)
        self.lbl_total.configure(text=f"Total: {nt} tarros ({fmt_l(tt, 0)})  +  camión {fmt_l(tc)}  =  "
                                      f"{fmt_l(tt + tc)}")

    def guardar(self):
        fecha = parse_fecha(self.v_fecha.get())
        if not fecha:
            self.error.configure(text="Fecha inválida. Use dd-mm-aaaa.")
            return
        if not self.v_turno.get():
            self.error.configure(text="Seleccione el turno.")
            return
        items = {}
        for f in self.filas:
            t, c = self._leer(f)
            nom = f["aceite"]["nombre"]
            if t is None or t < 0:
                self.error.configure(text=f"«{nom}»: los tarros deben ser un número entero mayor o igual a 0.")
                return
            if c is None or c < 0:
                self.error.configure(text=f"«{nom}»: los litros del camión deben ser un número mayor o igual a 0.")
                return
            items[f["aceite"]["parte"]] = {"tarros": t, "camion": round(c, 3)}
        self.resultado = {"turno": self.v_turno.get(), "fecha": fecha.isoformat(), "persona": self.v_persona.get().strip(),
                          "obs": self.v_obs.get().strip(), "items": items}
        self.destroy()


# ---------------------------------------------------------------- consumos
class FormularioConsumos(Dialogo):
    """Consumo total de la semana por aceite y tarros rellenados al camión, con el sobrante calculado en vivo."""

    def __init__(self, master, aceites: list[dict], inicial: dict, lt: float, previo: dict | None = None,
                 recibidos: dict[str, int] | None = None):
        self.lt = lt
        self.ini = inicial.get("items", {})
        self.rec = recibidos or {}
        previo = previo or {}
        items = previo.get("items", {})
        super().__init__(master, "Consumos de la semana",
                         "Litros consumidos por aceite (salen del camión) y tarros rellenados al camión. "
                         f"Cada relleno resta {fmt_num(lt, 0)} L a los tarros y suma {fmt_num(lt, 0)} L al camión: "
                         "el total queda cuadrado.",
                         icono="consumo", ancho=1180, alto=660)
        d0 = parse_fecha(inicial.get("fecha")) or dt.date.today()
        cab = tk.Frame(self.cuerpo, background=TARJETA)
        cab.pack(fill="x", pady=(0, 10))
        self.v_desde = tk.StringVar(value=fmt_fecha(previo.get("desde")) or f"{d0:%d-%m-%Y}")
        self.v_hasta = tk.StringVar(value=fmt_fecha(previo.get("hasta")) or f"{d0 + dt.timedelta(days=6):%d-%m-%Y}")
        self.v_obs = tk.StringVar(value=previo.get("obs", ""))
        _campo(cab, 0, 0, "Semana desde", self.v_desde, 12)
        _campo(cab, 0, 2, "hasta", self.v_hasta, 12)
        ttk.Label(cab, text="Observaciones", style="Cab.TLabel").grid(row=0, column=4, sticky="w", padx=(0, 6))
        ttk.Entry(cab, textvariable=self.v_obs).grid(row=0, column=5, sticky="ew")
        cab.columnconfigure(5, weight=1)

        cols = ("Aceite", "Stock inicial\n+ recibido", "Consumo\nsemana (L)", "Tarros\nrellenados\nal camión",
                "Tarros\ncalculados", "Camión\ncalculado (L)", "Sobrante\ntotal (L)", "Estado")
        anchos = (28, 20, 12, 11, 10, 13, 12, 34)
        tabla_f = tk.Frame(self.cuerpo, background=TARJETA, highlightthickness=1, highlightbackground=BORDE)
        tabla_f.pack(fill="both", expand=True)
        enc = tk.Frame(tabla_f, background=tema.NAVY2)
        enc.pack(fill="x")
        for i, (t, a) in enumerate(zip(cols, anchos)):
            tk.Label(enc, text=t, background=tema.NAVY2, foreground=tema.ACENTO, font=(FUENTE, 9, "bold"),
                     width=a, justify="center").grid(row=0, column=i, padx=2, pady=4, sticky="ew")
            enc.columnconfigure(i, weight=1)
        desp = Desplazable(tabla_f)
        desp.pack(fill="both", expand=True)
        cuerpo = desp.interior
        self.filas = []
        for r, a in enumerate(aceites):
            bg = TARJETA if r % 2 == 0 else tema.ALT
            i0 = self.ini.get(a["parte"], {"tarros": 0, "camion": 0})
            it = items.get(a["parte"], {})
            vcons = tk.StringVar(value=fmt_num(it.get("consumo", 0), 2) if it else "0")
            vrel = tk.StringVar(value=str(it.get("rellenos", 0)))
            tk.Label(cuerpo, text=f"{a['nombre']}\n{a['parte']}", background=bg, anchor="w", justify="left", width=28,
                     font=(FUENTE, 9, "bold"), foreground=TEXTO).grid(row=r, column=0, sticky="ew", padx=2, ipady=3)
            nrec = int(self.rec.get(a["parte"], 0))
            txt_ini = f"{i0['tarros']} tarros + {fmt_num(i0['camion'])} L"
            if nrec:
                txt_ini += f"\n+ {nrec} recibido{'s' if nrec != 1 else ''}"
            txt_ini += f"\n= {fmt_l(i0['tarros'] * lt + i0['camion'] + nrec * lt)}"
            tk.Label(cuerpo, text=txt_ini, background=bg, width=20, foreground=SUAVE, justify="center").grid(
                row=r, column=1, sticky="ew", padx=2, ipady=3)
            en = ttk.Entry(cuerpo, textvariable=vcons, width=10, justify="right")
            en.grid(row=r, column=2, padx=6, pady=3)
            sp = ttk.Spinbox(cuerpo, from_=0, to=max(0, int(i0["tarros"]) + nrec), increment=1, textvariable=vrel, width=6,
                             justify="center")
            sp.grid(row=r, column=3, padx=6, pady=3)
            lbls = []
            for c, w in ((4, 10), (5, 13), (6, 12)):
                lb = tk.Label(cuerpo, text="", background=bg, width=w, foreground=TITULO_C, font=(FUENTE, 9, "bold"))
                lb.grid(row=r, column=c, sticky="ew", padx=2, ipady=3)
                lbls.append(lb)
            est = tk.Label(cuerpo, text="", background=bg, width=34, anchor="w", justify="left", wraplength=250,
                           font=(FUENTE, 8, "bold"))
            est.grid(row=r, column=7, sticky="ew", padx=4, ipady=3)
            for v in (vcons, vrel):
                v.trace_add("write", lambda *_: self._actualizar())
            self.filas.append(dict(aceite=a, ini=i0, rec=nrec, vcons=vcons, vrel=vrel, lbls=lbls, est=est, en=en))
        for i in range(len(cols)):
            cuerpo.columnconfigure(i, weight=1)
        pie = tk.Frame(tabla_f, background=tema.TOTAL_BG)
        pie.pack(fill="x")
        self.lbl_total = tk.Label(pie, text="", background=tema.TOTAL_BG, foreground=TITULO_C, font=(FUENTE, 10, "bold"),
                                  anchor="w", justify="left")
        self.lbl_total.pack(fill="x", padx=12, pady=6)

        self.boton("Guardar y calcular sobrante", "Verde", self.guardar)
        self.boton("Cancelar", "Gris", self.cancelar)
        self.bind("<Return>", lambda e: self.guardar())
        self._actualizar()
        if self.filas:
            self.after(50, lambda: self.filas[0]["en"].focus_set())

    def _leer(self, f):
        return parse_num(f["vcons"].get()), parse_entero(f["vrel"].get())

    def _actualizar(self):
        t_ini = t_cons = t_sob = t_rel = t_rec = 0.0
        for f in self.filas:
            cons, rel = self._leer(f)
            if cons is None or rel is None or cons < 0 or rel < 0:
                for lb in f["lbls"]:
                    lb.configure(text="—")
                f["est"].configure(text="Revise el valor ingresado", foreground=ROJO)
                continue
            c = calcular_sobrante(f["ini"]["tarros"], f["ini"]["camion"], cons, rel, self.lt, f["rec"])
            f["lbls"][0].configure(text=str(c["tarros"]))
            f["lbls"][1].configure(text=fmt_num(c["camion"]), foreground=ROJO if c["camion"] < 0 else TITULO_C)
            f["lbls"][2].configure(text=fmt_num(c["total"]), foreground=ROJO if c["total"] < 0 else TITULO_C)
            if c["avisos"]:
                nivel = "error" if any(n == "error" for n, _ in c["avisos"]) else "aviso"
                f["est"].configure(text=" ".join(t for _, t in c["avisos"]),
                                   foreground=ROJO if nivel == "error" else ACENTO)
            else:
                txt = "✔ Cuadrado"
                if c["rellenos"]:
                    txt += f"\n−{fmt_num(c['litros_rellenos'], 0)} L tarros / +{fmt_num(c['litros_rellenos'], 0)} L camión"
                f["est"].configure(text=txt, foreground=VERDE)
            t_ini += c["total_ini"]
            t_rec += c["litros_recibidos"]
            t_cons += cons
            t_sob += c["total"]
            t_rel += c["litros_rellenos"]
        self.lbl_total.configure(
            text=f"Stock inicial {fmt_l(t_ini)}  +  recibido {fmt_l(t_rec, 0)}  −  consumo {fmt_l(t_cons)}  =  "
                 f"sobrante {fmt_l(t_sob)}"
                 f"   |   Rellenos al camión: −{fmt_l(t_rel, 0)} en tarros y +{fmt_l(t_rel, 0)} en camión (balance 0 L)")

    def guardar(self):
        d1, d2 = parse_fecha(self.v_desde.get()), parse_fecha(self.v_hasta.get())
        if not d1 or not d2:
            self.error.configure(text="Fechas inválidas. Use dd-mm-aaaa.")
            return
        if d2 < d1:
            self.error.configure(text="La fecha «hasta» es anterior a «desde».")
            return
        items = {}
        for f in self.filas:
            cons, rel = self._leer(f)
            nom = f["aceite"]["nombre"]
            if cons is None or cons < 0:
                self.error.configure(text=f"«{nom}»: el consumo debe ser un número mayor o igual a 0.")
                return
            if rel is None or rel < 0:
                self.error.configure(text=f"«{nom}»: los tarros rellenados deben ser un entero mayor o igual a 0.")
                return
            disp = int(f["ini"]["tarros"]) + f["rec"]
            if rel > disp:
                det = f" ({f['ini']['tarros']} iniciales + {f['rec']} recibidos)" if f["rec"] else ""
                self.error.configure(text=f"«{nom}»: se rellenaron {rel} tarros, pero había {disp}{det}.")
                return
            items[f["aceite"]["parte"]] = {"consumo": round(cons, 3), "rellenos": rel}
        self.resultado = {"desde": d1.isoformat(), "hasta": d2.isoformat(), "obs": self.v_obs.get().strip(),
                          "items": items}
        self.destroy()


# ---------------------------------------------------------------- sobrante
class VentanaSobrante(Dialogo):
    """Informa el sobrante calculado de aceite (punto 5)."""

    def __init__(self, master, res: dict):
        t = res["totales"]
        lt = res["litros_tarro"]
        super().__init__(master, "Sobrante de aceite calculado",
                         "Stock inicial + aceite recibido − consumos de la semana, con los rellenos al camión "
                         "cuadrados en litros.",
                         icono="gota", ancho=1060, alto=560)
        kp = tk.Frame(self.cuerpo, background=TARJETA)
        kp.pack(fill="x", pady=(0, 10))
        for i, (tit, val, det, col) in enumerate((
                ("Stock inicial", fmt_l(t["ini"]), f"{t['ini_tarros']} tarros + {fmt_l(t['ini_camion'])} en camión", tema.SERIE_INI),
                ("Recibido", fmt_l(t["recibido"], 0), f"{t['rec_tarros']} tarros en {len(res['recepciones'])} "
                                                         f"recepción(es)", MORADO),
                ("Consumo semana", fmt_l(t["consumo"]), f"{t['rellenos']} tarros rellenados al camión", AZUL),
                ("Sobrante calculado", fmt_l(t["calc"]), f"{t['calc_tarros']} tarros + {fmt_l(t['calc_camion'])} en camión",
                 VERDE if t["calc"] >= 0 else ROJO),
                ("Equivalente", f"{fmt_num(t['calc'] / lt, 2)} tarros", f"a {fmt_num(lt, 0)} L por tarro", tema.AMBAR))):
            c = tk.Frame(kp, background=TARJETA, highlightthickness=1, highlightbackground=BORDE)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            kp.columnconfigure(i, weight=1)
            tk.Frame(c, background=col, height=4).pack(fill="x")
            tk.Label(c, text=tit, background=TARJETA, foreground=SUAVE, font=(FUENTE, 9, "bold")).pack(anchor="w", padx=10, pady=(6, 0))
            tk.Label(c, text=val, background=TARJETA, foreground=col, font=(FUENTE, 16, "bold")).pack(anchor="w", padx=10)
            tk.Label(c, text=det, background=TARJETA, foreground=SUAVE, font=(FUENTE, 8)).pack(anchor="w", padx=10, pady=(0, 8))

        tv = tabla(self.cuerpo, [("ac", "Aceite", 260, "w"), ("ini", "Inicial (L)", 84, "e"),
                                 ("rec", "Recibido (L)", 88, "e"), ("con", "Consumo (L)", 86, "e"), ("rel", "Rellenos", 70, "center"),
                                 ("tar", "Tarros", 60, "center"), ("cam", "Camión (L)", 90, "e"),
                                 ("sob", "Sobrante (L)", 100, "e"), ("eq", "≈ Tarros", 70, "e"),
                                 ("cua", "Cuadratura", 90, "center")], alto=min(10, len(res["filas"]) + 1))
        tv.marco.pack(fill="both", expand=True)
        for i, f in enumerate(res["filas"]):
            c = f["calc"]
            tv.insert("", "end", tags=("par",) if i % 2 else (), values=(
                etiqueta(f["nombre"], f["parte"]), fmt_num(c["total_ini"]), fmt_num(c["litros_recibidos"]),
                fmt_num(c["consumo"]),
                c["rellenos"] + c["rellenos_implicitos"], c["tarros"], fmt_num(c["camion"]), fmt_num(c["total"]),
                fmt_num(c["equiv_tarros"], 2), "✔ OK" if c["cuadra"] and not c["avisos"] else "⚠ Revisar"))
        tv.insert("", "end", tags=("total",), values=(
            "TOTAL", fmt_num(t["ini"]), fmt_num(t["recibido"]), fmt_num(t["consumo"]), t["rellenos"], t["calc_tarros"],
            fmt_num(t["calc_camion"]), fmt_num(t["calc"]), fmt_num(t["calc"] / lt, 2), ""))
        if res["avisos"]:
            txt = "\n".join(f"• {p}: {m}" for p, _, m in res["avisos"])
            tk.Label(self.cuerpo, text=txt, background=TARJETA, foreground=ACENTO, font=(FUENTE, 9, "bold"),
                     justify="left", anchor="w", wraplength=940).pack(fill="x", pady=(8, 0))
        self.boton("Aceptar", "Verde", self.cancelar)


# -------------------------------------------------------------- recepciones
class FormularioRecepcion(Dialogo):
    """Aceite recibido durante la semana: tarros llenos por aceite."""

    def __init__(self, master, aceites: list[dict], lt: float, turno: str, fecha=None):
        self.lt = lt
        super().__init__(master, "Recepción de aceites",
                         f"Tarros llenos ({fmt_num(lt, 0)} L c/u) que llegaron durante el turno. Se suman al stock de "
                         f"tarros y entran en el cálculo del sobrante.", icono="recepcion", ancho=880, alto=600)
        cab = tk.Frame(self.cuerpo, background=TARJETA)
        cab.pack(fill="x", pady=(0, 10))
        self.v_turno = tk.StringVar(value=turno)
        self.v_fecha = tk.StringVar(value=fmt_fecha(fecha) or f"{dt.date.today():%d-%m-%Y}")
        self.v_obs = tk.StringVar()
        _campo(cab, 0, 0, "Turno", self.v_turno, 12, combo=TURNOS)
        _campo(cab, 0, 2, "Fecha (dd-mm-aaaa)", self.v_fecha, 12)
        ttk.Label(cab, text="Observaciones", style="Cab.TLabel").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(cab, textvariable=self.v_obs).grid(row=1, column=1, columnspan=3, sticky="ew", pady=3)
        cab.columnconfigure(3, weight=1)

        tabla_f = tk.Frame(self.cuerpo, background=TARJETA, highlightthickness=1, highlightbackground=BORDE)
        tabla_f.pack(fill="both", expand=True)
        enc = tk.Frame(tabla_f, background=tema.NAVY2)
        enc.pack(fill="x")
        anchos = (34, 10, 16, 14)
        for i, (t, a) in enumerate(zip(("Aceite", "Código", f"Tarros recibidos\n(× {fmt_num(lt, 0)} L)", "Litros"),
                                        anchos)):
            tk.Label(enc, text=t, background=tema.NAVY2, foreground=tema.ACENTO, font=(FUENTE, 9, "bold"),
                     width=a, justify="center").grid(row=0, column=i, padx=2, pady=4, sticky="ew")
            enc.columnconfigure(i, weight=3 if i == 0 else 1)
        desp = Desplazable(tabla_f)
        desp.pack(fill="both", expand=True)
        cuerpo = desp.interior
        self.filas = []
        for r, a in enumerate(aceites):
            bg = TARJETA if r % 2 == 0 else tema.ALT
            v = tk.StringVar(value="0")
            tk.Label(cuerpo, text=a["nombre"], background=bg, anchor="w", width=34, font=(FUENTE, 9, "bold"),
                     foreground=TEXTO).grid(row=r, column=0, sticky="ew", padx=2, ipady=6)
            tk.Label(cuerpo, text=a["parte"], background=bg, width=10, foreground=SUAVE).grid(
                row=r, column=1, sticky="ew", padx=2, ipady=6)
            sp = ttk.Spinbox(cuerpo, from_=0, to=9999, increment=1, textvariable=v, width=8, justify="center")
            sp.grid(row=r, column=2, padx=8, pady=3)
            lb = tk.Label(cuerpo, text="0", background=bg, width=14, foreground=TITULO_C, font=(FUENTE, 9, "bold"))
            lb.grid(row=r, column=3, sticky="ew", padx=2, ipady=6)
            v.trace_add("write", lambda *_: self._actualizar())
            self.filas.append(dict(aceite=a, v=v, lb=lb, sp=sp))
        for i in range(len(anchos)):
            cuerpo.columnconfigure(i, weight=3 if i == 0 else 1)
        pie = tk.Frame(tabla_f, background=tema.TOTAL_BG)
        pie.pack(fill="x")
        self.lbl_total = tk.Label(pie, text="", background=tema.TOTAL_BG, foreground=TITULO_C, font=(FUENTE, 10, "bold"),
                                  anchor="e")
        self.lbl_total.pack(fill="x", padx=12, pady=6)
        self.boton("Guardar recepción", "Verde", self.guardar)
        self.boton("Cancelar", "Gris", self.cancelar)
        self.bind("<Return>", lambda e: self.guardar())
        self._actualizar()
        if self.filas:
            self.after(50, lambda: self.filas[0]["sp"].focus_set())

    def _actualizar(self):
        n = 0
        for f in self.filas:
            t = parse_entero(f["v"].get())
            if t is None or t < 0:
                f["lb"].configure(text="revisar", foreground=ROJO)
            else:
                f["lb"].configure(text=fmt_num(t * self.lt, 0), foreground=TITULO_C)
                n += t
        self.lbl_total.configure(text=f"Total recibido: {n} tarros = {fmt_l(n * self.lt, 0)}")

    def guardar(self):
        fecha = parse_fecha(self.v_fecha.get())
        if not fecha:
            self.error.configure(text="Fecha inválida. Use dd-mm-aaaa.")
            return
        items = {}
        for f in self.filas:
            t = parse_entero(f["v"].get())
            if t is None or t < 0:
                self.error.configure(text=f"«{f['aceite']['nombre']}»: los tarros deben ser un entero mayor o igual a 0.")
                return
            if t:
                items[f["aceite"]["parte"]] = t
        if not items:
            self.error.configure(text="Ingrese al menos un tarro recibido.")
            return
        self.resultado = {"fecha": fecha.isoformat(), "turno": self.v_turno.get(), "obs": self.v_obs.get().strip(),
                          "items": items}
        self.destroy()


def detalle_recepcion(rec: dict) -> str:
    """«LL-0001: 2 · LL-0003: 1» (tarros por aceite)."""
    return " · ".join(f"{p}: {n}" for p, n in sorted((rec.get("items") or {}).items()))


class VentanaRecepciones(Dialogo):
    """Lista de recepciones del control: agregar y eliminar."""

    def __init__(self, master, control: dict, al_cambiar):
        self.control = control
        self.al_cambiar = al_cambiar
        self.lt = float(control.get("litros_tarro") or 208)
        super().__init__(master, "Recepciones de aceite de la semana",
                         "Aceite que llegó durante la semana (tarros llenos). Puede registrar varias recepciones.",
                         icono="recepcion", ancho=920, alto=None)
        bar = tk.Frame(self.cuerpo, background=TARJETA)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Button(bar, text="+  Agregar recepción", style="Verde.TButton", command=self.agregar).pack(side="left")
        ttk.Button(bar, text="Eliminar seleccionada", style="Rojo.TButton", command=self.eliminar).pack(side="right")
        self.tv = tabla(self.cuerpo, [("n", "N°", 40, "center"), ("fecha", "Fecha", 90, "center"),
                                      ("turno", "Turno", 80, "center"), ("det", "Tarros por aceite", 300, "w"),
                                      ("tar", "Tarros", 60, "center"), ("lit", "Litros", 80, "e"),
                                      ("obs", "Observaciones", 180, "w")], alto=8)
        self.tv.marco.pack(fill="both", expand=True)
        self.lbl = tk.Label(self.cuerpo, text="", background=TARJETA, foreground=TITULO_C, font=(FUENTE, 10, "bold"),
                            anchor="w")
        self.lbl.pack(fill="x", pady=(8, 0))
        self.boton("Cerrar", "Gris", self.cancelar)
        self._llenar()

    def _llenar(self):
        self.tv.delete(*self.tv.get_children())
        recs = self.control.get("recepciones") or []
        tt = 0
        for i, r in enumerate(recs):
            n = sum(int(v) for v in r["items"].values())
            tt += n
            self.tv.insert("", "end", iid=str(i), tags=("par",) if i % 2 else (), values=(
                i + 1, fmt_fecha(r.get("fecha")), r.get("turno", ""), detalle_recepcion(r), n,
                fmt_num(n * self.lt, 0), r.get("obs", "")))
        self.lbl.configure(text=f"{len(recs)} recepción(es) · {tt} tarros · {fmt_l(tt * self.lt, 0)}" if recs
                           else "Sin recepciones registradas.")

    def agregar(self):
        ini = self.control.get("inicial") or {}
        recs = self.control.get("recepciones") or []
        turno = recs[-1]["turno"] if recs else ini.get("turno", TURNOS[0])
        r = FormularioRecepcion(self, self.control["aceites"], self.lt, turno).mostrar()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        if r:
            self.control.setdefault("recepciones", [])
            if self.control["recepciones"] is None:
                self.control["recepciones"] = []
            self.control["recepciones"].append(r)
            self.control["recepciones"].sort(key=lambda x: x.get("fecha") or "")
            self.al_cambiar()
            self._llenar()

    def eliminar(self):
        s = self.tv.selection()
        if not s:
            self.error.configure(text="Seleccione una recepción.")
            return
        i = int(s[0])
        r = self.control["recepciones"][i]
        if messagebox.askyesno(TITULO, f"¿Eliminar la recepción del {fmt_fecha(r.get('fecha'))} "
                                       f"({detalle_recepcion(r)})?", icon="warning", parent=self):
            self.control["recepciones"].pop(i)
            self.al_cambiar()
            self._llenar()
