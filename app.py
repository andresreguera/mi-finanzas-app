import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Mi Finanzas Simple", page_icon="💰", layout="centered")

# --- FUNCIÓN DE FORMATO VISUAL (ESTÁNDAR) ---
def formato_euros(valor):
    """
    Muestra el dinero en formato estándar internacional.
    Ejemplo: 4000.50 -> "4,000.50 €"
    """
    try:
        if valor is None: return "0.00 €"
        # Formato: Coma para miles, Punto para decimales
        return "{:,.2f} €".format(float(valor))
    except:
        return "0.00 €"

# --- FUNCIÓN DE LIMPIEZA (LÓGICA SIMPLE) ---
def limpiar_numero(texto):
    """
    Reglas simples:
    - 4000 -> 4000.0
    - 9.14 -> 9.14
    - 1,000 -> 1000.0 (Ignoramos las comas de miles si las pones)
    """
    if not texto: return 0.0
    
    # Si ya es número, perfecto
    if isinstance(texto, (int, float)):
        return float(texto)
    
    s = str(texto).strip()
    try:
        # Eliminamos comas por si acaso pusiste "1,000"
        s = s.replace(",", "")
        return float(s)
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
        st.error(f"Error conexión: {e}")
        return None

libro = conectar_google_sheets()
if not libro: st.stop()

try:
    hoja_movimientos = libro.sheet1
    hoja_objetivos = libro.worksheet("Objetivos")
except:
    st.error("⚠️ Falta la hoja 'Objetivos'.")
    st.stop()

# --- INTERFAZ ---
st.title("💰 Mi Planificador (Modo Simple)")

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
        # Limpiamos usando la lógica simple
        df['Monto_Num'] = df['Monto'].apply(limpiar_numero)
        
        ingresos = df[df['Monto_Num'] > 0]['Monto_Num'].sum()
        gastos = df[df['Monto_Num'] < 0]['Monto_Num'].sum()
        saldo_total = df['Monto_Num'].sum()

    # Tarjetas
    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Actual", formato_euros(saldo_total))
    c2.metric("Ingresos", formato_euros(ingresos))
    c3.metric("Gastos", formato_euros(gastos), delta_color="inverse")

    st.divider()

    st.subheader("Nuevo Movimiento")
    with st.form("entrada"):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha", datetime.now())
        
        # INPUT SIMPLE: Sin trucos.
        monto_txt = c1.text_input("Monto (€)", placeholder="Ej: 9.14")
        
        tipo = c2.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo Mensual"])
        cat = c2.selectbox("Categoría", ["Comida", "Transporte", "Vivienda", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        val_real = limpiar_numero(monto_txt)
        if monto_txt:
            st.caption(f"👀 Se guardará: {val_real}")
        
        if st.form_submit_button("💾 Guardar"):
            if val_real > 0:
                final = -val_real if tipo == "Gasto" else val_real
                # Guardamos el número limpio en Google Sheets
                hoja_movimientos.append_row([str(fecha), cat, desc, final, tipo])
                st.success("¡Guardado!")
                st.rerun()
            else:
                st.warning("Pon una cantidad válida (mayor a 0).")

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
        c_txt = st.text_input("Cantidad (€)", placeholder="Ej: 1500.00")
        f_lim = st.date_input("Fecha Límite")
        
        c_real = limpiar_numero(c_txt)
        
        if st.form_submit_button("Crear Meta") and c_real > 0:
            hoja_objetivos.append_row([nom, c_real, str(f_lim), str(date.today())])
            st.rerun()

    try:
        data = hoja_objetivos.get_all_records()
        df_obj = pd.DataFrame(data)
    except: df_obj = pd.DataFrame()

    if not df_obj.empty:
        st.divider()
        sueldo_txt = st.text_input("💰 Tu Sueldo (para calcular)", value="1500.00")
        sueldo = limpiar_numero(sueldo_txt)

        for i, row in df_obj.iterrows():
            meta = limpiar_numero(row['Monto_Meta'])
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