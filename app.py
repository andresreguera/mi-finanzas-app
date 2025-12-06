import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mi Finanzas Pro", page_icon="📈", layout="centered")

# --- CONEXIÓN SEGURA ---
@st.cache_resource
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["google_creds"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Abrimos el libro completo (Spreadsheet)
        libro = client.open("Finanzas_DB")
        return libro
    except Exception as e:
        st.error(f"Error al conectar: {e}")
        return None

libro = conectar_google_sheets()
if not libro:
    st.stop()

# Accedemos a las hojas (Pestañas)
try:
    hoja_movimientos = libro.sheet1
    # Intentamos abrir la hoja de Objetivos. Si no existe, avisamos.
    hoja_objetivos = libro.worksheet("Objetivos")
except gspread.exceptions.WorksheetNotFound:
    st.error("⚠️ Falta la hoja 'Objetivos' en tu Google Sheet. Por favor, créala con columnas: Objetivo, Monto_Meta, Fecha_Limite, Fecha_Creacion")
    st.stop()

# --- TÍTULO PRINCIPAL ---
st.title("📈 Mi Planificador Financiero")

# Creamos dos pestañas superiores
tab1, tab2 = st.tabs(["📝 Diario & Saldos", "🎯 Metas de Ahorro"])

# ==========================================================
# PESTAÑA 1: DIARIO (LO QUE YA TENÍAS + SUELDO)
# ==========================================================
with tab1:
    # --- CÁLCULOS DE SALDO ---
    try:
        registros = hoja_movimientos.get_all_records()
        df = pd.DataFrame(registros)
    except:
        df = pd.DataFrame()

    if not df.empty and 'Monto' in df.columns:
        df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce').fillna(0)
        ingresos = df[df['Monto'] > 0]['Monto'].sum()
        gastos = df[df['Monto'] < 0]['Monto'].sum()
        saldo_total = df['Monto'].sum()
    else:
        ingresos, gastos, saldo_total = 0, 0, 0

    # Tarjetas KPI
    col1, col2, col3 = st.columns(3)
    col1.metric("Saldo Actual", f"{saldo_total:.2f}€")
    col2.metric("Ingresos", f"{ingresos:.2f}€", delta_color="normal")
    col3.metric("Gastos", f"{gastos:.2f}€", delta=f"{gastos:.2f}€", delta_color="inverse")

    st.divider()

    # --- REGISTRO DE MOVIMIENTOS ---
    st.subheader("Nuevo Movimiento")
    with st.form("entrada_datos", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            fecha = st.date_input("Fecha", datetime.now())
            monto = st.number_input("Monto (€)", min_value=0.0, step=0.01, format="%.2f")
        with col_b:
            tipo = st.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo Mensual"]) 
            # He añadido "Sueldo Mensual" explícitamente para que lo diferencies
            
            categoria = st.selectbox("Categoría", ["Comida", "Transporte", "Vivienda", "Ocio", "Salud", "Ahorro", "Otros", "Nómina/Sueldo"])
        
        concepto = st.text_input("Descripción", placeholder="Ej: Compra semanal")
        guardar = st.form_submit_button("💾 Guardar", use_container_width=True)

    if guardar:
        if monto > 0:
            # Si es Gasto, negativo. Si es Ingreso o Sueldo, positivo.
            es_gasto = tipo == "Gasto"
            valor_final = -monto if es_gasto else monto
            
            datos = [str(fecha), categoria, concepto, valor_final, tipo]
            hoja_movimientos.append_row(datos)
            st.success("¡Movimiento registrado!")
            st.rerun()
        else:
            st.warning("El monto debe ser mayor a 0")

    # Historial rápido
    if not df.empty:
        st.caption("Últimos movimientos")
        st.dataframe(df.tail(5).sort_index(ascending=False)[['Fecha', 'Categoria', 'Monto', 'Concepto']], use_container_width=True, hide_index=True)

# ==========================================================
# PESTAÑA 2: OBJETIVOS (LA NUEVA FUNCIONALIDAD)
# ==========================================================
with tab2:
    st.header("🎯 Mis Metas Futuras")
    
    # --- FORMULARIO PARA CREAR OBJETIVO ---
    with st.expander("➕ Añadir Nuevo Objetivo"):
        with st.form("form_objetivo"):
            obj_nombre = st.text_input("Nombre de la meta", placeholder="Ej: Viaje a Japón")
            obj_monto = st.number_input("¿Cuánto necesitas? (€)", min_value=0.0)
            obj_fecha = st.date_input("¿Para cuándo?", min_value=datetime.now())
            
            submit_obj = st.form_submit_button("Crear Objetivo")
            
            if submit_obj and obj_nombre and obj_monto > 0:
                hoja_objetivos.append_row([obj_nombre, obj_monto, str(obj_fecha), str(date.today())])
                st.success("¡Objetivo fijado! Vamos a por ello.")
                st.rerun()

    st.divider()

    # --- CALCULADORA Y VISUALIZACIÓN ---
    try:
        data_obj = hoja_objetivos.get_all_records()
        df_obj = pd.DataFrame(data_obj)
    except:
        df_obj = pd.DataFrame()

    if not df_obj.empty:
        # Input opcional para calcular viabilidad
        sueldo_estimado = st.number_input("💰 Tu Sueldo Mensual (para calcular viabilidad)", min_value=0.0, step=100.0, value=1500.0)

        st.subheader("Plan de Ahorro")
        
        for index, row in df_obj.iterrows():
            # Cálculos Matemáticos
            meta = row['Monto_Meta']
            fecha_limite = pd.to_datetime(row['Fecha_Limite']).date()
            hoy = date.today()
            
            # Días restantes
            dias_restantes = (fecha_limite - hoy).days
            meses_restantes = dias_restantes / 30
            
            # Evitar división por cero si la fecha es hoy
            if meses_restantes <= 0: meses_restantes = 0.1
            
            ahorro_mensual_necesario = meta / meses_restantes
            
            # --- TARJETA VISUAL DE CADA OBJETIVO ---
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"### 🚀 {row['Objetivo']}")
                c1.markdown(f"Meta: **{meta}€** para el **{fecha_limite}**")
                
                if dias_restantes > 0:
                    c1.info(f"Necesitas ahorrar **{ahorro_mensual_necesario:.2f}€ al mes** durante los próximos {meses_restantes:.1f} meses.")
                    
                    # Semáforo de viabilidad
                    if sueldo_estimado > 0:
                        porcentaje_sueldo = (ahorro_mensual_necesario / sueldo_estimado) * 100
                        if porcentaje_sueldo > 50:
                            c1.error(f"⚠️ ¡Cuidado! Esto requiere el {porcentaje_sueldo:.0f}% de tu sueldo.")
                        elif porcentaje_sueldo > 20:
                            c1.warning(f"📊 Supone un {porcentaje_sueldo:.0f}% de tu sueldo.")
                        else:
                            c1.success(f"✅ Factible: Solo es el {porcentaje_sueldo:.0f}% de tu sueldo.")
                else:
                    c1.success("¡La fecha ha llegado! ¿Lo conseguiste?")
                    
    else:
        st.info("No tienes objetivos activos. ¡Crea uno arriba!")