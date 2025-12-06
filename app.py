import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Finanzas", page_icon="💰", layout="centered")

# --- 🎨 ESTILO "MODO FANTASMA" (CSS NUCLEAR) ---
hide_styles = """
    <style>
        header {visibility: hidden !important; height: 0px !important;}
        header[data-testid="stHeader"] {display: none !important;}
        div[data-testid="stDecoration"] {display: none !important; height: 0px !important;}
        div[data-testid="stToolbar"] {display: none !important; visibility: hidden !important;}
        #MainMenu {visibility: hidden !important; display: none !important;}
        footer {visibility: hidden !important; display: none !important;}
        .block-container {
            padding-top: 0rem !important;
            padding-bottom: 5rem !important;
        }
        .stDeployButton {display: none !important;}
        [data-testid="stStatusWidget"] {display: none !important;}
    </style>
"""
st.markdown(hide_styles, unsafe_allow_html=True)

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
try:
    hoja_deudas = libro.worksheet("Deudas")
except:
    hoja_deudas = None

# --- FUNCIONES ---
def procesar_texto_a_numero(valor):
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
    if st.button("⚠️ BORRAR TODO Y REINICIAR", type="primary"):
        hoja1.clear()
        hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        if hoja_deudas:
            hoja_deudas.clear()
            hoja_deudas.append_row(["Fecha", "Persona", "Concepto", "Monto", "Tipo"])
        st.cache_data.clear()
        st.rerun()

# --- CÁLCULOS ---
saldo_actual, ingresos, gastos = 0.0, 0.0, 0.0
df_movimientos = pd.DataFrame()

try:
    data = hoja1.get_all_records(numericise_ignore=['all'])
    df_movimientos = pd.DataFrame(data)
    if not df_movimientos.empty and 'Monto' in df_movimientos.columns:
        df_movimientos['Monto_Calc'] = df_movimientos['Monto'].apply(procesar_texto_a_numero)
        df_movimientos['Fecha_Dt'] = pd.to_datetime(df_movimientos['Fecha'], dayfirst=True, errors='coerce')
        ingresos = df_movimientos[df_movimientos['Monto_Calc'] > 0]['Monto_Calc'].sum()
        gastos = df_movimientos[df_movimientos['Monto_Calc'] < 0]['Monto_Calc'].sum()
        saldo_actual = df_movimientos['Monto_Calc'].sum()
except: pass

# --- INTERFAZ ---
st.title("💰 Mi Cartera")

c1, c2, c3 = st.columns(3)
c1.metric("Saldo", formato_visual(saldo_actual))
c2.metric("Ingresos", formato_visual(ingresos))
c3.metric("Gastos", formato_visual(gastos), delta_color="inverse")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["📝 Diario", "📊 Reporte", "🎯 Metas", "💸 Deudas"])

# PESTAÑA 1: DIARIO
with tab1:
    with st.form("mov"):
        c_a, c_b = st.columns(2)
        fecha = c_a.date_input("Fecha")
        monto_txt = c_a.text_input("Cantidad (€)", placeholder="Ej: 9,14")
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina", "Otros"])
        desc = st.text_input("Concepto")
        val = procesar_texto_a_numero(monto_txt)
        if st.form_submit_button("Guardar"):
            if val > 0:
                final = -val if tipo == "Gasto" else val
                hoja1.append_row([fecha.strftime("%d/%m/%Y"), cat, desc, str(final).replace(".", ","), tipo])
                st.cache_data.clear()
                st.rerun()
    if not df_movimientos.empty:
        df_s = df_movimientos.copy()
        df_s['Monto'] = df_s['Monto_Calc'].apply(formato_visual)
        cols = [c for c in ['Fecha', 'Categoría', 'Monto', 'Concepto'] if c in df_s.columns]
        st.dataframe(df_s[cols].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# PESTAÑA 2: REPORTE
with tab2:
    if not df_movimientos.empty:
        hoy = date.today()
        c_m, c_y = st.columns(2)
        mes = c_m.selectbox("Mes", range(1,13), index=hoy.month-1, format_func=lambda x: datetime(2022, x, 1).strftime('%B'))
        anio = c_y.number_input("Año", value=hoy.year)
        df_m = df_movimientos[(df_movimientos['Fecha_Dt'].dt.month == mes) & (df_movimientos['Fecha_Dt'].dt.year == anio)]
        if not df_m.empty:
            i_m = df_m[df_m['Monto_Calc'] > 0]['Monto_Calc'].sum()
            g_m = df_m[df_m['Monto_Calc'] < 0]['Monto_Calc'].sum()
            st.metric("Ahorro Mes", formato_visual(i_m+g_m))
            df_g = df_m[df_m['Monto_Calc'] < 0].copy()
            if not df_g.empty:
                df_g['Abs'] = df_g['Monto_Calc'].abs()
                fig = px.pie(df_g, values='Abs', names='Categoría', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)

# PESTAÑA 3: METAS (ACTUALIZADA CON PORCENTAJE)
with tab3:
    with st.expander("➕ Meta"):
        with st.form("new_obj"):
            nom = st.text_input("Nombre")
            cant = st.text_input("Total (€)")
            fin = st.date_input("Fin")
            v = procesar_texto_a_numero(cant)
            if st.form_submit_button("Crear") and v>0:
                hoja_obj.append_row([nom, str(v).replace(".", ","), str(fin), str(date.today())])
                st.cache_data.clear()
                st.rerun()
    try:
        do = hoja_obj.get_all_records(numericise_ignore=['all'])
        if do:
            st.divider()
            sueldo = procesar_texto_a_numero(st.text_input("Sueldo Mensual", "200,00"))
            
            for i, r in pd.DataFrame(do).iterrows():
                m = procesar_texto_a_numero(r['Monto_Meta'])
                falta = m - saldo_actual
                dias = (pd.to_datetime(r['Fecha_Limite']).date() - date.today()).days
                meses = max(dias/30.44, 0.1)
                
                with st.container(border=True):
                    c1, c2 = st.columns([3,1])
                    c1.write(f"**{r['Objetivo']}** | Faltan: {formato_visual(falta)}")
                    
                    if falta > 0 and dias > 0:
                        ahorro_mes = falta / meses
                        
                        # --- CÁLCULO DEL PORCENTAJE ---
                        pct = 0.0
                        if sueldo > 0:
                            pct = (ahorro_mes / sueldo) * 100
                        
                        msg = f"Ahorra **{formato_visual(ahorro_mes)}/mes** ({pct:.0f}% de tu sueldo)"
                        
                        # Semáforo de colores
                        if pct > 40:
                            c1.error(f"⚠️ {msg}")
                        elif pct > 20:
                            c1.warning(f"📊 {msg}")
                        else:
                            c1.success(f"✅ {msg}")
                            
                        # Calendario
                        with st.expander("📅 Ver Plan"):
                            fechas = pd.date_range(start=date.today(), end=pd.to_datetime(r['Fecha_Limite']), freq='ME')
                            if len(fechas) > 0:
                                cuota = falta / len(fechas)
                                df_plan = pd.DataFrame({"Fecha": fechas, "Cuota": [cuota]*len(fechas)})
                                df_plan['Acumulado'] = df_plan['Cuota'].cumsum() + saldo_actual
                                df_plan['Fecha'] = df_plan['Fecha'].dt.strftime('%B %Y')
                                df_plan['Cuota'] = df_plan['Cuota'].apply(formato_visual)
                                df_plan['Acumulado'] = df_plan['Acumulado'].apply(formato_visual)
                                st.dataframe(df_plan, use_container_width=True, hide_index=True)
                    
                    elif dias <= 0:
                        c1.error("¡Fecha Vencida!")
                    
                    if c2.button("🗑️", key=f"d{i}"):
                        hoja_obj.delete_rows(i+2)
                        st.cache_data.clear()
                        st.rerun()
    except: pass

# PESTAÑA 4: DEUDAS
with tab4:
    with st.expander("➕ Deuda"):
        with st.form("new_deuda"):
            p = st.text_input("Persona")
            m = st.text_input("€")
            c = st.text_input("Motivo")
            t = st.radio("Tipo", ["🔴 DEBO", "🟢 ME DEBEN"])
            v = procesar_texto_a_numero(m)
            if st.form_submit_button("Anotar") and v>0:
                tg = "DEBO" if "🔴" in t else "ME DEBEN"
                hoja_deudas.append_row([date.today().strftime("%d/%m/%Y"), p, c, str(v).replace(".", ","), tg])
                st.cache_data.clear()
                st.rerun()
    try:
        dd = hoja_deudas.get_all_records(numericise_ignore=['all'])
        if dd:
            st.divider()
            for i, r in pd.DataFrame(dd).iterrows():
                imp = procesar_texto_a_numero(r['Monto'])
                with st.container(border=True):
                    c1, c2 = st.columns([4,1])
                    if r['Tipo']=="DEBO": c1.error(f"🔴 Debo a **{r['Persona']}**: {formato_visual(imp)}")
                    else: c1.success(f"🟢 Me debe **{r['Persona']}**: {formato_visual(imp)}")
                    if c2.button("✅", key=f"s{i}"):
                        hoja_deudas.delete_rows(i+2)
                        st.cache_data.clear()
                        st.rerun()
    except: pass