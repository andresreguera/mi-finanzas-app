import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Finanzas Final", page_icon="💰", layout="centered")

# --- CONEXIÓN ---
@st.cache_resource
def conectar():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = st.secrets["google_creds"]
        return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, scope)).open("Finanzas_DB")
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

libro = conectar()
hoja1 = libro.sheet1
try:
    hoja_obj = libro.worksheet("Objetivos")
except:
    st.error("Falta la hoja 'Objetivos'")
    st.stop()

# --- FUNCIONES DE LIMPIEZA BLINDADAS ---

def procesar_texto_a_numero(valor):
    """
    ESTA ES LA SOLUCIÓN.
    Fuerza que cualquier coma que venga del Excel se convierta en punto decimal.
    Entrada: "4139,14" (Texto del Excel) -> Salida: 4139.14 (Número Python)
    """
    # 1. Convertimos a texto obligatoriamente para manipularlo
    texto = str(valor).strip()
    
    if not texto: return 0.0

    try:
        # SI TIENE COMA, ES DECIMAL.
        # Paso A: Quitamos cualquier punto que haya (por si acaso hay miles: 1.000,50)
        texto = texto.replace(".", "")
        
        # Paso B: La coma se convierte en el ÚNICO punto decimal
        texto = texto.replace(",", ".")
        
        return float(texto)
    except:
        return 0.0

def formato_visual(numero):
    # Esto solo pinta el número bonito: 4.139,14 €
    try:
        return "{:,.2f} €".format(float(numero)).replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0,00 €"

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Opciones")
    if st.button("🔄 RECARGAR DATOS", type="primary"):
        st.cache_data.clear()
        st.rerun()

# --- INTERFAZ ---
st.title("💰 Mi Cartera")

tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos"])

# === PESTAÑA DIARIO ===
with tab1:
    # 1. Cargar Datos
    try:
        # TRUCO: numericise_ignore=['all'] obliga a leer todo como TEXTO
        # Así evitamos que Google intente adivinar el número y falle.
        data = hoja1.get_all_records(numericise_ignore=['all'])
        df = pd.DataFrame(data)
    except: df = pd.DataFrame()

    ingresos, gastos, saldo = 0.0, 0.0, 0.0

    if not df.empty and 'Monto' in df.columns:
        # APLICAMOS LA FUERZA BRUTA A LA COLUMNA MONTO
        df['Monto_Calc'] = df['Monto'].apply(procesar_texto_a_numero)
        
        ingresos = df[df['Monto_Calc'] > 0]['Monto_Calc'].sum()
        gastos = df[df['Monto_Calc'] < 0]['Monto_Calc'].sum()
        saldo = df['Monto_Calc'].sum()

    # 2. Mostrar Saldos
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
        monto_txt = c_a.text_input("Cantidad (€)", placeholder="Ej: 4139,14")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        # Procesamos lo que escribes igual que lo que leemos del Excel
        val_guardar = procesar_texto_a_numero(monto_txt)
        
        if monto_txt:
            st.info(f"🔢 Se guardará como: **{val_guardar}**")

        if st.form_submit_button("Guardar"):
            if val_guardar > 0:
                final = -val_guardar if tipo == "Gasto" else val_guardar
                # Al guardar, convertimos a string con coma para que Excel lo vea "Español"
                valor_excel = str(final).replace(".", ",")
                
                hoja1.append_row([str(fecha), cat, desc, valor_excel, tipo])
                st.success("Guardado.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Introduce una cantidad válida.")

    # 4. Tabla Historial
    if not df.empty:
        df_show = df.copy()
        df_show['Monto'] = df_show['Monto_Calc'].apply(formato_visual)
        cols_existentes = [c for c in ['Fecha', 'Categoría', 'Monto', 'Concepto'] if c in df_show.columns]
        st.dataframe(df_show[cols_existentes].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# === PESTAÑA OBJETIVOS ===
with tab2:
    st.header("🎯 Metas")
    with st.form("obj"):
        nom = st.text_input("Meta")
        cant = st.text_input("Cantidad", placeholder="Ej: 1500,00")
        fin = st.date_input("Fecha Fin")
        val = procesar_texto_a_numero(cant)
        
        if st.form_submit_button("Crear") and val > 0:
            val_excel = str(val).replace(".", ",")
            hoja_obj.append_row([nom, val_excel, str(fin), str(date.today())])
            st.rerun()

    try:
        # Leemos también objetivos como texto puro
        do = hoja_obj.get_all_records(numericise_ignore=['all'])
        dfo = pd.DataFrame(do)
        if not dfo.empty:
            st.divider()
            sueldo = procesar_texto_a_numero(st.text_input("Sueldo Mensual", "1500"))
            for i, r in dfo.iterrows():
                m = procesar_texto_a_numero(r['Monto_Meta'])
                dias = (pd.to_datetime(r['Fecha_Limite']).date() - date.today()).days
                ahorro = m / max(dias/30, 0.1)
                st.info(f"**{r['Objetivo']}**: Ahorra {formato_visual(ahorro)}/mes")
    except: pass