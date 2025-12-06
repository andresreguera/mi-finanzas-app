import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Finanzas Simple", page_icon="💰", layout="centered")

# --- CONEXIÓN ---
@st.cache_resource
def conectar():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = st.secrets["google_creds"]
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, scope)).open("Finanzas_DB")
    except Exception as e:
        st.error(f"Error conexión: {e}")
        st.stop()

libro = conectar()
hoja1 = libro.sheet1
try:
    hoja_obj = libro.worksheet("Objetivos")
except:
    st.error("Falta hoja 'Objetivos'")
    st.stop()

# --- FUNCIONES DE LIMPIEZA (SIMPLIFICADAS AL MÁXIMO) ---

def numero_puro(valor):
    """
    ESTA ES LA CORRECCIÓN:
    Ya NO borramos puntos.
    Si entra 9.14 -> sale 9.14
    Si entra "9.14" -> sale 9.14
    Si entra "9,14" -> lo arreglamos a 9.14 (por si acaso)
    """
    if valor is None or valor == "": return 0.0
    
    # Si ya es número, devolverlo tal cual
    if isinstance(valor, (int, float)):
        return float(valor)
    
    # Si es texto
    s = str(valor).strip()
    try:
        # Solo cambiamos coma por punto (para teclados españoles)
        # PERO NUNCA QUITAMOS EL PUNTO QUE YA EXISTA
        s = s.replace(",", ".")
        return float(s)
    except:
        return 0.0

def formato_visual(numero):
    # Muestra 9.14 € (Formato estándar)
    return "{:,.2f} €".format(numero)

# --- BARRA LATERAL ---
with st.sidebar:
    st.write("### ⚙️ Mantenimiento")
    if st.button("⚠️ BORRAR TODO Y REINICIAR", type="primary"):
        hoja1.clear()
        hoja1.append_row(["Fecha", "Categoría", "Descripción", "Monto", "Tipo"])
        st.cache_data.clear()
        st.success("Tabla vaciada. Recarga la página.")

# --- INTERFAZ ---
st.title("💰 Mi Cartera")
tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos"])

# PESTAÑA 1: DIARIO
with tab1:
    # 1. Leer Excel
    try:
        data = hoja1.get_all_records()
        df = pd.DataFrame(data)
    except: df = pd.DataFrame()

    # 2. Calcular Saldos
    ingresos, gastos, saldo = 0.0, 0.0, 0.0

    if not df.empty and 'Monto' in df.columns:
        # Limpiamos columna Monto respetando el punto
        df['Monto_Num'] = df['Monto'].apply(numero_puro)
        
        ingresos = df[df['Monto_Num'] > 0]['Monto_Num'].sum()
        gastos = df[df['Monto_Num'] < 0]['Monto_Num'].sum()
        saldo = df['Monto_Num'].sum()

    # 3. Mostrar Tarjetas
    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Actual", formato_visual(saldo))
    c2.metric("Ingresos", formato_visual(ingresos))
    c3.metric("Gastos", formato_visual(gastos), delta_color="inverse")

    st.divider()

    # 4. Formulario
    st.subheader("Nuevo Movimiento")
    with st.form("movimiento"):
        col_a, col_b = st.columns(2)
        fecha = col_a.date_input("Fecha")
        # Texto de ayuda claro
        monto_txt = col_a.text_input("Cantidad", placeholder="Ej: 9.14")
        
        tipo = col_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = col_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        # Procesar
        val_real = numero_puro(monto_txt)
        
        # Chivato para que veas qué va a pasar antes de guardar
        if monto_txt:
            st.caption(f"👀 Se guardará como: {val_real}")

        if st.form_submit_button("Guardar"):
            if val_real > 0:
                final = -val_real if tipo == "Gasto" else val_real
                hoja1.append_row([str(fecha), cat, desc, final, tipo])
                st.success("Guardado.")
                st.rerun()
            else:
                st.warning("Introduce una cantidad mayor a 0")

    # 5. Tabla
    if not df.empty:
        df_show = df.copy()
        df_show['Monto'] = df_show['Monto_Num'].apply(formato_visual)
        st.dataframe(df_show[['Fecha', 'Categoria', 'Monto', 'Concepto']].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# PESTAÑA 2: OBJETIVOS
with tab2:
    st.header("🎯 Metas")
    with st.form("obj"):
        nom = st.text_input("Nombre")
        obj_txt = st.text_input("Cantidad Meta", placeholder="Ej: 1500.00")
        f_fin = st.date_input("Fecha Límite")
        
        obj_val = numero_puro(obj_txt)
        
        if st.form_submit_button("Crear Meta") and obj_val > 0:
            hoja_obj.append_row([nom, obj_val, str(f_fin), str(date.today())])
            st.rerun()
            
    try:
        data_o = hoja_obj.get_all_records()
        df_o = pd.DataFrame(data_o)
    except: df_o = pd.DataFrame()

    if not df_o.empty:
        st.divider()
        sueldo_in = st.text_input("Tu sueldo mensual", value="1500")
        sueldo = numero_puro(sueldo_in)

        for i, row in df_o.iterrows():
            meta = numero_puro(row['Monto_Meta'])
            dias = (pd.to_datetime(row['Fecha_Limite']).date() - date.today()).days
            meses = max(dias/30, 0.1)
            ahorro = meta/meses
            
            with st.container(border=True):
                c1, c2 = st.columns([3,1])
                c1.markdown(f"### {row['Objetivo']}")
                c1.write(f"Meta: **{formato_visual(meta)}**")
                if dias>0:
                    c1.info(f"Ahorra **{formato_visual(ahorro)}/mes**")
                else:
                    c1.success("Finalizado")