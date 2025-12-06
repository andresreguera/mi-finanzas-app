import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Gestor Financiero Pro",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        border-left: 5px solid #ff4b4b;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- LÓGICA DE NEGOCIO Y UTILIDADES ---

def parsear_monto_europeo(valor):
    """
    Convierte strings formato español (1.200,50) a float Python (1200.50).
    Maneja errores y formatos mixtos.
    """
    if valor is None or str(valor).strip() == "":
        return 0.0
    
    # Si ya es número, devolverlo
    if isinstance(valor, (int, float)):
        return float(valor)
    
    texto = str(valor).strip()
    
    try:
        # Lógica estricta:
        # 1. Eliminar puntos de miles (ej: 1.500 -> 1500)
        texto = texto.replace(".", "")
        # 2. Reemplazar coma decimal por punto (ej: 1500,50 -> 1500.50)
        texto = texto.replace(",", ".")
        # 3. Convertir
        return float(texto)
    except ValueError:
        return 0.0

def formatear_moneda(valor):
    """Devuelve string en formato: 1.200,50 €"""
    return "{:,.2f} €".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")

# --- GESTIÓN DE DATOS (CONEXIÓN GOOGLE O LOCAL) ---

@st.cache_resource
def obtener_conexion_google():
    """Intenta conectar con Google Sheets. Devuelve None si falla."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Intenta leer secrets.toml
        if "google_creds" in st.secrets:
            creds_dict = st.secrets["google_creds"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client.open("Finanzas_DB") # Asegúrate que tu Sheet se llama así
        else:
            return None
    except Exception as e:
        return None

def cargar_datos(sheet_obj):
    """Carga datos desde Google Sheet o Local CSV (fallback)"""
    if sheet_obj:
        try:
            worksheet = sheet_obj.sheet1
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error leyendo hoja: {e}")
            return pd.DataFrame()
    else:
        # Modo Local (Si no hay conexión a Google)
        if 'local_data' not in st.session_state:
            # Datos de ejemplo para primera carga
            st.session_state.local_data = pd.DataFrame([
                {"Fecha": str(date.today()), "Categoria": "Ingreso", "Concepto": "Ejemplo Saldo Inicial", "Monto": 1500.00, "Tipo": "Ingreso"},
                {"Fecha": str(date.today()), "Categoria": "Comida", "Concepto": "Ejemplo Supermercado", "Monto": -120.50, "Tipo": "Gasto"}
            ])
        return st.session_state.local_data

def guardar_dato(sheet_obj, fecha, cat, desc, monto, tipo):
    """Guarda en Google Sheet o en sesión local"""
    fila = [str(fecha), cat, desc, monto, tipo]
    
    if sheet_obj:
        try:
            worksheet = sheet_obj.sheet1
            # Importante: Convertir monto a float o string con formato punto para Google Sheets (depende de tu config regional de Sheet)
            # Recomendación: Mandar string con coma para que Sheets en español lo entienda como número
            monto_str_sheets = str(monto).replace(".", ",") 
            worksheet.append_row([str(fecha), cat, desc, monto_str_sheets, tipo])
            return True
        except Exception as e:
            st.error(f"Error guardando en Google: {e}")
            return False
    else:
        # Guardado Local
        nuevo_df = pd.DataFrame([{"Fecha": str(fecha), "Categoria": cat, "Concepto": desc, "Monto": monto, "Tipo": tipo}])
        st.session_state.local_data = pd.concat([st.session_state.local_data, nuevo_df], ignore_index=True)
        return True

# --- INICIO DE LA APP ---

# 1. Configurar Conexión
libro = obtener_conexion_google()
modo_offline = libro is None

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    if modo_offline:
        st.warning("⚠️ Modo Local (Sin conexión a Google)")
        st.info("Configura '.streamlit/secrets.toml' para conectar tu Google Sheet.")
    else:
        st.success("✅ Conectado a Google Sheets")
    
    st.divider()
    st.write("Esta aplicación arregla el problema de los decimales usando un parseador estricto europeo.")

# 2. Cargar DataFrame
df = cargar_datos(libro)

# Procesamiento de datos
if not df.empty:
    # Aseguramos que 'Monto' sea procesado correctamente
    df['Monto_Num'] = df['Monto'].apply(parsear_monto_europeo)
    df['Fecha_Dt'] = pd.to_datetime(df['Fecha'], errors='coerce')
else:
    df = pd.DataFrame(columns=['Fecha', 'Categoria', 'Concepto', 'Monto', 'Tipo', 'Monto_Num'])

# Cálculos KPI
saldo_total = df['Monto_Num'].sum()
ingresos_total = df[df['Monto_Num'] > 0]['Monto_Num'].sum()
gastos_total = df[df['Monto_Num'] < 0]['Monto_Num'].sum()

# --- INTERFAZ PRINCIPAL ---

st.title("💶 Dashboard Financiero Pro")

# SECCIÓN 1: KPIS (Indicadores Clave)
col1, col2, col3 = st.columns(3)
col1.metric(label="💰 Saldo Total", value=formatear_moneda(saldo_total))
col2.metric(label="📈 Ingresos Totales", value=formatear_moneda(ingresos_total))
col3.metric(label="📉 Gastos Totales", value=formatear_moneda(gastos_total), delta_color="inverse")

st.divider()

# SECCIÓN 2: FORMULARIO DE ENTRADA
with st.container():
    st.subheader("➕ Nuevo Movimiento")
    with st.form("entry_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        
        fecha_in = c1.date_input("Fecha", date.today())
        
        # EL SECRETO: Usar text_input para control total del formato
        monto_in = c2.text_input("Cantidad (€)", placeholder="Ej: 1.250,50")
        
        tipo_in = c3.selectbox("Tipo", ["Gasto", "Ingreso", "Ahorro"])
        
        cat_opciones = ["Vivienda", "Comida", "Transporte", "Ocio", "Salud", "Nómina", "Inversión", "Otros"]
        cat_in = c4.selectbox("Categoría", cat_opciones)
        
        desc_in = st.text_input("Descripción / Concepto", placeholder="Ej. Compra Mercadona")
        
        # Botón de envío
        submitted = st.form_submit_button("💾 Registrar Movimiento", type="primary")
        
        if submitted:
            # 1. Validar y Convertir Monto
            monto_final = parsear_monto_europeo(monto_in)
            
            if monto_final == 0:
                st.error("⚠️ La cantidad no es válida. Usa formato: 10,50 o 10.50")
            elif desc_in.strip() == "":
                st.error("⚠️ Añade una descripción.")
            else:
                # 2. Ajustar signo negativo para gastos
                if tipo_in == "Gasto":
                    monto_final = -abs(monto_final)
                else:
                    monto_final = abs(monto_final)
                
                # 3. Guardar
                exito = guardar_dato(libro, fecha_in, cat_in, desc_in, monto_final, tipo_in)
                
                if exito:
                    st.success(f"Movimiento guardado: {formatear_moneda(monto_final)}")
                    st.rerun() # Recargar la página para actualizar gráficos

# SECCIÓN 3: GRÁFICOS Y ANÁLISIS
if not df.empty:
    st.subheader("📊 Análisis Visual")
    
    tab1, tab2 = st.tabs(["Evolución", "Desglose"])
    
    with tab1:
        # Gráfico de Línea (Evolución de saldo acumulado)
        df_sorted = df.sort_values('Fecha_Dt')
        df_sorted['Saldo_Acumulado'] = df_sorted['Monto_Num'].cumsum()
        
        fig_line = px.line(df_sorted, x='Fecha_Dt', y='Saldo_Acumulado', 
                           title='Evolución del Saldo', markers=True)
        fig_line.update_layout(xaxis_title="Fecha", yaxis_title="Euros (€)")
        st.plotly_chart(fig_line, use_container_width=True)

    with tab2:
        # Gráfico de Pastel (Solo Gastos)
        df_gastos = df[df['Monto_Num'] < 0].copy()
        if not df_gastos.empty:
            df_gastos['Gasto_Abs'] = df_gastos['Monto_Num'].abs()
            fig_pie = px.pie(df_gastos, values='Gasto_Abs', names='Categoria', 
                             title='Distribución de Gastos', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay gastos registrados para mostrar el gráfico.")

# SECCIÓN 4: HISTORIAL DETALLADO
st.divider()
with st.expander("📝 Ver Historial de Movimientos Completo", expanded=False):
    # Formatear tabla para visualización
    df_display = df.copy()
    df_display = df_display[['Fecha', 'Categoria', 'Concepto', 'Tipo', 'Monto_Num']]
    df_display['Monto_Num'] = df_display['Monto_Num'].apply(formatear_moneda)
    df_display.columns = ['Fecha', 'Categoría', 'Concepto', 'Tipo', 'Cantidad']
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)