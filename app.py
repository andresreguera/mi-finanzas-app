import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Finanzas Pro", page_icon="💶", layout="centered")

# --- CONEXIÓN ---
@st.cache_resource
def conectar():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = st.secrets["google_creds"]
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, scope)).open("Finanzas_DB")
    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()

libro = conectar()
hoja1 = libro.sheet1
try:
    hoja_obj = libro.worksheet("Objetivos")
except:
    st.error("Falta hoja Objetivos")
    st.stop()

# --- FUNCIONES DE LIMPIEZA CRÍTICAS ---

def procesar_dato_del_excel(valor):
    """
    ESTA ES LA CORRECCIÓN CLAVE.
    Convierte lo que viene del Excel (formato español) a número Python.
    Excel: "9,14" -> Python: 9.14
    Excel: "1.000,00" -> Python: 1000.0
    """
    if isinstance(valor, (int, float)):
        return float(valor)
    
    s = str(valor).strip()
    if not s: return 0.0

    try:
        # Lógica Española Estricta para leer del Excel
        # 1. Los puntos son de miles -> Fuera
        s = s.replace(".", "") 
        # 2. Las comas son decimales -> Cambiar a punto
        s = s.replace(",", ".")
        return float(s)
    except:
        return 0.0

def limpiar_input(valor):
    """
    Permite escribir con punto o coma, pero prioriza decimales.
    """
    if not valor: return 0.0
    s = str(valor).strip()
    try:
        # Si usas coma, es decimal
        s = s.replace(",", ".")
        return float(s)
    except:
        return 0.0

def formato_visual(numero):
    # Muestra 1.234,56 €
    try:
        return "{:,.2f} €".format(float(numero)).replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0,00 €"

# --- INTERFAZ ---
st.title("💶 Mi Cartera")

# Botón para forzar recarga de datos si algo se ve mal
if st.sidebar.button("🔄 Actualizar Cálculos"):
    st.cache_data.clear()
    st.rerun()

tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos"])

with tab1:
    # 1. Cargar Datos
    try:
        data = hoja1.get_all_records()
        df = pd.DataFrame(data)
    except: df = pd.DataFrame()

    ingresos, gastos, saldo = 0.0, 0.0, 0.0

    if not df.empty and 'Monto' in df.columns:
        # APLICAMOS LA CORRECCIÓN AL LEER
        df['Monto_Real'] = df['Monto'].apply(procesar_dato_del_excel)
        
        ingresos = df[df['Monto_Real'] > 0]['Monto_Real'].sum()
        gastos = df[df['Monto_Real'] < 0]['Monto_Real'].sum()
        saldo = df['Monto_Real'].sum()

    # 2. Mostrar Tarjetas
    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Actual", formato_visual(saldo))
    c2.metric("Ingresos", formato_visual(ingresos))
    c3.metric("Gastos", formato_visual(gastos), delta_color="inverse")

    st.divider()

    # 3. Formulario
    st.subheader("Nuevo Movimiento")
    with st.form("mov"):
        c_a, c_b = st.columns(2)
        fecha = c_a.date_input("Fecha")
        monto_in = c_a.text_input("Cantidad (€)", placeholder="Ej: 9,14")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        val_guardar = limpiar_input(monto_in)
        if monto_in:
            st.info(f"Se guardará: {formato_visual(val_guardar)}")

        if st.form_submit_button("Guardar"):
            if val_guardar > 0:
                final = -val_guardar if tipo == "Gasto" else val_guardar
                # Al Excel mandamos el número con punto (formato estándar internacional)
                # O si prefieres forzar coma, lo convertimos a string. 
                # Pero lo mejor es mandar float y que Excel lo formatee.
                hoja1.append_row([str(fecha), cat, desc, final, tipo])
                st.success("Guardado.")
                st.cache_data.clear() # Limpiamos caché para ver el cambio al instante
                st.rerun()
            else:
                st.warning("Cantidad mayor a 0")

    # 4. Historial (Usando los datos corregidos)
    if not df.empty:
        df_show = df.copy()
        df_show['Monto_Visual'] = df_show['Monto_Real'].apply(formato_visual)
        
        # Seleccionamos columnas seguras
        cols_final = ['Fecha', 'Categoría', 'Monto_Visual', 'Concepto']
        # Mapeo si los nombres en Excel son distintos
        df_show = df_show.rename(columns={'Monto_Visual': 'Monto'})
        
        cols_existentes = [c for c in ['Fecha', 'Categoría', 'Monto', 'Concepto'] if c in df_show.columns]
        st.dataframe(df_show[cols_existentes].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

with tab2:
    st.header("Metas")
    with st.form("meta"):
        nom = st.text_input("Meta")
        cant = st.text_input("Cantidad", placeholder="Ej: 1500,00")
        fin = st.date_input("Fecha Fin")
        val = limpiar_input(cant)
        
        if st.form_submit_button("Crear") and val > 0:
            hoja_obj.append_row([nom, val, str(fin), str(date.today())])
            st.rerun()

    try:
        dfo = pd.DataFrame(hoja_obj.get_all_records())
        if not dfo.empty:
            st.divider()
            sueldo = limpiar_input(st.text_input("Sueldo Mensual", "1500"))
            for i, r in dfo.iterrows():
                m = procesar_dato_del_excel(r['Monto_Meta'])
                dias = (pd.to_datetime(r['Fecha_Limite']).date() - date.today()).days
                ahorro = m / max(dias/30, 0.1)
                st.info(f"**{r['Objetivo']}**: Ahorra {formato_visual(ahorro)}/mes")
    except: pass