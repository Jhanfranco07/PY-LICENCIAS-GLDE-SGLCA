# integraciones/codart.py

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests
import streamlit as st

BASE_URL = "https://api.codart.cgrt.net/api/v1/consultas"


class CodartAPIError(Exception):
    """Errores al consumir CODART (token, límites, caídas, WAF, etc.)."""


def _get_token() -> str:
    """
    Streamlit Cloud: usa st.secrets["CODART_TOKEN"].
    Fallback: variable de entorno CODART_TOKEN.
    """
    token = None
    try:
        token = st.secrets.get("CODART_TOKEN")
    except Exception:
        token = None

    if not token:
        token = os.getenv("CODART_TOKEN")

    if not token:
        raise CodartAPIError(
            "Falta CODART_TOKEN. Configúralo en Streamlit Cloud: Settings → Secrets."
        )
    return str(token).strip()


@st.cache_resource
def _get_session(token: str) -> requests.Session:
    """
    Session cacheada (mejor performance) + headers anti-406/WAF.
    Queda cacheada por token: si cambias el secret, se crea otra sesión.
    """
    s = requests.Session()
    s.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            # clave para evitar bloqueos típicos en Cloud/WAF:
            "User-Agent": "Mozilla/5.0 (Streamlit; CODART client)",
        }
    )
    return s

def _get_json(url: str, params: Optional[dict] = None) -> Dict[str, Any]:
    token = _get_token()

    session = requests.Session()

    headers = {
        "Authorization": f"Bearer {token}",
        # ModSecurity suele bloquear requests “sin cara de navegador”
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "*/*",  # evita 406 por negociación de contenido
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Content-Type": "application/json",  # tu API lo exige (415)
    }

    def parse(resp: requests.Response) -> Dict[str, Any]:
        try:
            data = resp.json()
        except Exception:
            raise CodartAPIError(f"HTTP {resp.status_code}: {(resp.text or '')[:300]}")

        if not isinstance(data, dict):
            raise CodartAPIError("Respuesta inesperada (no es dict).")

        if data.get("success") is not True:
            msg = data.get("message") or data.get("error") or "success=false"
            raise CodartAPIError(f"CODART respondió error: {msg}")

        return data

    # Intento 1: GET
    resp = session.get(url, headers=headers, params=params, timeout=25)

    # Si WAF bloquea (406) o Content-Type (415), probamos variantes
    if resp.status_code in (406, 415, 403):
        # Intento 2: POST con JSON (muchas APIs terminan aceptando esto mejor)
        resp2 = session.post(url, headers=headers, json=(params or {}), timeout=25)
        if resp2.status_code < 400:
            return parse(resp2)

        # Intento 3: GET sin params (si params causan regla WAF), y params en URL “manual”
        # (opcional, útil si el WAF odia ciertos patrones)
        resp3 = session.get(url, headers=headers, timeout=25)
        if resp3.status_code < 400:
            return parse(resp3)

        # Si nada funcionó, muestra ambos para debug
        raise CodartAPIError(
            f"Bloqueado por servidor/WAF. GET={resp.status_code} POST={resp2.status_code}. "
            f"GET body: {(resp.text or '')[:200]}"
        )

    if resp.status_code >= 400:
        raise CodartAPIError(f"HTTP {resp.status_code}: {(resp.text or '')[:300]}")

    return parse(resp)




def validar_dni(dni: str) -> str:
    dni = (dni or "").strip()
    if not (dni.isdigit() and len(dni) == 8):
        raise ValueError("DNI inválido. Debe tener 8 dígitos.")
    return dni


def validar_ruc(ruc: str) -> str:
    ruc = (ruc or "").strip()
    if not (ruc.isdigit() and len(ruc) == 11):
        raise ValueError("RUC inválido. Debe tener 11 dígitos.")
    return ruc


@st.cache_data(ttl=60 * 60 * 24)  # 24h
def consultar_dni(dni: str) -> Dict[str, Any]:
    """
    RENIEC DNI.
    Soporta /reniec/dni/{dni} y /reniec/dni/dni?dni=...
    """
    dni_ok = validar_dni(dni)

    url_a = f"{BASE_URL}/reniec/dni/{dni_ok}"
    url_b = f"{BASE_URL}/reniec/dni/dni"
    params_b = {"dni": dni_ok}

    try:
        data = _get_json(url_a)
        return data.get("result", {}) or {}
    except CodartAPIError as e:
        msg = str(e)
        if "HTTP 404" in msg or "HTTP 406" in msg:
            data = _get_json(url_b, params=params_b)
            return data.get("result", {}) or {}
        raise


@st.cache_data(ttl=60 * 60 * 24)  # 24h
def consultar_ruc(ruc: str) -> Dict[str, Any]:
    """
    SUNAT RUC.
    Soporta /sunat/ruc/{ruc} y /sunat/ruc/ruc?ruc=...
    """
    ruc_ok = validar_ruc(ruc)

    url_a = f"{BASE_URL}/sunat/ruc/{ruc_ok}"
    url_b = f"{BASE_URL}/sunat/ruc/ruc"
    params_b = {"ruc": ruc_ok}

    try:
        data = _get_json(url_a)
        return data.get("result", {}) or {}
    except CodartAPIError as e:
        msg = str(e)
        if "HTTP 404" in msg or "HTTP 406" in msg:
            data = _get_json(url_b, params=params_b)
            return data.get("result", {}) or {}
        raise


def dni_a_nombre_completo(res: Dict[str, Any]) -> str:
    """
    Arma nombre completo con el orden:
      NOMBRES APELLIDO_PATERNO APELLIDO_MATERNO
    """
    nombres = (res.get("first_name") or "").strip()
    ape1 = (res.get("first_last_name") or "").strip()
    ape2 = (res.get("second_last_name") or "").strip()

    # Si viene todo vacío, intenta fallback con full_name (por si cambia la API)
    if not (nombres or ape1 or ape2):
        full = (res.get("full_name") or "").strip()
        return full

    return " ".join([p for p in [nombres, ape1, ape2] if p]).upper().strip()

