import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import plotly.express as px

# --- 1. CONFIGURACIÓN ---
st.set_page_config(
    page_title="Mi Economía", 
    page_icon="💎", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS "FINTECH PREMIUM" ---
estilo_premium = """
    <style>
        /* FUENTE MODERNA */
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', sans-serif;
            color: #1e293b; /* Texto gris oscuro elegante */
        }

        /* FONDO GENERAL */
        .stApp {
            background-color: #f1f5f9; /* Gris pizarra muy suave */
        }

        /* --- MODO FANTASMA (OCULTAR BARRAS) --- */
        header {visibility: hidden !important; height: 0px !important;}
        div[data-testid="stToolbar"] {display: none !important;}
        div[data-testid="stDecoration"] {display: none !important;}
        footer {display: none !important;}
        
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 6rem !important;
        }

        /* --- TARJETAS MÉTRICAS (KPIs) --- */
        div[data-testid="metric-container"] {
            background-color: #ffffff;
            border-radius: 20px;
            padding: 20px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
            border: 1px solid #e2e8f0;
            transition: all 0.3s ease;
        }
        
        div[data-testid="metric-container"]:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        }

        /* Títulos de las métricas */
        div[data-testid="metric-container"] label {
            font-size: 0.9rem;
            color: #64748b;
            font-weight: 600;
        }

        /* --- BOTONES CON DEGRADADO ÚNICO --- */
        .stButton button {
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); /* Índigo vibrante */
            color: white !important;
            border: none;
            border-radius: 12px;
            padding: 0.6rem 1rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.3);
            transition: all 0.2s;
        }
        
        .stButton button:active {
            transform: scale(0.97);
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
        }

        /* Botones secundarios (Borrar) */
        button[kind="secondary"] {
            background: white !important;
            color: #ef4444 !important; /* Rojo suave */
            border: 1px solid #fee2e2 !important;
        }

        /* --- CONTENEDORES Y FORMULARIOS --- */
        div.stContainer, div[data-testid="stExpander"] {
            background-color: #ffffff;
            border-radius: 16px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
            padding: 10px;
        }

        /* Inputs más limpios */
        .stTextInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
            border-radius: 10px;
            border: 1px solid #cbd5e1;
            background-color: #f8fafc;
        }

        /* --- PESTAÑAS --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: transparent;
            padding-bottom: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 40px;
            border-radius: 20px;
            padding: 0 20px;
            background-color: #e2e8f0;
            color: #475569;
            font-weight: 600;
            border: none;
        }
        .stTabs [aria-selected="true"] {
            background-color: #4f46e5;
            color: white !important;
            box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.4);
        }
    </style>
"""
st.markdown(estilo_premium, unsafe_allow_html=True)

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
    if st.button("⚠️ Reiniciar Base de Datos", type="primary"):
        hoja1.clear(); hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        if hoja_deudas:
            hoja_deudas.clear(); hoja_deudas.append_row(["Fecha", "Persona", "Concepto", "Monto", "Tipo"])
        st.cache_data.clear(); st.success("Todo limpio."); st.rerun()

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

# --- 7. HEADER PREMIUM ---
st.markdown(f"<h1 style='color: #1e293b; font-size: 2rem;'>{saludo_dinamico()}, Andrés</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='color: #64748b; margin-top: -15px;'>Balance actualizado a {date.today().strftime('%d/%m')}</p>", unsafe_allow_html=True)

# KPI CARDS
col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
col_kpi1.metric("Disponible", formato_visual(saldo_actual))
col_kpi2.metric("Ingresos", formato_visual(ingresos))
col_kpi3.metric("Gastos", formato_visual(gastos), delta_color="inverse")

st.markdown("<br>", unsafe_allow_html=True)

# --- 8. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["Diario", "Reporte", "Metas", "Deudas"])

# PESTAÑA 1: DIARIO
with tab1:
    with st.container():
        st.markdown("##### 📝 Nuevo Registro")
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
                    st.toast("Guardado", icon="✅")
                    st.cache_data.clear(); st.rerun()
                else: st.toast("Escribe una cantidad", icon="⚠️")

    if not df_movimientos.empty:
        st.markdown("##### 📜 Historial Reciente")
        df_s = df_movimientos.copy()
        df_s['Monto'] = df_s['Monto_Calc'].apply(formato_visual)
        cols = [c for c in ['Fecha', 'Categoría', 'Monto', 'Concepto'] if c in df_s.columns]
        st.dataframe(df_s[cols].tail(7).sort_index(ascending=False), use_container_width=True, hide_index=True)

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
            
            # Usamos un contenedor coloreado para el resultado del mes
            st.markdown(f"""
            <div style="background-color: #d1fae5; padding: 15px; border-radius: 12px; border: 1px solid #10b981; color: #065f46; text-align: center; margin-bottom: 20px;">
                <strong>Balance de {datetime(2022, mes, 1).strftime('%B')}:</strong> <span style="font-size: 1.2rem;">{formato_visual(ahorro)}</span>
            </div>
            """, unsafe_allow_html=True)
            
            df_g = df_m[df_m['Monto_Calc'] < 0].copy()
            if not df_g.empty:
                st.markdown("##### Distribución de Gastos")
                df_g['Abs'] = df_g['Monto_Calc'].abs()
                # Colores únicos y elegantes para el gráfico
                fig = px.pie(df_g, values='Abs', names='Categoría', hole=0.6, 
                             color_discrete_sequence=["#6366f1", "#8b5cf6", "#ec4899", "#f43f5e", "#f59e0b", "#10b981"])
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
                fig.update_traces(textposition='outside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            else: st.success("🎉 ¡Mes limpio de gastos!")
        else: st.info("No hay movimientos en esta fecha.")

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
            st.markdown("<br>", unsafe_allow_html=True)
            sueldo = procesar_texto_a_numero(st.text_input("Tu Ingreso Mensual", "200,00"))
            
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
                            # Colores semánticos personalizados
                            color_texto = "#10b981" if pct < 20 else "#f59e0b" if pct < 40 else "#ef4444"
                            st.markdown(f"<span style='color:{color_texto}; font-weight:bold; font-size:1.1rem;'>{formato_visual(mensual)}/mes</span>", unsafe_allow_html=True)
                            st.caption(f"{pct:.0f}% de tu ingreso")
                        elif dias<=0: st.error("¡Vencida!")
                    with col_del:
                        if st.button("✕", key=f"d{i}"):
                            hoja_obj.delete_rows(i+2); st.cache_data.clear(); st.rerun()
                    
                    if falta > 0 and dias > 0:
                        with st.expander("📅 Ver Plan"):
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
            st.markdown("<br>", unsafe_allow_html=True)
            for i, r in pd.DataFrame(dd).iterrows():
                imp = procesar_texto_a_numero(r['Monto'])
                with st.container():
                    c1, c2 = st.columns([4,1])
                    with c1:
                        if r['Tipo']=="DEBO": 
                            st.markdown(f"<span style='color:#ef4444'>🔴 Debo a <b>{r['Persona']}</b></span>", unsafe_allow_html=True)
                        else: 
                            st.markdown(f"<span style='color:#10b981'>🟢 Me debe <b>{r['Persona']}</b></span>", unsafe_allow_html=True)
                        st.markdown(f"**{formato_visual(imp)}** <span style='color:#94a3b8; font-size:0.8rem'>| {r['Concepto']}</span>", unsafe_allow_html=True)
                    with c2:
                        if st.button("✅", key=f"s{i}"):
                            hoja_deudas.delete_rows(i+2); st.toast("Saldado"); st.cache_data.clear(); st.rerun()
        else: st.caption("Estás en paz ☮️")
    except: pass