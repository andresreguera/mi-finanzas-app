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

# --- FUNCIONES DE LIMPIEZA Y FORMATO ---

def limpiar_numero(valor):
    """
    Convierte cualquier entrada a un número decimal válido para Python.
    ESTRATEGIA:
    1. Si hay puntos y comas (ej: 4.139,14), asumimos punto=miles, coma=decimal.
    2. Si solo hay coma (ej: 9,14), coma=decimal.
    3. Si solo hay punto (ej: 10.50), punto=decimal.
    """
    if valor is None or str(valor).strip() == "": return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    
    s = str(valor).strip()
    try:
        # Caso complejo: 1.000,50 -> Quitamos el punto
        if "." in s and "," in s:
            s = s.replace(".", "")
        
        # Regla de oro: La coma siempre pasa a ser punto decimal
        s = s.replace(",", ".")
        return float(s)
    except:
        return 0.0

def formato_visual(numero):
    # Transforma 4139.14 en "4.139,14 €"
    try:
        return "{:,.2f} €".format(float(numero)).replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0,00 €"

# --- BARRA LATERAL (RESET) ---
with st.sidebar:
    st.header("⚙️ Opciones")
    if st.button("⚠️ BORRAR TODO Y REINICIAR TABLA", type="primary"):
        hoja1.clear()
        # Encabezados exactos para evitar errores futuros
        hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        st.cache_data.clear()
        st.success("Tabla limpia. Los errores antiguos han desaparecido.")
        st.rerun()

# --- INTERFAZ ---
st.title("💰 Mi Cartera")

tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos"])

# === PESTAÑA DIARIO ===
with tab1:
    # 1. Cargar Datos
    try:
        data = hoja1.get_all_records()
        df = pd.DataFrame(data)
    except: df = pd.DataFrame()

    ingresos, gastos, saldo = 0.0, 0.0, 0.0

    if not df.empty and 'Monto' in df.columns:
        # Limpiamos los datos matemáticamente
        df['Monto_Calc'] = df['Monto'].apply(limpiar_numero)
        
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
        monto_txt = c_a.text_input("Cantidad (€)", placeholder="Ej: 9,14 o 4000")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        # Previsualización para tu tranquilidad
        val_guardar = limpiar_numero(monto_txt)
        if monto_txt:
            st.info(f"🔢 El sistema guardará: **{val_guardar}** (que visualmente es {formato_visual(val_guardar)})")

        if st.form_submit_button("Guardar"):
            if val_guardar > 0:
                final = -val_guardar if tipo == "Gasto" else val_guardar
                # Guardamos el número limpio en el Excel
                hoja1.append_row([str(fecha), cat, desc, final, tipo])
                st.success("Guardado correctamente.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Introduce una cantidad válida.")

    # 4. Tabla Historial (SOLUCIÓN DEL ERROR VALUE ERROR)
    if not df.empty:
        # Creamos una copia para visualizar
        df_show = df.copy()
        
        # SOBRESCRIBIMOS la columna Monto con el texto bonito
        # Esto evita tener dos columnas 'Monto' y 'Monto_Visual' chocando
        df_show['Monto'] = df_show['Monto_Calc'].apply(formato_visual)
        
        # Seleccionamos las columnas que existen seguro
        cols_finales = ['Fecha', 'Categoría', 'Monto', 'Concepto']
        # Filtramos por si acaso alguna columna cambió de nombre en el Excel
        cols_existentes = [c for c in cols_finales if c in df_show.columns]
        
        st.dataframe(df_show[cols_existentes].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# === PESTAÑA OBJETIVOS ===
with tab2:
    st.header("🎯 Metas")
    with st.form("obj"):
        nom = st.text_input("Meta")
        cant = st.text_input("Cantidad", placeholder="Ej: 1500,00")
        fin = st.date_input("Fecha Fin")
        val = limpiar_numero(cant)
        
        if st.form_submit_button("Crear") and val > 0:
            hoja_obj.append_row([nom, val, str(fin), str(date.today())])
            st.rerun()

    try:
        dfo = pd.DataFrame(hoja_obj.get_all_records())
        if not dfo.empty:
            st.divider()
            sueldo = limpiar_numero(st.text_input("Sueldo Mensual", "1500"))
            for i, r in dfo.iterrows():
                m = limpiar_numero(r['Monto_Meta'])
                dias = (pd.to_datetime(r['Fecha_Limite']).date() - date.today()).days
                ahorro = m / max(dias/30, 0.1)
                st.info(f"**{r['Objetivo']}**: Ahorra {formato_visual(ahorro)}/mes")
    except: pass