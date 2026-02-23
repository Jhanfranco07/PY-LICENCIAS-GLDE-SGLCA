# licencias/app_compatibilidad.py

import io
import os
from datetime import date

import streamlit as st
from docxtpl import DocxTemplate

from integraciones.codart import (
    CodartAPIError,
    consultar_dni,
    consultar_ruc,
    dni_a_nombre_completo,
)

from utils import (
    asegurar_dirs,
    fmt_fecha_larga,
    safe_filename_pretty,
    to_upper,
)

# -------------------- Catálogos --------------------

ZONAS = [
    ("RDM",   "Residencial de Densidad Media"),
    ("RDM-1", "Residencial de Densidad Media - 1"),
    ("RDM-e", "Residencial de Densidad Media Especial"),
    ("RDB",   "Residencial de Densidad Baja"),
    ("CZ",    "Comercio Zonal"),
    ("CV",    "Comercio Vecinal"),
    ("E1",    "Educación Básica"),
    ("E2",    "Educación Superior Tecnológica"),
    ("E3",    "Educación Superior Universitaria"),
    ("PTP",   "Protección y Tratamiento Paisajista"),
    ("ZRP",   "Zona de Recreación Pública"),
    ("ZRE",   "Zona de Reglamentación Especial"),
    ("ZTE",   "Zona de Tratamiento Especial"),
    ("ZTE 1", "Zona de Tratamiento Especial 1"),
    ("ZTE 2", "Zona de Tratamiento Especial 2"),
    ("CH",    "Casa Huerta"),
    ("CH-1",  "Casa Huerta 1"),
    ("CH-2",  "Casa Huerta 2"),
    ("CH-3",  "Casa Huerta 3"),
    ("OU",    "Otros Usos"),
    ("OU-C",  "Otros Usos - Cementerio"),
    ("OU-ZA", "Otros Usos - Zona Arqueológica"),
    ("H2",    "Centro de Salud"),
    ("H3",    "Hospital General"),
    ("A",     "Agrícola"),
    ("I2",    "Industria Liviana"),
    ("I4",    "Industria Pesada Básica"),
]
ZONAS_DICT = {c: d for c, d in ZONAS}

ORDENANZAS = [
    "ORD. 1117-MML",
    "ORD. 1146-MML",
    "ORD. 2236-MML",
    "ORD. 933-MML",
    "ORD. 270-2021-PACHACAMAC",
]


# -------------------- Helpers --------------------

def fecha_mes_abrev(d: date) -> str:
    """Ej: 16 DIC 2025 (para el paréntesis del expediente)."""
    if not d:
        return ""
    meses = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
             "JUL", "AGO", "SET", "OCT", "NOV", "DIC"]
    return f"{d.day:02d} {meses[d.month - 1]} {d.year}"


def render_doc(context: dict, filename_stem: str, plantilla_path: str):
    """Renderiza la plantilla Word y muestra botón de descarga."""
    try:
        doc = DocxTemplate(plantilla_path)
    except Exception as e:
        st.error(f"No se pudo abrir la plantilla: {plantilla_path}")
        st.error(str(e))
        return

    try:
        doc.render(context, autoescape=True)
    except Exception as e:
        st.error("Ocurrió un error al rellenar la plantilla.")
        st.error(str(e))
        return

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    out_name = safe_filename_pretty(filename_stem) + ".docx"

    st.success(f"Documento generado: {out_name}")
    st.download_button(
        "⬇️ Descargar compatibilidad en Word",
        data=buffer,
        file_name=out_name,
        mime=(
            "application/vnd.openxmlformats-"
            "officedocument.wordprocessingml.document"
        ),
    )


# -------------------- Callbacks (autocompletar) --------------------

def _set_flash(kind: str, text: str):
    st.session_state["_flash_kind"] = kind
    st.session_state["_flash_text"] = text


def _autocompletar_con_dni():
    st.session_state["_last_action"] = "dni"
    try:
        dni = (st.session_state.get("dni") or "").strip()
        res = consultar_dni(dni)
        nombre = (dni_a_nombre_completo(res) or "").strip()
        if not nombre:
            _set_flash("warning", "RENIEC respondió, pero no llegó el nombre.")
            return
        st.session_state["persona"] = nombre
        _set_flash("success", "Solicitante actualizado con RENIEC (DNI).")
    except (ValueError, CodartAPIError) as e:
        _set_flash("error", str(e))
    except Exception as e:
        _set_flash("error", f"Error inesperado consultando DNI: {e}")


def _autocompletar_con_ruc():
    st.session_state["_last_action"] = "ruc"
    try:
        ruc = (st.session_state.get("ruc") or "").strip()
        res = consultar_ruc(ruc)
        razon = (res.get("razon_social") or "").strip()
        if not razon:
            _set_flash("warning", "SUNAT respondió, pero no llegó la razón social.")
            return
        st.session_state["persona"] = razon
        _set_flash("success", "Solicitante actualizado con SUNAT (RUC).")
    except (ValueError, CodartAPIError) as e:
        _set_flash("error", str(e))
    except Exception as e:
        _set_flash("error", f"Error inesperado consultando RUC: {e}")


# -------------------- Módulo principal --------------------

def run_modulo_compatibilidad():
    st.header("🏢 Evaluación de Compatibilidad de Uso")

    asegurar_dirs()
    os.makedirs("plantilla_compa", exist_ok=True)

    # rutas fijas de las plantillas
    TPL_COMP_INDETERMINADA = "plantilla_compa/compatibilidad_indeterminada.docx"
    TPL_COMP_TEMPORAL = "plantilla_compa/compatibilidad_temporal.docx"

    # Defaults
    st.session_state.setdefault("persona", "")
    st.session_state.setdefault("dni", "")
    st.session_state.setdefault("ruc", "")
    st.session_state.setdefault("_flash_kind", "")
    st.session_state.setdefault("_flash_text", "")
    st.session_state.setdefault("_last_action", "")

    # Estilos visuales
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.9rem;
            max-width: 980px;
            background: #f7f9fc;
            border-radius: 12px;
            padding-left: 14px;
            padding-right: 14px;
            padding-bottom: 18px;
        }
        .stButton>button {
            border-radius: 10px;
            padding: .55rem 1rem;
            font-weight: 600;
            border: 1px solid #cbd5e1;
            background: #ffffff;
        }
        .stButton>button:hover {
            border-color: #94a3b8;
            background: #f8fafc;
        }
        .card {
            border: 1px solid #d7dee8;
            border-radius: 16px;
            padding: 18px 20px;
            margin-bottom: 18px;
            background: #ffffff;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.05);
        }
        .subcard {
            border: 1px solid #dbeafe;
            border-radius: 12px;
            padding: 12px 14px 8px 14px;
            background: #f8fbff;
            margin: 10px 0 12px 0;
        }
        .section-title {
            font-size: 0.92rem;
            text-transform: uppercase;
            letter-spacing: .08em;
            color: #475569;
            margin-bottom: 0.45rem;
            font-weight: 700;
        }
        .section-divider {
            margin: 0.5rem 0 1rem 0;
            border-top: 1px solid #e2e8f0;
        }
        /* Mejor contraste en campos */
        .stTextInput label, .stTextArea label, .stSelectbox label, .stMultiSelect label {
            color: #334155 !important;
            font-weight: 600;
        }
        .stTextInput input, .stTextArea textarea {
            background: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            color: #0f172a !important;
        }
        .stTextInput input:focus, .stTextArea textarea:focus {
            border-color: #2563eb !important;
            box-shadow: 0 0 0 1px #2563eb !important;
        }
        .stSelectbox [data-baseweb="select"] > div,
        .stMultiSelect [data-baseweb="select"] > div {
            background: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            color: #0f172a !important;
        }
        .stSelectbox [data-baseweb="select"] > div:focus-within,
        .stMultiSelect [data-baseweb="select"] > div:focus-within {
            border-color: #2563eb !important;
            box-shadow: 0 0 0 1px #2563eb !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Flash message (si hubo autocompletar)
    if st.session_state.get("_flash_text"):
        kind = st.session_state.get("_flash_kind", "")
        txt = st.session_state.get("_flash_text", "")
        if kind == "success":
            st.success(txt)
        elif kind == "warning":
            st.warning(txt)
        elif kind == "error":
            st.error(txt)
        else:
            st.info(txt)
        # limpiar para que no se repita siempre
        st.session_state["_flash_kind"] = ""
        st.session_state["_flash_text"] = ""

    st.markdown('<div class="card">', unsafe_allow_html=True)

    # ---------- Formulario principal ----------
    with st.container():

        # ---------------- Encabezado ----------------
        st.markdown(
            '<div class="section-title">Encabezado</div>',
            unsafe_allow_html=True,
        )
        n_compa = st.text_input(
            "N° de compatibilidad*",
            max_chars=10,
            placeholder="Ej: 1010",
        )

        st.markdown('<hr class="section-divider" />', unsafe_allow_html=True)

        # ---------------- Datos del solicitante ----------------
        st.markdown(
            '<div class="section-title">Datos del solicitante</div>',
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Solicitante*", max_chars=150, key="persona")
            st.text_input("DNI (si es persona natural)", max_chars=8, key="dni")
        with c2:
            st.text_input("RUC (si es persona jurídica)", max_chars=11, key="ruc")
            nom_comercio = st.text_input("Nombre comercial (opcional)")

        # Botones: usan callback (NO rompe session_state)
        b1, b2 = st.columns(2)
        with b1:
            st.button(
                "⚡ Autocompletar solicitante con DNI",
                use_container_width=True,
                on_click=_autocompletar_con_dni,
                key="btn_auto_dni_compa",
            )
        with b2:
            st.button(
                "⚡ Autocompletar solicitante con RUC",
                use_container_width=True,
                on_click=_autocompletar_con_ruc,
                key="btn_auto_ruc_compa",
            )

        direccion = st.text_input("Dirección*", max_chars=200)

        st.markdown('<hr class="section-divider" />', unsafe_allow_html=True)

        # ---------------- Datos de la actividad ----------------
        st.markdown(
            '<div class="section-title">Datos de la actividad</div>',
            unsafe_allow_html=True,
        )

        giro = st.text_area(
            "Uso comercial / giro (texto general)*",
            height=80,
            placeholder="Ej: SERVICIO DE CONSULTORIOS ODONTOLÓGICOS",
        )

        col_ord, col_area = st.columns([2, 1])
        with col_ord:
            ordenanzas_sel = st.multiselect(
                "Ordenanzas aplicables*",
                ORDENANZAS,
                default=["ORD. 2236-MML"],
            )
        with col_area:
            area = st.text_input("Área comercial (m²)*", max_chars=50)

        col_itse, col_cert, col_tipo = st.columns(3)
        with col_itse:
            itse = st.selectbox(
                "ITSE / Nivel de riesgo*",
                [
                    "ITSE RIESGO MUY ALTO",
                    "ITSE RIESGO ALTO",
                    "ITSE RIESGO MEDIO",
                ],
            )
        with col_cert:
            certificador = st.selectbox(
                "Certificador de riesgo*",
                [
                    "AMBROSIO BARRIOS P.",
                    "SILVANO BELITO T.",
                ],
            )
        with col_tipo:
            tipo_licencia_simple = st.selectbox(
                "Tipo de licencia*",
                ["INDETERMINADA", "TEMPORAL"],
            )

        st.markdown('<hr class="section-divider" />', unsafe_allow_html=True)

        # ---------------- Actividades generales + zonificación ----------------
        st.markdown(
            '<div class="section-title">Actividad general y zonificación</div>',
            unsafe_allow_html=True,
        )

        sel_act_col, _ = st.columns([1, 2])
        with sel_act_col:
            n_actividades = st.selectbox(
                "N° de actividades generales*",
                options=[1, 2, 3, 4, 5],
                index=0,
                key="n_actividades_compa",
            )
        n_actividades = int(n_actividades)
        zona_opciones = [f"{c} – {d}" for c, d in ZONAS]

        actividades_generales = []
        for i in range(n_actividades):
            st.markdown('<div class="subcard">', unsafe_allow_html=True)
            st.markdown(f"**Actividad general {i + 1}**")
            col_act1, col_act2 = st.columns([3, 1])
            with col_act1:
                actividad_i = st.text_input(
                    f"Actividad general {i + 1}*",
                    max_chars=200,
                    key=f"actividad_{i + 1}",
                )
            with col_act2:
                codigo_i = st.text_input(
                    f"Código de la actividad {i + 1}*",
                    max_chars=50,
                    key=f"codigo_actividad_{i + 1}",
                )

            zona_sel_i = st.selectbox(
                f"Zonificación (código) actividad {i + 1}*",
                zona_opciones,
                key=f"zona_sel_{i + 1}",
            )
            zona_codigo_i = zona_sel_i.split(" – ")[0]
            zona_desc_i = ZONAS_DICT.get(zona_codigo_i, "")

            sel_giro_col, _ = st.columns([1, 2])
            with sel_giro_col:
                n_giros_i = st.selectbox(
                    f"N° de giros para actividad {i + 1}*",
                    options=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                    index=0,
                    key=f"n_giros_tabla_{i + 1}",
                )
            n_giros_i = int(n_giros_i)

            giros_i = []
            for j in range(n_giros_i):
                st.markdown(f"Giro {j + 1} de actividad {i + 1}")
                cg1, cg2, cg3 = st.columns([2, 4, 2])
                with cg1:
                    cod_giro = st.text_input(
                        f"Código giro {i + 1}.{j + 1}",
                        max_chars=50,
                        key=f"codigo_giro_{i + 1}_{j + 1}",
                    )
                with cg2:
                    giro_desc = st.text_input(
                        f"Descripción del giro {i + 1}.{j + 1}",
                        max_chars=200,
                        key=f"desc_giro_{i + 1}_{j + 1}",
                    )
                with cg3:
                    conf_giro = st.selectbox(
                        f"Conformidad giro {i + 1}.{j + 1}",
                        ["SI", "NO"],
                        key=f"conf_giro_{i + 1}_{j + 1}",
                    )

                giros_i.append(
                    {
                        "codigo": cod_giro,
                        "giro": giro_desc,
                        "conf_si": "X" if conf_giro == "SI" else "",
                        "conf_no": "X" if conf_giro == "NO" else "",
                    }
                )

            actividades_generales.append(
                {
                    "actividad": actividad_i,
                    "codigo": codigo_i,
                    "zona": zona_codigo_i,
                    "zona_desc": zona_desc_i,
                    "giros": giros_i,
                }
            )

            if i < n_actividades - 1:
                st.markdown('<hr class="section-divider" />', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<hr class="section-divider" />', unsafe_allow_html=True)

        # ---------------- Datos de expediente y fecha ----------------
        st.markdown(
            '<div class="section-title">Datos de expediente y fecha</div>',
            unsafe_allow_html=True,
        )

        col_exp1, col_exp2 = st.columns([2, 1])
        with col_exp1:
            ds = st.text_input("N° de expediente / DS*", max_chars=20)
        with col_exp2:
            fecha_ds = st.date_input(
                "Fecha del expediente",
                value=date.today(),
            )

        fecha_doc = st.date_input(
            "Fecha del documento",
            value=date.today(),
        )

        st.markdown("")
        generar = st.button("🧾 Generar compatibilidad (.docx)", key="btn_generar_compa")

    st.markdown("</div>", unsafe_allow_html=True)

    # Si el submit fue por autocompletar, NO generamos (evita consumir lógica y errores)
    if st.session_state.get("_last_action") in ("dni", "ruc"):
        st.session_state["_last_action"] = ""
        st.stop()

    # Si no se presionó generar, salir
    if not generar:
        return

    # Mapear opción corta de licencia al texto completo del documento
    tipo_licencia_map = {
        "INDETERMINADA": "LICENCIA DE FUNCIONAMIENTO INDETERMINADA",
        "TEMPORAL": "LICENCIA DE FUNCIONAMIENTO TEMPORAL (01 AÑO)",
    }
    tipo_licencia = tipo_licencia_map.get(tipo_licencia_simple, "")

    # --------- Validaciones básicas ---------
    persona = (st.session_state.get("persona") or "").strip()
    dni = (st.session_state.get("dni") or "").strip()
    ruc = (st.session_state.get("ruc") or "").strip()

    faltantes = []
    for key, val in {
        "n_compa": n_compa,
        "persona": persona,
        "direccion": direccion,
        "giro": giro,
        "area": area,
        "itse": itse,
        "certificador": certificador,
        "tipo_licencia": tipo_licencia,
        "ds": ds,
    }.items():
        if isinstance(val, str) and not val.strip():
            faltantes.append(key)

    if not ordenanzas_sel:
        faltantes.append("ordenanzas")
    if not fecha_ds:
        faltantes.append("fecha_ds")
    if not fecha_doc:
        faltantes.append("fecha_doc")

    # Validar actividades generales y sus giros
    if not actividades_generales:
        faltantes.append("actividades_generales")
    else:
        for idx, ag in enumerate(actividades_generales, start=1):
            if not str(ag.get("actividad", "")).strip():
                faltantes.append(f"actividad_{idx}")
            if not str(ag.get("codigo", "")).strip():
                faltantes.append(f"codigo_actividad_{idx}")
            if not str(ag.get("zona", "")).strip():
                faltantes.append(f"zona_{idx}")

            giros_ag = ag.get("giros", []) or []
            if not giros_ag:
                faltantes.append(f"giros_actividad_{idx}")
            else:
                for jdx, fila in enumerate(giros_ag, start=1):
                    if not str(fila.get("codigo", "")).strip():
                        faltantes.append(f"codigo_giro_{idx}_{jdx}")
                    if not str(fila.get("giro", "")).strip():
                        faltantes.append(f"desc_giro_{idx}_{jdx}")

    if faltantes:
        st.error("Faltan campos obligatorios: " + ", ".join(faltantes))
        return

    # DNI / RUC con “--------------------” cuando falte
    dni_val = dni
    ruc_val = ruc
    if dni_val and not ruc_val:
        ruc_val = "--------------------"
    elif ruc_val and not dni_val:
        dni_val = "--------------------"
    elif not dni_val and not ruc_val:
        dni_val = "--------------------"
        ruc_val = "--------------------"

    # Nombre comercial vacío
    nom_com_val = (nom_comercio or "").strip() or "--------------------"

    ordenanza_texto = ", ".join(ordenanzas_sel)

    actividades_generales_ctx = []
    for ag in actividades_generales:
        giros_ctx = []
        for fila in ag.get("giros", []):
            giros_ctx.append(
                {
                    "codigo": str(fila.get("codigo", "")).strip(),
                    "giro": to_upper(fila.get("giro", "")),
                    "conf_si": fila.get("conf_si", ""),
                    "conf_no": fila.get("conf_no", ""),
                }
            )

        actividades_generales_ctx.append(
            {
                "actividad": to_upper(ag.get("actividad", "")),
                "codigo": str(ag.get("codigo", "")).strip(),
                "zona": str(ag.get("zona", "")).strip(),
                "zona_desc": to_upper(ag.get("zona_desc", "")),
                "giros": giros_ctx,
            }
        )

    # Compatibilidad retroactiva por si alguna plantilla aÃºn usa variables antiguas
    primera_actividad = actividades_generales_ctx[0] if actividades_generales_ctx else {}

    # --------- Contexto para la plantilla ---------
    ctx = {
        "n_compa": n_compa,
        "persona": to_upper(persona),
        "dni": dni_val,
        "ruc": ruc_val,
        "nom_comercio": to_upper(nom_com_val),
        "direccion": to_upper(direccion),
        "giro": to_upper(giro),

        "ordenanza": ordenanza_texto,
        "area": area,
        "itse": itse,
        "certificador": certificador,
        "tipo_licencia": tipo_licencia,

        "actividad": primera_actividad.get("actividad", ""),
        "codigo": primera_actividad.get("codigo", ""),

        "zona": primera_actividad.get("zona", ""),
        "zona_desc": primera_actividad.get("zona_desc", ""),

        "ds": ds,
        "fecha_ds": fecha_mes_abrev(fecha_ds),
        "fecha_actual": fmt_fecha_larga(fecha_doc),

        "actividades_tabla": primera_actividad.get("giros", []),
        "actividades_generales": actividades_generales_ctx,
    }

    # Elegir plantilla según tipo de licencia
    if "LICENCIA DE FUNCIONAMIENTO INDETERMINADA" in tipo_licencia:
        tpl_path = TPL_COMP_INDETERMINADA
    else:
        tpl_path = TPL_COMP_TEMPORAL

    base_name = f"{n_compa} - {fecha_doc.year} - {to_upper(persona)}"
    render_doc(ctx, base_name, tpl_path)


if __name__ == "__main__":
    st.set_page_config(page_title="Compatibilidad de Uso", layout="centered")
    run_modulo_compatibilidad()
