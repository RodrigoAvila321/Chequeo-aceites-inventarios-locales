"""Reporte PDF de inconsistencias (o de cuadratura, si no hay diferencias)."""
from __future__ import annotations

import datetime as dt

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from . import TITULO, __version__
from .calculo import CUADRADO, FALTANTE, SOBRANTE, TRASPASO, conclusion, resultado
from .util import fmt_fecha, fmt_fechahora, fmt_l, fmt_num, fmt_signo

NAVY = colors.HexColor("#15233A")
NAVY2 = colors.HexColor("#22354F")
NARANJA = colors.HexColor("#F28C28")
AMARILLO = colors.HexColor("#F6C343")
BORDE = colors.HexColor("#D8E0E9")
SUAVE = colors.HexColor("#6B7785")
GRIS_F = colors.HexColor("#F3F5F8")
COL_ESTADO = {CUADRADO: colors.HexColor("#2E9E5B"), TRASPASO: colors.HexColor("#1F6FB2"),
              FALTANTE: colors.HexColor("#D64545"), SOBRANTE: colors.HexColor("#F28C28")}
FONDO_ESTADO = {CUADRADO: colors.HexColor("#E3F4EA"), TRASPASO: colors.HexColor("#E1EEF9"),
                FALTANTE: colors.HexColor("#FBE3E3"), SOBRANTE: colors.HexColor("#FDEEDD")}
COL_NIVEL = {"info": "#1F6FB2", "aviso": "#C46A10", "error": "#D64545"}

_E = dict(
    normal=ParagraphStyle("n", fontName="Helvetica", fontSize=8.5, leading=11),
    peq=ParagraphStyle("p", fontName="Helvetica", fontSize=7.3, leading=9),
    peqb=ParagraphStyle("pb", fontName="Helvetica-Bold", fontSize=7.3, leading=9),
    cab=ParagraphStyle("c", fontName="Helvetica-Bold", fontSize=7.3, leading=9, textColor=colors.white,
                       alignment=1),
    sec=ParagraphStyle("s", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=NAVY, spaceBefore=8,
                       spaceAfter=4),
    concl=ParagraphStyle("cc", fontName="Helvetica-Bold", fontSize=9.5, leading=13, textColor=NAVY,
                         alignment=TA_LEFT),
)


def _t(txt) -> str:
    """Helvetica (WinAnsi) no trae algunos símbolos: se reemplazan por equivalentes."""
    return (str(txt).replace("−", "-").replace("→", "a").replace("≈", "aprox.").replace("✔", "")
            .replace("⚠", "!"))


def _p(t, est="peq"):
    return Paragraph(_t(t), _E[est])


def _encabezado(titulo: str, subtitulo: str):
    def dibujar(c, doc):
        w, h = doc.pagesize
        c.saveState()
        c.setFillColor(NAVY)
        c.rect(0, h - 26 * mm, w, 26 * mm, fill=1, stroke=0)
        # franja de seguridad
        c.setFillColor(AMARILLO)
        c.rect(0, h - 28.5 * mm, w, 2.5 * mm, fill=1, stroke=0)
        c.setFillColor(NAVY)
        x = 0
        while x < w:
            p = c.beginPath()
            p.moveTo(x, h - 28.5 * mm)
            p.lineTo(x + 2.5 * mm, h - 26 * mm)
            p.lineTo(x + 5 * mm, h - 26 * mm)
            p.lineTo(x + 2.5 * mm, h - 28.5 * mm)
            p.close()
            c.drawPath(p, fill=1, stroke=0)
            x += 6 * mm
        # logo: gota
        cx, cy = 20 * mm, h - 13 * mm
        c.setFillColor(NARANJA)
        c.circle(cx, cy, 8.5 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.circle(cx, cy - 1.6 * mm, 3.6 * mm, fill=1, stroke=0)
        p = c.beginPath()
        p.moveTo(cx, cy + 6 * mm)
        p.lineTo(cx - 3.3 * mm, cy - 0.3 * mm)
        p.lineTo(cx + 3.3 * mm, cy - 0.3 * mm)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(33 * mm, h - 12.5 * mm, titulo)
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#B9C4D3"))
        c.drawString(33 * mm, h - 18.5 * mm, subtitulo)
        c.setFont("Helvetica", 7.5)
        c.drawRightString(w - 12 * mm, h - 12.5 * mm, f"{TITULO} v{__version__}")
        c.drawRightString(w - 12 * mm, h - 18.5 * mm, f"Generado: {dt.datetime.now():%d-%m-%Y %H:%M}")
        # pie
        c.setFillColor(SUAVE)
        c.setFont("Helvetica", 7)
        c.drawString(12 * mm, 7 * mm, "Control de aceites: tarros + camión lubricador. Cuadratura en litros.")
        c.drawRightString(w - 12 * mm, 7 * mm, f"Página {doc.page}")
        c.restoreState()
    return dibujar


def exportar_reporte(control: dict, ruta: str) -> str:
    res = resultado(control)
    lt = res["litros_tarro"]
    t = res["totales"]
    ini = control.get("inicial") or {}
    con = control.get("consumos") or {}
    ent = control.get("entrega") or {}
    cerrado = res["etapa"] >= 3
    hay_inc = cerrado and res["inconsistencias"] > 0
    titulo = "Reporte de inconsistencias de aceite" if hay_inc else "Reporte de cuadratura de aceite"
    sub = (f"Control N° {control.get('id', '-')}  ·  Stock inicial {ini.get('turno', '')} "
           f"{fmt_fecha(ini.get('fecha'))}  ·  Tarro = {fmt_num(lt, 0)} L")

    doc = SimpleDocTemplate(ruta, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=33 * mm, bottomMargin=13 * mm, title=titulo, author=TITULO)
    ancho = doc.width
    h = []

    # ---- datos del control
    datos = [
        [_p("<b>Stock inicial</b>"), _p(f"{ini.get('turno', '')} · {fmt_fecha(ini.get('fecha'))}"),
         _p("<b>Jefe de operaciones</b>"), _p(ini.get("persona") or "—"),
         _p("<b>Período de consumos</b>"), _p(f"{fmt_fecha(con.get('desde'))} a {fmt_fecha(con.get('hasta'))}"
                                             if con else "Sin ingresar")],
        [_p("<b>Stock entregado</b>"), _p(f"{ent.get('turno', '')} · {fmt_fecha(ent.get('fecha'))}" if ent
                                         else "Sin ingresar"),
         _p("<b>Responsable entrega</b>"), _p(ent.get("persona") or "—"),
         _p("<b>Última actualización</b>"), _p(fmt_fechahora(control.get("actualizado")))],
    ]
    tb = Table(datos, colWidths=[ancho * x for x in (0.12, 0.17, 0.14, 0.2, 0.15, 0.22)])
    tb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, BORDE), ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDE),
                            ("BACKGROUND", (0, 0), (0, -1), GRIS_F), ("BACKGROUND", (2, 0), (2, -1), GRIS_F),
                            ("BACKGROUND", (4, 0), (4, -1), GRIS_F), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    h.append(tb)
    h.append(Spacer(1, 4 * mm))

    # ---- indicadores
    kpis = [("Stock inicial", fmt_l(t["ini"]), f"{t['ini_tarros']} tarros + {fmt_l(t['ini_camion'])} camión", NAVY2),
            ("Consumo semana", fmt_l(t["consumo"]), f"{t['rellenos']} tarros rellenados al camión",
             colors.HexColor("#1F6FB2")),
            ("Sobrante calculado", fmt_l(t["calc"]), f"{t['calc_tarros']} tarros + {fmt_l(t['calc_camion'])} camión",
             colors.HexColor("#C98A12"))]
    if cerrado:
        kpis += [("Stock entregado", fmt_l(t["ent"]), f"{t['ent_tarros']} tarros + {fmt_l(t['ent_camion'])} camión",
                  colors.HexColor("#2E9E5B")),
                 ("Diferencia neta", fmt_signo(t["dif"]) + " L",
                  f"{res['inconsistencias']} aceite(s) con inconsistencia",
                  colors.HexColor("#D64545") if abs(t["dif"]) > 0.004 else colors.HexColor("#2E9E5B"))]
    celdas = []
    for tit, val, det, col in kpis:
        celdas.append([Paragraph(f"<font size=7.5 color='#6B7785'><b>{tit.upper()}</b></font>", _E["peq"]),
                       Paragraph(f"<font size=14 color='{col.hexval().replace('0x', '#')}'><b>{val}</b></font>",
                                 ParagraphStyle("k", leading=17)),
                       Paragraph(f"<font size=7 color='#6B7785'>{det}</font>", _E["peq"])])
    kt = Table([celdas], colWidths=[ancho / len(kpis)] * len(kpis))
    est = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]
    for i, (_, _, _, col) in enumerate(kpis):
        est += [("BOX", (i, 0), (i, 0), 0.6, BORDE), ("LINEABOVE", (i, 0), (i, 0), 3, col)]
    kt.setStyle(TableStyle(est))
    h.append(kt)

    # ---- conclusión
    h.append(Spacer(1, 4 * mm))
    concl = Table([[Paragraph(_t(conclusion(res)), _E["concl"])]], colWidths=[ancho])
    color_c = (colors.HexColor("#D64545") if res["con_diferencia_litros"] else colors.HexColor("#1F6FB2")) \
        if hay_inc else colors.HexColor("#2E9E5B")
    concl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GRIS_F), ("LINEBEFORE", (0, 0), (0, 0), 4, color_c),
                               ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    h.append(concl)

    # ---- tabla por aceite
    h.append(Paragraph("Detalle por aceite (litros)", _E["sec"]))
    g = ["Aceite", "Stock inicial", "", "", "Semana", "", "Sobrante calculado", "", "",
         "Stock entregado", "", "", "Diferencia (real - calculado)", "", "", "Estado"]
    sub_c = ["", "Tarros", "Camión", "Total", "Consumo", "Rellenos", "Tarros", "Camión", "Total",
             "Tarros", "Camión", "Total", "Tarros", "Camión", "Total", ""]
    filas = [[_p(x, "cab") for x in g], [_p(x, "cab") for x in sub_c]]
    estilos = []
    for i, f in enumerate(res["filas"]):
        c, e = f["calc"], f["entrega"]
        r = len(filas)
        fila = [_p(f"<b>{f['nombre']}</b>" + ("" if f["parte"] in f["nombre"] else
                                                  f"<br/><font color='#6B7785'>{f['parte']}</font>")),
                c["tarros_ini"], fmt_num(c["camion_ini"]), fmt_num(c["total_ini"]),
                fmt_num(c["consumo"]), c["rellenos"] + c["rellenos_implicitos"],
                c["tarros"], fmt_num(c["camion"]), fmt_num(c["total"])]
        if e:
            fila += [e["tarros"], fmt_num(e["camion"]), fmt_num(e["total"]),
                     fmt_signo(e["dif_tarros"], 0), fmt_signo(e["dif_camion"]), fmt_signo(e["dif_total"]),
                     _p(f"<b>{e['estado']}</b>")]
            estilos += [("BACKGROUND", (15, r), (15, r), FONDO_ESTADO[e["estado"]]),
                        ("TEXTCOLOR", (12, r), (14, r), COL_ESTADO[e["estado"]] if e["inconsistente"]
                         else colors.black)]
        else:
            fila += ["—"] * 6 + [_p("Pendiente")]
        if i % 2:
            estilos.append(("BACKGROUND", (0, r), (14, r), colors.HexColor("#F7F9FB")))
        filas.append(fila)
    tr = [_p("<b>TOTAL</b>"), t["ini_tarros"], fmt_num(t["ini_camion"]), fmt_num(t["ini"]), fmt_num(t["consumo"]),
          t["rellenos"], t["calc_tarros"], fmt_num(t["calc_camion"]), fmt_num(t["calc"])]
    if cerrado:
        tr += [t["ent_tarros"], fmt_num(t["ent_camion"]), fmt_num(t["ent"]),
               fmt_signo(t["ent_tarros"] - t["calc_tarros"], 0), fmt_signo(t["ent_camion"] - t["calc_camion"]),
               fmt_signo(t["dif"]), ""]
    else:
        tr += [""] * 7
    filas.append(tr)
    anchos_rel = [0.155] + [0.05, 0.06, 0.06, 0.068, 0.06, 0.05, 0.06, 0.06, 0.05, 0.06, 0.06, 0.05, 0.058, 0.058, 0.075]
    s = sum(anchos_rel)
    tabla = Table(filas, colWidths=[ancho * x / s for x in anchos_rel], repeatRows=2)
    base = [("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
            ("BACKGROUND", (0, 0), (-1, 1), NAVY2),
            ("SPAN", (1, 0), (3, 0)), ("SPAN", (4, 0), (5, 0)), ("SPAN", (6, 0), (8, 0)), ("SPAN", (9, 0), (11, 0)),
            ("SPAN", (12, 0), (14, 0)), ("SPAN", (0, 0), (0, 1)), ("SPAN", (15, 0), (15, 1)),
            ("ALIGN", (1, 2), (-1, -1), "RIGHT"), ("ALIGN", (15, 2), (15, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDE), ("BOX", (0, 0), (-1, -1), 0.6, BORDE),
            ("LINEAFTER", (0, 0), (0, -1), 0.8, colors.white), ("LINEAFTER", (3, 0), (3, -1), 0.9, NAVY2),
            ("LINEAFTER", (5, 0), (5, -1), 0.9, NAVY2), ("LINEAFTER", (8, 0), (8, -1), 0.9, NAVY2),
            ("LINEAFTER", (11, 0), (11, -1), 0.9, NAVY2), ("LINEAFTER", (14, 0), (14, -1), 0.9, NAVY2),
            ("BACKGROUND", (6, 2), (8, -2), colors.HexColor("#FBF4E4")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8EDF3")),
            ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 7.5),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    tabla.setStyle(TableStyle(base + estilos))
    h.append(tabla)

    # ---- cuadratura de rellenos
    h.append(Paragraph("Cuadratura de rellenos (tarros al camión)", _E["sec"]))
    lr = t["rellenos"] * lt
    h.append(Paragraph(
        f"Tarros rellenados al camión: <b>{t['rellenos']}</b>: salen <b>{fmt_l(lr, 0)}</b> de los tarros y entran "
        f"<b>{fmt_l(lr, 0)}</b> al camión (balance 0 L). Stock inicial {fmt_l(t['ini'])} - consumo "
        f"{fmt_l(t['consumo'])} = sobrante calculado <b>{fmt_l(t['calc'])}</b>. "
        + ("Cuadratura verificada en todos los aceites." if res["cuadratura_ok"] else
           "<font color='#D64545'><b>Hay aceites que no cuadran: revise los avisos.</b></font>"), _E["normal"]))

    # ---- hallazgos
    lineas = []
    for f in res["filas"]:
        items = [(n, m) for n, m in f["calc"]["avisos"]]
        if f["entrega"]:
            items += f["entrega"]["hallazgos"]
        if not items:
            continue
        estado = f["entrega"]["estado"] if f["entrega"] else ""
        col = COL_ESTADO.get(estado, NAVY).hexval().replace("0x", "#")
        txt = "<br/>".join(f"<font color='{COL_NIVEL.get(n, '#1F2A37')}'>•</font> {m}" for n, m in items)
        nom = f["nombre"] if f["parte"] in f["nombre"] else f"{f['nombre']}<br/><font color='#6B7785'>{f['parte']}</font>"
        lineas.append([_p(f"<b>{nom}</b>"),
                       _p(f"<font color='{col}'><b>{estado}</b></font>"), _p(txt)])
    h.append(Paragraph("Hallazgos e inconsistencias", _E["sec"]))
    if lineas:
        th = Table(lineas, colWidths=[ancho * 0.2, ancho * 0.12, ancho * 0.68])
        th.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDE),
                                ("BOX", (0, 0), (-1, -1), 0.6, BORDE), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        h.append(th)
    else:
        h.append(Paragraph("Sin hallazgos." if cerrado else "Pendiente el stock entregado.", _E["normal"]))
    h.append(Spacer(1, 2 * mm))
    h.append(Paragraph(
        "<font color='#6B7785'>Criterio: se informa cualquier diferencia en litros. Si faltan tarros y su volumen "
        "aparece en el camión lubricador, se considera traspaso al camión (tarros vaciados o cargados en el camión) "
        "y no pérdida. «Cuadra en litros» = el total coincide y solo cambió la ubicación del aceite.</font>",
        _E["peq"]))

    # ---- observaciones
    obs = [(n, x) for n, x in (("Stock inicial", ini.get("obs")), ("Consumos", con.get("obs")),
                                ("Stock entregado", ent.get("obs"))) if x]
    if obs:
        h.append(Paragraph("Observaciones", _E["sec"]))
        for n, x in obs:
            h.append(Paragraph(f"<b>{n}:</b> {x}", _E["normal"]))

    # ---- firmas
    firmas = [("Jefe de operaciones", ini.get("persona") or "", ini.get("turno", "")),
              ("Responsable entrega", ent.get("persona") or "", ent.get("turno", "")),
              ("Revisado por", "", "Supervisor / Jefe de mantenimiento")]
    e_firma = ParagraphStyle("f", parent=_E["peq"], alignment=1, fontSize=8, leading=10)
    celdas = [[Paragraph("<br/><br/><br/>______________________________"
                         f"<br/><b>{a}</b><br/>{b}<br/><font color='#6B7785'>{c}</font>", e_firma)
               for a, b, c in firmas]]
    tf = Table(celdas, colWidths=[ancho / 3] * 3)
    tf.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    h.append(Spacer(1, 6 * mm))
    h.append(KeepTogether([tf]))

    enc = _encabezado(titulo, sub)
    doc.build(h, onFirstPage=enc, onLaterPages=enc)
    return ruta
