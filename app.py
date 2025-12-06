import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Finanzas Inteligente", page_icon="🧠", layout="centered")

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

# --- CEREBRO INTELIGENTE DE NÚMEROS ---
def limpiar_input_inteligente(valor):
    """
    Distingue automáticamente entre miles y decimales.
    - 9,14   -> 9.14 (Decimal)
    - 10.50  -> 10.50 (Decimal)
    - 4.000  -> 4000 (Mil)
    """
    if valor is None or str(valor).strip() == "": return 0.0
    
    # Si ya es número, devolverlo
    if isinstance(valor, (int, float)): return float(valor)
    
    s = str(valor).strip()
    try:
        # CASO 1: Tiene COMA (Formato Español explícito) -> 9,14 o 1.000,50
        if "," in s:
            # Borramos puntos de miles (1.000 -> 1000)
            s = s.replace(".", "")
            # Cambiamos coma a punto decimal
            s = s.replace(",", ".")
            return float(s)
            
        # CASO 2: Tiene PUNTO pero NO coma (Formato Híbrido)
        elif "." in s:
            partes = s.split(".")
            decimales = partes[-1]
            
            # Si tiene exactamente 3 "decimales" (Ej: 4.000), asumimos que son MILES
            if len(decimales) == 3 and len(partes) > 1:
                s = s.replace(".", "") # 4.000 -> 4000
                return float(s)
            else:
                # Si tiene 2 o 1 decimal (Ej: 10.50 o 10.5), es DECIMAL
                return float(s)
        
        # CASO 3: Número entero simple (Ej: 50)
        else:
            return float(s)
    except:
        return 0.0

def formato_visual(numero):
    # Siempre muestra: 1.234,56 €
    return "{:,.2f} €".format(numero).replace(",", "X").replace(".", ",").replace("X", ".")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Opciones")
    if st.button("⚠️ BORRAR TODO (RESETEAR)", type="primary"):
        hoja1.clear()
        hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        st.cache_data.clear()
        st.success("Tabla limpia. Los errores antiguos se han borrado.")
        st.rerun()

# --- INTERFAZ ---
st.title("💰 Mi Cartera")
tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos"])

with tab1:
    # 1. Cargar
    try:
        data = hoja1.get_all_records()
        df = pd.DataFrame(data)
    except: df = pd.DataFrame()

    ingresos, gastos, saldo = 0.0, 0.0, 0.0

    if not df.empty and 'Monto' in df.columns:
        # Usamos el limpiador inteligente en todo lo que viene del Excel
        df['Monto_Limpio'] = df['Monto'].apply(limpiar_input_inteligente)
        
        ingresos = df[df['Monto_Limpio'] > 0]['Monto_Limpio'].sum()
        gastos = df[df['Monto_Limpio'] < 0]['Monto_Limpio'].sum()
        saldo = df['Monto_Limpio'].sum()

    # 2. Tarjetas
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
        monto_txt = c_a.text_input("Cantidad", placeholder="Ej: 9,14 o 10.50")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        # Previsualización INTELIGENTE
        val_real = limpiar_input_inteligente(monto_txt)
        if monto_txt:
            st.info(f"🔢 El sistema detecta: **{val_real}**")

        if st.form_submit_button("Guardar"):
            if val_real > 0:
                final = -val_real if tipo == "Gasto" else val_real
                hoja1.append_row([str(fecha), cat, desc, final, tipo])
                st.success("Guardado.")
                st.rerun()
            else:
                st.warning("Introduce una cantidad válida.")

    # 4. Historial
    if not df.empty:
        df_show = df.copy()
        df_show['Monto'] = df_show['Monto_Limpio'].apply(formato_visual)
        cols = [c for c in ['Fecha', 'Categoría', 'Monto', 'Concepto'] if c in df_show.columns]
        st.dataframe(df_show[cols].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

with tab2:
    st.header("🎯 Metas")
    with st.form("obj"):
        nom = st.text_input("Meta")
        obj_txt = st.text_input("Cantidad", placeholder="Ej: 1500,00")
        f_fin = st.date_input("Fecha Fin")
        val_obj = limpiar_input_inteligente(obj_txt)
        if st.form_submit_button("Crear") and val_obj > 0:
            hoja_obj.append_row([nom, val_obj, str(f_fin), str(date.today())])
            st.rerun()

    try:
        dfo = pd.DataFrame(hoja_obj.get_all_records())
        if not dfo.empty:
            st.divider()
            sueldo = limpiar_input_inteligente(st.text_input("Sueldo mensual", "1500"))
            for i, r in dfo.iterrows():
                m = limpiar_input_inteligente(r['Monto_Meta'])
                dias = (pd.to_datetime(r['Fecha_Limite']).date() - date.today()).days
                ahorro = m / max(dias/30, 0.1)
                st.info(f"**{r['Objetivo']}**: Ahorra {formato_visual(ahorro)}/mes")
    except: pass