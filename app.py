import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Mi Finanzas Pro", page_icon="💰", layout="centered")

# --- MOTOR DE LIMPIEZA Y FORMATO (NUEVO) ---

def formato_bonito(numero):
    """
    Imprime el dinero limpio.
    Ej: 1500.5 -> "1,500.50 €"
    """
    if numero is None: return "0.00 €"
    return "{:,.2f} €".format(numero)

def limpiar_dato_del_excel(dato):
    """
    ESTE ES EL FILTRO NUEVO.
    Coge lo que haya en el Excel (sea texto sucio o numero) y lo arregla.
    """
    # 1. Si ya es un número limpio, nos vale.
    if isinstance(dato, (int, float)):
        return float(dato)
    
    # 2. Si es texto, lo limpiamos agresivamente.
    texto = str(dato).strip()
    if not texto: return 0.0
    
    try:
        # Quitamos comas (por si hay formatos 1,000)
        texto_limpio = texto.replace(",", "")
        return float(texto_limpio)
    except:
        return 0.0

def limpiar_input_usuario(texto):
    """
    Para lo que escribes ahora: 
    Acepta '9.14' o '4000'. 
    Si pones coma '9,14' la cambia a punto para que no falle.
    """
    if not texto: return 0.0
    try:
        s = str(texto).replace(",", ".") # Arreglamos coma a punto
        return float(s)
    except:
        return 0.0

# --- CONEXIÓN ---
@st.cache_resource
def conectar():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = st.secrets["google_creds"]
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, scope)).open("Finanzas_DB")

try:
    libro = conectar()
    hoja1 = libro.sheet1
    hoja_obj = libro.worksheet("Objetivos")
except:
    st.error("Error de conexión o falta hoja 'Objetivos'.")
    st.stop()

# --- BARRA LATERAL (HERRAMIENTAS) ---
with st.sidebar:
    st.header("⚙️ Configuración")
    st.write("Si ves saldos gigantes por error, pulsa esto para reiniciar tu hoja:")
    if st.button("⚠️ BORRAR TODO Y EMPEZAR DE CERO", type="primary"):
        # Borra todo menos los encabezados
        hoja1.clear()
        hoja1.append_row(["Fecha", "Categoría", "Descripción", "Monto", "Tipo"])
        st.success("¡Base de datos reiniciada! Recarga la página.")
        st.cache_data.clear()

# --- INTERFAZ ---
st.title("💰 Mi Cartera")
tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos"])

# ==========================================================
# PESTAÑA 1: NUEVA LÓGICA DE SALDOS
# ==========================================================
with tab1:
    # 1. Descargamos datos
    try:
        data = hoja1.get_all_records()
        df = pd.DataFrame(data)
    except: df = pd.DataFrame()

    # 2. RECONSTRUCCIÓN DE CÁLCULOS (MOTOR NUEVO)
    ingresos = 0.0
    gastos = 0.0
    saldo = 0.0

    if not df.empty and 'Monto' in df.columns:
        # Pasamos la "aspiradora" por cada fila del Excel
        df['Monto_Limpio'] = df['Monto'].apply(limpiar_dato_del_excel)
        
        # Sumamos solo lo limpio
        ingresos = df[df['Monto_Limpio'] > 0]['Monto_Limpio'].sum()
        gastos = df[df['Monto_Limpio'] < 0]['Monto_Limpio'].sum()
        saldo = df['Monto_Limpio'].sum()

    # 3. IMPRESIÓN DE DATOS (REHECHA)
    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Total", formato_bonito(saldo))
    c2.metric("Ingresos", formato_bonito(ingresos))
    c3.metric("Gastos", formato_bonito(gastos), delta_color="inverse")

    st.divider()

    # 4. FORMULARIO
    st.subheader("Nuevo Movimiento")
    with st.form("add"):
        c_a, c_b = st.columns(2)
        fecha = c_a.date_input("Fecha")
        
        # Input texto para flexibilidad
        monto_in = c_a.text_input("Cantidad", placeholder="Ej: 9.14 o 4000")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        # Limpieza al vuelo
        val_real = limpiar_input_usuario(monto_in)
        if monto_in: st.caption(f"Se guardará: {val_real}")
        
        if st.form_submit_button("Guardar"):
            if val_real > 0:
                final = -val_real if tipo == "Gasto" else val_real
                hoja1.append_row([str(fecha), cat, desc, final, tipo])
                st.success("Guardado.")
                st.rerun()

    # 5. TABLA HISTORIAL (FORMATO NUEVO)
    if not df.empty:
        df_show = df.copy()
        df_show['Monto'] = df_show['Monto_Limpio'].apply(formato_bonito)
        st.dataframe(df_show[['Fecha', 'Categoria', 'Monto', 'Concepto']].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# ==========================================================
# PESTAÑA 2: OBJETIVOS
# ==========================================================
with tab2:
    st.header("🎯 Metas")
    with st.form("obj"):
        nom = st.text_input("Nombre")
        obj_in = st.text_input("Cantidad Meta", placeholder="Ej: 1500.00")
        f_fin = st.date_input("Fecha Fin")
        
        obj_val = limpiar_input_usuario(obj_in)
        
        if st.form_submit_button("Crear Meta") and obj_val > 0:
            hoja_obj.append_row([nom, obj_val, str(f_fin), str(date.today())])
            st.rerun()

    try:
        data_obj = hoja_obj.get_all_records()
        df_o = pd.DataFrame(data_obj)
    except: df_o = pd.DataFrame()

    if not df_o.empty:
        st.divider()
        sueldo_in = st.text_input("Tu sueldo mensual", value="1500")
        sueldo = limpiar_input_usuario(sueldo_in)

        for i, row in df_o.iterrows():
            meta = limpiar_dato_del_excel(row['Monto_Meta'])
            dias = (pd.to_datetime(row['Fecha_Limite']).date() - date.today()).days
            meses = max(dias/30, 0.1)
            ahorro = meta/meses
            
            with st.container(border=True):
                col_a, col_b = st.columns([3,1])
                col_a.markdown(f"### {row['Objetivo']}")
                col_a.write(f"Meta: **{formato_bonito(meta)}**")
                if dias>0:
                    col_a.info(f"Ahorra **{formato_bonito(ahorro)}/mes**")
                else:
                    col_a.success("¡Tiempo cumplido!")