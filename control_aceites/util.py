"""Formato y lectura de números y fechas (formato chileno: 1.234,5 y dd-mm-aaaa)."""
from __future__ import annotations

import datetime as dt
import re


def parse_num(txt) -> float | None:
    """Lee «1.234,5», «1234,5», «1234.5» o «10». Vacío = 0. Devuelve None si no es un número."""
    if txt is None:
        return 0.0
    if isinstance(txt, (int, float)):
        return float(txt)
    s = str(txt).strip().replace(" ", "").replace("L", "").replace("l", "")
    if s == "":
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"-?[1-9]\d{0,2}(\.\d{3})+", s):
        s = s.replace(".", "")          # 1.234 o 12.345.678 = miles
    try:
        return float(s)
    except ValueError:
        return None


def parse_entero(txt) -> int | None:
    v = parse_num(txt)
    if v is None or abs(v - round(v)) > 1e-9:
        return None
    return int(round(v))


def fmt_num(v, dec: int = 1) -> str:
    """1234.5 -> «1.234,5»; 1234.0 -> «1.234»."""
    if v is None:
        return ""
    v = round(float(v), dec)
    if abs(v) < 10 ** -(dec + 1):
        v = 0.0
    if dec == 0 or abs(v - round(v)) < 1e-9:
        s = f"{round(v):,.0f}"
    else:
        s = f"{v:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_l(v, dec: int = 1) -> str:
    return f"{fmt_num(v, dec)} L"


def fmt_signo(v, dec: int = 1) -> str:
    s = fmt_num(v, dec)
    return s if s.startswith("-") or s == "0" else f"+{s}"


def parse_fecha(txt) -> dt.date | None:
    if isinstance(txt, dt.datetime):
        return txt.date()
    if isinstance(txt, dt.date):
        return txt
    s = str(txt or "").strip()
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        pass
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})", s)
    if not m:
        return None
    d, mes, a = (int(x) for x in m.groups())
    if a < 100:
        a += 2000
    try:
        return dt.date(a, mes, d)
    except ValueError:
        return None


def fmt_fecha(d) -> str:
    d = parse_fecha(d)
    return f"{d:%d-%m-%Y}" if d else ""


def ahora_iso() -> str:
    return dt.datetime.now().isoformat(sep=" ", timespec="seconds")


def fmt_fechahora(s) -> str:
    try:
        return f"{dt.datetime.fromisoformat(str(s)):%d-%m-%Y %H:%M}"
    except ValueError:
        return str(s or "")
