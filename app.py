import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json  # <--- Esta es la clave para leer los secretos

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mi Cartera", page_icon="💰", layout="centered")

# --- CONEXIÓN SEGURA (USANDO SECRETS) ---
@st.cache_resource
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Leemos la credencial desde los secretos de Streamlit (la nube)
        # Esto evita que tengamos que subir el archivo .json a GitHub
        creds_dict = json.loads(st.secrets["google_creds"])
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Asegúrate de que tu hoja en Google Sheets se llame EXACTAMENTE así:
        sheet = client.open("Finanzas_DB").sheet1
        return sheet
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return None

# Intentamos conectar
hoja = conectar_google_sheets()

# Si falla la conexión, paramos la app
if not hoja:
    st.stop()

# --- TÍTULO ---
st.title("💰 Tracker Financiero")

# --- CÁLCULOS Y MÉTRICAS (KPIs) ---
# Traemos los datos para calcular el saldo
try:
    registros = hoja.get_all_records()
    df = pd.DataFrame(registros)
except:
    df = pd.DataFrame()

# Si hay datos, calculamos. Si no, todo es 0.
if not df.empty and 'Monto' in df.columns:
    # Aseguramos que la columna Monto sea numérica
    df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce').fillna(0)
    
    ingresos = df[df['Monto'] > 0]['Monto'].sum()
    gastos = df[df['Monto'] < 0]['Monto'].sum()
    saldo_total = df['Monto'].sum()
else:
    ingresos = 0
    gastos = 0
    saldo_total = 0

# Mostramos las tarjetas
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

# --- LÓGICA DE GUARDADO ---
if guardar:
    if monto > 0:
        try:
            # Si es gasto, lo ponemos negativo
            valor_final = monto if tipo == "Ingreso" else -monto
            
            datos = [str(fecha), categoria, concepto, valor_final, tipo]
            
            with st.spinner("Guardando en la nube..."):
                hoja.append_row(datos)
            
            st.success("¡Guardado correctamente!")
            # Recargar para actualizar el saldo
            st.rerun()
            
        except Exception as e:
            st.error(f"Error al guardar: {e}")
    else:
        st.warning("El monto debe ser mayor a 0")

# --- HISTORIAL ---
st.subheader("📜 Últimos 5 Movimientos")
if not df.empty:
    # Mostramos columnas clave y ordenamos por fecha (o índice) inverso
    st.dataframe(
        df.tail(5).sort_index(ascending=False)[['Fecha', 'Categoria', 'Monto', 'Concepto']], 
        use_container_width=True,
        hide_index=True
    )