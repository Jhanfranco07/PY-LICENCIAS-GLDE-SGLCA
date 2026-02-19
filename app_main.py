import streamlit as st

from anuncios.app_anuncios import run_modulo_anuncios
from comercio.app_documentos import run_documentos_comercio
from comercio.app_permisos import run_permisos_comercio
from integraciones.app_consultas import run_modulo_consultas
from licencias.app_compatibilidad import run_modulo_compatibilidad


SYSTEM_NAME = "Sistema Integrado de Tramites Municipales - GLDE"
SYSTEM_SUBTITLE = "Gestion de Licencias, Permisos, Anuncios y Documentos"


def _inject_main_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #f3f6fb;
        }
        .block-container {
            max-width: 1020px;
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
        .title-wrap {
            border: 1px solid #d9e2ec;
            border-radius: 14px;
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
            padding: 14px 16px 12px 16px;
            margin-bottom: 12px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
        }
        .title-main {
            margin: 0;
            color: #0f172a;
            font-size: 1.65rem;
            font-weight: 800;
            line-height: 1.25;
            letter-spacing: .01em;
        }
        .title-sub {
            margin: 4px 0 0 0;
            color: #475569;
            font-size: .93rem;
            letter-spacing: .02em;
        }
        section[data-testid="stSidebar"] {
            background: #f8fafc;
            border-right: 1px solid #e2e8f0;
        }
        section[data-testid="stSidebar"] .stRadio > div {
            gap: .35rem;
        }
        section[data-testid="stSidebar"] .stRadio label {
            border-radius: 8px;
            padding: 6px 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    st.markdown(
        f"""
        <div class="title-wrap">
            <h1 class="title-main">{SYSTEM_NAME}</h1>
            <p class="title-sub">{SYSTEM_SUBTITLE}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title=SYSTEM_NAME,
        page_icon="🏛️",
        layout="centered",
    )

    _inject_main_styles()
    _render_header()

    st.sidebar.title("Modulos")
    modulo = st.sidebar.radio(
        "Selecciona el modulo:",
        (
            "📥 Documentos Simples (Comercio Ambulatorio)",
            "🧾 Permisos de Comercio Ambulatorio",
            "📢 Anuncios Publicitarios",
            "🏢 Compatibilidad de Uso (Licencias)",
            "🔎 Consultas DNI / RUC (Pruebas)",
        ),
    )

    if modulo == "📥 Documentos Simples (Comercio Ambulatorio)":
        run_documentos_comercio()
    elif modulo == "🧾 Permisos de Comercio Ambulatorio":
        run_permisos_comercio()
    elif modulo == "📢 Anuncios Publicitarios":
        run_modulo_anuncios()
    elif modulo == "🏢 Compatibilidad de Uso (Licencias)":
        run_modulo_compatibilidad()
    elif modulo == "🔎 Consultas DNI / RUC (Pruebas)":
        run_modulo_consultas()


if __name__ == "__main__":
    main()
