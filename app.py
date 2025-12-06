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

# --- FUNCIONES DE LIMPIEZA ---

def procesar_texto_a_numero(valor):
    """
    Convierte texto del Excel (formato español) a número Python.
    "4139,14" -> 4139.14
    """
    texto = str(valor).strip()
    if not texto: return 0.0
    try:
        texto = texto.replace(".", "").replace(",", ".")
        return float(texto)
    except:
        return 0.0

def formato_visual(numero):
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
    try:
        data = hoja1.get_all_records(numericise_ignore=['all'])
        df = pd.DataFrame(data)
    except: df = pd.DataFrame()

    ingresos, gastos, saldo = 0.0, 0.0, 0.0

    if not df.empty and 'Monto' in df.columns:
        df['Monto_Calc'] = df['Monto'].apply(procesar_texto_a_numero)
        ingresos = df[df['Monto_Calc'] > 0]['Monto_Calc'].sum()
        gastos = df[df['Monto_Calc'] < 0]['Monto_Calc'].sum()
        saldo = df['Monto_Calc'].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo Actual", formato_visual(saldo))
    c2.metric("Ingresos", formato_visual(ingresos))
    c3.metric("Gastos", formato_visual(gastos), delta_color="inverse")

    st.divider()

    st.subheader("Nuevo Movimiento")
    with st.form("mov"):
        c_a, c_b = st.columns(2)
        fecha = c_a.date_input("Fecha")
        monto_txt = c_a.text_input("Cantidad (€)", placeholder="Ej: 4139,14")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        val_guardar = procesar_texto_a_numero(monto_txt)
        if monto_txt: st.info(f"🔢 Se guardará como: **{val_guardar}**")

        if st.form_submit_button("Guardar"):
            if val_guardar > 0:
                final = -val_guardar if tipo == "Gasto" else val_guardar
                valor_excel = str(final).replace(".", ",")
                hoja1.append_row([str(fecha), cat, desc, valor_excel, tipo])
                st.success("Guardado.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Introduce una cantidad válida.")

    if not df.empty:
        df_show = df.copy()
        df_show['Monto'] = df_show['Monto_Calc'].apply(formato_visual)
        cols = [c for c in ['Fecha', 'Categoría', 'Monto', 'Concepto'] if c in df_show.columns]
        st.dataframe(df_show[cols].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# === PESTAÑA OBJETIVOS (CON ELIMINAR) ===
with tab2:
    st.header("🎯 Metas")
    
    # Formulario Crear
    with st.expander("➕ Añadir Nueva Meta", expanded=False):
        with st.form("obj"):
            nom = st.text_input("Meta")
            cant = st.text_input("Cantidad (€)", placeholder="Ej: 1500,00")
            fin = st.date_input("Fecha Fin")
            val = procesar_texto_a_numero(cant)
            
            if st.form_submit_button("Crear") and val > 0:
                val_excel = str(val).replace(".", ",")
                hoja_obj.append_row([nom, val_excel, str(fin), str(date.today())])
                st.success("¡Meta creada!")
                st.cache_data.clear()
                st.rerun()

    # Listado de Metas con Botón de Borrar
    try:
        do = hoja_obj.get_all_records(numericise_ignore=['all'])
        dfo = pd.DataFrame(do)
        
        if not dfo.empty:
            st.divider()
            sueldo = procesar_texto_a_numero(st.text_input("Sueldo Mensual (para calcular)", "1500"))
            
            # Recorremos las metas
            for i, r in dfo.iterrows():
                m = procesar_texto_a_numero(r['Monto_Meta'])
                dias = (pd.to_datetime(r['Fecha_Limite']).date() - date.today()).days
                ahorro = m / max(dias/30, 0.1)
                
                # Usamos columnas para poner el botón a la derecha
                with st.container(border=True):
                    col_info, col_borrar = st.columns([4, 1])
                    
                    with col_info:
                        st.markdown(f"### {r['Objetivo']}")
                        st.write(f"Meta: **{formato_visual(m)}**")
                        if dias > 0:
                            st.info(f"Ahorra **{formato_visual(ahorro)}/mes**")
                        else:
                            st.success("¡Tiempo cumplido!")
                    
                    with col_borrar:
                        st.write("") # Espacio para bajar el botón
                        # El truco: key=f"del_{i}" hace que cada botón sea único
                        if st.button("🗑️", key=f"del_{i}", help="Eliminar esta meta"):
                            # Borramos la fila en Excel (i + 2 porque Excel tiene encabezados)
                            hoja_obj.delete_rows(i + 2)
                            st.toast("Meta eliminada correctamente")
                            st.cache_data.clear()
                            st.rerun()
        else:
            st.info("No tienes metas activas.")
            
    except Exception as e: 
        st.error(f"Error cargando metas: {e}")