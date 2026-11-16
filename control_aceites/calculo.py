"""Cálculo del sobrante y análisis de inconsistencias. Todo se cuadra en litros.

Modelo por aceite:
    stock inicial  = tarros_ini × L_tarro + camión_ini
    rellenos       = tarros vaciados al camión: −R × L_tarro en tarros y +R × L_tarro en el camión (suma cero)
    consumo        = litros despachados por el camión durante la semana
    sobrante calc. = tarros (tarros_ini − R) + camión (camión_ini + R × L_tarro − consumo)

Si el consumo supera lo que hay en el camión, la diferencia se cubre con tarros completos (relleno no
registrado) y se avisa. Al recibir el stock entregado por el turno se compara contra el sobrante calculado:
los tarros que faltan y aparecen como litros en el camión se identifican como traspaso al camión (no es pérdida).
"""
from __future__ import annotations

import math

from .util import fmt_l, fmt_num

LITROS_TARRO = 208.0
EPS = 0.005          # «cualquier diferencia»: solo se ignoran errores de redondeo menores a 0,005 L
TURNOS = ("Turno A", "Turno B")

CUADRADO = "Cuadrado"
TRASPASO = "Cuadra en litros"
FALTANTE = "Faltante"
SOBRANTE = "Sobrante"


def _r(v: float) -> float:
    v = round(float(v), 3)
    return 0.0 if abs(v) < EPS else v


def etiqueta(nombre: str, parte: str) -> str:
    """«Aceite motor (LL-0001)»; si el nombre ya contiene el N° de parte, no lo repite."""
    return nombre if parte in nombre else f"{nombre} ({parte})"


def _tarros(n: int) -> str:
    return f"{n} tarro" if abs(n) == 1 else f"{n} tarros"


# --------------------------------------------------------------------- sobrante
def calcular_sobrante(tarros_ini, camion_ini, consumo, rellenos, lt: float = LITROS_TARRO) -> dict:
    tarros_ini, rellenos = int(tarros_ini or 0), int(rellenos or 0)
    camion_ini, consumo = float(camion_ini or 0), float(consumo or 0)
    avisos: list[tuple[str, str]] = []
    total_ini = tarros_ini * lt + camion_ini

    rel = rellenos
    if rellenos > tarros_ini:
        rel = tarros_ini
        avisos.append(("error", f"Se registraron {_tarros(rellenos)} rellenados al camión, pero solo había "
                                f"{_tarros(tarros_ini)}. Se consideran {rel}."))
    tarros = tarros_ini - rel
    camion = camion_ini + rel * lt - consumo

    implicitos = 0
    if camion < -EPS and tarros > 0:
        implicitos = min(tarros, math.ceil((-camion - EPS) / lt))
        tarros -= implicitos
        camion += implicitos * lt
        avisos.append(("aviso", f"El consumo superó el aceite disponible en el camión: se descontaron "
                                f"{_tarros(implicitos)} ({fmt_l(implicitos * lt, 0)}) como relleno no registrado."))
    if camion < -EPS:
        avisos.append(("error", f"El consumo supera el stock total: faltan {fmt_l(-camion)} para cubrir "
                                f"el consumo registrado."))

    total = tarros * lt + camion
    mov_tarros = -(rel + implicitos) * lt          # litros que salen de los tarros
    mov_camion_rellenos = (rel + implicitos) * lt  # litros que entran al camión
    cuadra_rellenos = abs(mov_tarros + mov_camion_rellenos) < EPS
    cuadra_total = abs(total_ini - consumo - total) < EPS
    return dict(tarros_ini=tarros_ini, camion_ini=_r(camion_ini), total_ini=_r(total_ini), consumo=_r(consumo),
                rellenos=rel, rellenos_implicitos=implicitos, tarros=tarros, camion=_r(camion), total=_r(total),
                equiv_tarros=total / lt if lt else 0.0, litros_rellenos=_r(mov_camion_rellenos),
                cuadra=cuadra_rellenos and cuadra_total, avisos=avisos)


# ----------------------------------------------------------- stock entregado
def analizar_entrega(calc: dict, tarros_real, camion_real, lt: float = LITROS_TARRO) -> dict:
    """Compara el stock entregado por el turno contra el sobrante calculado."""
    tarros_real, camion_real = int(tarros_real or 0), float(camion_real or 0)
    total_real = tarros_real * lt + camion_real
    d_tarros = tarros_real - calc["tarros"]
    d_camion = camion_real - calc["camion"]
    d_total = d_tarros * lt + d_camion

    def _mejor(n_max: int, litros: float) -> int:
        """N° de tarros (0..n_max) cuyo volumen explica mejor «litros». Empate: el mayor."""
        mejor, err = 0, abs(litros)
        for t in range(1, n_max + 1):
            e = abs(litros - t * lt)
            if e <= err + EPS:
                mejor, err = t, e
        return mejor

    traspaso = _mejor(-d_tarros, d_camion) if d_tarros < 0 and d_camion > EPS else 0
    inverso = _mejor(d_tarros, -d_camion) if d_tarros > 0 and d_camion < -EPS else 0
    tarros_sin = d_tarros + traspaso - inverso
    camion_sin = d_camion - traspaso * lt + inverso * lt

    hallazgos: list[tuple[str, str]] = []
    if traspaso:
        hallazgos.append(("info", f"{_tarros(traspaso)} ({fmt_l(traspaso * lt, 0)}) pasaron al camión lubricador "
                                  f"sin registrarse como relleno (vaciados o cargados en el camión). "
                                  f"Este movimiento no es pérdida: cuadra en litros."))
    if inverso:
        hallazgos.append(("aviso", f"Hay {_tarros(inverso)} más y {fmt_l(inverso * lt, 0)} menos en el camión: "
                                   f"posible relleno registrado que no se realizó, o error de conteo."))
    if tarros_sin < 0:
        n = -tarros_sin
        hallazgos.append(("error", f"Faltan {_tarros(n)} ({fmt_l(n * lt, 0)}) que no aparecen en el camión."))
    elif tarros_sin > 0:
        hallazgos.append(("aviso", f"Hay {_tarros(tarros_sin)} más que lo calculado ({fmt_l(tarros_sin * lt, 0)})."))
    if camion_sin < -EPS:
        hallazgos.append(("error", f"El camión tiene {fmt_l(-camion_sin)} menos que lo calculado."))
    elif camion_sin > EPS:
        hallazgos.append(("aviso", f"El camión tiene {fmt_l(camion_sin)} más que lo calculado."))

    if d_tarros == 0 and abs(d_camion) < EPS:
        estado = CUADRADO
    elif abs(d_total) < EPS:
        estado = TRASPASO
    elif d_total < 0:
        estado = FALTANTE
    else:
        estado = SOBRANTE

    if estado == FALTANTE:
        hallazgos.append(("error", f"Resultado: faltante neto de {fmt_l(-d_total)} "
                                   f"(≈ {fmt_num(-d_total / lt, 2)} tarros)."))
    elif estado == SOBRANTE:
        hallazgos.append(("aviso", f"Resultado: sobrante neto de {fmt_l(d_total)} "
                                   f"(≈ {fmt_num(d_total / lt, 2)} tarros); revise consumos no registrados de menos."))
    elif estado == TRASPASO:
        hallazgos.append(("info", "Resultado: el total en litros cuadra; la diferencia está solo en la "
                                  "ubicación del aceite (tarros / camión)."))

    return dict(tarros=tarros_real, camion=_r(camion_real), total=_r(total_real), dif_tarros=d_tarros,
                dif_camion=_r(d_camion), dif_total=_r(d_total), traspaso=traspaso, inverso=inverso,
                tarros_sin_explicar=tarros_sin, camion_sin_explicar=_r(camion_sin), estado=estado,
                inconsistente=estado != CUADRADO, hallazgos=hallazgos)


# ------------------------------------------------------------------ control
def etapa(control: dict | None) -> int:
    """0 = sin control, 1 = stock inicial, 2 = consumos, 3 = stock entregado (cerrado)."""
    if not control or not control.get("inicial"):
        return 0
    if not control.get("consumos"):
        return 1
    if not control.get("entrega"):
        return 2
    return 3


def resultado(control: dict) -> dict:
    """Calcula todas las filas (una por aceite) y los totales de un control."""
    lt = float(control.get("litros_tarro") or LITROS_TARRO)
    ini = (control.get("inicial") or {}).get("items", {})
    con = (control.get("consumos") or {}).get("items", {}) if control.get("consumos") else None
    ent = (control.get("entrega") or {}).get("items", {}) if control.get("entrega") else None
    filas = []
    for ac in control.get("aceites", []):
        p = ac["parte"]
        i = ini.get(p, {})
        c = (con or {}).get(p, {})
        calc = calcular_sobrante(i.get("tarros", 0), i.get("camion", 0), c.get("consumo", 0),
                                 c.get("rellenos", 0), lt)
        an = None
        if ent is not None:
            e = ent.get(p, {})
            an = analizar_entrega(calc, e.get("tarros", 0), e.get("camion", 0), lt)
        filas.append(dict(parte=p, nombre=ac.get("nombre", p), calc=calc, entrega=an, con_consumo=con is not None))

    def s(fn):
        return _r(sum(fn(f) for f in filas))

    tot = dict(
        ini=s(lambda f: f["calc"]["total_ini"]),
        ini_tarros=sum(f["calc"]["tarros_ini"] for f in filas),
        ini_camion=s(lambda f: f["calc"]["camion_ini"]),
        consumo=s(lambda f: f["calc"]["consumo"]),
        rellenos=sum(f["calc"]["rellenos"] + f["calc"]["rellenos_implicitos"] for f in filas),
        calc=s(lambda f: f["calc"]["total"]),
        calc_tarros=sum(f["calc"]["tarros"] for f in filas),
        calc_camion=s(lambda f: f["calc"]["camion"]),
    )
    if ent is not None:
        tot.update(ent=s(lambda f: f["entrega"]["total"]),
                   ent_tarros=sum(f["entrega"]["tarros"] for f in filas),
                   ent_camion=s(lambda f: f["entrega"]["camion"]),
                   dif=s(lambda f: f["entrega"]["dif_total"]),
                   faltante=s(lambda f: min(0.0, f["entrega"]["dif_total"])),
                   sobrante=s(lambda f: max(0.0, f["entrega"]["dif_total"])),
                   traspasos=sum(f["entrega"]["traspaso"] for f in filas))
    n_inc = sum(1 for f in filas if f["entrega"] and f["entrega"]["inconsistente"])
    n_perd = sum(1 for f in filas if f["entrega"] and f["entrega"]["estado"] in (FALTANTE, SOBRANTE))
    avisos = [(f["parte"], nivel, txt) for f in filas for nivel, txt in f["calc"]["avisos"]]
    return dict(filas=filas, totales=tot, litros_tarro=lt, inconsistencias=n_inc, con_diferencia_litros=n_perd,
                avisos=avisos, etapa=etapa(control),
                cuadratura_ok=all(f["calc"]["cuadra"] for f in filas))


def conclusion(res: dict) -> str:
    """Texto de conclusión para la pantalla y el reporte."""
    if res["etapa"] < 3:
        return "Control abierto: falta ingresar el stock entregado al finalizar el turno."
    t = res["totales"]
    n = res["inconsistencias"]
    if n == 0:
        return "Sin inconsistencias: el stock entregado coincide con el sobrante calculado en todos los aceites."
    partes = [f"Se encontraron inconsistencias en {n} aceite{'s' if n != 1 else ''}."]
    if t.get("traspasos"):
        partes.append(f"{_tarros(t['traspasos'])} ({fmt_l(t['traspasos'] * res['litros_tarro'], 0)}) pasaron al "
                      f"camión sin registrarse; ese movimiento cuadra en litros.")
    if t.get("faltante", 0) < -EPS:
        partes.append(f"Faltante total: {fmt_l(-t['faltante'])}.")
    if t.get("sobrante", 0) > EPS:
        partes.append(f"Sobrante total: {fmt_l(t['sobrante'])}.")
    if res["con_diferencia_litros"] == 0:
        partes.append("No hay diferencias en litros: solo cambió la ubicación del aceite.")
    return " ".join(partes)
