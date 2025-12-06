import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Mi Finanzas Pro", page_icon="📈", layout="centered")

# --- FUNCIÓN 1: PINTAR BONITO (Para que lo veas bien) ---
def formato_euros(valor):
    try:
        if valor is None: return "0,00 €"
        # Esto pone 1.234,56 € (Puntos para miles, coma para decimales)
        texto = "{:,.2f}".format(float(valor))
        return texto.replace(",", "X").replace(".", ",").replace("X", ".") + " €"
    except:
        return "0,00 €"

# --- FUNCIÓN 2: LEER DEL EXCEL (EL ARREGLO ESTÁ AQUÍ) ---
def procesar_dato_del_excel(dato):
    """
    Esta función es la clave.
    1. Si Google nos da un número (1.11), lo devuelve tal cual.
    2. Si Google nos da texto ("1.11" o "1,11"), lo arregla.
    """
    if isinstance(dato, (int, float)):
        return float(dato) # ¡Si ya es número, no lo tocamos! (Evita el error 1.11 -> 111)
    
    texto = str(dato).strip()
    if not texto: return 0.0
    
    try:
        # Si tiene coma, asumimos formato europeo: 1.000,50
        if "," in texto:
            # Quitamos puntos de miles y cambiamos coma por punto
            texto = texto.replace(".", "").replace(",", ".")
        return float(texto)
    except:
        return 0.0

# --- FUNCIÓN 3: ESCRIBIR (INPUT) ---
def limpiar_input_usuario(texto_input):
    if not texto_input: return 0.0
    texto = str(texto_input).strip()
    try:
        # Input: "1.000,50" -> Quitamos punto, cambiamos coma -> 1000.50
        texto = texto.replace(".", "").replace(",", ".")
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
        st.error(f"Error: {e}")
        return None

libro = conectar_google_sheets()
if not libro: st.stop()

try:
    hoja_movimientos = libro.sheet1
    hoja_objetivos = libro.worksheet("Objetivos")
except:
    st.error("⚠️ Crea una hoja llamada 'Objetivos' en tu Excel.")
    st.stop()

# --- INTERFAZ ---
st.title("📈 Mi Planificador Financiero")
tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos"])

# ==========================================================
# PESTAÑA 1: DIARIO
# ==========================================================
with tab1:
    try:
        registros = hoja_movimientos.get_all_records()
        df = pd.DataFrame(registros)
    except: df = pd.DataFrame()

    # --- CÁLCULOS SEGURAS ---
    ingresos, gastos, saldo_total = 0.0, 0.0, 0.0

    if not df.empty and 'Monto' in df.columns:
        # Aplicamos la función inteligente a cada fila
        df['Monto_Num'] = df['Monto'].apply(procesar_dato_del_excel)
        
        ingresos = df[df['Monto_Num'] > 0]['Monto_Num'].sum()
        gastos = df[df['Monto_Num'] < 0]['Monto_Num'].sum()
        saldo_total = df['Monto_Num'].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Saldo Actual", formato_euros(saldo_total))
    col2.metric("Ingresos", formato_euros(ingresos))
    col3.metric("Gastos", formato_euros(gastos), delta_color="inverse")

    st.divider()

    st.subheader("Nuevo Movimiento")
    with st.form("entrada"):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha", datetime.now())
        monto_txt = c1.text_input("Monto (€)", placeholder="Ej: 1,11")
        
        tipo = c2.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo Mensual"])
        cat = c2.selectbox("Categoría", ["Comida", "Transporte", "Vivienda", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        # Previsualización
        monto_real = limpiar_input_usuario(monto_txt)
        st.caption(f"👀 Se guardará: {formato_euros(monto_real)}")
        
        if st.form_submit_button("💾 Guardar"):
            if monto_real > 0:
                final = -monto_real if tipo == "Gasto" else monto_real
                hoja_movimientos.append_row([str(fecha), cat, desc, final, tipo])
                st.success("¡Guardado!")
                st.rerun()
            else:
                st.warning("El monto debe ser mayor a 0")

    # Historial
    if not df.empty:
        df_show = df.copy()
        df_show['Monto'] = df_show['Monto_Num'].apply(formato_euros)
        st.dataframe(df_show[['Fecha', 'Categoria', 'Monto', 'Concepto']].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# ==========================================================
# PESTAÑA 2: OBJETIVOS
# ==========================================================
with tab2:
    st.header("🎯 Metas")
    with st.form("meta"):
        nom = st.text_input("Objetivo")
        c_txt = st.text_input("Cantidad (€)", placeholder="Ej: 1500,00")
        f_lim = st.date_input("Fecha Límite")
        c_real = limpiar_input_usuario(c_txt)
        
        if st.form_submit_button("Crear Meta") and c_real > 0:
            hoja_objetivos.append_row([nom, c_real, str(f_lim), str(date.today())])
            st.rerun()

    # Lista Objetivos
    try:
        data = hoja_objetivos.get_all_records()
        df_obj = pd.DataFrame(data)
    except: df_obj = pd.DataFrame()

    if not df_obj.empty:
        st.divider()
        sueldo_txt = st.text_input("💰 Tu Sueldo (opcional)", value="1500,00")
        sueldo = limpiar_input_usuario(sueldo_txt)

        for i, row in df_obj.iterrows():
            meta = procesar_dato_del_excel(row['Monto_Meta'])
            dias = (pd.to_datetime(row['Fecha_Limite']).date() - date.today()).days
            
            # Evitar división por cero
            meses = max(dias / 30, 0.1) 
            ahorro = meta / meses
            
            with st.container(border=True):
                cc1, cc2 = st.columns([3,1])
                cc1.markdown(f"### {row['Objetivo']}")
                cc1.write(f"Meta: **{formato_euros(meta)}**")
                
                if dias > 0:
                    pct = (ahorro / sueldo * 100) if sueldo > 0 else 0
                    msg = f"Ahorra **{formato_euros(ahorro)}/mes** ({pct:.0f}% sueldo)"
                    if pct > 40: cc1.error(msg)
                    elif pct > 20: cc1.warning(msg)
                    else: cc1.success(msg)
                else:
                    cc1.success("¡Tiempo finalizado!")