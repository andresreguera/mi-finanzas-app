import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import plotly.express as px

# --- 1. CONFIGURACIÓN ---
st.set_page_config(
    page_title="Mi Economía", 
    page_icon="💳", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS DE ANIMACIONES FLUIDAS (EL MOTOR VISUAL) ---
estilo_animado = """
    <style>
        /* IMPORTAR FUENTE DE APPLE (SF PRO / HELVETICA) */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* --- 1. OCULTAR ELEMENTOS DE STREAMLIT (MODO LIMPIO) --- */
        header {visibility: hidden !important; height: 0px !important;}
        div[data-testid="stToolbar"] {display: none !important;}
        div[data-testid="stDecoration"] {display: none !important;}
        footer {display: none !important;}
        #MainMenu {display: none !important;}
        
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 6rem !important;
            max_width: 800px;
        }

        /* --- 2. ANIMACIÓN DE ENTRADA (FADE IN UP) --- */
        @keyframes fadeInUp {
            from { opacity: 0; transform: translate3d(0, 20px, 0); }
            to { opacity: 1; transform: translate3d(0, 0, 0); }
        }

        .main {
            animation: fadeInUp 0.6s ease-out;
        }

        /* --- 3. TARJETAS FLOTANTES (KPIs y CONTENEDORES) --- */
        div[data-testid="metric-container"], div[data-testid="stExpander"], div.stContainer {
            background-color: #ffffff;
            border: 1px solid #f0f2f6;
            border-radius: 16px; /* Bordes más redondeados estilo iOS */
            padding: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.02);
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        }

        /* Efecto al pasar el ratón o tocar */
        div[data-testid="metric-container"]:hover {
            transform: translateY(-4px) scale(1.01);
            box-shadow: 0 12px 20px rgba(0,0,0,0.08);
            border-color: #e0e0e0;
        }

        /* --- 4. BOTONES TÁCTILES --- */
        .stButton button {
            border-radius: 12px;
            font-weight: 600;
            border: none;
            transition: all 0.2s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        /* Efecto de pulsación real */
        .stButton button:active {
            transform: scale(0.95);
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
        }

        /* Botones primarios (Guardar) con degradado sutil */
        button[kind="primary"] {
            background: linear-gradient(135deg, #FF4B4B 0%, #FF2B2B 100%);
            color: white;
        }

        /* --- 5. PESTAÑAS MODERNAS --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            height: 45px;
            white-space: pre-wrap;
            border-radius: 10px;
            padding: 0 15px;
            transition: background 0.3s;
        }
        .stTabs [aria-selected="true"] {
            background-color: #ffffff;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            color: #FF4B4B !important;
            font-weight: 700;
        }
    </style>
"""
st.markdown(estilo_animado, unsafe_allow_html=True)

# --- 3. CONEXIÓN ---
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
try: hoja_obj = libro.worksheet("Objetivos")
except: st.error("Falta hoja Objetivos"); st.stop()
try: hoja_deudas = libro.worksheet("Deudas")
except: hoja_deudas = None

# --- 4. FUNCIONES ---
def procesar_texto_a_numero(valor):
    texto = str(valor).strip()
    if not texto: return 0.0
    try: return float(texto.replace(".", "").replace(",", "."))
    except: return 0.0

def formato_visual(numero):
    try: return "{:,.2f} €".format(float(numero)).replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00 €"

def saludo_dinamico():
    h = datetime.now().hour
    if 6 <= h < 12: return "Buenos días ☀️"
    elif 12 <= h < 20: return "Buenas tardes 🌤️"
    else: return "Buenas noches 🌙"

# --- 5. BARRA LATERAL ---
with st.sidebar:
    st.write("### ⚙️ Ajustes")
    if st.button("⚠️ Reiniciar Base de Datos", type="primary"):
        hoja1.clear(); hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        if hoja_deudas:
            hoja_deudas.clear(); hoja_deudas.append_row(["Fecha", "Persona", "Concepto", "Monto", "Tipo"])
        st.cache_data.clear(); st.success("Limpio."); st.rerun()

# --- 6. CÁLCULOS ---
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

# --- 7. HEADER CON ESTILO ---
col_head, col_img = st.columns([4, 1])
with col_head:
    st.title(saludo_dinamico())
    st.caption(f"Balance actual a {date.today().strftime('%d/%m')}")

# KPI CARDS
c1, c2, c3 = st.columns(3)
c1.metric("Disponible", formato_visual(saldo_actual))
c2.metric("Entradas", formato_visual(ingresos))
c3.metric("Salidas", formato_visual(gastos), delta_color="inverse")

st.markdown("---")

# --- 8. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📝 Diario", "📊 Visión", "🎯 Metas", "💸 Deudas"])

# PESTAÑA 1: DIARIO
with tab1:
    st.subheader("Registrar")
    with st.container():
        with st.form("mov", border=False):
            c_a, c_b = st.columns(2)
            fecha = c_a.date_input("Fecha")
            monto_txt = c_a.text_input("Cantidad (€)", placeholder="0,00")
            tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
            cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina", "Ropa", "Salud", "Otros"])
            desc = st.text_input("Concepto (Opcional)")
            
            val = procesar_texto_a_numero(monto_txt)
            if st.form_submit_button("Guardar Movimiento", use_container_width=True):
                if val > 0:
                    final = -val if tipo == "Gasto" else val
                    hoja1.append_row([fecha.strftime("%d/%m/%Y"), cat, desc, str(final).replace(".", ","), tipo])
                    st.toast("✅ Guardado", icon="💾")
                    st.cache_data.clear(); st.rerun()
                else: st.toast("⚠️ Pon una cantidad", icon="🚫")

    if not df_movimientos.empty:
        st.write("#### Historial Reciente")
        df_s = df_movimientos.copy()
        df_s['Monto'] = df_s['Monto_Calc'].apply(formato_visual)
        cols = [c for c in ['Fecha', 'Categoría', 'Monto', 'Concepto'] if c in df_s.columns]
        st.dataframe(df_s[cols].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# PESTAÑA 2: REPORTE
with tab2:
    if not df_movimientos.empty:
        hoy = date.today()
        c_m, c_y = st.columns(2)
        mes = c_m.selectbox("Mes", range(1,13), index=hoy.month-1, format_func=lambda x: datetime(2022, x, 1).strftime('%B').capitalize())
        anio = c_y.number_input("Año", value=hoy.year)
        
        df_m = df_movimientos[(df_movimientos['Fecha_Dt'].dt.month == mes) & (df_movimientos['Fecha_Dt'].dt.year == anio)]
        
        if not df_m.empty:
            i_m = df_m[df_m['Monto_Calc'] > 0]['Monto_Calc'].sum()
            g_m = df_m[df_m['Monto_Calc'] < 0]['Monto_Calc'].sum()
            ahorro = i_m + g_m
            
            st.info(f"💰 Balance de {datetime(2022, mes, 1).strftime('%B')}: **{formato_visual(ahorro)}**")
            
            df_g = df_m[df_m['Monto_Calc'] < 0].copy()
            if not df_g.empty:
                st.write("##### Distribución de Gastos")
                df_g['Abs'] = df_g['Monto_Calc'].abs()
                fig = px.pie(df_g, values='Abs', names='Categoría', hole=0.6, color_discrete_sequence=px.colors.qualitative.Prism)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
                fig.update_traces(textposition='outside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            else: st.success("🎉 Cero gastos este mes")
        else: st.info("Sin movimientos en esta fecha.")

# PESTAÑA 3: METAS
with tab3:
    with st.expander("➕ Nueva Meta"):
        with st.form("new_obj"):
            nom = st.text_input("Objetivo")
            cant = st.text_input("Total (€)")
            fin = st.date_input("Fecha Fin")
            v = procesar_texto_a_numero(cant)
            if st.form_submit_button("Crear Meta", use_container_width=True) and v>0:
                hoja_obj.append_row([nom, str(v).replace(".", ","), str(fin), str(date.today())])
                st.cache_data.clear(); st.rerun()
    try:
        do = hoja_obj.get_all_records(numericise_ignore=['all'])
        if do:
            st.divider()
            sueldo = procesar_texto_a_numero(st.text_input("Tu Sueldo Mensual", "200,00"))
            
            for i, r in pd.DataFrame(do).iterrows():
                m = procesar_texto_a_numero(r['Monto_Meta'])
                falta = m - saldo_actual
                dias = (pd.to_datetime(r['Fecha_Limite']).date() - date.today()).days
                meses = max(dias/30.44, 0.1)
                
                with st.container():
                    col_txt, col_num, col_del = st.columns([3, 2, 0.5])
                    with col_txt:
                        st.markdown(f"**{r['Objetivo']}**")
                        if falta <= 0: st.success("✅ ¡Logrado!")
                        else: st.caption(f"Faltan: {formato_visual(falta)}")
                    with col_num:
                        if falta > 0 and dias > 0:
                            mensual = falta/meses
                            pct = (mensual/sueldo*100) if sueldo > 0 else 0
                            color = "green" if pct < 20 else "orange" if pct < 40 else "red"
                            st.markdown(f":{color}[**{formato_visual(mensual)}/mes**]")
                            st.caption(f"{pct:.0f}% sueldo")
                        elif dias<=0: st.error("¡Vencida!")
                    with col_del:
                        if st.button("✕", key=f"d{i}"):
                            hoja_obj.delete_rows(i+2); st.cache_data.clear(); st.rerun()
                    
                    if falta > 0 and dias > 0:
                        with st.expander("📅 Ver Plan de Pagos"):
                            fechas = pd.date_range(start=date.today(), end=pd.to_datetime(r['Fecha_Limite']), freq='ME')
                            if len(fechas) > 0:
                                df_p = pd.DataFrame({"Fecha": fechas, "Cuota": [falta/len(fechas)]*len(fechas)})
                                df_p['Acumulado'] = df_p['Cuota'].cumsum() + saldo_actual
                                df_p['Fecha'] = df_p['Fecha'].dt.strftime('%B %Y')
                                df_p['Cuota'] = df_p['Cuota'].apply(formato_visual)
                                df_p['Acumulado'] = df_p['Acumulado'].apply(formato_visual)
                                st.dataframe(df_p, use_container_width=True, hide_index=True)
    except: pass

# PESTAÑA 4: DEUDAS
with tab4:
    with st.expander("➕ Apuntar Deuda"):
        with st.form("new_deuda"):
            c1, c2 = st.columns(2)
            p = c1.text_input("Persona")
            m = c1.text_input("€")
            c = c2.text_input("Motivo")
            t = c2.radio("Tipo", ["🔴 DEBO", "🟢 ME DEBEN"])
            v = procesar_texto_a_numero(m)
            if st.form_submit_button("Guardar", use_container_width=True) and v>0:
                tg = "DEBO" if "🔴" in t else "ME DEBEN"
                hoja_deudas.append_row([date.today().strftime("%d/%m/%Y"), p, c, str(v).replace(".", ","), tg])
                st.cache_data.clear(); st.rerun()
    try:
        dd = hoja_deudas.get_all_records(numericise_ignore=['all'])
        if dd:
            st.divider()
            for i, r in pd.DataFrame(dd).iterrows():
                imp = procesar_texto_a_numero(r['Monto'])
                with st.container():
                    c1, c2 = st.columns([4,1])
                    with c1:
                        emoji = "🔴" if r['Tipo']=="DEBO" else "🟢"
                        texto = f"Debo a **{r['Persona']}**" if r['Tipo']=="DEBO" else f"Me debe **{r['Persona']}**"
                        st.markdown(f"{emoji} {texto}: **{formato_visual(imp)}**")
                        st.caption(f"{r['Concepto']} | {r['Fecha']}")
                    with c2:
                        if st.button("✅", key=f"s{i}", help="Saldar"):
                            hoja_deudas.delete_rows(i+2); st.toast("Saldado"); st.cache_data.clear(); st.rerun()
        else: st.caption("No tienes deudas pendientes.")
    except: pass