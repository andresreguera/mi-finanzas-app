import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mi Cartera", page_icon="💰", layout="centered")

# --- CONEXIÓN SEGURA (VERSIÓN TOML) ---
@st.cache_resource
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # CAMBIO CLAVE: Ya no usamos json.loads(). 
        # Streamlit lee directamente la configuración que pegaste en Secrets como un diccionario.
        creds_dict = st.secrets["google_creds"]
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Abre la hoja. Asegúrate de que se llame igual en Google Sheets.
        sheet = client.open("Finanzas_DB").sheet1
        return sheet
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return None

# Intentamos conectar
hoja = conectar_google_sheets()

# Si falla la conexión, paramos la app para no mostrar errores feos
if not hoja:
    st.stop()

# --- TÍTULO ---
st.title("💰 Tracker Financiero")

# --- CÁLCULOS Y MÉTRICAS (KPIs) ---
try:
    registros = hoja.get_all_records()
    df = pd.DataFrame(registros)
except:
    df = pd.DataFrame()

# Si hay datos, calculamos. Si no, todo es 0.
if not df.empty and 'Monto' in df.columns:
    # Convertimos a números por si acaso Google Sheets lo guardó como texto
    df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce').fillna(0)
    
    ingresos = df[df['Monto'] > 0]['Monto'].sum()
    gastos = df[df['Monto'] < 0]['Monto'].sum()
    saldo_total = df['Monto'].sum()
else:
    ingresos = 0
    gastos = 0
    saldo_total = 0

# Mostramos las tarjetas de resumen
col1, col2, col3 = st.columns(3)
col1.metric("Saldo Total", f"{saldo_total:.2f}€")
col2.metric("Ingresos", f"{ingresos:.2f}€", delta_color="normal")
col3.metric("Gastos", f"{gastos:.2f}€", delta=f"{gastos:.2f}€", delta_color="inverse")

st.divider()

# --- FORMULARIO DE ENTRADA ---
st.subheader("📝 Nuevo Movimiento")

with st.form("entrada_datos", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    with col_a:
        fecha = st.date_input("Fecha", datetime.now())
        monto = st.number_input("Monto (€)", min_value=0.0, step=0.01, format="%.2f")
    with col_b:
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        categoria = st.selectbox("Categoría", [
            "Comida", "Transporte", "Vivienda", "Ocio", 
            "Salud", "Ropa", "Ahorro", "Otros", "Nómina"
        ])
        
    concepto = st.text_input("Descripción", placeholder="Ej: Supermercado")
    guardar = st.form_submit_button("💾 Guardar Movimiento", use_container_width=True)

# --- LÓGICA AL GUARDAR ---
if guardar:
    if monto > 0:
        try:
            # Si es Gasto, lo convertimos a negativo para facilitar sumas
            valor_final = monto if tipo == "Ingreso" else -monto
            
            # Preparamos la fila para Excel
            datos = [str(fecha), categoria, concepto, valor_final, tipo]
            
            with st.spinner("Guardando en la nube..."):
                hoja.append_row(datos)
            
            st.success("¡Guardado correctamente!")
            # Recargamos la página para ver el saldo actualizado al instante
            st.rerun()
            
        except Exception as e:
            st.error(f"Error al guardar: {e}")
    else:
        st.warning("El monto debe ser mayor a 0")

# --- HISTORIAL ---
st.subheader("📜 Últimos 5 Movimientos")
if not df.empty:
    # Mostramos los últimos 5, ordenados para ver el más reciente arriba
    st.dataframe(
        df.tail(5).sort_index(ascending=False)[['Fecha', 'Categoria', 'Monto', 'Concepto']], 
        use_container_width=True,
        hide_index=True
    )