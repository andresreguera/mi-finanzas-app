import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Mi Finanzas Pro", page_icon="📈", layout="centered")

# --- FUNCIÓN 1: PINTAR BONITO (Salida en pantalla) ---
def formato_euros(valor):
    """
    Convierte el número 4000.50 en texto "4.000,50 €"
    """
    try:
        if valor is None: return "0,00 €"
        # Primero formato estándar (4,000.50)
        texto = "{:,.2f}".format(float(valor))
        # Invertimos símbolos: Coma a Punto, Punto a Coma
        return texto.replace(",", "X").replace(".", ",").replace("X", ".") + " €"
    except:
        return "0,00 €"

# --- FUNCIÓN 2: LEER DATOS (Aquí estaba el error y aquí está la solución) ---
def leer_dato_seguro(dato):
    """
    Analiza qué nos manda Google Sheets.
    - Si manda el número 1.11 -> Lo dejamos como 1.11 (NO borramos el punto)
    - Si manda texto "1.000,50" -> Lo limpiamos a 1000.50
    """
    # CASO A: Ya es un número (int o float). ¡NO TOCAR!
    if isinstance(dato, (int, float)):
        return float(dato)
    
    # CASO B: Es texto. Aplicamos TU lógica.
    texto = str(dato).strip()
    if not texto: return 0.0
    
    try:
        # 1. Quitamos los puntos (son separadores de miles visuales)
        # "4.000,00" -> "4000,00"
        texto = texto.replace(".", "")
        
        # 2. Cambiamos la coma por punto (para que Python calcule)
        # "4000,00" -> "4000.00"
        texto = texto.replace(",", ".")
        
        return float(texto)
    except:
        return 0.0

# --- FUNCIÓN 3: ESCRIBIR DATOS (Tu Input) ---
def limpiar_input_usuario(texto_input):
    """
    Tus reglas estrictas:
    - 4.000 -> 4000 (Punto se borra)
    - 9,14  -> 9.14 (Coma se vuelve punto)
    """
    if not texto_input: return 0.0
    texto = str(texto_input).strip()
    
    try:
        # Paso 1: Eliminar puntos de miles
        texto = texto.replace(".", "")
        # Paso 2: Convertir coma decimal a punto
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
        st.error(f"Error crítico: {e}")
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
    try:
        registros = hoja_movimientos.get_all_records()
        df = pd.DataFrame(registros)
    except: df = pd.DataFrame()

    ingresos, gastos, saldo_total = 0.0, 0.0, 0.0

    if not df.empty and 'Monto' in df.columns:
        # APLICAMOS LA LECTURA SEGURA FILA POR FILA
        df['Monto_Num'] = df['Monto'].apply(leer_dato_seguro)
        
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
        
        # INPUT DE TEXTO: Para que tú escribas "4.000" o "9,14" libremente
        monto_txt = c1.text_input("Monto (€)", placeholder="Ej: 4.000 o 9,14")
        
        tipo = c2.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo Mensual"])
        cat = c2.selectbox("Categoría", ["Comida", "Transporte", "Vivienda", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        # LÓGICA DE PREVISUALIZACIÓN
        monto_real = limpiar_input_usuario(monto_txt)
        if monto_txt:
            st.caption(f"👀 El sistema leerá: **{formato_euros(monto_real)}**")
        
        if st.form_submit_button("💾 Guardar", use_container_width=True):
            if monto_real > 0:
                final = -monto_real if tipo == "Gasto" else monto_real
                # Guardamos en Sheets
                hoja_movimientos.append_row([str(fecha), cat, desc, final, tipo])
                st.success("¡Guardado!")
                st.rerun()
            else:
                st.warning("Escribe una cantidad válida.")

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
        c_txt = st.text_input("Cantidad (€)", placeholder="Ej: 15.000,00")
        f_lim = st.date_input("Fecha Límite")
        
        c_real = limpiar_input_usuario(c_txt)
        if c_txt: st.caption(f"👀 Meta de: {formato_euros(c_real)}")
        
        if st.form_submit_button("Crear Meta") and c_real > 0:
            hoja_objetivos.append_row([nom, c_real, str(f_lim), str(date.today())])
            st.rerun()

    try:
        data = hoja_objetivos.get_all_records()
        df_obj = pd.DataFrame(data)
    except: df_obj = pd.DataFrame()

    if not df_obj.empty:
        st.divider()
        sueldo_txt = st.text_input("💰 Tu Sueldo (opcional)", value="1.500,00")
        sueldo = limpiar_input_usuario(sueldo_txt)

        for i, row in df_obj.iterrows():
            meta = leer_dato_seguro(row['Monto_Meta'])
            dias = (pd.to_datetime(row['Fecha_Limite']).date() - date.today()).days
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