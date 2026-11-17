"""Interfaz gráfica principal (Tkinter)."""
from __future__ import annotations

import datetime as dt
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import TITULO, __version__, tema
from .calculo import conclusion, etapa, etiqueta, recibidos_por_aceite, resultado
from .catalogo import (CATALOGO_DEFECTO, NOMBRES_REALES, buscar_db_pm, es_nombre_generico, fusionar,
                       leer_catalogo)
from .db import NOMBRE_DB, Repositorio, carpeta_datos
from .dialogos import FormularioConsumos, FormularioStock, PreguntaTurno, VentanaRecepciones, VentanaSobrante
from .reporte_pdf import exportar_reporte
from .tema import ACENTO, AZUL, FONDO, FUENTE, NAVY, NAVY_HOVER, ROJO, SUAVE, TARJETA, TEXTO, TITULO_C, VERDE
from .util import fmt_fecha, fmt_fechahora, fmt_l, fmt_num, fmt_signo, parse_num
from .widgets import Desplazable, FranjaSeguridad, GraficoLitros, Indicador, Pasos, tabla, tarjeta

AYUDA = """\
FLUJO DEL CONTROL SEMANAL

1. INGRESAR STOCK INICIAL
   • El programa pregunta a qué turno (Turno A / Turno B) corresponde el stock existente.
   • Por cada aceite se ingresan los tarros llenos (208 L cada uno) y los litros en el camión lubricador,
     según lo indicado por el jefe de operaciones.

RECEPCIÓN DE ACEITES (DURANTE LA SEMANA)
   • Botón «Recepción de aceites»: registra los tarros llenos (208 L c/u) que llegan durante el turno,
     con fecha, turno y observaciones. Puede registrar varias recepciones y eliminarlas.
   • Lo recibido se suma al stock de tarros: sobrante = inicial + recibido − consumo.
   • Los tarros recibidos también pueden rellenarse al camión.
   • Si al recibir el stock entregado sobran tarros completos, el programa sugiere una posible recepción
     no registrada.

2. INGRESAR CONSUMOS DE LA SEMANA
   • Litros totales consumidos por aceite durante la semana posterior (salen del camión lubricador).
   • Tarros rellenados al camión: cada tarro vaciado resta 208 L a los tarros y suma 208 L al camión.
     El total en litros no cambia: queda cuadrado.
   • Si el consumo supera lo que hay en el camión, se descuentan tarros completos (relleno no registrado)
     y se avisa.

3. SOBRANTE CALCULADO
   • Al guardar los consumos se informa el sobrante por aceite: tarros, litros en camión, total y
     equivalencia en tarros. También queda visible en la tabla principal.

4. INGRESAR STOCK ENTREGADO
   • Al finalizar el turno se ingresa el conteo físico entregado (tarros y litros en camión).
   • Se compara contra el sobrante calculado y se informa cualquier diferencia.
   • Si faltan tarros y su volumen aparece en el camión, se identifica como TRASPASO AL CAMIÓN
     (tarros vaciados o cargados en el camión): no es pérdida, «Cuadra en litros».
   • Estados: Cuadrado · Cuadra en litros · Faltante · Sobrante.

5. REPORTE PDF
   • Si hay inconsistencias, el programa ofrece generar el reporte PDF de inmediato.
   • Incluye datos del turno, indicadores, detalle por aceite, cuadratura de rellenos, hallazgos,
     conclusión y espacios para firmas.

NUEVO CONTROL
   • «Nuevo control» comienza otro ciclo. Puede usar el stock entregado como stock inicial del siguiente.
   • Los controles anteriores quedan en «Historial», desde donde se pueden abrir o reimprimir.

ACEITES
   • Corresponden a los lubricantes del programa Planificación PM. LL-000X es el código de compra:
       LL-0001  Mobil Delvac MX 15W40          LL-0005  Mobil SHC Gear 320
       LL-0002  M. Lube HD Plus 75W90          LL-0006  Mobil Almo 529
       LL-0003  Mobil SHC Rarus 46             LL-0007  Mobil Mining Coolant 50%
       LL-0004  Mobil DTE 10 Excel 46
   • «Configuración > Leer desde Planificación PM» actualiza los nombres desde el Excel Planificacion_PM
     (.xlsm) o su base de datos (.db), siempre en modo solo lectura: esos archivos nunca se modifican.
   • En «Configuración» puede activar/desactivar aceites, editar nombres y los litros por tarro.

DATOS
   • Se guardan en Documentos\\ControlAceites\\ControlAceites_datos.db (o junto al .exe si ahí existe).
   • Respaldo: Configuración > Respaldar base de datos.
"""


class App(tk.Tk):
    def __init__(self, ruta_db: str | Path | None = None):
        super().__init__()
        self.withdraw()
        self.title(f"{TITULO} - Tarros y camión lubricador")
        tema.aplicar(self)
        try:
            self._icono_ventana = tema.icono(self, "logo", 64, "#FFFFFF")
            self.iconphoto(True, self._icono_ventana)
        except tk.TclError:
            pass
        self.ruta_db = Path(ruta_db) if ruta_db else carpeta_datos() / NOMBRE_DB
        self.repo = Repositorio(self.ruta_db)
        self._inicializar_catalogo()
        self.control: dict | None = self.repo.control(self.repo.get("control_actual"))

        self.geometry("1320x820")
        self.minsize(1080, 680)
        self._construir()
        self.mostrar("control")
        self.deiconify()
        if sys.platform.startswith("win"):
            try:
                self.state("zoomed")
            except tk.TclError:
                pass

    # ------------------------------------------------------------- catálogo
    def _inicializar_catalogo(self):
        self.origen_catalogo = self.repo.get("origen_catalogo", "")
        if self.repo.catalogo():
            self._migrar_nombres()
            return
        ruta = buscar_db_pm()
        cat = None
        if ruta:
            try:
                cat = leer_catalogo(ruta)
                self.origen_catalogo = str(ruta)
            except ValueError:
                cat = None
        if not cat:
            cat = [dict(a) for a in CATALOGO_DEFECTO]
            self.origen_catalogo = "Nombres de Planificación PM incluidos en el programa"
        self.repo.set("catalogo", cat)
        self.repo.set("origen_catalogo", self.origen_catalogo)

    def _migrar_nombres(self):
        """Reemplaza los nombres provisorios de v1.0/v1.1 («Lubricante LL-0001») por los nombres reales,
        en el catálogo y en los controles guardados."""
        cat = self.repo.catalogo()
        cambio = False
        for a in cat:
            if es_nombre_generico(a["nombre"]) and a["parte"] in NOMBRES_REALES:
                a["nombre"] = NOMBRES_REALES[a["parte"]]
                cambio = True
        if cambio:
            self.repo.set("catalogo", cat)
            self.origen_catalogo = "Nombres de Planificación PM incluidos en el programa"
            self.repo.set("origen_catalogo", self.origen_catalogo)
        for c in self.repo.controles():
            mod = False
            for a in c.get("aceites", []):
                if es_nombre_generico(a.get("nombre", "")) and a["parte"] in NOMBRES_REALES:
                    a["nombre"] = NOMBRES_REALES[a["parte"]]
                    mod = True
            if mod:
                self.repo.guardar_control(c, tocar=False)

    # ---------------------------------------------------------- estructura
    def _construir(self):
        # ---- barra superior: logo, pestañas y estado
        barra = tk.Frame(self, background=NAVY, height=68)
        barra.pack(side="top", fill="x")
        barra.pack_propagate(False)
        logo = tk.Frame(barra, background=NAVY)
        logo.pack(side="left", padx=(18, 26))
        self._img_logo = tema.icono(self, "logo", 42)
        tk.Label(logo, image=self._img_logo, background=NAVY).pack(side="left")
        t = tk.Frame(logo, background=NAVY)
        t.pack(side="left", padx=10)
        tk.Label(t, text="CONTROL DE ACEITES", background=NAVY, foreground=TITULO_C,
                 font=(FUENTE, 13, "bold")).pack(anchor="w")
        tk.Label(t, text="Tarros · camión lubricador · cuadratura en litros", background=NAVY, foreground=ACENTO,
                 font=(FUENTE, 8)).pack(anchor="w")
        tk.Frame(barra, background=tema.BORDE, width=1).pack(side="left", fill="y", pady=16)

        pest = tk.Frame(barra, background=NAVY)
        pest.pack(side="left", fill="y", padx=(14, 0))
        self._nav = {}
        for clave, texto, ico in (("control", "Control semanal", "panel"), ("historial", "Historial", "historial"),
                                  ("config", "Configuración", "config"), ("ayuda", "Ayuda", "ayuda")):
            self._nav[clave] = self._boton_nav(pest, texto, ico, lambda c=clave: self.mostrar(c))

        der = tk.Frame(barra, background=NAVY)
        der.pack(side="right", padx=18)
        self.lbl_estado_lat = tk.Label(der, text="", background=NAVY, foreground=SUAVE, font=(FUENTE, 8),
                                       justify="right", anchor="e")
        self.lbl_estado_lat.pack(anchor="e")
        tk.Label(der, text=f"v{__version__}", background=NAVY, foreground=tema.GRIS,
                 font=(FUENTE, 8, "bold")).pack(anchor="e")
        FranjaSeguridad(self, alto=3).pack(side="top", fill="x")

        self.contenedor = tk.Frame(self, background=FONDO)
        self.contenedor.pack(fill="both", expand=True)
        self.paginas = {
            "control": self._pagina_control(),
            "historial": self._pagina_historial(),
            "config": self._pagina_config(),
            "ayuda": self._pagina_ayuda(),
        }

    def _boton_nav(self, master, texto, ico, cmd):
        """Pestaña superior: ícono + texto, subrayado ámbar cuando está activa."""
        f = tk.Frame(master, background=NAVY, cursor="hand2")
        f.pack(side="left", fill="y")
        img = tema.icono(self, ico, 16, SUAVE)
        img_a = tema.icono(self, ico, 16, ACENTO)
        cuerpo = tk.Frame(f, background=NAVY)
        cuerpo.pack(fill="both", expand=True, padx=16)
        li = tk.Label(cuerpo, image=img, background=NAVY)
        li.pack(side="left", padx=(0, 7))
        lt = tk.Label(cuerpo, text=texto, background=NAVY, foreground=SUAVE, font=(FUENTE, 10))
        lt.pack(side="left")
        linea = tk.Frame(f, background=NAVY, height=3)
        linea.pack(side="bottom", fill="x")
        widgets = (f, cuerpo, li, lt)

        def fijar(activo):
            for w in widgets:
                w.configure(background=NAVY_HOVER if activo else NAVY)
            linea.configure(background=ACENTO if activo else NAVY)
            li.configure(image=img_a if activo else img)
            lt.configure(foreground=TITULO_C if activo else SUAVE, font=(FUENTE, 10, "bold" if activo else "normal"))
            f.activo = activo

        def hover(on):
            if not getattr(f, "activo", False):
                lt.configure(foreground=TEXTO if on else SUAVE)
                linea.configure(background=tema.GRIS if on else NAVY)

        for w in widgets:
            w.bind("<Button-1>", lambda e: cmd())
            w.bind("<Enter>", lambda e: hover(True))
            w.bind("<Leave>", lambda e: hover(False))
        f.fijar = fijar
        return f

    def mostrar(self, clave):
        for k, p in self.paginas.items():
            p.pack_forget()
            self._nav[k].fijar(k == clave)
        self.paginas[clave].pack(fill="both", expand=True)
        {"control": self.refrescar, "historial": self.refrescar_historial,
         "config": self.refrescar_config, "ayuda": lambda: None}[clave]()

    def _titulo_pagina(self, master, titulo, nota):
        cab = tk.Frame(master, background=FONDO)
        cab.pack(fill="x", padx=22, pady=(14, 8))
        tk.Label(cab, text=titulo, background=FONDO, foreground=TITULO_C, font=(FUENTE, 17, "bold")).pack(anchor="w")
        lb = tk.Label(cab, text=nota, background=FONDO, foreground=SUAVE, font=(FUENTE, 9))
        lb.pack(anchor="w")
        return cab, lb

    # ---------------------------------------------------- página control
    def _pagina_control(self):
        pag = tk.Frame(self.contenedor, background=FONDO)
        desp = Desplazable(pag, fondo=FONDO)
        desp.pack(fill="both", expand=True)
        p = desp.interior
        cab, self.lbl_nota_control = self._titulo_pagina(p, "Control semanal de aceites", "")

        # pasos + datos del control
        c = tarjeta(p)
        c.pack(fill="x", padx=22, pady=(0, 10))
        self.pasos = Pasos(c.inner)
        self.pasos.pack(fill="x")
        self.lbl_info = tk.Label(c.inner, text="", background=TARJETA, foreground=TEXTO, font=(FUENTE, 9),
                                 justify="left", anchor="w")
        self.lbl_info.pack(fill="x", pady=(4, 0))
        c.inner.bind("<Configure>", lambda e: self.lbl_info.configure(wraplength=max(300, e.width - 10)))

        # botones de acción
        acc = tk.Frame(p, background=FONDO)
        acc.pack(fill="x", padx=22, pady=(0, 10))
        self.b_inicial = self._boton_accion(acc, "1  Stock inicial", "tarro", "Naranja", self.ingresar_inicial)
        self.b_recepcion = self._boton_accion(acc, "Recepción de aceites", "recepcion", "Morado", self.recepciones)
        self.b_consumos = self._boton_accion(acc, "2  Consumos semana", "consumo", "Azul", self.ingresar_consumos)
        self.b_entrega = self._boton_accion(acc, "3  Stock entregado", "entrega", "Verde", self.ingresar_entrega)
        for i, b in enumerate((self.b_inicial, self.b_recepcion, self.b_consumos, self.b_entrega)):
            b.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            acc.columnconfigure(i, weight=1, uniform="acc")
        # acciones secundarias, junto al título de la página
        sec = tk.Frame(cab, background=FONDO)
        sec.place(relx=1.0, rely=0.5, anchor="e")
        self.b_reporte = self._boton_accion(sec, "Reporte PDF", "reporte", "Gris", self.generar_reporte, grande=False)
        self.b_nuevo = self._boton_accion(sec, "Nuevo control", "nuevo", "Navy", self.nuevo_control, grande=False)
        self.b_reporte.pack(side="left")
        self.b_nuevo.pack(side="left", padx=(8, 0))

        # indicadores
        ind = tk.Frame(p, background=FONDO)
        ind.pack(fill="x", padx=22, pady=(0, 10))
        self.ind = {}
        for i, (k, tit, ico, col) in enumerate((("ini", "Stock inicial", "tarro", tema.SERIE_INI),
                                                ("rec", "Recibido semana", "recepcion", tema.MORADO),
                                                ("con", "Consumo semana", "consumo", AZUL),
                                                ("calc", "Sobrante calculado", "gota", tema.AMBAR),
                                                ("ent", "Stock entregado", "entrega", VERDE),
                                                ("dif", "Diferencia", "camion", ROJO))):
            w = Indicador(ind, tit, ico, col)
            w.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            ind.columnconfigure(i, weight=1, uniform="ind")
            self.ind[k] = w

        # tabla
        t = tarjeta(p, "Detalle por aceite (litros)", "gota")
        t.pack(fill="x", padx=22, pady=(0, 10))
        cols = [("ac", "Aceite", 190, "w"), ("pt", "Código", 62, "center"),
                ("it", "Inicial\ntarros", 52, "center"), ("ic", "Inicial\ncamión", 62, "e"),
                ("itot", "Inicial\ntotal", 66, "e"), ("rc", "Recib.\ntarros", 52, "center"),
                ("co", "Consumo\nsemana", 64, "e"),
                ("re", "Relle-\nnos", 48, "center"), ("ct", "Calc.\ntarros", 52, "center"),
                ("cc", "Calc.\ncamión", 62, "e"), ("ctot", "Sobrante\ncalculado", 70, "e"),
                ("et", "Entreg.\ntarros", 56, "center"), ("ec", "Entreg.\ncamión", 62, "e"),
                ("etot", "Entreg.\ntotal", 66, "e"), ("dif", "Dife-\nrencia", 60, "e"),
                ("est", "Estado", 112, "center")]
        self.tv = tabla(t.inner, cols, alto=8)
        self.tv.marco.pack(fill="x")
        ley = tk.Frame(t.inner, background=TARJETA)
        ley.pack(fill="x", pady=(6, 0))
        for est, col in tema.FONDO_ESTADO.items():
            tk.Label(ley, text="  ", background=col, highlightthickness=1,
                     highlightbackground=tema.COLOR_ESTADO[est]).pack(side="left", padx=(0, 4))
            tk.Label(ley, text=est, background=TARJETA, foreground=SUAVE, font=(FUENTE, 8)).pack(side="left",
                                                                                                padx=(0, 14))

        # gráfico + hallazgos
        fila = tk.Frame(p, background=FONDO)
        fila.pack(fill="x", padx=22, pady=(0, 16))
        g = tarjeta(fila, "Litros por aceite", "tarro")
        g.grid(row=0, column=0, sticky="nsew")
        self.grafico = GraficoLitros(g.inner)
        self.grafico.pack(fill="both", expand=True)
        h = tarjeta(fila, "Resultado y hallazgos", "reporte")
        h.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        fila.columnconfigure(0, weight=1, uniform="f")
        fila.columnconfigure(1, weight=1, uniform="f")
        self.txt = tk.Text(h.inner, height=11, wrap="word", relief="flat", background=TARJETA, foreground=TEXTO,
                           font=(FUENTE, 9), padx=4, pady=4, highlightthickness=0)
        sb = ttk.Scrollbar(h.inner, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt.pack(fill="both", expand=True)
        for tag, col in (("error", ROJO), ("aviso", tema.ACENTO), ("info", AZUL), ("ok", VERDE)):
            self.txt.tag_configure(tag, foreground=col)
        self.txt.tag_configure("tit", font=(FUENTE, 9, "bold"), foreground=TITULO_C)
        self.txt.tag_configure("concl", font=(FUENTE, 10, "bold"), foreground=TITULO_C, spacing3=6)
        return pag

    def _boton_accion(self, master, texto, ico, estilo, cmd, grande=True):
        img = tema.icono(self, ico, 20 if grande else 16, NAVY if estilo == "Naranja" else "#FFFFFF")
        b = ttk.Button(master, text=" " + texto, image=img, compound="left",
                       style=f"{estilo}{'Grande' if grande else ''}.TButton", command=cmd)
        b.image = img
        return b

    # ---------------------------------------------------------- refresco
    def refrescar(self):
        ctl = self.control
        et = etapa(ctl)
        self.pasos.fijar({0: 0, 1: 1, 2: 3}.get(et) if et < 3 else (5 if ctl.get("reporte") else 4))
        self.b_recepcion.state(["!disabled"] if et >= 1 else ["disabled"])
        self.b_consumos.state(["!disabled"] if et >= 1 else ["disabled"])
        self.b_entrega.state(["!disabled"] if et >= 2 else ["disabled"])
        self.b_reporte.state(["!disabled"] if et >= 1 else ["disabled"])
        self.b_nuevo.state(["!disabled"] if et >= 1 else ["disabled"])
        self.tv.delete(*self.tv.get_children())
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        lat = f"Aceites activos: {len(self.repo.aceites_activos())}"
        if et == 0:
            self.lbl_nota_control.configure(text="Comience ingresando el stock existente en tarros y en el camión "
                                                 "lubricador indicado por el jefe de operaciones.")
            self.lbl_info.configure(text="Sin control abierto. Presione «1  Ingresar stock inicial».")
            for w in self.ind.values():
                w.fijar("—")
            self.grafico.fijar([])
            self.txt.insert("end", "Sin datos todavía.\n\n", "tit")
            self.txt.insert("end", "1. Stock inicial  →  2. Consumos de la semana  →  sobrante calculado  →  "
                                   "3. Stock entregado al finalizar el turno  →  reporte de inconsistencias.")
            self.txt.configure(state="disabled")
            self.lbl_estado_lat.configure(text=lat)
            return

        res = resultado(ctl)
        t = res["totales"]
        lt = res["litros_tarro"]
        ini, con, ent = ctl.get("inicial") or {}, ctl.get("consumos") or {}, ctl.get("entrega") or {}
        self.lbl_nota_control.configure(text=f"Control N° {ctl.get('id')}  ·  tarro = {fmt_num(lt, 0)} L  ·  "
                                             f"actualizado {fmt_fechahora(ctl.get('actualizado'))}")
        info = [f"Stock inicial: {ini.get('turno')} · {fmt_fecha(ini.get('fecha'))} · Jefe de operaciones: "
                f"{ini.get('persona') or '—'}"]
        nrec = len(ctl.get("recepciones") or [])
        info.append(f"Recepciones: {nrec} ({t['rec_tarros']} tarros)" if nrec else "Recepciones: ninguna")
        info.append(f"Consumos: {fmt_fecha(con.get('desde'))} a {fmt_fecha(con.get('hasta'))}" if con
                    else "Consumos: pendiente")
        info.append(f"Stock entregado: {ent.get('turno')} · {fmt_fecha(ent.get('fecha'))} · Responsable: "
                    f"{ent.get('persona') or '—'}" if ent else "Stock entregado: pendiente")
        self.lbl_info.configure(text="   |   ".join(info))
        lat = (f"Control N° {ctl.get('id')} · {ini.get('turno')} · " +
               ("cerrado" if et >= 3 else "abierto, " + ("falta consumos" if et == 1 else "falta stock entregado")) +
               f"   ·   {lat}")
        self.lbl_estado_lat.configure(text=lat)

        self.ind["ini"].fijar(fmt_l(t["ini"]), f"{t['ini_tarros']} tarros + {fmt_l(t['ini_camion'])} camión")
        self.ind["rec"].fijar(fmt_l(t["recibido"], 0), f"{t['rec_tarros']} tarros en {nrec} recepción(es)"
                              if nrec else "sin recepciones")
        if et >= 2:
            self.ind["con"].fijar(fmt_l(t["consumo"]), f"{t['rellenos']} tarros rellenados al camión")
            self.ind["calc"].fijar(fmt_l(t["calc"]), f"{t['calc_tarros']} tarros + {fmt_l(t['calc_camion'])} camión",
                                   ROJO if t["calc"] < 0 else None)
        else:
            self.ind["con"].fijar("—", "pendiente")
            self.ind["calc"].fijar("—", "pendiente")
        if et >= 3:
            self.ind["ent"].fijar(fmt_l(t["ent"]), f"{t['ent_tarros']} tarros + {fmt_l(t['ent_camion'])} camión")
            col = VERDE if res["inconsistencias"] == 0 else (ROJO if abs(t["dif"]) > 0.004 else AZUL)
            self.ind["dif"].fijar(fmt_signo(t["dif"], 1) + " L", f"{res['inconsistencias']} con inconsistencia", col)
        else:
            self.ind["ent"].fijar("—", "pendiente")
            self.ind["dif"].fijar("—", "pendiente")

        datos_g = []
        for i, f in enumerate(res["filas"]):
            c, e = f["calc"], f["entrega"]
            vals = [f"{f['nombre']}", f["parte"], c["tarros_ini"], fmt_num(c["camion_ini"]), fmt_num(c["total_ini"]),
                    c["recibidos"] or ""]
            if et >= 2:
                vals += [fmt_num(c["consumo"]), c["rellenos"] + c["rellenos_implicitos"], c["tarros"],
                         fmt_num(c["camion"]), fmt_num(c["total"])]
            else:
                vals += [""] * 5
            if e:
                vals += [e["tarros"], fmt_num(e["camion"]), fmt_num(e["total"]), fmt_signo(e["dif_total"]), e["estado"]]
                tags = (e["estado"],)
            else:
                vals += ["", "", "", "", "Pendiente"]
                tags = ("par",) if i % 2 else ()
            self.tv.insert("", "end", values=vals, tags=tags)
            datos_g.append((f["parte"], [c["total_ini"], c["total"] if et >= 2 else None, e["total"] if e else None]))
        tot = ["TOTAL", "", t["ini_tarros"], fmt_num(t["ini_camion"]), fmt_num(t["ini"]), t["rec_tarros"]]
        tot += [fmt_num(t["consumo"]), t["rellenos"], t["calc_tarros"], fmt_num(t["calc_camion"]),
                fmt_num(t["calc"])] if et >= 2 else [""] * 5
        tot += [t["ent_tarros"], fmt_num(t["ent_camion"]), fmt_num(t["ent"]), fmt_signo(t["dif"]),
                f"{res['inconsistencias']} incons."] if et >= 3 else [""] * 5
        self.tv.insert("", "end", values=tot, tags=("total",))
        self.tv.configure(height=len(res["filas"]) + 1)
        self.grafico.fijar(datos_g)

        # hallazgos
        self.txt.insert("end", conclusion(res) + "\n", "concl")
        if et >= 2:
            ok = res["cuadratura_ok"]
            lr = t["rellenos"] * lt
            self.txt.insert("end", ("✔ " if ok else "⚠ ") + f"Cuadratura: rellenos −{fmt_l(lr, 0)} en tarros / "
                            f"+{fmt_l(lr, 0)} en camión. Inicial {fmt_l(t['ini'])} + recibido "
                            f"{fmt_l(t['recibido'], 0)} − consumo {fmt_l(t['consumo'])} = sobrante "
                            f"{fmt_l(t['calc'])}.\n", "ok" if ok else "error")
        for f in res["filas"]:
            items = list(f["calc"]["avisos"]) + (f["entrega"]["hallazgos"] if f["entrega"] else [])
            if f["entrega"] and not f["entrega"]["inconsistente"] and not f["calc"]["avisos"]:
                continue
            if not items:
                continue
            self.txt.insert("end", f"\n{etiqueta(f['nombre'], f['parte'])}" +
                            (f" — {f['entrega']['estado']}" if f["entrega"] else "") + "\n", "tit")
            for nivel, m in items:
                self.txt.insert("end", f"  • {m}\n", nivel)
        self.txt.configure(state="disabled")

    # ------------------------------------------------------------ acciones
    def _guardar(self):
        self.repo.guardar_control(self.control)
        self.repo.set("control_actual", self.control["id"])
        self.control = self.repo.control(self.control["id"])

    def ingresar_inicial(self, previo: dict | None = None):
        ctl = self.control
        if ctl and etapa(ctl) >= 1 and previo is None:
            aceites = ctl["aceites"]
            lt = ctl["litros_tarro"]
            previo = ctl["inicial"]
        else:
            aceites = self.repo.aceites_activos()
            lt = self.repo.litros_tarro()
            if not aceites:
                messagebox.showwarning(TITULO, "No hay aceites activos. Revise «Configuración».", parent=self)
                return
        turno = PreguntaTurno(self, "¿A qué turno corresponde este stock existente?",
                              (previo or {}).get("turno")).mostrar()
        if not turno:
            return
        r = FormularioStock(self, "inicial", aceites, lt, turno, previo).mostrar()
        if not r:
            return
        if ctl and etapa(ctl) >= 1 and ctl.get("inicial") is previo:
            ctl["inicial"] = r
        else:
            self.control = {"aceites": aceites, "litros_tarro": lt, "inicial": r, "recepciones": [],
                            "consumos": None, "entrega": None}
        self.control.pop("reporte", None)
        self._guardar()
        self.refrescar()
        if etapa(self.control) == 1:
            res = resultado(self.control)
            messagebox.showinfo(TITULO, f"Stock inicial registrado ({r['turno']}).\n\n"
                                        f"Total: {fmt_l(res['totales']['ini'])} "
                                        f"({res['totales']['ini_tarros']} tarros + "
                                        f"{fmt_l(res['totales']['ini_camion'])} en camión).\n\n"
                                        "Durante la semana: «Recepción de aceites» si llegan tarros.\n"
                                        "Luego: «2  Consumos semana».", parent=self)

    def recepciones(self):
        ctl = self.control
        if etapa(ctl) < 1:
            return
        if etapa(ctl) >= 3 and not messagebox.askyesno(
                TITULO, "Este control ya tiene el stock entregado.\n\nSi agrega o elimina recepciones se recalculan "
                        "el sobrante y el análisis de inconsistencias. ¿Continuar?", parent=self):
            return
        antes = resultado(ctl)["inconsistencias"]

        def al_cambiar():
            ctl.pop("reporte", None)
            self.repo.guardar_control(ctl)
            self.repo.set("control_actual", ctl["id"])
            self.control = ctl
            self.refrescar()

        VentanaRecepciones(self, ctl, al_cambiar).mostrar()
        self.control = self.repo.control(ctl["id"])
        self.refrescar()
        res = resultado(self.control)
        if etapa(self.control) >= 3 and res["inconsistencias"] != antes:
            messagebox.showinfo(TITULO, "Análisis recalculado.\n\n" + conclusion(res), parent=self)

    def ingresar_consumos(self):
        ctl = self.control
        if etapa(ctl) < 1:
            return
        r = FormularioConsumos(self, ctl["aceites"], ctl["inicial"], ctl["litros_tarro"], ctl.get("consumos"),
                               recibidos_por_aceite(ctl)).mostrar()
        if not r:
            return
        ctl["consumos"] = r
        ctl.pop("reporte", None)
        self._guardar()
        self.refrescar()
        VentanaSobrante(self, resultado(self.control)).mostrar()

    def ingresar_entrega(self):
        ctl = self.control
        if etapa(ctl) < 2:
            return
        previo = ctl.get("entrega")
        turno = PreguntaTurno(self, "¿Qué turno entrega este stock al finalizar?",
                              (previo or {}).get("turno")).mostrar()
        if not turno:
            return
        r = FormularioStock(self, "entrega", ctl["aceites"], ctl["litros_tarro"], turno, previo).mostrar()
        if not r:
            return
        ctl["entrega"] = r
        ctl.pop("reporte", None)
        self._guardar()
        self.refrescar()
        res = resultado(self.control)
        if res["inconsistencias"]:
            if messagebox.askyesno(TITULO, conclusion(res) + "\n\n¿Generar ahora el reporte PDF de inconsistencias?",
                                   icon="warning", parent=self):
                self.generar_reporte()
        else:
            messagebox.showinfo(TITULO, conclusion(res) + "\n\nPuede generar el reporte de cuadratura con "
                                                         "«Reporte PDF».", parent=self)

    def _ruta_reportes(self) -> Path:
        r = self.ruta_db.parent / "Reportes"
        r.mkdir(parents=True, exist_ok=True)
        return r

    def generar_reporte(self, control: dict | None = None):
        ctl = control or self.control
        if etapa(ctl) < 1:
            return
        res = resultado(ctl)
        tipo = "Inconsistencias" if res["etapa"] >= 3 and res["inconsistencias"] else "Cuadratura"
        ini = ctl["inicial"]
        nombre = (f"Reporte_{tipo}_aceites_N{ctl['id']}_{ini.get('turno', '').replace(' ', '')}_"
                  f"{fmt_fecha(ini.get('fecha'))}.pdf")
        ruta = filedialog.asksaveasfilename(parent=self, title="Guardar reporte PDF", defaultextension=".pdf",
                                            initialdir=str(self._ruta_reportes()), initialfile=nombre,
                                            filetypes=[("PDF", "*.pdf")])
        if not ruta:
            return
        try:
            exportar_reporte(ctl, ruta)
        except PermissionError:
            messagebox.showerror(TITULO, "No se pudo escribir el archivo. ¿Está abierto en otro programa?", parent=self)
            return
        if control is None or (self.control and control.get("id") == self.control.get("id")):
            self.control["reporte"] = ruta
            self._guardar()
            self.refrescar()
        if messagebox.askyesno(TITULO, f"Reporte generado:\n{ruta}\n\n¿Abrirlo ahora?", parent=self):
            abrir_archivo(ruta)

    def nuevo_control(self):
        ctl = self.control
        et = etapa(ctl)
        if et == 0:
            return
        if et < 3 and not messagebox.askyesno(
                TITULO, "El control actual no tiene stock entregado (queda abierto en Historial).\n\n"
                        "¿Comenzar un nuevo control de todas formas?", icon="warning", parent=self):
            return
        previo = None
        if et >= 3 and messagebox.askyesno(TITULO, "¿Usar el stock entregado por el turno como stock inicial del "
                                                   "nuevo control?", parent=self):
            previo = {"items": ctl["entrega"]["items"], "persona": "", "obs": "",
                      "turno": ctl["entrega"].get("turno"), "fecha": ctl["entrega"].get("fecha")}
        aceites = self.repo.aceites_activos()
        if previo:
            # aceites nuevos del catálogo parten en cero
            previo["items"] = {a["parte"]: previo["items"].get(a["parte"], {"tarros": 0, "camion": 0}) for a in aceites}
        self.control = None
        self.ingresar_inicial(previo)
        if self.control is None:        # se canceló: se vuelve al control anterior
            self.control = ctl
        self.refrescar()

    # -------------------------------------------------------- historial
    def _pagina_historial(self):
        p = tk.Frame(self.contenedor, background=FONDO)
        self._titulo_pagina(p, "Historial de controles", "Doble clic para abrir un control en la pantalla principal.")
        c = tarjeta(p)
        c.pack(fill="both", expand=True, padx=22, pady=(0, 16))
        bar = tk.Frame(c.inner, background=TARJETA)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Button(bar, text="Abrir", style="Naranja.TButton", command=self._hist_abrir).pack(side="left")
        ttk.Button(bar, text="Reporte PDF", style="Morado.TButton", command=self._hist_reporte).pack(side="left", padx=8)
        ttk.Button(bar, text="Eliminar", style="Rojo.TButton", command=self._hist_eliminar).pack(side="right")
        self.tv_hist = tabla(c.inner, [("id", "N°", 50, "center"), ("turno", "Turno", 80, "center"),
                                       ("fecha", "Fecha stock", 90, "center"), ("jefe", "Jefe de operaciones", 160, "w"),
                                       ("sem", "Semana consumos", 160, "center"), ("ini", "Inicial (L)", 90, "e"),
                                       ("rec", "Recibido (L)", 90, "e"),
                                       ("con", "Consumo (L)", 90, "e"), ("calc", "Sobrante calc. (L)", 110, "e"),
                                       ("ent", "Entregado (L)", 100, "e"), ("dif", "Diferencia (L)", 100, "e"),
                                       ("est", "Estado", 190, "w")], alto=20)
        self.tv_hist.marco.pack(fill="both", expand=True)
        self.tv_hist.bind("<Double-1>", lambda e: self._hist_abrir())
        return p

    def refrescar_historial(self):
        tv = self.tv_hist
        tv.delete(*tv.get_children())
        for i, c in enumerate(self.repo.controles()):
            res = resultado(c)
            t = res["totales"]
            et = res["etapa"]
            ini, con = c.get("inicial") or {}, c.get("consumos") or {}
            if et < 3:
                est = "Abierto: " + ("falta consumos" if et == 1 else "falta stock entregado")
                tag = ()
            elif res["inconsistencias"]:
                est = f"{res['inconsistencias']} inconsistencia(s)"
                tag = ("Faltante",) if res["con_diferencia_litros"] else ("Cuadra en litros",)
            else:
                est = "Cuadrado"
                tag = ("Cuadrado",)
            if self.control and c["id"] == self.control.get("id"):
                est = "▶ " + est
            tv.insert("", "end", iid=str(c["id"]), tags=tag, values=(
                c["id"], ini.get("turno"), fmt_fecha(ini.get("fecha")), ini.get("persona") or "",
                f"{fmt_fecha(con.get('desde'))} a {fmt_fecha(con.get('hasta'))}" if con else "",
                fmt_num(t["ini"]), fmt_num(t["recibido"]) if t["recibido"] else "",
                fmt_num(t["consumo"]) if et >= 2 else "", fmt_num(t["calc"]) if et >= 2 else "",
                fmt_num(t["ent"]) if et >= 3 else "", fmt_signo(t["dif"]) if et >= 3 else "", est))

    def _hist_sel(self):
        s = self.tv_hist.selection()
        if not s:
            messagebox.showinfo(TITULO, "Seleccione un control.", parent=self)
            return None
        return self.repo.control(int(s[0]))

    def _hist_abrir(self):
        c = self._hist_sel()
        if c:
            self.control = c
            self.repo.set("control_actual", c["id"])
            self.mostrar("control")

    def _hist_reporte(self):
        c = self._hist_sel()
        if c:
            self.generar_reporte(c)

    def _hist_eliminar(self):
        c = self._hist_sel()
        if c and messagebox.askyesno(TITULO, f"¿Eliminar el control N° {c['id']}? No se puede deshacer.",
                                     icon="warning", parent=self):
            self.repo.borrar_control(c["id"])
            if self.control and self.control.get("id") == c["id"]:
                self.control = None
            self.refrescar_historial()

    # ---------------------------------------------------- configuración
    def _pagina_config(self):
        p = tk.Frame(self.contenedor, background=FONDO)
        self._titulo_pagina(p, "Configuración", "Aceites del proyecto Planificación PM, litros por tarro y datos.")
        fila = tk.Frame(p, background=FONDO)
        fila.pack(fill="both", expand=True, padx=22, pady=(0, 16))
        c = tarjeta(fila, "Aceites (lubricantes de Planificación PM)", "gota")
        c.grid(row=0, column=0, sticky="nsew")
        fila.columnconfigure(0, weight=3)
        fila.columnconfigure(1, weight=2)
        fila.rowconfigure(0, weight=1)
        self.lbl_origen = tk.Label(c.inner, text="", background=TARJETA, foreground=SUAVE, font=(FUENTE, 8),
                                   justify="left", anchor="w", wraplength=560)
        self.lbl_origen.pack(fill="x", pady=(0, 6))
        bar = tk.Frame(c.inner, background=TARJETA)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Button(bar, text="Leer desde Planificación PM (.xlsm / .db)", style="Naranja.TButton",
                   command=self._cfg_importar).pack(side="left")
        ttk.Button(bar, text="Activar / desactivar", style="Azul.TButton", command=self._cfg_toggle).pack(side="left",
                                                                                                         padx=6)
        ttk.Button(bar, text="Editar nombre", style="Gris.TButton", command=self._cfg_editar).pack(side="left")
        ttk.Button(bar, text="Agregar", style="Verde.TButton", command=self._cfg_agregar).pack(side="left", padx=6)
        ttk.Button(bar, text="Quitar", style="Rojo.TButton", command=self._cfg_quitar).pack(side="left")
        self.tv_cat = tabla(c.inner, [("parte", "Código compra", 100, "center"), ("nombre", "Lubricante", 320, "w"),
                                      ("act", "Activo", 70, "center")], alto=12)
        self.tv_cat.marco.pack(fill="both", expand=True)
        self.tv_cat.bind("<Double-1>", lambda e: self._cfg_editar())
        tk.Label(c.inner, text="Los cambios aplican a los controles nuevos; los existentes conservan sus aceites.",
                 background=TARJETA, foreground=SUAVE, font=(FUENTE, 8)).pack(anchor="w", pady=(6, 0))

        d = tarjeta(fila, "Parámetros y datos", "config")
        d.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        f = tk.Frame(d.inner, background=TARJETA)
        f.pack(fill="x")
        ttk.Label(f, text="Litros por tarro", style="Cab.TLabel").grid(row=0, column=0, sticky="w")
        self.v_lt = tk.StringVar()
        ttk.Entry(f, textvariable=self.v_lt, width=10, justify="right").grid(row=0, column=1, padx=8)
        ttk.Button(f, text="Guardar", style="Verde.TButton", command=self._cfg_lt).grid(row=0, column=2)
        tk.Label(d.inner, text="Base de datos de este programa:", background=TARJETA, foreground=TITULO_C,
                 font=(FUENTE, 9, "bold")).pack(anchor="w", pady=(18, 0))
        self.lbl_ruta = tk.Label(d.inner, text="", background=TARJETA, foreground=SUAVE, font=(FUENTE, 8),
                                 justify="left", anchor="w", wraplength=380)
        self.lbl_ruta.pack(fill="x")
        b = tk.Frame(d.inner, background=TARJETA)
        b.pack(fill="x", pady=8)
        ttk.Button(b, text="Respaldar base de datos", style="Azul.TButton", command=self._cfg_respaldar).pack(
            side="left")
        ttk.Button(b, text="Abrir carpeta", style="Gris.TButton",
                   command=lambda: abrir_archivo(str(self.ruta_db.parent))).pack(side="left", padx=6)
        tk.Label(d.inner, text="La base de Planificación PM (repositorio Prueba) solo se lee; este programa nunca la "
                               "modifica.", background=TARJETA, foreground=SUAVE, font=(FUENTE, 8), justify="left",
                 wraplength=380).pack(anchor="w", pady=(10, 0))
        return p

    def refrescar_config(self):
        self.v_lt.set(fmt_num(self.repo.litros_tarro(), 2))
        self.lbl_ruta.configure(text=str(self.ruta_db))
        self.lbl_origen.configure(text=f"Origen de los nombres: {self.repo.get('origen_catalogo', '')}")
        tv = self.tv_cat
        tv.delete(*tv.get_children())
        for i, a in enumerate(self.repo.catalogo()):
            tv.insert("", "end", iid=a["parte"], values=(a["parte"], a["nombre"], "Sí" if a.get("activo", True) else "No"),
                      tags=("par",) if i % 2 else ())

    def _cfg_sel(self):
        s = self.tv_cat.selection()
        if not s:
            messagebox.showinfo(TITULO, "Seleccione un aceite.", parent=self)
        return s[0] if s else None

    def _cfg_set(self, cat):
        self.repo.set("catalogo", cat)
        self.refrescar_config()

    def _cfg_importar(self):
        ruta = buscar_db_pm()
        if ruta and not messagebox.askyesno(TITULO, f"Se encontró la base de Planificación PM:\n{ruta}\n\n"
                                                    "¿Leer los aceites desde ella? (Elija «No» para elegir el Excel "
                                                    "Planificacion_PM u otro archivo.)", parent=self):
            ruta = None
        if not ruta:
            ruta = filedialog.askopenfilename(parent=self, title="Excel o base de datos de Planificación PM",
                                              filetypes=[("Planificación PM (Excel o base)", "*.xlsm *.xlsx *.db"),
                                                         ("Todos", "*.*")])
            if not ruta:
                return
        try:
            nuevo = leer_catalogo(ruta)
        except ValueError as ex:
            messagebox.showerror(TITULO, str(ex), parent=self)
            return
        self.repo.set("origen_catalogo", str(ruta))
        self._cfg_set(fusionar(self.repo.catalogo(), nuevo))
        messagebox.showinfo(TITULO, f"Se leyeron {len(nuevo)} aceites desde Planificación PM.", parent=self)

    def _cfg_toggle(self):
        p = self._cfg_sel()
        if p:
            cat = self.repo.catalogo()
            for a in cat:
                if a["parte"] == p:
                    a["activo"] = not a.get("activo", True)
            self._cfg_set(cat)

    def _cfg_editar(self):
        p = self._cfg_sel()
        if not p:
            return
        cat = self.repo.catalogo()
        a = next(x for x in cat if x["parte"] == p)
        n = simpledialog.askstring(TITULO, f"Nombre del lubricante {p}:", initialvalue=a["nombre"], parent=self)
        if n and n.strip():
            a["nombre"] = n.strip()
            self._cfg_set(cat)

    def _cfg_agregar(self):
        p = simpledialog.askstring(TITULO, "Código de compra del aceite (ej.: LL-0008):", parent=self)
        if not p or not p.strip():
            return
        p = p.strip().upper()
        cat = self.repo.catalogo()
        if any(a["parte"] == p for a in cat):
            messagebox.showwarning(TITULO, f"El código {p} ya existe.", parent=self)
            return
        n = simpledialog.askstring(TITULO, f"Nombre del lubricante {p}:", parent=self) or f"Lubricante {p}"
        cat.append({"parte": p, "nombre": n.strip(), "activo": True})
        self._cfg_set(cat)

    def _cfg_quitar(self):
        p = self._cfg_sel()
        if p and messagebox.askyesno(TITULO, f"¿Quitar {p} del catálogo?", parent=self):
            self._cfg_set([a for a in self.repo.catalogo() if a["parte"] != p])

    def _cfg_lt(self):
        v = parse_num(self.v_lt.get())
        if v is None or v <= 0:
            messagebox.showerror(TITULO, "Ingrese un número de litros mayor que 0.", parent=self)
            return
        self.repo.set("litros_tarro", v)
        self.refrescar_config()
        messagebox.showinfo(TITULO, f"Litros por tarro: {fmt_num(v, 2)} L (aplica a los controles nuevos).",
                            parent=self)

    def _cfg_respaldar(self):
        ruta = filedialog.asksaveasfilename(parent=self, title="Respaldar base de datos", defaultextension=".db",
                                            initialfile=f"ControlAceites_respaldo_{dt.date.today():%Y-%m-%d}.db",
                                            filetypes=[("Base de datos", "*.db")])
        if ruta:
            self.repo.respaldar(ruta)
            messagebox.showinfo(TITULO, f"Respaldo guardado en:\n{ruta}", parent=self)

    # ------------------------------------------------------------- ayuda
    def _pagina_ayuda(self):
        p = tk.Frame(self.contenedor, background=FONDO)
        self._titulo_pagina(p, "Ayuda", "Cómo funciona el control de aceites.")
        c = tarjeta(p)
        c.pack(fill="both", expand=True, padx=22, pady=(0, 16))
        txt = tk.Text(c.inner, wrap="word", relief="flat", background=TARJETA, foreground=TEXTO, font=(FUENTE, 10),
                      padx=6, pady=6, highlightthickness=0)
        sb = ttk.Scrollbar(c.inner, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        txt.tag_configure("tit", font=(FUENTE, 11, "bold"), foreground=TITULO_C, spacing1=8)
        for linea in AYUDA.splitlines():
            txt.insert("end", linea + "\n", "tit" if linea and linea == linea.upper() and linea[0].isalpha()
                       or (linea[:1].isdigit() and linea[1:3] == ". ") else ())
        txt.configure(state="disabled")
        return p


def abrir_archivo(ruta: str):
    try:
        if sys.platform.startswith("win"):
            os.startfile(ruta)  # noqa: S606
        elif sys.platform == "darwin":
            os.system(f'open "{ruta}"')  # noqa: S605
        else:
            os.system(f'xdg-open "{ruta}" >/dev/null 2>&1 &')  # noqa: S605
    except OSError:
        pass


def main():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ControlAceites")
        except (AttributeError, OSError):
            pass
    app = App()
    app.mainloop()

