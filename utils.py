import os, re
import pandas as pd
from datetime import datetime
from unidecode import unidecode

def asegurar_dirs():
    os.makedirs("salidas", exist_ok=True)
    os.makedirs("plantillas", exist_ok=True)

def slugify(texto: str) -> str:
    t = unidecode(str(texto)).lower().strip()
    t = re.sub(r"[^a-z0-9\-_. ]+", "", t)
    t = re.sub(r"\s+", "_", t)
    return t[:100] or "documento"

def safe_filename_pretty(texto: str) -> str:
    prohibidos = '<>:"/\\|?*'
    limpio = ''.join('_' if c in prohibidos else c for c in str(texto))
    return limpio.replace('\n', ' ').replace('\r', ' ').strip()

def fmt_fecha_corta(d) -> str:
    """15/09/2025"""
    try:
        return pd.to_datetime(d).strftime("%d/%m/%Y")
    except Exception:
        return ""

def fmt_fecha_larga(d) -> str:
    """16 de setiembre del 2025 (con 'del')"""
    meses = [
        "enero","febrero","marzo","abril","mayo","junio",
        "julio","agosto","setiembre","octubre","noviembre","diciembre"
    ]
    try:
        dt = pd.to_datetime(d)
        return f"{dt.day} de {meses[dt.month-1]} del {dt.year}"
    except Exception:
        return ""

def fmt_fecha_larga_de(d) -> str:
    """16 de setiembre de 2025 (con 'de')"""
    return fmt_fecha_larga(d).replace(" del ", " de ")

# 👇 Alias pensado para usar en anuncios (más semántico)
def fecha_larga(d) -> str:
    """Alias de fmt_fecha_larga, para usar como fecha_larga(fecha)."""
    return fmt_fecha_larga(d)

def build_vigencia(fecha_inicio, fecha_fin) -> str:
    """
    Devuelve: '24 de setiembre de 2025 hasta el 24 de octubre de 2025'
    sin 'desde el', usando 'de' (no 'del').
    """
    ini = fmt_fecha_larga_de(fecha_inicio)
    fin = fmt_fecha_larga_de(fecha_fin)
    if not ini or not fin:
        return ""
    return f"{ini} hasta el {fin}"

def build_vigencia2(fecha_inicio, fecha_fin) -> str:
    """
    Devuelve: '24/09/2025 - 24/10/2025'
    Útil para certificados o formatos más compactos.
    """
    i = fmt_fecha_corta(fecha_inicio)
    f = fmt_fecha_corta(fecha_fin)
    if not i or not f:
        return ""
    return f"{i} - {f}"

def to_upper(s: str) -> str:
    return (s or "").strip().upper()
