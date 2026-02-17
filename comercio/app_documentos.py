import pandas as pd
import streamlit as st

from integraciones.codart import (
    CodartAPIError,
    consultar_dni,
    dni_a_nombre_completo,
)
from comercio.sheets_comercio import (
    append_documento,
    leer_documentos,
)
# Reutilizamos las opciones de giros y el helper to_upper
from comercio.app_permisos import GIROS_OPCIONES, to_upper


def _fmt_fecha_corta(d) -> str:
    """Devuelve la fecha en formato DD/MM/YYYY."""
    try:
        return pd.to_datetime(d).strftime("%d/%m/%Y")
    except Exception:
        return ""


def _doc_identidad_valido(val: str) -> bool:
    """
    Acepta:
    - DNI: 8 dígitos
    - CE:  9 dígitos
    """
    doc = (val or "").strip()
    return doc.isdigit() and len(doc) in (8, 9)


# ===== Autocomplete DNI solo para este módulo DS =====
def _init_dni_state_ds():
    st.session_state.setdefault("dni_ds_msg", "")


def _cb_autocomplete_dni_ds():
    dni_val = (st.session_state.get("dni_ds") or "").strip()
    st.session_state["dni_ds_msg"] = ""

    if not dni_val:
        return

    # Solo consulta RENIEC para DNI de 8 dígitos.
    # Si es CE (9 dígitos), no consulta CODART.
    if not (dni_val.isdigit() and len(dni_val) == 8):
        return

    try:
        res = consultar_dni(dni_val)
        nombre = dni_a_nombre_completo(res)

        if nombre:
            st.session_state["nombre_ds"] = nombre
            st.session_state[
                "dni_ds_msg"
            ] = "✅ DNI válido: nombre autocompletado."
        else:
            st.session_state["dni_ds_msg"] = (
                "⚠️ DNI OK, pero no se encontró nombre."
            )
    except ValueError as e:
        st.session_state["dni_ds_msg"] = f"⚠️ {e}"
    except CodartAPIError as e:
        st.session_state["dni_ds_msg"] = f"⚠️ {e}"
    except Exception as e:
        st.session_state["dni_ds_msg"] = f"⚠️ Error consultando DNI: {e}"


def run_documentos_comercio():
    _init_dni_state_ds()

    # --- Estilos (todo en mayúsculas visualmente) ---
    st.markdown(
        """
    <style>
    .block-container { padding-top: 1.0rem; max-width: 980px; }
    .card { border: 1px solid #e5e7eb; border-radius: 16px; padding: 16px; margin-bottom: 12px; background: #0f172a08; }
    .stButton>button { border-radius: 10px; padding: .55rem 1rem; font-weight: 600; }
    /* solo apariencia, el valor real lo limpiamos en Python */
    input[type="text"], textarea {
        text-transform: uppercase;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("📥 Registro de Documentos Simples – Comercio Ambulatorio")
    st.caption(
        "Registra los Documentos Simples (D.S.) que luego se usarán en la "
        "Evaluación y Autorización de comercio ambulatorio."
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Nuevo Documento Simple")

    # ------------------------------------------------------------------
    # Tipo de solicitud / Asunto
    # ------------------------------------------------------------------
    tipo_asunto = st.selectbox(
        "Tipo de solicitud*",
        [
            "RENOVACION",
            "SOLICITUD DE COMERCIO AMBULATORIO",
            "OTROS (especificar)",
        ],
        key="tipo_asunto_ds",
    )

    asunto_otro = ""
    if tipo_asunto == "OTROS (especificar)":
        asunto_otro = st.text_input(
            "Asunto (texto libre)*",
            key="asunto_otro",
            placeholder="Ej.: Solicitud de constancia, queja, etc.",
        )

    # ------------------------------------------------------------------
    # Datos básicos
    # ------------------------------------------------------------------
    c1, c2 = st.columns(2)
    with c1:
        fecha_ingreso = st.date_input(
            "Fecha de ingreso*",
            key="fecha_ingreso_ds",
            value=None,
            format="DD/MM/YYYY",
        )
    with c2:
        num_ds = st.text_input(
            "N° de Documento Simple*",
            key="num_ds",
            placeholder="Ej.: 17168-2025",
        )

    # DNI + nombre con autocomplete
    c3, c4 = st.columns([2, 3])
    with c3:
        dni = st.text_input(
            "DNI / CE (8 o 9 dígitos)*",
            key="dni_ds",
            max_chars=9,
            placeholder="#########",
            on_change=_cb_autocomplete_dni_ds,
        )
    dni_clean = (dni or "").strip()
    if dni_clean.isdigit() and len(dni_clean) == 8:
        st.caption("Tipo detectado: DNI")
    elif dni_clean.isdigit() and len(dni_clean) == 9:
        st.caption("Tipo detectado: CE")
    with c4:
        nombre = st.text_input(
            "Nombre y apellido*",
            key="nombre_ds",
            value=st.session_state.get("nombre_ds", ""),
        )

    msg_dni = (st.session_state.get("dni_ds_msg") or "").strip()
    if msg_dni:
        if msg_dni.startswith("✅"):
            st.success(msg_dni)
        else:
            st.warning(msg_dni)

    domicilio = st.text_input("Domicilio fiscal*", key="domicilio_ds")

    # ------------------------------------------------------------------
    # Giro / motivo de la solicitud (condicional)
    # ------------------------------------------------------------------
    if tipo_asunto in ("RENOVACION", "SOLICITUD DE COMERCIO AMBULATORIO"):
        giro_label_1 = st.selectbox(
            "Giro principal (según Ordenanza)*",
            GIROS_OPCIONES,
            key="giro_motivo_ds_select",
        )

        add_segundo = st.checkbox(
            "Agregar segundo giro (opcional)",
            key="add_segundo_giro",
        )

        giro_label_2 = ""
        if add_segundo:
            opciones_segundo = [g for g in GIROS_OPCIONES if g != giro_label_1]
            giro_label_2 = st.selectbox(
                "Segundo giro (opcional)",
                opciones_segundo,
                key="giro_motivo_ds_select_2",
            )

        if giro_label_2:
            giro_motivo = f"{giro_label_1} Y {giro_label_2}"
        else:
            giro_motivo = giro_label_1
    else:
        giro_motivo = st.text_input(
            "Giro o motivo de la solicitud*",
            key="giro_motivo_ds",
            placeholder="Describe el motivo de la solicitud",
        )

    ubicacion = st.text_input(
        "Ubicación a solicitar*",
        key="ubicacion_ds",
        placeholder="Av./Jr./Parque ...",
    )

    celular = st.text_input(
        "N° de celular",
        key="celular_ds",
        placeholder="Ej.: 987654321",
    )

    procedencia = st.selectbox(
        "Procedente / Improcedente*",
        ["PROCEDENTE", "IMPROCEDENTE"],
        key="procedencia_ds",
    )

    c5, c6, c7 = st.columns(3)
    with c5:
        num_carta = st.text_input("N° de carta", key="num_carta_ds")
    with c6:
        fecha_carta = st.date_input(
            "Fecha de la carta",
            key="fecha_carta_ds",
            value=None,
            format="DD/MM/YYYY",
        )
    with c7:
        fecha_notif = st.date_input(
            "Fecha de notificación",
            key="fecha_notif_ds",
            value=None,
            format="DD/MM/YYYY",
        )

    folios = st.text_input("Folios", key="folios_ds")

    st.markdown("</div>", unsafe_allow_html=True)

    # ----------------- Botón GUARDAR D.S. -----------------
    if st.button("💾 Registrar Documento Simple"):
        falt = []

        # Asunto que se guarda en la columna ASUNTO
        asunto_final = (
            asunto_otro.strip()
            if tipo_asunto == "OTROS (especificar)"
            else tipo_asunto
        )

        if not fecha_ingreso:
            falt.append("fecha_ingreso")
        if not num_ds.strip():
            falt.append("num_ds")
        if not asunto_final:
            falt.append("asunto")
        if not nombre.strip():
            falt.append("nombre")
        if not dni.strip():
            falt.append("dni")
        if not domicilio.strip():
            falt.append("domicilio")
        if not giro_motivo.strip():
            falt.append("giro_motivo")
        if not ubicacion.strip():
            falt.append("ubicacion")

        if dni and (not _doc_identidad_valido(dni)):
            st.error("Documento inválido: debe tener 8 (DNI) o 9 (CE) dígitos.")
        elif falt:
            st.error("Faltan campos obligatorios: " + ", ".join(falt))
        else:
            try:
                append_documento(
                    fecha_ingreso=_fmt_fecha_corta(fecha_ingreso),
                    num_documento_simple=num_ds.strip(),
                    asunto=to_upper(asunto_final),
                    nombre=to_upper(nombre),
                    dni=dni.strip(),
                    domicilio_fiscal=to_upper(domicilio),
                    giro_motivo=to_upper(giro_motivo),
                    ubicacion_solicitar=to_upper(ubicacion),
                    celular=celular.strip(),
                    procedencia=to_upper(procedencia),
                    num_carta=to_upper(num_carta),
                    fecha_carta=_fmt_fecha_corta(fecha_carta)
                    if fecha_carta
                    else "",
                    fecha_notificacion=_fmt_fecha_corta(fecha_notif)
                    if fecha_notif
                    else "",
                    folios=to_upper(folios),
                    estado="PENDIENTE",
                )
                st.success("Documento Simple registrado correctamente.")
            except Exception as e:
                st.error(f"No se pudo registrar el Documento Simple: {e}")

    # ----------------- Vista rápida de la BD -----------------
    st.markdown("---")
    with st.expander("📊 Ver últimos Documentos registrados"):
        try:
            df = leer_documentos()
            if df.empty:
                st.info("Aún no hay documentos registrados.")
            else:
                st.dataframe(df.tail(50), use_container_width=True)
        except Exception as e:
            st.error(f"No se pudo leer la base de datos: {e}")


# Para usar este archivo solo (sin app_main.py)
if __name__ == "__main__":
    st.set_page_config(
        page_title="Documentos Simples – Comercio Ambulatorio",
        page_icon="📥",
        layout="centered",
    )
    run_documentos_comercio()
