# comercio/sheets_comercio.py
"""
Manejo de Google Sheets para Comercio Ambulatorio:

- Un solo Google Sheets (SPREADSHEET_ID_COMERCIO).
- Tres hojas:
    • Evaluaciones_CA
    • Autorizaciones_CA
    • Documentos_CA  (registro de Documentos Simples)
"""

from __future__ import annotations

from typing import List, Dict

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# CONFIG BÁSICA
# ---------------------------------------------------------------------------

# 👉 ID del Google Sheets de COMERCIO AMBULATORIO
SPREADSHEET_ID_COMERCIO = "1Sd9f0PTfGvFsOPQhA32hUp2idcdkX_LVYQ-bAX2nYU8"

EVAL_SHEET_NAME = "Evaluaciones_CA"
AUTO_SHEET_NAME = "Autorizaciones_CA"
DOCS_SHEET_NAME = "Documentos_CA"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ---------------------------------------------------------------------------
# COLUMNAS
# ---------------------------------------------------------------------------

COLUMNAS_EVALUACION: List[str] = [
    "N°",
    "NUMERO DE DOCUMENTO SIMPLE",
    "NOMBRES Y APELLIDOS",
    "N° DE EVALUACIÓN",
    "FECHA",
    "N° DE RESOLUCIÓN",
    "FECHA DE RESOLUCIÓN",
    "N° DE AUTORIZACIÓN",
    "FECHA DE AUTORIZACION",
]

COLUMNAS_AUTORIZACION: List[str] = [
    "FECHA DE INGRESO",
    "D.S",
    "NOMBRE Y APELLIDO",
    "DNI",
    "GENERO",
    "DOMICILIO FISCAL",
    "CERTIFICADO ANTERIOR",
    "FECHA EMITIDA CERTIFICADO ANTERIOR",
    "FECHA DE CADUCIDAD CERTIFICADO ANTERIOR",
    "N° DE EVALUACION",
    "FECHA DE EVALUACION",
    "N° DE RESOLUCIÓN",
    "FECHA RESOLUCIÓN",
    "N° DE CERTIFICADO",
    "FECHA EMITIDA CERTIFICADO",
    "VIGENCIA DE AUTORIZACIÓN",
    "LUGAR DE VENTA",
    "COORDENADAS",
    "REFERENCIA",
    "GIRO",
    "HORARIO",
    "N° TELEFONO",
    "TIEMPO",
    "PLAZO",
]

COLUMNAS_DOCUMENTOS: List[str] = [
    "ESTADO",
    "N°",
    "FECHA DE INGRESO",
    "N° DE DOCUMENTO SIMPLE",
    "ASUNTO",
    "NOMBRE Y APELLIDO",
    "DNI",
    "DOMICILIO FISCAL",
    "GIRO O MOTIVO DE LA SOLICITUD",
    "UBICACIÓN A SOLICITAR",
    "N° DE CELULAR",
    "PROCEDENTE / IMPROCEDENTE",
    "N° DE CARTA",
    "FECHA DE LA CARTA",
    "FECHA DE NOTIFICACION",
    "FOLIOS",
]

# ---------------------------------------------------------------------------
# CLIENTE GSPREAD
# ---------------------------------------------------------------------------


@st.cache_resource
def _get_client() -> gspread.Client:
    """
    Crea el cliente de Google Sheets usando st.secrets["gcp_service_account"].
    """
    creds_info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client


def _get_spreadsheet():
    client = _get_client()
    return client.open_by_key(SPREADSHEET_ID_COMERCIO)


def _get_worksheet(sheet_name: str, columnas: List[str]) -> gspread.Worksheet:
    """
    Devuelve la worksheet indicada. Si no existe, la crea.
    Si está vacía, escribe la fila de encabezados.
    """
    sh = _get_spreadsheet()
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=len(columnas) + 2)

    values = ws.get_all_values()
    if not values:
        ws.update("A1", [columnas])

    return ws


# ---------------------------------------------------------------------------
# HELPERS GENÉRICOS
# ---------------------------------------------------------------------------


def _leer_df(sheet_name: str, columnas: List[str]) -> pd.DataFrame:
    ws = _get_worksheet(sheet_name, columnas)
    values = ws.get_all_values()

    if not values:
        return pd.DataFrame(columns=columnas)

    header = values[0]
    filas = values[1:]

    df = pd.DataFrame(filas, columns=header)

    # Asegura que existan todas las columnas esperadas
    for col in columnas:
        if col not in df.columns:
            df[col] = ""

    df = df[columnas]
    return df


def _escribir_df(sheet_name: str, columnas: List[str], df: pd.DataFrame) -> None:
    ws = _get_worksheet(sheet_name, columnas)

    df = df.copy()
    for col in columnas:
        if col not in df.columns:
            df[col] = ""
    df = df[columnas].fillna("")

    values = [df.columns.tolist()] + df.astype(str).values.tolist()

    ws.clear()
    ws.update("A1", values)


def _append_fila(
    sheet_name: str,
    columnas: List[str],
    fila: Dict[str, str],
    auto_numero_col: str | None = None,
) -> None:
    """
    Agrega una nueva fila:
    - 'fila' es un dict {columna: valor}
    - si auto_numero_col no es None, se rellena con correlativo (1,2,3,...)
    """
    df = _leer_df(sheet_name, columnas)

    nueva = {col: "" for col in columnas}
    for col, val in fila.items():
        if col in nueva:
            nueva[col] = val

    if auto_numero_col and auto_numero_col in nueva:
        nueva[auto_numero_col] = len(df) + 1

    df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
    _escribir_df(sheet_name, columnas, df)


# ---------------------------------------------------------------------------
# API – EVALUACIONES
# ---------------------------------------------------------------------------


def leer_evaluaciones() -> pd.DataFrame:
    return _leer_df(EVAL_SHEET_NAME, COLUMNAS_EVALUACION)


def escribir_evaluaciones(df: pd.DataFrame) -> None:
    _escribir_df(EVAL_SHEET_NAME, COLUMNAS_EVALUACION, df)


def append_evaluacion(
    *,
    num_ds: str,
    nombre_completo: str,
    cod_evaluacion: str,
    fecha_eval: str,
    cod_resolucion: str = "",
    fecha_resolucion: str = "",
    num_autorizacion: str = "",
    fecha_autorizacion: str = "",
) -> None:
    """
    Agrega una fila a Evaluaciones_CA.
    Todas las fechas deben venir ya como string (ej. '16/01/2026').
    """
    fila = {
        "NUMERO DE DOCUMENTO SIMPLE": num_ds,
        "NOMBRES Y APELLIDOS": nombre_completo,
        "N° DE EVALUACIÓN": cod_evaluacion,
        "FECHA": fecha_eval,
        "N° DE RESOLUCIÓN": cod_resolucion,
        "FECHA DE RESOLUCIÓN": fecha_resolucion,
        "N° DE AUTORIZACIÓN": num_autorizacion,
        "FECHA DE AUTORIZACION": fecha_autorizacion,
    }

    _append_fila(
        EVAL_SHEET_NAME,
        COLUMNAS_EVALUACION,
        fila,
        auto_numero_col="N°",
    )


def actualizar_evaluacion_con_resolucion(
    *,
    cod_evaluacion: str,
    cod_resolucion: str,
    fecha_resolucion: str,
    num_autorizacion: str,
    fecha_autorizacion: str,
) -> None:
    """
    Actualiza la fila de Evaluaciones_CA correspondiente al N° de Evaluación.
    """
    df = leer_evaluaciones()
    if df.empty:
        return

    mask = df["N° DE EVALUACIÓN"].astype(str) == str(cod_evaluacion)
    if not mask.any():
        return

    df.loc[mask, "N° DE RESOLUCIÓN"] = cod_resolucion
    df.loc[mask, "FECHA DE RESOLUCIÓN"] = fecha_resolucion
    df.loc[mask, "N° DE AUTORIZACIÓN"] = num_autorizacion
    df.loc[mask, "FECHA DE AUTORIZACION"] = fecha_autorizacion

    escribir_evaluaciones(df)


def evaluaciones_sin_resolucion() -> pd.DataFrame:
    """
    Devuelve evaluaciones que aún no tienen N° de Resolución.
    """
    df = leer_evaluaciones()
    if df.empty:
        return df

    mask = df["N° DE RESOLUCIÓN"].astype(str).str.strip() == ""
    return df[mask].copy()


# ---------------------------------------------------------------------------
# API – AUTORIZACIONES
# ---------------------------------------------------------------------------


def leer_autorizaciones() -> pd.DataFrame:
    return _leer_df(AUTO_SHEET_NAME, COLUMNAS_AUTORIZACION)


def escribir_autorizaciones(df: pd.DataFrame) -> None:
    _escribir_df(AUTO_SHEET_NAME, COLUMNAS_AUTORIZACION, df)


def append_autorizacion(
    *,
    fecha_ingreso: str,
    ds: str,
    nombre: str,
    dni: str,
    genero: str,
    domicilio_fiscal: str,
    certificado_anterior: str,
    fecha_emitida_cert_anterior: str,
    fecha_caducidad_cert_anterior: str,
    num_eval: str,
    fecha_eval: str,
    num_resolucion: str,
    fecha_resolucion: str,
    num_certificado: str,
    fecha_emitida_cert: str,
    vigencia_autorizacion: str,
    lugar_venta: str,
    referencia: str,
    giro: str,
    horario: str,
    coordenadas: str = "",
    telefono: str = "",
    tiempo: str = "",
    plazo: str = "",
) -> None:
    """
    Agrega una fila a Autorizaciones_CA.

    Todos los campos se mandan ya como string formateado
    (fechas tipo '16/01/2026', etc.).
    """
    fila = {
        "FECHA DE INGRESO": fecha_ingreso,
        "D.S": ds,
        "NOMBRE Y APELLIDO": nombre,
        "DNI": dni,
        "GENERO": genero,
        "DOMICILIO FISCAL": domicilio_fiscal,
        "CERTIFICADO ANTERIOR": certificado_anterior,
        "FECHA EMITIDA CERTIFICADO ANTERIOR": fecha_emitida_cert_anterior,
        "FECHA DE CADUCIDAD CERTIFICADO ANTERIOR": fecha_caducidad_cert_anterior,
        "N° DE EVALUACION": num_eval,
        "FECHA DE EVALUACION": fecha_eval,
        "N° DE RESOLUCIÓN": num_resolucion,
        "FECHA RESOLUCIÓN": fecha_resolucion,
        "N° DE CERTIFICADO": num_certificado,
        "FECHA EMITIDA CERTIFICADO": fecha_emitida_cert,
        "VIGENCIA DE AUTORIZACIÓN": vigencia_autorizacion,
        "LUGAR DE VENTA": lugar_venta,
        "COORDENADAS": coordenadas,
        "REFERENCIA": referencia,
        "GIRO": giro,
        "HORARIO": horario,
        "N° TELEFONO": telefono,
        "TIEMPO": tiempo,
        "PLAZO": plazo,
    }

    _append_fila(
        AUTO_SHEET_NAME,
        COLUMNAS_AUTORIZACION,
        fila,
        auto_numero_col=None,  # aquí no hay columna "N°"
    )


def actualizar_autorizacion_resolucion_y_cert(
    *,
    num_eval: str,
    certificado_anterior: str,
    fecha_emitida_cert_anterior: str,
    fecha_caducidad_cert_anterior: str,
    num_resolucion: str,
    fecha_resolucion: str,
    num_certificado: str,
    fecha_emitida_cert: str,
    vigencia_autorizacion: str,
) -> None:
    """
    Completa/actualiza en Autorizaciones_CA los datos de resolución y certificado
    para una evaluación ya registrada.
    """
    df = leer_autorizaciones()
    if df.empty:
        return

    mask = df["N° DE EVALUACION"].astype(str) == str(num_eval)
    if not mask.any():
        return

    df.loc[mask, "CERTIFICADO ANTERIOR"] = certificado_anterior
    df.loc[mask, "FECHA EMITIDA CERTIFICADO ANTERIOR"] = (
        fecha_emitida_cert_anterior
    )
    df.loc[mask, "FECHA DE CADUCIDAD CERTIFICADO ANTERIOR"] = (
        fecha_caducidad_cert_anterior
    )
    df.loc[mask, "N° DE RESOLUCIÓN"] = num_resolucion
    df.loc[mask, "FECHA RESOLUCIÓN"] = fecha_resolucion
    df.loc[mask, "N° DE CERTIFICADO"] = num_certificado
    df.loc[mask, "FECHA EMITIDA CERTIFICADO"] = fecha_emitida_cert
    df.loc[mask, "VIGENCIA DE AUTORIZACIÓN"] = vigencia_autorizacion

    escribir_autorizaciones(df)


def autorizaciones_pendientes_resolucion() -> pd.DataFrame:
    """
    Devuelve autorizaciones que todavía no tienen N° de Resolución.
    """
    df = leer_autorizaciones()
    if df.empty:
        return df

    mask = df["N° DE RESOLUCIÓN"].astype(str).str.strip() == ""
    return df[mask].copy()


# ---------------------------------------------------------------------------
# API – DOCUMENTOS SIMPLES
# ---------------------------------------------------------------------------


def leer_documentos() -> pd.DataFrame:
    return _leer_df(DOCS_SHEET_NAME, COLUMNAS_DOCUMENTOS)


def escribir_documentos(df: pd.DataFrame) -> None:
    _escribir_df(DOCS_SHEET_NAME, COLUMNAS_DOCUMENTOS, df)


def append_documento(
    *,
    fecha_ingreso: str,
    num_documento_simple: str,
    asunto: str,
    nombre: str,
    dni: str,
    domicilio_fiscal: str,
    giro_motivo: str,
    ubicacion_solicitar: str,
    celular: str,
    procedencia: str,
    num_carta: str = "",
    fecha_carta: str = "",
    fecha_notificacion: str = "",
    folios: str = "",
    estado: str = "PENDIENTE",
) -> None:
    """
    Registra un nuevo Documento Simple en Documentos_CA.
    """
    fila = {
        "ESTADO": estado,
        "FECHA DE INGRESO": fecha_ingreso,
        "N° DE DOCUMENTO SIMPLE": num_documento_simple,
        "ASUNTO": asunto,
        "NOMBRE Y APELLIDO": nombre,
        "DNI": dni,
        "DOMICILIO FISCAL": domicilio_fiscal,
        "GIRO O MOTIVO DE LA SOLICITUD": giro_motivo,
        "UBICACIÓN A SOLICITAR": ubicacion_solicitar,
        "N° DE CELULAR": celular,
        "PROCEDENTE / IMPROCEDENTE": procedencia,
        "N° DE CARTA": num_carta,
        "FECHA DE LA CARTA": fecha_carta,
        "FECHA DE NOTIFICACION": fecha_notificacion,
        "FOLIOS": folios,
    }

    _append_fila(
        DOCS_SHEET_NAME,
        COLUMNAS_DOCUMENTOS,
        fila,
        auto_numero_col="N°",
    )


def actualizar_estado_documento(num_documento_simple: str, nuevo_estado: str) -> None:
    """
    Cambia el ESTADO de un documento simple (por N° de Documento Simple).
    """
    df = leer_documentos()
    if df.empty:
        return

    mask = (
        df["N° DE DOCUMENTO SIMPLE"].astype(str).str.strip()
        == str(num_documento_simple).strip()
    )
    if not mask.any():
        return

    df.loc[mask, "ESTADO"] = str(nuevo_estado).upper()
    escribir_documentos(df)


def documentos_para_evaluacion() -> pd.DataFrame:
    """
    Devuelve los Documentos Simples que se pueden usar para Evaluación:

    - ASUNTO: RENOVACION o SOLICITUD DE COMERCIO AMBULATORIO
    - PROCEDENTE / IMPROCEDENTE: PROCEDENTE
    - ESTADO: PENDIENTE o EN EVALUACION
    """
    df = leer_documentos()
    if df.empty:
        return df

    asuntos_validos = {"RENOVACION", "SOLICITUD DE COMERCIO AMBULATORIO"}

    df["ASUNTO_UP"] = df["ASUNTO"].str.upper().str.strip()
    df["PROC_UP"] = df["PROCEDENTE / IMPROCEDENTE"].str.upper().str.strip()
    df["ESTADO_UP"] = df["ESTADO"].str.upper().str.strip()

    mask = (
        df["ASUNTO_UP"].isin(asuntos_validos)
        & (df["PROC_UP"] == "PROCEDENTE")
        & df["ESTADO_UP"].isin({"PENDIENTE", "EN EVALUACION"})
    )

    out = df[mask].copy()
    out.drop(columns=["ASUNTO_UP", "PROC_UP", "ESTADO_UP"], inplace=True)
    return out
