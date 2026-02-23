# integraciones/app_consultas.py
import json
import streamlit as st

from integraciones.codart import (
    CodartAPIError,
    consultar_dni,
    consultar_ruc,
    dni_a_nombre_completo,
)

def _val(v):
    v = (v or "").strip() if isinstance(v, str) else v
    return "-" if (v in [None, "", "Locked"]) else v

def run_modulo_consultas():
    st.title("📄 Consultas (DNI / RUC)")
    st.caption("Consulta RENIEC (DNI) y SUNAT (RUC) usando CODART.")

    tab_dni, tab_ruc = st.tabs(["DNI (RENIEC)", "RUC (SUNAT)"])

    with tab_dni:
        st.subheader("Consulta por DNI")

        c1, c2 = st.columns([3, 1])
        with c1:
            dni = st.text_input("DNI (8 dígitos)", max_chars=8, placeholder="Ej: 70238666", key="dni_in")
        with c2:
            btn = st.button("🔎 Consultar", use_container_width=True, key="btn_dni")

        if btn:
            try:
                res = consultar_dni(dni)
                nombre = dni_a_nombre_completo(res)

                st.success("Consulta DNI OK")

                st.markdown("### Resultado")
                st.markdown(
                    f"""
                    <div style="padding:14px;border:1px solid rgba(255,255,255,.12);border-radius:12px;">
                      <div style="font-size:14px;opacity:.8;">Nombre completo</div>
                      <div style="font-size:20px;font-weight:700;margin-top:4px;">{_val(nombre)}</div>
                      <div style="margin-top:10px;opacity:.9;">
                        <b>DNI:</b> {_val(res.get("document_number"))} &nbsp;&nbsp; | &nbsp;&nbsp;
                        <b>Nacionalidad:</b> {_val(res.get("nationality"))}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                with st.expander("Ver respuesta técnica (JSON)"):
                    st.code(json.dumps(res, indent=2, ensure_ascii=False), language="json")

            except ValueError as e:
                st.error(str(e))
            except CodartAPIError as e:
                st.error(str(e))
            except Exception as e:
                st.error("Error inesperado")
                st.exception(e)

    with tab_ruc:
        st.subheader("Consulta por RUC")

        c1, c2 = st.columns([3, 1])
        with c1:
            ruc = st.text_input("RUC (11 dígitos)", max_chars=11, placeholder="Ej: 20538856674", key="ruc_in")
        with c2:
            btn2 = st.button("🔎 Consultar", use_container_width=True, key="btn_ruc")

        if btn2:
            try:
                res = consultar_ruc(ruc)

                st.success("Consulta RUC OK")

                razon = _val(res.get("razon_social"))
                direccion = _val(res.get("direccion"))
                estado = _val(res.get("estado"))
                condicion = _val(res.get("condicion"))

                st.markdown("### Resultado")
                st.markdown(
                    f"""
                    <div style="padding:14px;border:1px solid rgba(255,255,255,.12);border-radius:12px;">
                      <div style="font-size:14px;opacity:.8;">Razón social</div>
                      <div style="font-size:20px;font-weight:700;margin-top:4px;">{razon}</div>
                      <div style="margin-top:10px;opacity:.9;">
                        <b>RUC:</b> {_val(res.get("ruc") or ruc)}<br/>
                        <b>Dirección:</b> {direccion}<br/>
                        <b>Estado / Condición:</b> {estado} / {condicion}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                with st.expander("Ver respuesta técnica (JSON)"):
                    st.code(json.dumps(res, indent=2, ensure_ascii=False), language="json")

            except ValueError as e:
                st.error(str(e))
            except CodartAPIError as e:
                st.error(str(e))
            except Exception as e:
                st.error("Error inesperado")
                st.exception(e)
