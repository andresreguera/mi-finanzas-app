import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Mi Finanzas Pro", page_icon="📈", layout="centered")

# --- FUNCIÓN DE FORMATO VISUAL (SOLO PARA LEER) ---
def formato_euros(valor):
    """
    Convierte 4139.14 -> "4.139,14 €"
    """
    try:
        if valor is None: return "0,00 €"
        # 1. Formato estándar con comas para miles (4,139.14)
        texto = "{:,.2f}".format(float(valor))
        # 2. Truco del cambio: Coma por X, Punto por Coma, X por Punto
        # Resultado final: 4.139,14
        return texto.replace(",", "X").replace(".", ",").replace("X", ".") + " €"
    except:
        return "0,00 €"

# --- FUNCIÓN DE LIMPIEZA (PARA ESCRIBIR) ---
def limpiar_input_dinero(texto_input):
    """
    Convierte lo que escribas a un número que Python entienda.
    Regla de Oro: LA COMA ES EL DECIMAL.
    "4.139,14" -> 4139.14
    "4139,14"  -> 4139.14
    "1000"     -> 1000.0
    """
    if not texto_input: return 0.0
    texto = str(texto_input).strip()
    
    try:
        # 1. Quitamos los puntos de los miles (si los pusiste)
        texto = texto.replace(".", "")
        # 2. Cambiamos la coma por punto (para Python)
        texto = texto.replace(",", ".")
        return float(texto)
    except:
        return 0.0

# --- CONEXIÓN ---
@st.cache_resource
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["google_creds"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Finanzas_DB")
    except Exception as e:
        st.error(f"Error conexión: {e}")
        return None

libro = conectar_google_sheets()
if not libro: st.stop()

try:
    hoja_movimientos = libro.sheet1
    hoja_objetivos = libro.worksheet("Objetivos")
except:
    st.error("⚠️ Falta la hoja 'Objetivos' en Google Sheets.")
    st.stop()

# --- INTERFAZ ---
st.title("📈 Mi Planificador Financiero")

tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos"])

# ==========================================================
# PESTAÑA 1: DIARIO
# ==========================================================
with tab1:
    # Cargar datos
    try:
        registros = hoja_movimientos.get_all_records()
        df = pd.DataFrame(registros)
    except:
        df = pd.DataFrame()

    # Cálculos
    ingresos = 0.0
    gastos = 0.0
    saldo_total = 0.0

    if not df.empty and 'Monto' in df.columns:
        # Forzamos conversión numérica segura
        lista_montos = []
        for x in df['Monto']:
            try:
                # Si en el Excel hay textos raros, intentamos arreglarlos
                val = float(str(x).replace(",", ".")) if isinstance(x, str) else float(x)
                lista_montos.append(val)
            except:
                lista_montos.append(0.0)
        
        df['Monto_Num'] = lista_montos
        
        ingresos = df[df['Monto_Num'] > 0]['Monto_Num'].sum()
        gastos = df[df['Monto_Num'] < 0]['Monto_Num'].sum()
        saldo_total = df['Monto_Num'].sum()

    # Tarjetas
    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Actual", formato_euros(saldo_total))
    c2.metric("Ingresos", formato_euros(ingresos))
    c3.metric("Gastos", formato_euros(gastos), delta_color="inverse")

    st.divider()

    # Formulario
    st.subheader("Nuevo Movimiento")
    with st.form("entrada"):
        c_a, c_b = st.columns(2)
        fecha = c_a.date_input("Fecha", datetime.now())
        
        # INPUT DE TEXTO PARA EVITAR PROBLEMAS
        monto_txt = c_a.text_input("Monto (€)", placeholder="Ej: 4139,14", help="Usa la COMA para los decimales")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo Mensual"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Vivienda", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        # CÁLCULO PREVIO PARA QUE VEAS QUÉ VA A PASAR
        monto_real = limpiar_input_dinero(monto_txt)
        st.caption(f"👀 Se guardará como: **{formato_euros(monto_real)}**")
        
        enviar = st.form_submit_button("💾 Guardar Movimiento", use_container_width=True)

    if enviar:
        if monto_real > 0:
            es_gasto = tipo == "Gasto"
            valor_final = -monto_real if es_gasto else monto_real
            
            # Guardamos como float nativo en Google Sheets
            hoja_movimientos.append_row([str(fecha), cat, desc, valor_final, tipo])
            st.success("¡Guardado!")
            st.rerun()
        else:
            st.warning("El monto debe ser mayor a 0")

    # Tabla Historial
    if not df.empty:
        st.subheader("Historial")
        # Copia para visualización bonita
        df_show = df.copy()
        df_show['Monto'] = df_show['Monto_Num'].apply(formato_euros)
        st.dataframe(df_show[['Fecha', 'Categoria', 'Monto', 'Concepto']].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# ==========================================================
# PESTAÑA 2: OBJETIVOS
# ==========================================================
with tab2:
    st.header("🎯 Metas")
    with st.form("obj_form"):
        nom = st.text_input("Meta")
        cant_txt = st.text_input("Cantidad (€)", placeholder="Ej: 1500,50")
        fecha_fin = st.date_input("Fecha Límite")
        
        cant_real = limpiar_input_dinero(cant_txt)
        st.caption(f"👀 Se guardará como: **{formato_euros(cant_real)}**")
        
        if st.form_submit_button("Crear Meta"):
            if cant_real > 0:
                hoja_objetivos.append_row([nom, cant_real, str(fecha_fin), str(date.today())])
                st.rerun()
    
    # Visualización de Metas
    try:
        data = hoja_objetivos.get_all_records()
        df_obj = pd.DataFrame(data)
    except: df_obj = pd.DataFrame()

    if not df_obj.empty:
        st.divider()
        sueldo_txt = st.text_input("💰 Tu Sueldo (para calcular viabilidad)", value="1500,00")
        sueldo = limpiar_input_dinero(sueldo_txt)

        for i, row in df_obj.iterrows():
            # Limpieza robusta al leer del Excel
            try:
                meta_val = float(str(row['Monto_Meta']).replace(",", ".")) if isinstance(row['Monto_Meta'], str) else float(row['Monto_Meta'])
            except: meta_val = 0.0

            dias = (pd.to_datetime(row['Fecha_Limite']).date() - date.today()).days
            meses = max(dias / 30, 0.1)
            ahorro = meta_val / meses
            
            with st.container(border=True):
                c1, c2 = st.columns([3,1])
                c1.markdown(f"### {row['Objetivo']}")
                c1.write(f"Meta: **{formato_euros(meta_val)}** ({dias} días restantes)")
                
                if dias > 0:
                    pct = (ahorro / sueldo * 100) if sueldo > 0 else 0
                    msg = f"Ahorra **{formato_euros(ahorro)}/mes** ({pct:.0f}% de tu sueldo)"
                    if pct > 40: c1.error(msg)
                    elif pct > 20: c1.warning(msg)
                    else: c1.success(msg)
                else:
                    c1.success("¡Tiempo finalizado!")