import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Finanzas V5", page_icon="💰", layout="centered")

# --- CONEXIÓN ---
@st.cache_resource
def conectar():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = st.secrets["google_creds"]
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, scope)).open("Finanzas_DB")
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

libro = conectar()
hoja1 = libro.sheet1
try:
    hoja_obj = libro.worksheet("Objetivos")
except:
    st.error("Falta hoja 'Objetivos'")
    st.stop()

# --- EL CEREBRO DE LA OPERACIÓN (EUROPEO ESTRICTO) ---
def forzar_formato_europeo(valor):
    """
    Esta función es la solución definitiva.
    Convierte CUALQUIER COSA a un número con decimales correcto.
    
    Reglas:
    - "4139,14" -> 4139.14 (La coma se vuelve punto)
    - "4.139,14" -> 4139.14 (El punto de mil se borra, la coma se vuelve punto)
    - 4139.14 (número) -> 4139.14 (Se queda igual)
    """
    if valor is None or str(valor).strip() == "":
        return 0.0
    
    # 1. Convertimos a texto para analizarlo
    texto = str(valor).strip()
    
    # CASO ESPECIAL: Si Google ya nos da un número puro (float), lo devolvemos
    if isinstance(valor, (int, float)):
        return float(valor)

    try:
        # 2. Si tiene PUNTOS y COMAS (ej: 4.139,14), borramos el punto primero
        if "." in texto and "," in texto:
            texto = texto.replace(".", "") # Queda "4139,14"

        # 3. TRANSFORMACIÓN CLAVE: Cambiamos la COMA por PUNTO
        # "4139,14" se convierte en "4139.14" (Esto es lo que Python entiende)
        texto = texto.replace(",", ".")
        
        return float(texto)
    except:
        return 0.0

def mostrar_euros(numero):
    # Formato visual: 4.139,14 €
    return "{:,.2f} €".format(numero).replace(",", "X").replace(".", ",").replace("X", ".")

# --- INTERFAZ ---
st.title("💰 Mi Cartera (Modo Europeo)")

# --- PESTAÑA PRINCIPAL ---
tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos"])

with tab1:
    # 1. Cargar Datos
    try:
        data = hoja1.get_all_records()
        df = pd.DataFrame(data)
    except: df = pd.DataFrame()

    ingresos, gastos, saldo = 0.0, 0.0, 0.0

    if not df.empty and 'Monto' in df.columns:
        # APLICAMOS LA CONVERSIÓN
        df['Monto_Calc'] = df['Monto'].apply(forzar_formato_europeo)
        
        # Filtros
        ingresos = df[df['Monto_Calc'] > 0]['Monto_Calc'].sum()
        gastos = df[df['Monto_Calc'] < 0]['Monto_Calc'].sum()
        saldo = df['Monto_Calc'].sum()

    # 2. Tarjetas
    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Actual", mostrar_euros(saldo))
    c2.metric("Ingresos", mostrar_euros(ingresos))
    c3.metric("Gastos", mostrar_euros(gastos), delta_color="inverse")

    st.divider()

    # 3. Formulario
    st.subheader("Nuevo Movimiento")
    with st.form("mov"):
        c_a, c_b = st.columns(2)
        fecha = c_a.date_input("Fecha")
        # Input texto para que puedas poner comas
        monto_txt = c_a.text_input("Cantidad (€)", placeholder="Ej: 4139,14")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        # Pre-cálculo para guardar
        val_guardar = forzar_formato_europeo(monto_txt)
        
        # PREVISUALIZACIÓN EN TIEMPO REAL
        if monto_txt:
            st.info(f"🔢 Tú escribes: **{monto_txt}** -> La App guarda: **{val_guardar}**")

        if st.form_submit_button("Guardar"):
            if val_guardar > 0:
                final = -val_guardar if tipo == "Gasto" else val_guardar
                # Guardamos tal cual el valor calculado
                hoja1.append_row([str(fecha), cat, desc, final, tipo])
                st.success("Guardado.")
                st.rerun()
            else:
                st.warning("Introduce una cantidad válida.")

    # 4. TABLA DE LA VERDAD (DEBUG)
    # Esto te mostrará qué está pasando "bajo el capó"
    if not df.empty:
        st.subheader("🔍 Auditoría de Datos")
        st.write("Mira esta tabla para ver si el Excel nos está mandando el dato mal:")
        
        # Preparamos tabla comparativa
        df_debug = df[['Monto', 'Monto_Calc']].copy()
        df_debug['Lo que llega del Excel'] = df_debug['Monto'].astype(str)
        df_debug['Lo que entiende la App'] = df_debug['Monto_Calc'].apply(mostrar_euros)
        
        st.dataframe(df_debug[['Lo que llega del Excel', 'Lo que entiende la App']].tail(5), use_container_width=True)

# --- PESTAÑA OBJETIVOS ---
with tab2:
    st.header("Metas")
    # (Código simplificado de objetivos para no alargar, usa la misma lógica)
    with st.form("obj"):
        nom = st.text_input("Meta")
        obj_txt = st.text_input("Cantidad", placeholder="Ej: 1500,00")
        f_fin = st.date_input("Fecha Límite")
        obj_val = forzar_formato_europeo(obj_txt)
        if st.form_submit_button("Crear") and obj_val > 0:
            hoja_obj.append_row([nom, obj_val, str(f_fin), str(date.today())])
            st.rerun()
    
    try:
        do = hoja_obj.get_all_records()
        dfo = pd.DataFrame(do)
        if not dfo.empty:
            for i, r in dfo.iterrows():
                m = forzar_formato_europeo(r['Monto_Meta'])
                st.info(f"Meta: {row['Objetivo']} - {mostrar_euros(m)}")
    except: pass