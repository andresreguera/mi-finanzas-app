import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import plotly.express as px

# --- 1. CONFIGURACIÓN ---
st.set_page_config(
    page_title="Mi Finanzas", 
    page_icon="🏛️", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS "BANCA CORPORATIVA" (ALTO CONTRASTE) ---
estilo_confianza = """
    <style>
        /* FUENTE ROBUSTA */
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Roboto', sans-serif;
            color: #0f172a; /* Negro azulado para máximo contraste */
        }

        /* FONDO PRINCIPAL */
        .stApp {
            background-color: #f1f5f9; /* Gris muy suave, descansa la vista */
        }

        /* --- MODO FANTASMA --- */
        header {visibility: hidden !important; height: 0px !important;}
        div[data-testid="stToolbar"] {display: none !important;}
        div[data-testid="stDecoration"] {display: none !important;}
        footer {display: none !important;}
        
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 6rem !important;
        }

        /* --- TÍTULOS Y TEXTOS --- */
        h1, h2, h3 {
            color: #1e3a8a !important; /* AZUL MARINO FUERTE */
            font-weight: 700 !important;
        }
        
        p, label, .stMarkdown {
            color: #334155 !important; /* Gris oscuro muy legible */
            font-size: 1rem !important;
        }

        /* --- TARJETAS (KPIs y CONTENEDORES) --- */
        div[data-testid="metric-container"] {
            background-color: #ffffff;
            border: 1px solid #cbd5e1; /* Borde sutil pero visible */
            border-left: 5px solid #1e3a8a; /* Borde lateral azul corporativo */
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        /* Texto de las métricas más grande y oscuro */
        div[data-testid="metric-container"] label {
            font-size: 1rem !important;
            color: #475569 !important;
        }
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
            color: #0f172a !important;
            font-weight: 700;
        }

        /* --- BOTONES SÓLIDOS --- */
        .stButton button {
            background-color: #1e40af !important; /* Azul Real */
            color: white !important;
            border: none;
            border-radius: 6px;
            padding: 0.75rem 1.5rem;
            font-weight: 600;
            text-transform: uppercase; /* Letras mayúsculas dan autoridad */
            letter-spacing: 0.5px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: background 0.3s;
        }
        
        .stButton button:hover {
            background-color: #1e3a8a !important; /* Azul más oscuro al pasar ratón */
        }

        /* Botones secundarios (Borrar/Rojos) */
        button[kind="secondary"] {
            background-color: white !important;
            color: #dc2626 !important;
            border: 2px solid #dc2626 !important;
        }

        /* --- INPUTS CLAROS --- */
        .stTextInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
            background-color: #ffffff;
            border: 2px solid #94a3b8; /* Borde más grueso para ver bien dónde escribir */
            color: #0f172a;
            border-radius: 6px;
            height: 45px;
        }
        
        /* --- PESTAÑAS --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 5px;
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #e2e8f0;
            color: #475569;
            font-weight: 600;
            border-radius: 6px 6px 0 0;
            border: 1px solid #cbd5e1;
            border-bottom: none;
        }
        .stTabs [aria-selected="true"] {
            background-color: #ffffff;
            color: #1e3a8a !important; /* Azul en la pestaña activa */
            border-top: 3px solid #1e3a8a; /* Línea superior azul */
        }
    </style>
"""
st.markdown(estilo_confianza, unsafe_allow_html=True)

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
    if 6 <= h < 12: return "Buenos días"
    elif 12 <= h < 20: return "Buenas tardes"
    else: return "Buenas noches"

# --- 5. BARRA LATERAL ---
with st.sidebar:
    st.markdown("### ⚙️ Configuración")
    if st.button("⚠️ RESTAURAR DATOS", type="primary"):
        hoja1.clear(); hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        if hoja_deudas:
            hoja_deudas.clear(); hoja_deudas.append_row(["Fecha", "Persona", "Concepto", "Monto", "Tipo"])
        st.cache_data.clear(); st.success("Sistema reiniciado."); st.rerun()

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

# --- 7. HEADER CORPORATIVO ---
st.markdown(f"<h2 style='text-align: left; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px;'>{saludo_dinamico()}, Andrés</h2>", unsafe_allow_html=True)
st.markdown(f"<p style='color: #475569;'>Estado financiero a <b>{date.today().strftime('%d/%m/%Y')}</b></p>", unsafe_allow_html=True)

# KPI CARDS
c1, c2, c3 = st.columns(3)
c1.metric("💰 Disponible", formato_visual(saldo_actual))
c2.metric("📈 Ingresos", formato_visual(ingresos))
c3.metric("📉 Gastos", formato_visual(gastos), delta_color="inverse")

st.markdown("<br>", unsafe_allow_html=True)

# --- 8. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["DIARIO", "INFORMES", "METAS", "DEUDAS"])

# PESTAÑA 1: DIARIO
with tab1:
    st.markdown("#### 📝 Registrar Operación")
    with st.container():
        with st.form("mov"):
            c_a, c_b = st.columns(2)
            fecha = c_a.date_input("Fecha operación")
            monto_txt = c_a.text_input("Importe (€)", placeholder="0,00")
            tipo = c_b.selectbox("Tipo de movimiento", ["Gasto", "Ingreso", "Sueldo"])
            cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Vivienda", "Ocio", "Ahorro", "Nómina", "Salud", "Otros"])
            desc = st.text_input("Concepto / Descripción")
            
            val = procesar_texto_a_numero(monto_txt)
            
            if st.form_submit_button("GUARDAR OPERACIÓN", use_container_width=True):
                if val > 0:
                    final = -val if tipo == "Gasto" else val
                    hoja1.append_row([fecha.strftime("%d/%m/%Y"), cat, desc, str(final).replace(".", ","), tipo])
                    st.toast("✅ Operación registrada con éxito")
                    st.cache_data.clear(); st.rerun()
                else: st.warning("El importe debe ser mayor a 0")

    if not df_movimientos.empty:
        st.markdown("#### 📋 Últimos Movimientos")
        df_s = df_movimientos.copy()
        df_s['Monto'] = df_s['Monto_Calc'].apply(formato_visual)
        cols = [c for c in ['Fecha', 'Categoría', 'Monto', 'Concepto'] if c in df_s.columns]
        st.dataframe(df_s[cols].tail(7).sort_index(ascending=False), use_container_width=True, hide_index=True)

# PESTAÑA 2: REPORTE
with tab2:
    if not df_movimientos.empty:
        hoy = date.today()
        c_m, c_y = st.columns(2)
        mes = c_m.selectbox("Mes del reporte", range(1,13), index=hoy.month-1, format_func=lambda x: datetime(2022, x, 1).strftime('%B').upper())
        anio = c_y.number_input("Año", value=hoy.year)
        
        df_m = df_movimientos[(df_movimientos['Fecha_Dt'].dt.month == mes) & (df_movimientos['Fecha_Dt'].dt.year == anio)]
        
        if not df_m.empty:
            i_m = df_m[df_m['Monto_Calc'] > 0]['Monto_Calc'].sum()
            g_m = df_m[df_m['Monto_Calc'] < 0]['Monto_Calc'].sum()
            ahorro = i_m + g_m
            
            st.info(f"💵 Resultado Neto de {datetime(2022, mes, 1).strftime('%B')}: **{formato_visual(ahorro)}**")
            
            df_g = df_m[df_m['Monto_Calc'] < 0].copy()
            if not df_g.empty:
                st.markdown("##### Desglose de Gastos")
                df_g['Abs'] = df_g['Monto_Calc'].abs()
                # Colores sólidos y profesionales para el gráfico
                fig = px.pie(df_g, values='Abs', names='Categoría', hole=0.5, 
                             color_discrete_sequence=["#1e3a8a", "#1d4ed8", "#3b82f6", "#60a5fa", "#93c5fd"])
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else: st.success("No hay gastos registrados en este periodo.")
        else: st.warning("No existen datos para el periodo seleccionado.")

# PESTAÑA 3: METAS
with tab3:
    with st.expander("➕ Definir Nuevo Objetivo"):
        with st.form("new_obj"):
            nom = st.text_input("Nombre del Objetivo")
            cant = st.text_input("Importe Necesario (€)")
            fin = st.date_input("Fecha Límite")
            v = procesar_texto_a_numero(cant)
            if st.form_submit_button("CREAR OBJETIVO", use_container_width=True) and v>0:
                hoja_obj.append_row([nom, str(v).replace(".", ","), str(fin), str(date.today())])
                st.cache_data.clear(); st.rerun()
    try:
        do = hoja_obj.get_all_records(numericise_ignore=['all'])
        if do:
            st.markdown("<br>", unsafe_allow_html=True)
            sueldo = procesar_texto_a_numero(st.text_input("Ingreso Mensual Neto", "200,00"))
            
            for i, r in pd.DataFrame(do).iterrows():
                m = procesar_texto_a_numero(r['Monto_Meta'])
                falta = m - saldo_actual
                dias = (pd.to_datetime(r['Fecha_Limite']).date() - date.today()).days
                meses = max(dias/30.44, 0.1)
                
                with st.container():
                    col_txt, col_num, col_del = st.columns([3, 2, 0.5])
                    with col_txt:
                        st.markdown(f"**{r['Objetivo']}**")
                        if falta <= 0: st.success("✅ Objetivo Alcanzado")
                        else: st.markdown(f"Faltan: **{formato_visual(falta)}**")
                    with col_num:
                        if falta > 0 and dias > 0:
                            mensual = falta/meses
                            pct = (mensual/sueldo*100) if sueldo > 0 else 0
                            # Colores de alerta estándar (Semáforo)
                            color_t = "green" if pct < 20 else "orange" if pct < 40 else "red"
                            st.markdown(f":{color_t}[**{formato_visual(mensual)} / mes**]")
                            st.caption(f"Esfuerzo: {pct:.0f}% del ingreso")
                        elif dias<=0: st.error("Plazo vencido")
                    with col_del:
                        if st.button("✖️", key=f"d{i}"):
                            hoja_obj.delete_rows(i+2); st.cache_data.clear(); st.rerun()
                    
                    if falta > 0 and dias > 0:
                        with st.expander("Ver Plan de Amortización"):
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
    with st.expander("➕ Registrar Deuda / Préstamo"):
        with st.form("new_deuda"):
            c1, c2 = st.columns(2)
            p = c1.text_input("Persona / Entidad")
            m = c1.text_input("Importe (€)")
            c = c2.text_input("Motivo")
            t = c2.radio("Tipo", ["🔴 DEBO (Pagar)", "🟢 ME DEBEN (Cobrar)"])
            v = procesar_texto_a_numero(m)
            if st.form_submit_button("REGISTRAR", use_container_width=True) and v>0:
                tg = "DEBO" if "🔴" in t else "ME DEBEN"
                hoja_deudas.append_row([date.today().strftime("%d/%m/%Y"), p, c, str(v).replace(".", ","), tg])
                st.cache_data.clear(); st.rerun()
    try:
        dd = hoja_deudas.get_all_records(numericise_ignore=['all'])
        if dd:
            st.markdown("<br>", unsafe_allow_html=True)
            for i, r in pd.DataFrame(dd).iterrows():
                imp = procesar_texto_a_numero(r['Monto'])
                with st.container():
                    c1, c2 = st.columns([4,1])
                    with c1:
                        if r['Tipo']=="DEBO": 
                            st.error(f"🔴 Debo a **{r['Persona']}**")
                        else: 
                            st.success(f"🟢 Me debe **{r['Persona']}**")
                        st.write(f"Importe: **{formato_visual(imp)}** | Motivo: {r['Concepto']}")
                    with c2:
                        st.write("")
                        if st.button("Saldar", key=f"s{i}"):
                            hoja_deudas.delete_rows(i+2); st.toast("Deuda saldada"); st.cache_data.clear(); st.rerun()
        else: st.info("No hay deudas pendientes.")
    except: pass