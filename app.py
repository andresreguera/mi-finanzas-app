import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mi Finanzas Pro", page_icon="📈", layout="centered")

# --- FUNCIÓN AUXILIAR: FORMATO EUROPEO (1.000,00€) ---
def formato_euros(valor):
    try:
        # Formatea con separador de miles coma y decimal punto (formato USA estandar)
        # Ejemplo: 1234.56 -> "1,234.56"
        texto = f"{float(valor):,.2f}"
        # Intercambiamos los caracteres: lo que era coma ahora es punto, y viceversa
        texto_europeo = texto.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{texto_europeo}€"
    except:
        return "0,00€"

# --- FUNCIÓN AUXILIAR: LIMPIAR INPUT (Admite comas y puntos) ---
def limpiar_input_dinero(texto_input):
    try:
        if isinstance(texto_input, (int, float)):
            return float(texto_input)
        # Reemplazamos la coma por punto para que Python entienda el decimal
        texto_limpio = str(texto_input).replace(",", ".")
        return float(texto_limpio)
    except ValueError:
        return 0.0

# --- CONEXIÓN SEGURA ---
@st.cache_resource
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["google_creds"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        libro = client.open("Finanzas_DB")
        return libro
    except Exception as e:
        st.error(f"Error al conectar: {e}")
        return None

libro = conectar_google_sheets()
if not libro:
    st.stop()

# Accedemos a las hojas
try:
    hoja_movimientos = libro.sheet1
    hoja_objetivos = libro.worksheet("Objetivos")
except gspread.exceptions.WorksheetNotFound:
    st.error("⚠️ Falta la hoja 'Objetivos'. Créala en Google Sheets.")
    st.stop()

# --- TÍTULO PRINCIPAL ---
st.title("📈 Mi Planificador Financiero")

tab1, tab2 = st.tabs(["📝 Diario & Saldos", "🎯 Metas de Ahorro"])

# ==========================================================
# PESTAÑA 1: DIARIO
# ==========================================================
with tab1:
    # --- CÁLCULOS DE SALDO ---
    try:
        registros = hoja_movimientos.get_all_records()
        df = pd.DataFrame(registros)
    except:
        df = pd.DataFrame()

    if not df.empty and 'Monto' in df.columns:
        # Convertimos todo a números asegurándonos de que entienda decimales
        df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce').fillna(0)
        
        ingresos = df[df['Monto'] > 0]['Monto'].sum()
        gastos = df[df['Monto'] < 0]['Monto'].sum()
        saldo_total = df['Monto'].sum()
    else:
        ingresos, gastos, saldo_total = 0, 0, 0

    # Tarjetas KPI (Usando el nuevo formato europeo)
    col1, col2, col3 = st.columns(3)
    col1.metric("Saldo Actual", formato_euros(saldo_total))
    col2.metric("Ingresos", formato_euros(ingresos), delta_color="normal")
    col3.metric("Gastos", formato_euros(gastos), delta=formato_euros(gastos), delta_color="inverse")

    st.divider()

    # --- REGISTRO DE MOVIMIENTOS ---
    st.subheader("Nuevo Movimiento")
    with st.form("entrada_datos", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            fecha = st.date_input("Fecha", datetime.now())
            # CAMBIO IMPORTANTE: Usamos text_input para permitir comas
            monto_txt = st.text_input("Monto (€)", value="", placeholder="Ej: 9,14")
        with col_b:
            tipo = st.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo Mensual"])
            categoria = st.selectbox("Categoría", ["Comida", "Transporte", "Vivienda", "Ocio", "Salud", "Ahorro", "Otros", "Nómina/Sueldo"])
        
        concepto = st.text_input("Descripción", placeholder="Ej: Compra semanal")
        guardar = st.form_submit_button("💾 Guardar", use_container_width=True)

    if guardar:
        # Convertimos el texto (con coma) a número (con punto)
        monto_num = limpiar_input_dinero(monto_txt)
        
        if monto_num > 0:
            es_gasto = tipo == "Gasto"
            valor_final = -monto_num if es_gasto else monto_num
            
            datos = [str(fecha), categoria, concepto, valor_final, tipo]
            hoja_movimientos.append_row(datos)
            st.success(f"¡Movimiento de {formato_euros(monto_num)} guardado!")
            st.rerun()
        else:
            st.warning("⚠️ Introduce una cantidad válida (mayor que 0).")

    # Historial rápido
    if not df.empty:
        st.caption("Últimos movimientos")
        # Mostramos una tabla simple. Streamlit la formatea automático, pero los datos están bien.
        st.dataframe(df.tail(5).sort_index(ascending=False)[['Fecha', 'Categoria', 'Monto', 'Concepto']], use_container_width=True, hide_index=True)

# ==========================================================
# PESTAÑA 2: OBJETIVOS
# ==========================================================
with tab2:
    st.header("🎯 Mis Metas Futuras")
    
    with st.expander("➕ Añadir Nuevo Objetivo"):
        with st.form("form_objetivo"):
            obj_nombre = st.text_input("Nombre de la meta", placeholder="Ej: Viaje a Japón")
            # También cambiamos a texto para permitir comas
            obj_monto_txt = st.text_input("¿Cuánto necesitas? (€)", value="", placeholder="Ej: 1500,00")
            obj_fecha = st.date_input("¿Para cuándo?", min_value=datetime.now())
            
            submit_obj = st.form_submit_button("Crear Objetivo")
            
            if submit_obj and obj_nombre:
                obj_monto_num = limpiar_input_dinero(obj_monto_txt)
                if obj_monto_num > 0:
                    hoja_objetivos.append_row([obj_nombre, obj_monto_num, str(obj_fecha), str(date.today())])
                    st.success("¡Objetivo fijado!")
                    st.rerun()
                else:
                    st.warning("Introduce un monto válido.")

    st.divider()

    try:
        data_obj = hoja_objetivos.get_all_records()
        df_obj = pd.DataFrame(data_obj)
    except:
        df_obj = pd.DataFrame()

    if not df_obj.empty:
        # Input de sueldo también flexible con comas
        sueldo_txt = st.text_input("💰 Tu Sueldo Mensual (para calcular)", value="1500,00")
        sueldo_estimado = limpiar_input_dinero(sueldo_txt)

        st.subheader("Plan de Ahorro")
        
        for index, row in df_obj.iterrows():
            meta = float(row['Monto_Meta']) # Aseguramos que sea float
            fecha_limite = pd.to_datetime(row['Fecha_Limite']).date()
            hoy = date.today()
            
            dias_restantes = (fecha_limite - hoy).days
            meses_restantes = dias_restantes / 30
            if meses_restantes <= 0: meses_restantes = 0.1
            
            ahorro_mensual_necesario = meta / meses_restantes
            
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"### 🚀 {row['Objetivo']}")
                c1.markdown(f"Meta: **{formato_euros(meta)}** para el **{fecha_limite.strftime('%d/%m/%Y')}**")
                
                if dias_restantes > 0:
                    c1.info(f"Necesitas ahorrar **{formato_euros(ahorro_mensual_necesario)} al mes** durante los próximos {meses_restantes:.1f} meses.")
                    
                    if sueldo_estimado > 0:
                        porcentaje_sueldo = (ahorro_mensual_necesario / sueldo_estimado) * 100
                        if porcentaje_sueldo > 50:
                            c1.error(f"⚠️ ¡Cuidado! Esto requiere el {porcentaje_sueldo:.0f}% de tu sueldo.")
                        elif porcentaje_sueldo > 20:
                            c1.warning(f"📊 Supone un {porcentaje_sueldo:.0f}% de tu sueldo.")
                        else:
                            c1.success(f"✅ Factible: Solo es el {porcentaje_sueldo:.0f}% de tu sueldo.")
                else:
                    c1.success("¡La fecha ha llegado!")
                    
    else:
        st.info("No tienes objetivos activos. ¡Crea uno arriba!")