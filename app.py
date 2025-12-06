import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mi Cartera", page_icon="💰", layout="centered")

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Finanzas_DB").sheet1
    return sheet

try:
    hoja = conectar_google_sheets()
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- TÍTULO ---
st.title("💰 Tracker Financiero")

# --- CÁLCULOS Y MÉTRICAS (LO NUEVO) ---
# 1. Traemos los datos ANTES de mostrar nada para calcular el saldo
registros = hoja.get_all_records()
df = pd.DataFrame(registros)

# 2. Si hay datos, calculamos. Si no, todo es 0.
if not df.empty:
    # Aseguramos que la columna Monto sea numérica
    df['Monto'] = pd.to_numeric(df['Monto'])
    
    ingresos = df[df['Monto'] > 0]['Monto'].sum()
    gastos = df[df['Monto'] < 0]['Monto'].sum()
    saldo_total = df['Monto'].sum()
else:
    ingresos = 0
    gastos = 0
    saldo_total = 0

# 3. Mostramos las tarjetas de colores (KPIs)
col1, col2, col3 = st.columns(3)
col1.metric("Saldo Total", f"{saldo_total:.2f}€")
col2.metric("Ingresos", f"{ingresos:.2f}€", delta_color="normal")
# El delta de gastos lo ponemos en rojo inverso para que se vea la salida de dinero
col3.metric("Gastos", f"{gastos:.2f}€", delta=f"{gastos:.2f}€", delta_color="inverse")

st.divider()

# --- FORMULARIO DE ENTRADA ---
st.subheader("📝 Nuevo Movimiento")

with st.form("entrada_datos", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    with col_a:
        fecha = st.date_input("Fecha", datetime.now())
        monto = st.number_input("Monto (€)", min_value=0.0, step=1.0, format="%.2f")
    with col_b:
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        categoria = st.selectbox("Categoría", [
            "Comida", "Transporte", "Vivienda", "Ocio", 
            "Salud", "Ropa", "Ahorro", "Otros", "Nómina"
        ])
        
    concepto = st.text_input("Descripción", placeholder="Ej: Supermercado")
    guardar = st.form_submit_button("💾 Guardar Movimiento", use_container_width=True)

if guardar:
    if monto > 0:
        valor_final = monto if tipo == "Ingreso" else -monto
        datos = [str(fecha), categoria, concepto, valor_final, tipo]
        hoja.append_row(datos)
        st.success("¡Guardado! Recarga la página para actualizar el saldo.")
        # Truco para recargar la web automáticamente
        st.rerun()
    else:
        st.warning("El monto debe ser mayor a 0")

# --- HISTORIAL RECIENTE ---
st.subheader("📜 Últimos 5 Movimientos")
if not df.empty:
    st.dataframe(df.tail(5).sort_index(ascending=False)[['Fecha', 'Categoria', 'Monto', 'Concepto']], use_container_width=True)