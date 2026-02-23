# comercio/app_permisos.py

import io
import os
import traceback

import pandas as pd
import streamlit as st
from docxtpl import DocxTemplate

from integraciones.codart import (
    CodartAPIError,
    consultar_dni,
    dni_a_nombre_completo,
)

from comercio.sheets_comercio import (
    append_evaluacion,
    append_autorizacion,
    documentos_para_evaluacion,
    actualizar_estado_documento,
    leer_evaluaciones,
    leer_autorizaciones,
)

# ========= Utils locales =========
def asegurar_dirs():
    os.makedirs("salidas", exist_ok=True)
    os.makedirs("plantillas", exist_ok=True)


def safe_filename_pretty(texto: str) -> str:
    prohibidos = '<>:"/\\|?*'
    limpio = "".join("_" if c in prohibidos else c for c in str(texto))
    return limpio.replace("\n", " ").replace("\r", " ").strip()


def to_upper(s: str) -> str:
    return (s or "").strip().upper()


def text_input_upper(label: str, key: str, **kwargs) -> str:
    """
    Wrapper de text_input que devuelve SIEMPRE en mayúsculas,
    pero sin modificar directamente st.session_state[key].
    Úsalo solo para campos de texto, no para DNI o teléfonos.
    """
    v = st.text_input(label, key=key, **kwargs)
    return to_upper(v)


def fmt_fecha_corta(d) -> str:
    try:
        return pd.to_datetime(d).strftime("%d/%m/%Y")
    except Exception:
        return ""


def fmt_fecha_larga(d) -> str:
    meses = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "setiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    try:
        dt = pd.to_datetime(d)
        return f"{dt.day} de {meses[dt.month - 1]} del {dt.year}"
    except Exception:
        return ""


def fmt_fecha_larga_de(d) -> str:
    t = fmt_fecha_larga(d)
    return t.replace(" del ", " de ") if t else t


def build_vigencia(fi, ff) -> str:
    ini = fmt_fecha_larga_de(fi)
    fin = fmt_fecha_larga_de(ff)
    return f"{ini} hasta el {fin}" if ini and fin else ""


def build_vigencia2(fi, ff) -> str:
    i = fmt_fecha_corta(fi)
    f = fmt_fecha_corta(ff)
    return f"{i} - {f}" if i and f else ""


def _parse_fecha_ddmmaaaa(val):
    """
    Intenta parsear '16/01/2026' → date. Si falla, devuelve None.
    """
    try:
        return pd.to_datetime(val, dayfirst=True).date()
    except Exception:
        return None


def _coordenadas_validas(val: str) -> bool:
    """
    Valida formato: "lat,lon" o "lat, lon" con rangos:
    lat [-90, 90], lon [-180, 180].
    """
    raw = (val or "").strip()
    if not raw or "," not in raw:
        return False
    lat_txt, lon_txt = [p.strip() for p in raw.split(",", 1)]
    try:
        lat = float(lat_txt)
        lon = float(lon_txt)
    except Exception:
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


def _doc_identidad_valido(val: str) -> bool:
    """
    Acepta:
    - DNI: 8 dígitos
    - CE:  9 dígitos
    """
    doc = (val or "").strip()
    return doc.isdigit() and len(doc) in (8, 9)


def _label_plazo(tiempo: int, unidad: str) -> str:
    """
    Devuelve el plazo en mayúsculas y con singular/plural correcto:
    - 1 + meses -> MES
    - n + meses -> MESES
    - 1 + años  -> AÑO
    - n + años  -> AÑOS
    """
    u = (unidad or "").strip().lower()
    t = int(tiempo or 0)
    if u == "meses":
        return "MES" if t == 1 else "MESES"
    if u == "años":
        return "AÑO" if t == 1 else "AÑOS"
    return (unidad or "").strip().upper()


def render_doc(context: dict, filename_stem: str, plantilla_path: str):
    if not os.path.exists(plantilla_path):
        st.error(f"No se encontró la plantilla: {plantilla_path}")
        return
    doc = DocxTemplate(plantilla_path)
    doc.render(context)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    out_name = f"{safe_filename_pretty(filename_stem)}.docx"
    with open(os.path.join("salidas", out_name), "wb") as f:
        f.write(buf.getvalue())
    st.success(f"Documento generado: {out_name}")
    st.download_button(
        "⬇️ Descargar .docx",
        buf,
        file_name=out_name,
        mime=(
            "application/vnd.openxmlformats-"
            "officedocument.wordprocessingml.document"
        ),
    )


def genero_labels(sexo: str):
    return (
        ("la señora", "la administrada", "identificada", "Sra")
        if sexo == "Femenino"
        else ("el señor", "el administrado", "identificado", "Sr")
    )


# ========= Catálogo de GIROS / RUBROS según Ordenanza =========
# ========= Catálogo de GIROS / RUBROS según Ordenanza =========
GIROS_RUBROS = [
    # Rubro 1
    {
        "label": "Rubro 1.a - Golosinas y afines (CÓDIGO G 001)",
        "giro": "GOLOSINAS Y AFINES, DEBIDAMENTE ENVASADOS CON REGISTRO SANITARIO Y CON FECHA DE VENCIMIENTO VIGENTE",
        "rubro": "1",
        "codigo": "001",
    },
    # Rubro 2
    {
        "label": "Rubro 2.a - Venta de frutas o verduras (CÓDIGO G 002)",
        "giro": "VENTA DE FRUTAS O VERDURAS",
        "rubro": "2",
        "codigo": "002",
    },
    {
        "label": "Rubro 2.b - Productos naturales con registro sanitario (CÓDIGO G 003)",
        "giro": "VENTA DE PRODUCTOS NATURALES, CON REGISTRO SANITARIO",
        "rubro": "2",
        "codigo": "003",
    },
    # Rubro 3
    {
        "label": "Rubro 3.a - Bebidas saludables (CÓDIGO G 004)",
        "giro": "BEBIDAS SALUDABLES: EMOLIENTE, QUINUA, MACA, SOYA",
        "rubro": "3",
        "codigo": "004",
    },
    {
        "label": "Rubro 3.b - Potajes tradicionales (CÓDIGO G 005)",
        "giro": "POTAJES TRADICIONALES",
        "rubro": "3",
        "codigo": "005",
    },
    {
        "label": "Rubro 3.c - Dulces tradicionales (CÓDIGO G 006)",
        "giro": "DULCES TRADICIONALES",
        "rubro": "3",
        "codigo": "006",
    },
    {
        "label": "Rubro 3.d - Sándwiches (CÓDIGO G 007)",
        "giro": "SÁNDWICHES",
        "rubro": "3",
        "codigo": "007",
    },
    {
        "label": "Rubro 3.e - Jugo de naranja y similares (CÓDIGO G 008)",
        "giro": "JUGO DE NARANJA Y SIMILARES",
        "rubro": "3",
        "codigo": "008",
    },
    {
        "label": "Rubro 3.f - Canchitas, confitería y similares (CÓDIGO G 009)",
        "giro": "CANCHITAS, CONFITERÍA Y SIMILARES",
        "rubro": "3",
        "codigo": "009",
    },
    # Rubro 4
    {
        "label": "Rubro 4.a - Mercería, bazar y útiles de escritorio (CÓDIGO G 010)",
        "giro": "MERCERÍAS, ARTÍCULOS DE BAZAR Y ÚTILES DE ESCRITORIO",
        "rubro": "4",
        "codigo": "010",
    },
    {
        "label": "Rubro 4.b - Diarios, revistas, libros y loterías (CÓDIGO G 011)",
        "giro": "DIARIOS Y REVISTAS, LIBROS Y LOTERÍAS",
        "rubro": "4",
        "codigo": "011",
    },
    {
        "label": "Rubro 4.c - Monedas y estampillas (CÓDIGO G 012)",
        "giro": "MONEDAS Y ESTAMPILLAS",
        "rubro": "4",
        "codigo": "012",
    },
    {
        "label": "Rubro 4.d - Artesanías (CÓDIGO G 013)",
        "giro": "ARTESANÍAS",
        "rubro": "4",
        "codigo": "013",
    },
    {
        "label": "Rubro 4.e - Artículos religiosos (CÓDIGO G 014)",
        "giro": "ARTÍCULOS RELIGIOSOS",
        "rubro": "4",
        "codigo": "014",
    },
    {
        "label": "Rubro 4.f - Artículos de limpieza (CÓDIGO G 015)",
        "giro": "ARTÍCULOS DE LIMPIEZA",
        "rubro": "4",
        "codigo": "015",
    },
    {
        "label": "Rubro 4.g - Pilas y relojes (CÓDIGO G 016)",
        "giro": "PILAS Y RELOJES",
        "rubro": "4",
        "codigo": "016",
    },
    # Rubro 5
    {
        "label": "Rubro 5.a - Duplicado de llaves / Cerrajería (CÓDIGO G 017)",
        "giro": "DUPLICADO DE LLAVES Y CERRAJERÍA",
        "rubro": "5",
        "codigo": "017",
    },
    {
        "label": "Rubro 5.b - Lustradores de calzado (CÓDIGO G 018)",
        "giro": "LUSTRADORES DE CALZADO",
        "rubro": "5",
        "codigo": "018",
    },
    {
        "label": "Rubro 5.c - Artistas plásticos y retratistas (CÓDIGO G 019)",
        "giro": "ARTISTAS PLÁSTICOS Y RETRATISTAS",
        "rubro": "5",
        "codigo": "019",
    },
    {
        "label": "Rubro 5.d - Fotografías (CÓDIGO G 020)",
        "giro": "FOTOGRAFÍAS",
        "rubro": "5",
        "codigo": "020",
    },
]


GIROS_OPCIONES = [item["label"] for item in GIROS_RUBROS]


def _label_to_info(label: str):
    """Devuelve el dict de GIROS_RUBROS cuyo label coincida (case-insensitive)."""
    if not label:
        return None
    label_up = label.strip().upper()
    for item in GIROS_RUBROS:
        if item["label"].strip().upper() == label_up:
            return item
    return None

def _labels_from_raw_giro(giro_motivo_raw: str):
    """
    A partir del texto guardado en BD (en mayúsculas),
    devuelve una lista de labels del catálogo GIROS_RUBROS
    que aparecen dentro del texto.
    Sirve tanto para 1 giro como para varios.
    """
    raw_up = (giro_motivo_raw or "").upper()
    encontrados = []
    for item in GIROS_RUBROS:
        lab_up = item["label"].upper()
        if lab_up and lab_up in raw_up:
            encontrados.append(item["label"])
    return encontrados

# ========= Autocomplete DNI (Codart) =========
def _init_dni_state():
    st.session_state.setdefault("dni_lookup_msg", "")


def _cb_autocomplete_dni():
    dni_val = (st.session_state.get("dni") or "").strip()
    st.session_state["dni_lookup_msg"] = ""

    if not dni_val:
        return

    # Solo consultamos RENIEC para DNI de 8 dígitos.
    # Si es CE (9 dígitos), no consultamos CODART.
    if not (dni_val.isdigit() and len(dni_val) == 8):
        return

    try:
        res = consultar_dni(dni_val)
        nombre = dni_a_nombre_completo(res)

        if nombre:
            st.session_state["nombre"] = to_upper(nombre)
            st.session_state[
                "dni_lookup_msg"
            ] = "✅ DNI válido: nombre autocompletado."
        else:
            st.session_state["dni_lookup_msg"] = (
                "⚠️ DNI OK, pero no se encontró nombre."
            )
    except ValueError as e:
        st.session_state["dni_lookup_msg"] = f"⚠️ {e}"
    except CodartAPIError as e:
        st.session_state["dni_lookup_msg"] = f"⚠️ {e}"
    except Exception as e:
        st.session_state["dni_lookup_msg"] = f"⚠️ Error consultando DNI: {e}"


# ========= MÓDULO COMPLETO: evaluación + resolución + certificado =========
def run_permisos_comercio():
    asegurar_dirs()
    _init_dni_state()

    st.markdown(
        """
    <style>
    .block-container { padding-top: 1.0rem; max-width: 980px; }
    .stButton>button { border-radius: 10px; padding: .55rem 1rem; font-weight: 600; }
    .card { border: 1px solid #e5e7eb; border-radius: 16px; padding: 16px; margin-bottom: 12px; background: #0f172a08; }
    .hint { color:#64748b; font-size:.9rem; }
    /* Solo apariencia: el valor real lo limpiamos en Python */
    input[type="text"], textarea {
        text-transform: uppercase;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("🧾 Permisos Ambulatorios")
    st.caption(
        "Completa **una sola vez** (Evaluación). "
        "Resolución y Certificado reutilizan automáticamente esos datos."
    )

    # Rutas plantillas
    TPL_EVAL = "plantillas/evaluacion_ambulante.docx"
    TPL_RES_NUEVO = "plantillas/resolucion_nuevo.docx"
    TPL_RES_DENTRO = "plantillas/resolucion_dentro_tiempo.docx"
    TPL_RES_FUERA = "plantillas/resolucion_fuera_tiempo.docx"
    TPL_CERT = "plantillas/certificado.docx"

    # ---------- Módulo 1: EVALUACIÓN ----------
    st.header("Módulo 1 · Evaluación")
    st.markdown('<div class="card">', unsafe_allow_html=True)

    # ----- 1.1 Selección de Documento Simple pendiente (opcional) -----
    st.subheader("1.1 Seleccionar Documento Simple pendiente (opcional)")

    try:
        df_docs = documentos_para_evaluacion()
    except Exception as e:
        df_docs = pd.DataFrame()
        st.error(f"No se pudo leer Documentos_CA: {e}")

    if df_docs is None or df_docs.empty:
        st.caption("No hay Documentos Simples procedentes pendientes.")
    else:
        opciones = [
            f"{row['N° DE DOCUMENTO SIMPLE']} · {row['NOMBRE Y APELLIDO']} "
            f"({row['ASUNTO']})"
            for _, row in df_docs.iterrows()
        ]
        idx_sel = st.selectbox(
            "Documentos Simples para evaluar",
            options=list(range(len(opciones))),
            format_func=lambda i: opciones[i],
            key="idx_ds_eval",
        )

        if st.button("📥 Cargar datos del D.S. seleccionado"):
            fila = df_docs.iloc[int(idx_sel)]

            st.session_state["ds"] = str(
                fila.get("N° DE DOCUMENTO SIMPLE", "")
            )
            st.session_state["nombre"] = to_upper(
                fila.get("NOMBRE Y APELLIDO", "")
            )
            st.session_state["dni"] = str(fila.get("DNI", "")).strip()
            st.session_state["domicilio"] = to_upper(
                fila.get("DOMICILIO FISCAL", "")
            )
            st.session_state["ubicacion"] = to_upper(
                fila.get("UBICACIÓN A SOLICITAR", "")
            )
            st.session_state["coordenadas"] = ""
            st.session_state["telefono"] = str(
                fila.get("N° DE CELULAR", "")
            ).strip()

            # --- NUEVO: procesar GIRO del D.S. ---
            giro_motivo_raw = str(
                fila.get("GIRO O MOTIVO DE LA SOLICITUD", "")
            ).strip()

            # Por defecto, referencia vacía (ahí ya NO debe ir el giro)
            st.session_state["referencia"] = ""

            # Buscamos qué giros del catálogo aparecen dentro del texto guardado
            labels_giro = _labels_from_raw_giro(giro_motivo_raw)

            if labels_giro:
                # Usamos el primer giro encontrado como seleccionado en el combo
                label_principal = labels_giro[0]
                st.session_state["giro_label"] = label_principal
                st.session_state["giro_label_custom_source"] = label_principal

                # Armamos la descripción completa para las plantillas ({{giro}})
                descripciones = []
                for lab in labels_giro:
                    info = _label_to_info(lab)
                    if info:
                        descripciones.append(info["giro"])
                if descripciones:
                    # Ej.: "Bebidas saludables... y Sándwiches."
                    st.session_state["giro_texto_custom"] = " y ".join(
                        descripciones
                    )
            else:
                # Si no coincide con ningún giro estándar,
                # lo mandamos a referencia como texto libre
                st.session_state["referencia"] = to_upper(giro_motivo_raw)

            st.session_state["fecha_ingreso"] = _parse_fecha_ddmmaaaa(
                fila.get("FECHA DE INGRESO", "")
            )

            st.success(
                "Datos del Documento Simple cargados en el formulario."
            )


    st.markdown("---")

    # ----- 1.2 Formulario de Evaluación -----

    dni = st.text_input(
        "DNI / CE* (8 o 9 dígitos)",
        key="dni",
        value=st.session_state.get("dni", ""),
        max_chars=9,
        placeholder="#########",
        on_change=_cb_autocomplete_dni,
    )
    dni_clean = (dni or "").strip()
    if dni_clean.isdigit() and len(dni_clean) == 8:
        st.caption("Tipo detectado: DNI")
    elif dni_clean.isdigit() and len(dni_clean) == 9:
        st.caption("Tipo detectado: CE")

    msg_dni = (st.session_state.get("dni_lookup_msg") or "").strip()
    if msg_dni:
        if msg_dni.startswith("✅"):
            st.success(msg_dni)
        else:
            st.warning(msg_dni)

    nombre = text_input_upper(
        "Solicitante (Nombre completo)*",
        key="nombre",
        value=st.session_state.get("nombre", ""),
    )

    sexo = st.selectbox(
        "Género de la persona*",
        ["Femenino", "Masculino"],
        key="sexo",
        index=0 if st.session_state.get("sexo", "Femenino") == "Femenino" else 1,
    )

    cod_evaluacion = text_input_upper(
        "Código de evaluación*",
        key="cod_evaluacion",
        value=st.session_state.get("cod_evaluacion", ""),
        placeholder="Ej: 121, 132, 142...",
    )

    if dni and (not _doc_identidad_valido(dni)):
        st.error("⚠️ El documento debe tener 8 (DNI) o 9 (CE) dígitos numéricos")

    ds = text_input_upper(
        "Documento Simple (DS)",
        key="ds",
        value=st.session_state.get("ds", ""),
        placeholder="Ej.: 123 (opcional)",
    )
    domicilio = text_input_upper(
        "Domicilio fiscal*",
        key="domicilio",
        value=st.session_state.get("domicilio", ""),
    )

    c1, c2 = st.columns(2)
    with c1:
        fecha_ingreso = st.date_input(
            "Fecha de ingreso*",
            key="fecha_ingreso",
            value=st.session_state.get("fecha_ingreso", None),
            format="DD/MM/YYYY",
        )
    with c2:
        fecha_evaluacion = st.date_input(
            "Fecha de evaluación*",
            key="fecha_evaluacion",
            value=st.session_state.get("fecha_evaluacion", None),
            format="DD/MM/YYYY",
        )

    giro_label = st.selectbox(
        "Giro solicitado* (según Ordenanza)",
        GIROS_OPCIONES,
        key="giro_label",
    )

    giro_info = _label_to_info(giro_label)
    giro_texto_base = giro_info["giro"] if giro_info else ""
    giro_custom = st.session_state.get("giro_texto_custom", "")
    giro_custom_source = st.session_state.get("giro_label_custom_source")

    # Si el texto custom viene del mismo giro que está seleccionado -> usarlo
    if giro_custom and giro_custom_source == giro_label:
        giro_texto = giro_custom
    else:
        giro_texto = giro_texto_base

    rubro_num = giro_info["rubro"] if giro_info else ""
    codigo_rubro = giro_info["codigo"] if giro_info else ""

    if rubro_num and codigo_rubro:
        st.caption(f"Se usará el rubro {rubro_num} con el código {codigo_rubro}.")
    else:
        st.caption("Selecciona un giro válido del catálogo.")

    ubicacion = text_input_upper(
        "Ubicación*",
        key="ubicacion",
        value=st.session_state.get("ubicacion", ""),
        placeholder="Av./Jr./Parque..., sin 'Distrito de Pachacámac'",
    )
    coordenadas = st.text_input(
        "Coordenadas* (lat, lon)",
        key="coordenadas",
        value=st.session_state.get("coordenadas", ""),
        placeholder="Ej.: -12.158784, -76.887945",
    ).strip()
    referencia = text_input_upper(
        "Referencia (opcional)",
        key="referencia",
        value=st.session_state.get("referencia", ""),
    )
    horario_eval = text_input_upper(
        "Horario (opcional)",
        key="horario",
        value=st.session_state.get("horario", ""),
        placeholder="Ej.: 16:00 A 21:00 HORAS",
    )

    telefono = st.text_input(
        "N° de teléfono (solo BD, no se imprime en plantillas)",
        key="telefono",
        value=st.session_state.get("telefono", ""),
        placeholder="Ej.: 987654321",
    )

    c3, c4 = st.columns(2)
    with c3:
        tiempo_num = st.number_input(
            "Tiempo*",
            key="tiempo",
            value=st.session_state.get("tiempo", 1),
            min_value=1,
            step=1,
        )
    with c4:
        plazo_unidad = st.selectbox(
            "Plazo*",
            ["meses", "años"],
            key="plazo",
            index=(
                ["meses", "años"].index(st.session_state.get("plazo", "meses"))
                if st.session_state.get("plazo", "meses") in ["meses", "años"]
                else 0
            ),
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("🧾 Generar Evaluación (.docx)"):
        falt = []
        req = {
            "cod_evaluacion": cod_evaluacion,
            "nombre": nombre,
            "dni": dni,
            "domicilio": domicilio,
            "giro": giro_texto,
            "ubicacion": ubicacion,
            "coordenadas": coordenadas,
        }
        for k, v in req.items():
            if not isinstance(v, str) or not v.strip():
                falt.append(k)
        if not fecha_ingreso:
            falt.append("fecha_ingreso")
        if not fecha_evaluacion:
            falt.append("fecha_evaluacion")
        if dni and (not _doc_identidad_valido(dni)):
            st.error("Documento inválido: usa 8 (DNI) o 9 (CE) dígitos")
        elif not _coordenadas_validas(coordenadas):
            st.error(
                "Coordenadas inválidas. Usa el formato: lat, lon (ej.: -12.158784, -76.887945)."
            )
        elif falt:
            st.error("Faltan campos: " + ", ".join(falt))
        else:
            ctx_eval = {
                "sexo": sexo,
                "cod_evaluacion": cod_evaluacion.strip(),
                "nombre": to_upper(nombre),
                "dni": dni.strip(),
                "ds": (ds or "").strip(),
                "domicilio": to_upper(domicilio),
                # En evaluación va en formato corto (DD/MM/YYYY)
                "fecha_ingreso": fmt_fecha_corta(fecha_ingreso),
                "fecha_evaluacion": fmt_fecha_larga(fecha_evaluacion),
                "giro": giro_texto,
                "ubicacion": ubicacion.strip(),
                "coordenadas": coordenadas,
                "referencia": to_upper(referencia),
                "horario": horario_eval.strip(),
                "tiempo": int(tiempo_num),
                "plazo": _label_plazo(int(tiempo_num), plazo_unidad),
                "rubro": rubro_num,
                "codigo_rubro": codigo_rubro,
                "telefono": telefono.strip(),
                "fecha_ingreso_raw": str(fecha_ingreso) if fecha_ingreso else "",
                "fecha_evaluacion_raw": str(fecha_evaluacion)
                if fecha_evaluacion
                else "",
            }
            st.session_state["eval_ctx"] = ctx_eval
            anio_eval = pd.to_datetime(fecha_evaluacion).year
            render_doc(
                ctx_eval,
                f"EV. N° {cod_evaluacion}-{anio_eval}_{to_upper(nombre)}",
                TPL_EVAL,
            )

    st.markdown("---")

    # ---------- Módulo 2: RESOLUCIÓN ----------
    st.header("Módulo 2 · Resolución")
    st.markdown('<div class="card">', unsafe_allow_html=True)

    eva = st.session_state.get("eval_ctx", {})
    if not eva:
        st.warning(
            "Primero completa y guarda la **Evaluación** (Módulo 1). "
            "Aquí solo pedimos lo propio de la Resolución."
        )
    else:
        res_tipo = st.selectbox(
            "Tipo de resolución / plantilla",
            ["NUEVO", "DENTRO_DE_TIEMPO", "FUERA_DE_TIEMPO"],
            index=0,
        )
        c0 = st.columns(2)
        with c0[0]:
            cod_resolucion = text_input_upper(
                "N° de resolución*",
                key="cod_resolucion",
                value=st.session_state.get("cod_resolucion", ""),
                placeholder="Ej: 456",
            )
        with c0[1]:
            fecha_resolucion = st.date_input(
                "Fecha de resolución*",
                key="fecha_resolucion",
                value=st.session_state.get("fecha_resolucion", None),
                format="DD/MM/YYYY",
            )

        st.markdown("**Vigencia de la autorización**")
        cv = st.columns(2)
        with cv[0]:
            res_vig_ini = st.date_input(
                "Inicio*",
                key="res_vig_ini",
                value=st.session_state.get("res_vig_ini", None),
                format="DD/MM/YYYY",
            )
        with cv[1]:
            res_vig_fin = st.date_input(
                "Fin*",
                key="res_vig_fin",
                value=st.session_state.get("res_vig_fin", None),
                format="DD/MM/YYYY",
            )

        c6 = st.columns(2)
        with c6[0]:
            cod_certificacion = text_input_upper(
                "N° de Certificado*",
                key="cod_certificacion",
                value=st.session_state.get("cod_certificacion", ""),
                placeholder="Ej: 789",
            )
        with c6[1]:
            antiguo_certificado = text_input_upper(
                "N° de Certificado anterior (opcional)",
                key="antiguo_certificado",
                value=st.session_state.get("antiguo_certificado", ""),
                placeholder="Ej: 121",
            )
            if antiguo_certificado and not str(antiguo_certificado).isdigit():
                st.error("El certificado anterior debe ser solo números (ej.: 121)")

        c7 = st.columns(2)
        with c7[0]:
            fecha_cert_ant_emision = st.date_input(
                "Fecha emitida cert. anterior (opcional)",
                key="fecha_cert_ant_emision",
                value=st.session_state.get("fecha_cert_ant_emision", None),
                format="DD/MM/YYYY",
            )
        with c7[1]:
            fecha_cert_ant_cad = st.date_input(
                "Fecha caducidad cert. anterior (opcional)",
                key="fecha_cert_ant_cad",
                value=st.session_state.get("fecha_cert_ant_cad", None),
                format="DD/MM/YYYY",
            )

        genero, genero2, genero3, sr = genero_labels(eva.get("sexo", "Femenino"))
        st.markdown("**Datos importados desde Evaluación (solo lectura):**")
        st.write(
            {
                "DS": eva.get("ds", ""),
                "Nombre": eva.get("nombre", ""),
                "DNI": eva.get("dni", ""),
                "Domicilio": eva.get("domicilio", "") + "-PACHACAMAC",
                "Ubicación": eva.get("ubicacion", ""),
                "Coordenadas": eva.get("coordenadas", ""),
                "Giro": eva.get("giro", ""),
                "Rubro": eva.get("rubro", ""),
                "Código de rubro": eva.get("codigo_rubro", ""),
                "Horario": eva.get("horario", ""),
                "Código de Evaluación": eva.get("cod_evaluacion", ""),
                "Fecha de Evaluación": eva.get("fecha_evaluacion", ""),
                "Tiempo": eva.get("tiempo", ""),
                "Plazo": eva.get("plazo", ""),
                "Teléfono": eva.get("telefono", ""),
                "Género -> (genero, genero2, genero3, sr)": (
                    genero,
                    genero2,
                    genero3,
                    sr,
                ),
            }
        )

        with st.expander("✏️ Ediciones rápidas (opcional)"):
            st.info("Por defecto NO necesitas tocar nada aquí.")
            eva["ds"] = text_input_upper(
                "DS (override opcional)", key="eva_ds_override", value=eva.get("ds", "")
            )
            eva["nombre"] = to_upper(
                st.text_input(
                    "Nombre (override opcional)", value=eva.get("nombre", "")
                )
            )
            eva["dni"] = st.text_input(
                "DNI (override opcional)",
                value=eva.get("dni", ""),
                max_chars=9,
            )
            eva["domicilio"] = to_upper(
                st.text_input(
                    "Domicilio (override opcional)", value=eva.get("domicilio", "")
                )
            )
            eva["ubicacion"] = to_upper(
                st.text_input(
                    "Ubicación (override opcional)", value=eva.get("ubicacion", "")
                )
            )
            eva["coordenadas"] = st.text_input(
                "Coordenadas (override opcional)",
                value=eva.get("coordenadas", ""),
                placeholder="Ej.: -12.158784, -76.887945",
            ).strip()
            eva["giro"] = to_upper(
                st.text_input(
                    "Giro (override opcional)", value=eva.get("giro", "")
                )
            )
            eva["horario"] = to_upper(
                st.text_input(
                    "Horario (override opcional)", value=eva.get("horario", "")
                )
            )
            eva["telefono"] = st.text_input(
                "Teléfono (override opcional)", value=eva.get("telefono", "")
            )
            st.session_state["eval_ctx"] = eva  # guarda cambios

        def plantilla_por_tipo(t):
            return (
                TPL_RES_NUEVO
                if t == "NUEVO"
                else (TPL_RES_DENTRO if t == "DENTRO_DE_TIEMPO" else TPL_RES_FUERA)
            )

        if st.button("📄 Generar Resolución"):
            falt = []
            for k, v in {
                "cod_resolucion": cod_resolucion,
                "fecha_resolucion": fecha_resolucion,
                "vig_ini": res_vig_ini,
                "vig_fin": res_vig_fin,
                "cod_certificacion": cod_certificacion,
            }.items():
                if v in [None, ""]:
                    falt.append(k)

            if eva.get("dni") and (
                not _doc_identidad_valido(str(eva["dni"]))
            ):
                st.error("Documento inválido (DNI 8 o CE 9 dígitos)")
            elif not eva.get("horario"):
                st.error(
                    "Falta **Horario** en Evaluación (o en Ediciones rápidas)."
                )
            elif falt:
                st.error("Faltan campos de Resolución: " + ", ".join(falt))
            else:
                anio_res = pd.to_datetime(fecha_resolucion).year
                vigencia_texto = build_vigencia(res_vig_ini, res_vig_fin)

                ctx_res = {
                    "cod_resolucion": str(cod_resolucion).strip(),
                    "fecha_resolucion": fmt_fecha_larga(fecha_resolucion),
                    "ds": str(eva.get("ds", "")).strip(),
                    # ahora también en largo
                    "fecha_ingreso": fmt_fecha_larga_de(
                        eva.get("fecha_ingreso_raw")
                    ),
                    "genero": genero,
                    "genero2": genero2,
                    "genero3": genero3,
                    "nombre": to_upper(eva.get("nombre", "")),
                    "dni": str(eva.get("dni", "")).strip(),
                    "domicilio": to_upper(eva.get("domicilio", ""))
                    + "-PACHACAMAC",
                    "giro": str(eva.get("giro", "")).strip(),
                    "rubro": str(eva.get("rubro", "")).strip(),
                    "codigo_rubro": str(eva.get("codigo_rubro", "")).strip(),
                    "ubicacion": str(eva.get("ubicacion", "")).strip(),
                    "horario": str(eva.get("horario", "")).strip(),
                    "cod_evaluacion": str(eva.get("cod_evaluacion", "")).strip(),
                    "fecha_evaluacion": eva.get("fecha_evaluacion", ""),
                    "cod_certificacion": str(cod_certificacion).strip(),
                    "vigencia": vigencia_texto,
                    "antiguo_certificado": str(antiguo_certificado or "").strip(),
                    "tiempo": eva.get("tiempo", ""),
                    "plazo": eva.get("plazo", ""),
                }

                tpl = plantilla_por_tipo(res_tipo)
                render_doc(
                    ctx_res,
                    f"RS. N° {ctx_res['cod_resolucion']}-{anio_res}_{to_upper(eva.get('nombre',''))}",
                    tpl,
                )

    st.markdown("---")

    # ---------- Módulo 3: Certificado ----------
    st.header("Módulo 3 · Certificado")
    st.markdown('<div class="card">', unsafe_allow_html=True)

    fecha_certificado = st.date_input(
        "Fecha del certificado*",
        key="fecha_certificado",
        value=st.session_state.get("fecha_certificado", None),
        format="DD/MM/YYYY",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("🪪 Generar Certificado"):
        eva = st.session_state.get("eval_ctx", {})
        if not eva:
            st.error(
                "Primero completa y guarda la **Evaluación** y la "
                "**Resolución** (fechas/vigencias)."
            )
        else:
            v_cod_cert = st.session_state.get("cod_certificacion", "")
            v_vig_ini = st.session_state.get("res_vig_ini", None)
            v_vig_fin = st.session_state.get("res_vig_fin", None)
            _, _, _, sr = genero_labels(eva.get("sexo", "Femenino"))

            falt = []
            if not v_cod_cert:
                falt.append("cod_certificacion")
            if not fecha_certificado:
                falt.append("fecha_certificado")
            if not eva.get("horario"):
                falt.append("horario (en Evaluación)")
            if not v_vig_ini or not v_vig_fin:
                falt.append("vigencia Inicio/Fin (en Resolución)")
            if falt:
                st.error("Faltan campos: " + ", ".join(falt))
            else:
                anio_cert = pd.to_datetime(fecha_certificado).year
                ctx_cert = {
                    "codigo_certificado": str(v_cod_cert).strip(),
                    "ds": str(eva.get("ds", "")).strip(),
                    "sr": sr,
                    "nombre": to_upper(eva.get("nombre", "")),
                    "dni": str(eva.get("dni", "")).strip(),
                    "ubicacion": str(eva.get("ubicacion", "")).strip(),
                    "referencia": to_upper(eva.get("referencia", "")),
                    "giro": str(eva.get("giro", "")).strip(),
                    "horario": str(eva.get("horario", "")).strip(),
                    "tiempo": eva.get("tiempo", ""),
                    "plazo": eva.get("plazo", ""),
                    "vigencia2": build_vigencia2(v_vig_ini, v_vig_fin),
                    "fecha_certificado": fmt_fecha_larga(fecha_certificado),
                }
                render_doc(
                    ctx_cert,
                    f"AU. {ctx_cert['codigo_certificado']}-{anio_cert}_{to_upper(eva.get('nombre',''))}",
                    TPL_CERT,
                )

    # ---------- Módulo 4: Base de Datos (Google Sheets) ----------
    st.markdown("---")
    st.header("Módulo 4 · Base de Datos (Google Sheets)")
    st.markdown('<div class="card">', unsafe_allow_html=True)

    st.subheader("4.1 Guardar TODO en BD (Evaluación + Resolución + Certificado)")

    if st.button("💾 Guardar TODO en BD (Google Sheets)"):
        eva = st.session_state.get("eval_ctx", {})
        if not eva:
            st.error(
                "Primero genera la **Evaluación**, la **Resolución** "
                "y el **Certificado** (fechas/vigencias)."
            )
        else:
            cod_resolucion_val = st.session_state.get("cod_resolucion", "")
            fecha_resolucion_val = st.session_state.get("fecha_resolucion", None)
            cod_cert_val = st.session_state.get("cod_certificacion", "")
            fecha_cert_val = st.session_state.get("fecha_certificado", None)
            res_vig_ini_val = st.session_state.get("res_vig_ini", None)
            res_vig_fin_val = st.session_state.get("res_vig_fin", None)
            fecha_cert_ant_emision = st.session_state.get(
                "fecha_cert_ant_emision", None
            )
            fecha_cert_ant_cad = st.session_state.get("fecha_cert_ant_cad", None)
            antiguo_cert = st.session_state.get("antiguo_certificado", "")

            falt_bd = []
            if not cod_resolucion_val:
                falt_bd.append("N° de resolución")
            if not fecha_resolucion_val:
                falt_bd.append("Fecha de resolución")
            if not cod_cert_val:
                falt_bd.append("N° de certificado")
            if not fecha_cert_val:
                falt_bd.append("Fecha del certificado")
            if not res_vig_ini_val or not res_vig_fin_val:
                falt_bd.append("Vigencia (inicio/fin) en Resolución")

            if falt_bd:
                st.error(
                    "No se puede guardar en BD porque faltan campos obligatorios: "
                    + ", ".join(falt_bd)
                )
            else:
                try:
                    vigencia_txt = build_vigencia(
                        res_vig_ini_val, res_vig_fin_val
                    )

                    # Evaluaciones_CA
                    append_evaluacion(
                        num_ds=eva.get("ds", ""),
                        nombre_completo=eva.get("nombre", ""),
                        cod_evaluacion=eva.get("cod_evaluacion", ""),
                        fecha_eval=fmt_fecha_corta(
                            eva.get("fecha_evaluacion_raw", "")
                        ),
                        cod_resolucion=str(cod_resolucion_val),
                        fecha_resolucion=fmt_fecha_corta(
                            fecha_resolucion_val
                        ),
                        num_autorizacion=str(cod_cert_val),
                        fecha_autorizacion=fmt_fecha_corta(fecha_cert_val),
                    )

                    # Autorizaciones_CA
                    append_autorizacion(
                        fecha_ingreso=fmt_fecha_corta(
                            eva.get("fecha_ingreso_raw", "")
                        ),
                        ds=eva.get("ds", ""),
                        nombre=eva.get("nombre", ""),
                        dni=eva.get("dni", ""),
                        genero=eva.get("sexo", ""),
                        domicilio_fiscal=eva.get("domicilio", ""),
                        certificado_anterior=str(antiguo_cert or ""),
                        fecha_emitida_cert_anterior=fmt_fecha_corta(
                            fecha_cert_ant_emision
                        ),
                        fecha_caducidad_cert_anterior=fmt_fecha_corta(
                            fecha_cert_ant_cad
                        ),
                        num_eval=eva.get("cod_evaluacion", ""),
                        fecha_eval=fmt_fecha_corta(
                            eva.get("fecha_evaluacion_raw", "")
                        ),
                        num_resolucion=str(cod_resolucion_val),
                        fecha_resolucion=fmt_fecha_corta(
                            fecha_resolucion_val
                        ),
                        num_certificado=str(cod_cert_val),
                        fecha_emitida_cert=fmt_fecha_corta(fecha_cert_val),
                        vigencia_autorizacion=vigencia_txt,
                        lugar_venta=eva.get("ubicacion", ""),
                        coordenadas=eva.get("coordenadas", ""),
                        referencia=eva.get("referencia", ""),
                        giro=eva.get("giro", ""),
                        horario=eva.get("horario", ""),
                        telefono=eva.get("telefono", ""),
                        tiempo=str(eva.get("tiempo", "")),
                        plazo=str(eva.get("plazo", "")),
                    )

                    if eva.get("ds"):
                        actualizar_estado_documento(
                            eva.get("ds", ""), "AUTORIZADO"
                        )

                    st.success(
                        "Evaluación, Resolución y Certificado guardados en Google Sheets."
                    )
                except Exception as e:
                    tb = traceback.format_exc()
                    st.error(f"No se pudo guardar todo en BD: {e}")
                    st.code(tb, language="python")

    st.markdown("---")

    st.subheader("4.2 Ver registros en Google Sheets (solo lectura)")

    with st.expander("📊 Ver tablas de Evaluaciones y Autorizaciones"):
        try:
            tabs = st.tabs(["Evaluaciones_CA", "Autorizaciones_CA"])

            with tabs[0]:
                df_eva = leer_evaluaciones()
                if df_eva.empty:
                    st.info("No hay registros en Evaluaciones_CA.")
                else:
                    st.dataframe(df_eva, use_container_width=True)

            with tabs[1]:
                df_auto = leer_autorizaciones()
                if df_auto.empty:
                    st.info("No hay registros en Autorizaciones_CA.")
                else:
                    st.dataframe(df_auto, use_container_width=True)

        except Exception as e:
            st.error(f"No se pudo leer las tablas de Google Sheets: {e}")

    st.markdown("</div>", unsafe_allow_html=True)

    # ---------- Ayuda ----------
    with st.expander("ℹ️ Llaves por plantilla (qué se llena)"):
        st.markdown(
            """
**Evaluación (`evaluacion_ambulante.docx`):**  
{{cod_evaluacion}}, {{nombre}}, {{dni}}, {{ds}}, {{domicilio}},  
{{fecha_ingreso}}, {{fecha_evaluacion}}, {{giro}}, {{ubicacion}},  
{{referencia}}, {{horario}}, {{tiempo}}, {{plazo}}, {{rubro}}, {{codigo_rubro}}

**Resolución (NUEVO / DENTRO / FUERA):**  
{{cod_resolucion}}, {{fecha_resolucion}},  
{{ds}}, {{fecha_ingreso}},  
{{genero}}, {{genero2}}, {{genero3}},  
{{nombre}}, {{dni}}, {{domicilio}},  
{{giro}}, {{rubro}}, {{codigo_rubro}}, {{ubicacion}}, {{horario}},  
{{cod_evaluacion}}, {{fecha_evaluacion}},  
{{cod_certificacion}}, {{vigencia}}, {{antiguo_certificado}},  
{{tiempo}}, {{plazo}}

**Certificado (`certificado.docx`):**  
{{codigo_certificado}}, {{ds}},  
{{sr}}, {{nombre}}, {{dni}},  
{{ubicacion}}, {{referencia}}, {{giro}},  
{{horario}},  
{{tiempo}}, {{plazo}},  
{{vigencia2}},  
{{fecha_certificado}}
"""
        )


if __name__ == "__main__":
    st.set_page_config(
        page_title="Permisos (Evaluación, Resolución, Certificado)",
        page_icon="🧾",
        layout="centered",
    )
    run_permisos_comercio()
