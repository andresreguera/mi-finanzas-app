import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Mi Cartera Pro", page_icon="💰", layout="centered")

# --- CONEXIÓN CON GOOGLE SHEETS ---
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
    st.error("⚠️ Falta la hoja 'Objetivos' en tu Excel.")
    st.stop()

# --- FUNCIONES DE LIMPIEZA (LÓGICA TODOTERRENO) ---
def numero_puro(valor):
    """
    Convierte cualquier cosa que escribas en un número válido.
    - 9,14 -> 9.14
    - 9.14 -> 9.14
    - 1000 -> 1000.0
    """
    if valor is None or str(valor).strip() == "": 
        return 0.0
    
    # Si ya es número, perfecto
    if isinstance(valor, (int, float)):
        return float(valor)
    
    # Si es texto, hacemos la magia
    s = str(valor).strip()
    try:
        # Regla de oro: Cambiamos la COMA por PUNTO siempre.
        # Así Python entiende que es un decimal.
        s = s.replace(",", ".")
        return float(s)
    except:
        return 0.0

def formato_visual(numero):
    """Muestra el dinero bonito: 1.234,56 €"""
    try:
        txt = "{:,.2f}".format(float(numero))
        return txt.replace(",", "X").replace(".", ",").replace("X", ".") + " €"
    except:
        return "0,00 €"

# --- BARRA LATERAL: ZONA DE MANTENIMIENTO ---
with st.sidebar:
    st.header("⚙️ Mantenimiento")
    st.warning("Usa este botón si los saldos salen mal para empezar de cero.")
    
    # EL BOTÓN NUCLEAR ☢️
    if st.button("☢️ RESETEAR TABLA (BORRAR TODO)", type="primary"):
        hoja1.clear()
        # Escribimos los encabezados correctos automáticamente
        hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        st.cache_data.clear()
        st.success("✅ Tabla reiniciada y limpia. ¡Empieza de nuevo!")
        st.rerun()

# --- INTERFAZ PRINCIPAL ---
st.title("💰 Mi Cartera")
tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos"])

# === PESTAÑA 1: DIARIO ===
with tab1:
    # 1. Leer datos del Excel
    try:
        data = hoja1.get_all_records()
        df = pd.DataFrame(data)
    except: df = pd.DataFrame()

    # 2. Calcular Saldos (Usando el limpiador todoterreno)
    ingresos, gastos, saldo = 0.0, 0.0, 0.0

    if not df.empty and 'Monto' in df.columns:
        # Limpiamos la columna Monto entera
        df['Monto_Limpio'] = df['Monto'].apply(numero_puro)
        
        ingresos = df[df['Monto_Limpio'] > 0]['Monto_Limpio'].sum()
        gastos = df[df['Monto_Limpio'] < 0]['Monto_Limpio'].sum()
        saldo = df['Monto_Limpio'].sum()

    # 3. Mostrar Tarjetas de Saldo
    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Actual", formato_visual(saldo))
    c2.metric("Ingresos", formato_visual(ingresos))
    c3.metric("Gastos", formato_visual(gastos), delta_color="inverse")

    st.divider()

    # 4. Formulario de Entrada
    st.subheader("Nuevo Movimiento")
    with st.form("mov"):
        c_a, c_b = st.columns(2)
        fecha = c_a.date_input("Fecha")
        
        # Input de texto para que puedas poner comas o puntos libremente
        monto_txt = c_a.text_input("Cantidad (€)", placeholder="Ej: 9,14")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        # Previsualización inteligente
        val_real = numero_puro(monto_txt)
        if monto_txt:
            st.caption(f"👀 Se guardará como: **{val_real}**")

        if st.form_submit_button("Guardar"):
            if val_real > 0:
                final = -val_real if tipo == "Gasto" else val_real
                # Guardamos las 5 columnas en orden exacto
                hoja1.append_row([str(fecha), cat, desc, final, tipo])
                st.success("¡Guardado!")
                st.rerun()
            else:
                st.warning("Pon una cantidad mayor a 0")

    # 5. Tabla Historial
    if not df.empty:
        df_show = df.copy()
        df_show['Monto'] = df_show['Monto_Limpio'].apply(formato_visual)
        
        # Mostramos solo las columnas que nos interesan
        cols = ['Fecha', 'Categoría', 'Monto', 'Concepto']
        # Filtro de seguridad por si faltan columnas
        cols_existentes = [c for c in cols if c in df_show.columns]
        
        st.dataframe(df_show[cols_existentes].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# === PESTAÑA 2: OBJETIVOS ===
with tab2:
    st.header("🎯 Mis Metas")
    with st.form("obj"):
        nom = st.text_input("Meta")
        obj_txt = st.text_input("Cantidad Meta (€)", placeholder="Ej: 1500,00")
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
        sueldo_in = st.text_input("Tu sueldo mensual (para calcular)", value="1500")
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
                
                if dias > 0:
                    pct = (ahorro / sueldo * 100) if sueldo > 0 else 0
                    msg = f"Ahorra **{formato_visual(ahorro)}/mes** ({pct:.0f}% sueldo)"
                    if pct > 40: c1.error(msg)
                    elif pct > 20: c1.warning(msg)
                    else: c1.success(msg)
                else:
                    c1.success("¡Meta finalizada!")