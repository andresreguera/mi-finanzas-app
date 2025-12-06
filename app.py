import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Finanzas", page_icon="💰", layout="centered")

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
    st.error("Falta la hoja 'Objetivos' en el Excel.")
    st.stop()

# --- FUNCIONES DE LIMPIEZA (LÓGICA BRUTA) ---

def forzar_decimales(valor):
    """
    Esta función NO piensa. Solo ejecuta:
    1. Si ya es número, perfecto.
    2. Si es texto, cambia TODAS las comas por puntos.
    Ej: "9,14" -> 9.14
    Ej: "1000" -> 1000.0
    """
    if valor is None or str(valor).strip() == "": 
        return 0.0
    
    # Si ya es número (int o float), devolverlo
    if isinstance(valor, (int, float)):
        return float(valor)
    
    # Si es texto
    s = str(valor).strip()
    try:
        # ELIMINAR CUALQUIER PUNTO DE MILES (ej: 1.000 -> 1000)
        # Esto asume que NO usas puntos para decimales si usas comas
        if "." in s and "," in s:
            s = s.replace(".", "") # Caso complejo 1.000,50 -> 1000,50
            
        # CAMBIAR COMA POR PUNTO (La regla de oro para Python)
        s = s.replace(",", ".")
        return float(s)
    except:
        return 0.0

def mostrar_euros(numero):
    # Muestra siempre: 1.234,56 €
    try:
        txt = "{:,.2f}".format(float(numero))
        return txt.replace(",", "X").replace(".", ",").replace("X", ".") + " €"
    except:
        return "0,00 €"

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚠️ Mantenimiento")
    st.write("Pulsa esto UNA VEZ para arreglar las columnas y borrar datos viejos.")
    if st.button("RESETEAR TABLA (BORRAR TODO)", type="primary"):
        hoja1.clear()
        # Definimos los encabezados exactos que usa el código
        hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        st.cache_data.clear()
        st.success("Tabla reiniciada correctamente. Recarga la página.")

# --- INTERFAZ ---
st.title("💰 Mi Cartera")
tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos"])

# PESTAÑA 1: DIARIO
with tab1:
    # 1. Leer datos
    try:
        data = hoja1.get_all_records()
        df = pd.DataFrame(data)
    except: df = pd.DataFrame()

    # 2. Calcular Saldos (Usando la función bruta)
    ingresos, gastos, saldo = 0.0, 0.0, 0.0

    if not df.empty and 'Monto' in df.columns:
        # Limpiamos la columna Monto
        df['Monto_Limpio'] = df['Monto'].apply(forzar_decimales)
        
        ingresos = df[df['Monto_Limpio'] > 0]['Monto_Limpio'].sum()
        gastos = df[df['Monto_Limpio'] < 0]['Monto_Limpio'].sum()
        saldo = df['Monto_Limpio'].sum()

    # 3. Mostrar Tarjetas
    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Actual", mostrar_euros(saldo))
    c2.metric("Ingresos", mostrar_euros(ingresos))
    c3.metric("Gastos", mostrar_euros(gastos), delta_color="inverse")

    st.divider()

    # 4. Formulario
    st.subheader("Nuevo Movimiento")
    with st.form("mov"):
        c_a, c_b = st.columns(2)
        fecha = c_a.date_input("Fecha")
        # Texto simple: Pon lo que quieras
        monto_in = c_a.text_input("Cantidad (€)", placeholder="Ej: 9,14")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        # Limpieza previa
        val_real = forzar_decimales(monto_in)
        
        if monto_in:
            st.caption(f"👀 Se guardará: {val_real} (Si pusiste coma, ya es punto)")

        if st.form_submit_button("Guardar"):
            if val_real > 0:
                final = -val_real if tipo == "Gasto" else val_real
                # Guardamos las 5 columnas exactas
                hoja1.append_row([str(fecha), cat, desc, final, tipo])
                st.success("Guardado.")
                st.rerun()
            else:
                st.warning("Cantidad debe ser mayor a 0")

    # 5. Tabla Historial
    if not df.empty:
        # Preparamos tabla para ver
        df_show = df.copy()
        df_show['Monto'] = df_show['Monto_Limpio'].apply(mostrar_euros)
        
        # Solo mostramos columnas si existen (Evita KeyError)
        cols_view = ['Fecha', 'Categoría', 'Monto', 'Concepto']
        cols_existentes = [c for c in cols_view if c in df_show.columns]
        
        st.dataframe(df_show[cols_existentes].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# PESTAÑA 2: OBJETIVOS
with tab2:
    st.header("🎯 Metas")
    with st.form("obj"):
        nom = st.text_input("Meta")
        obj_in = st.text_input("Cantidad Meta (€)", placeholder="Ej: 1500,00")
        f_fin = st.date_input("Fecha Límite")
        
        obj_val = forzar_decimales(obj_in)
        
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
        sueldo = forzar_decimales(sueldo_in)

        for i, row in df_o.iterrows():
            meta = forzar_decimales(row['Monto_Meta'])
            dias = (pd.to_datetime(row['Fecha_Limite']).date() - date.today()).days
            meses = max(dias/30, 0.1)
            ahorro = meta/meses
            
            with st.container(border=True):
                c1, c2 = st.columns([3,1])
                c1.markdown(f"### {row['Objetivo']}")
                c1.write(f"Meta: **{mostrar_euros(meta)}**")
                if dias>0:
                    c1.info(f"Ahorra **{mostrar_euros(ahorro)}/mes**")
                else:
                    c1.success("Finalizado")