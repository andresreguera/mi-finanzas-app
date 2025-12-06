import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mi Finanzas Pro", page_icon="📈", layout="centered")

# --- FUNCIONES AUXILIARES DE FORMATO ---

def formato_euros(valor):
    """Convierte un número (float) a formato visual español: 1.234,56€"""
    try:
        # Formateamos primero estilo USA: 1,234.56
        texto = f"{float(valor):,.2f}"
        # Invertimos los signos: comas por puntos y puntos por comas
        # 1. Cambiamos la coma por una X temporal
        texto = texto.replace(",", "X")
        # 2. Cambiamos el punto por coma
        texto = texto.replace(".", ",")
        # 3. Cambiamos la X por punto
        texto = texto.replace("X", ".")
        return f"{texto}€"
    except:
        return "0,00€"

def limpiar_input_dinero(texto_input):
    """
    Lógica ESTRICTA Europea:
    - Los puntos "." se ignoran (son separadores de miles).
    - Las comas "," son los decimales.
    Ejemplos que arregla:
    "4139,14" -> 4139.14 (Correcto)
    "4.139,14" -> 4139.14 (Correcto)
    "9,14" -> 9.14 (Correcto)
    """
    if not texto_input:
        return 0.0
    
    texto = str(texto_input).strip()
    
    try:
        # PASO 1: Eliminar todos los puntos (separadores de miles)
        # Si alguien pone 4.139,14 se convierte en 4139,14
        texto = texto.replace(".", "")
        
        # PASO 2: Cambiar la coma por punto (para que Python entienda el decimal)
        # 4139,14 se convierte en 4139.14
        texto = texto.replace(",", ".")
        
        return float(texto)
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
        # Forzamos la conversión a número por si Sheets lo guardó como texto
        df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce').fillna(0)
        
        ingresos = df[df['Monto'] > 0]['Monto'].sum()
        gastos = df[df['Monto'] < 0]['Monto'].sum()
        saldo_total = df['Monto'].sum()
    else:
        ingresos, gastos, saldo_total = 0, 0, 0

    # Tarjetas KPI
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
            # Input de texto para permitir formato libre (comas)
            monto_txt = st.text_input("Monto (€)", value="", placeholder="Ej: 4139,14")
        with col_b:
            tipo = st.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo Mensual"])
            categoria = st.selectbox("Categoría", ["Comida", "Transporte", "Vivienda", "Ocio", "Salud", "Ahorro", "Otros", "Nómina/Sueldo"])
        
        concepto = st.text_input("Descripción", placeholder="Ej: Compra semanal")
        guardar = st.form_submit_button("💾 Guardar", use_container_width=True)

    if guardar:
        # Aplicamos la limpieza ESTRICTA europea
        monto_num = limpiar_input_dinero(monto_txt)
        
        if monto_num > 0:
            es_gasto = tipo == "Gasto"
            valor_final = -monto_num if es_gasto else monto_num
            
            # Guardamos en Google Sheets (usando float para que Sheet entienda que es número)
            datos = [str(fecha), categoria, concepto, valor_final, tipo]
            hoja_movimientos.append_row(datos)
            
            st.success(f"¡Movimiento de {formato_euros(monto_num)} guardado!")
            st.rerun()
        else:
            st.warning("⚠️ Introduce una cantidad válida (mayor que 0).")

    # Historial rápido
    if not df.empty:
        st.caption("Últimos movimientos")
        # Creamos una copia visual para formatear la columna Monto
        df_visual = df.tail(5).sort_index(ascending=False).copy()
        # Aplicamos el formato bonito solo para ver (no afecta a los cálculos)
        df_visual['Monto'] = df_visual['Monto'].apply(formato_euros)
        
        st.dataframe(
            df_visual[['Fecha', 'Categoria', 'Monto', 'Concepto']], 
            use_container_width=True, 
            hide_index=True
        )

# ==========================================================
# PESTAÑA 2: OBJETIVOS
# ==========================================================
with tab2:
    st.header("🎯 Mis Metas Futuras")
    
    with st.expander("➕ Añadir Nuevo Objetivo"):
        with st.form("form_objetivo"):
            obj_nombre = st.text_input("Nombre de la meta", placeholder="Ej: Coche Nuevo")
            obj_monto_txt = st.text_input("¿Cuánto necesitas? (€)", value="", placeholder="Ej: 15000,00")
            obj_fecha = st.date_input("¿Para cuándo?", min_value=datetime.now())
            
            submit_obj = st.form_submit_button("Crear Objetivo")
            
            if submit_obj and obj_nombre:
                obj_monto_num = limpiar_input_dinero(obj_monto_txt)
                
                if obj_monto_num > 0:
                    hoja_objetivos.append_row([obj_nombre, obj_monto_num, str(obj_fecha), str(date.today())])
                    st.success(f"¡Objetivo de {formato_euros(obj_monto_num)} fijado!")
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
        sueldo_txt = st.text_input("💰 Tu Sueldo Mensual (para calcular)", value="1500,00")
        sueldo_estimado = limpiar_input_dinero(sueldo_txt)

        st.subheader("Plan de Ahorro")
        
        for index, row in df_obj.iterrows():
            # Convertimos a número con seguridad
            try:
                meta = float(str(row['Monto_Meta']).replace(",", ".")) 
            except:
                meta = limpiar_input_dinero(row['Monto_Meta'])

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
                    c1.info(f"Necesitas ahorrar **{formato_euros(ahorro_mensual_necesario)} al mes** durante {meses_restantes:.1f} meses.")
                    
                    if sueldo_estimado > 0:
                        porcentaje_sueldo = (ahorro_mensual_necesario / sueldo_estimado) * 100
                        if porcentaje_sueldo > 50:
                            c1.error(f"⚠️ ¡Cuidado! Es el {porcentaje_sueldo:.0f}% de tu sueldo.")
                        elif porcentaje_sueldo > 20:
                            c1.warning(f"📊 Es el {porcentaje_sueldo:.0f}% de tu sueldo.")
                        else:
                            c1.success(f"✅ Factible: {porcentaje_sueldo:.0f}% de tu sueldo.")
                else:
                    c1.success("¡La fecha ha llegado!")
    else:
        st.info("No tienes objetivos activos.")