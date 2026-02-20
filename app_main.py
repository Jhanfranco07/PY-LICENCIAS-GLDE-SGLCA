import streamlit as st

from anuncios.app_anuncios import run_modulo_anuncios
from comercio.app_documentos import run_documentos_comercio
from comercio.app_permisos import run_permisos_comercio
from integraciones.app_consultas import run_modulo_consultas
from licencias.app_compatibilidad import run_modulo_compatibilidad


SYSTEM_NAME = "Plataforma Integral de Tramites Municipales"
SYSTEM_SUBTITLE = "SGLCA - Gestion de Licencias, Documentos y Evaluaciones"


def _inject_main_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1120px;
            padding-top: 1rem;
            padding-bottom: 1.2rem;
        }
        .hero-wrap {
            position: relative;
            overflow: hidden;
            border: 1px solid #dbe2ea;
            border-radius: 18px;
            background:
                radial-gradient(1200px 300px at -10% -30%, #c7d2fe 0%, transparent 60%),
                radial-gradient(1200px 300px at 120% 120%, #bae6fd 0%, transparent 60%),
                linear-gradient(135deg, #0f172a 0%, #1e293b 48%, #334155 100%);
            padding: 22px 24px;
            margin-bottom: 12px;
            color: #f8fafc;
            box-shadow: 0 6px 20px rgba(15, 23, 42, 0.18);
        }
        .hero-title {
            margin: 0;
            font-size: 1.65rem;
            line-height: 1.2;
            font-weight: 800;
            letter-spacing: .02em;
        }
        .hero-subtitle {
            margin-top: 6px;
            margin-bottom: 0;
            color: #cbd5e1;
            font-size: 0.95rem;
            letter-spacing: .03em;
            text-transform: uppercase;
        }
        .hero-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
        }
        .hero-chip {
            border: 1px solid rgba(203, 213, 225, 0.45);
            color: #e2e8f0;
            background: rgba(15, 23, 42, 0.25);
            border-radius: 999px;
            padding: 4px 10px;
            font-size: .75rem;
            font-weight: 600;
            letter-spacing: .03em;
        }
        section[data-testid="stSidebar"] {
            border-right: 1px solid #e2e8f0;
            background: #f8fafc;
        }
        section[data-testid="stSidebar"] .stRadio > div {
            gap: .45rem;
        }
        section[data-testid="stSidebar"] .stRadio label {
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 8px 10px;
            background: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_hero() -> None:
    st.markdown(
        f"""
        <div class="hero-wrap">
            <h1 class="hero-title">{SYSTEM_NAME}</h1>
            <p class="hero-subtitle">{SYSTEM_SUBTITLE}</p>
            <div class="hero-chip-row">
                <span class="hero-chip">Comercio Ambulatorio</span>
                <span class="hero-chip">Anuncios Publicitarios</span>
                <span class="hero-chip">Compatibilidad de Uso</span>
                <span class="hero-chip">Consultas DNI / RUC</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title=SYSTEM_NAME,
        page_icon="🏛️",
        layout="wide",
    )

    _inject_main_styles()
    _render_hero()

    st.sidebar.title("Navegacion")
    modulo = st.sidebar.radio(
        "Selecciona el modulo:",
        (
            "Documentos Simples (Comercio Ambulatorio)",
            "Permisos de Comercio Ambulatorio",
            "Anuncios Publicitarios",
            "Compatibilidad de Uso (Licencias)",
            "Consultas DNI / RUC (Pruebas)",
        ),
    )

    if modulo == "Documentos Simples (Comercio Ambulatorio)":
        run_documentos_comercio()
    elif modulo == "Permisos de Comercio Ambulatorio":
        run_permisos_comercio()
    elif modulo == "Anuncios Publicitarios":
        run_modulo_anuncios()
    elif modulo == "Compatibilidad de Uso (Licencias)":
        run_modulo_compatibilidad()
    elif modulo == "Consultas DNI / RUC (Pruebas)":
        run_modulo_consultas()


if __name__ == "__main__":
    main()
