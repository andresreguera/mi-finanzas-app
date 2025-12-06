import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import plotly.express as px

# --- 1. CONFIGURACIÓN ---
st.set_page_config(
    page_title="Mi Economía", 
    page_icon="💰", 
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# --- 2. ESTILO NATIVO LIMPIO (MODO FANTASMA) ---
# Eliminamos colores forzados. Dejamos que el sistema decida (Claro/Oscuro).
# Solo ocultamos la interfaz de Streamlit para que parezca una App.
hide_styles = """
    <style>
        /* Ocultar barras superiores, menú hamburguesa y decoración */
        header {visibility: hidden !important; height: 0px !important;}
        div[data-testid="stToolbar"] {display: none !important; visibility: hidden !important;}
        div[data-testid="stDecoration"] {display: none !important; height: 0px !important;}
        
        /* Ocultar pie de página */
        footer {display: none !important;}
        #MainMenu {visibility: hidden !important;}
        
        /* Ajustar espaciado para móviles (Subir contenido) */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 5rem !important;
        }

        /* Hacer que los contenedores se integren con el fondo (Sutil) */
        div[data-testid="stExpander"], div.stContainer {
            border: 1px solid rgba(128, 128, 128, 0.2); /* Borde muy suave */
            border-radius: 10px;
            background-color: transparent; /* Fondo transparente para adaptarse al tema */
        }
        
        /* Ajuste sutil en métricas para que no sean cajas blancas */
        div[data-testid="metric-container"] {
            background-color: rgba(128, 128, 128, 0.05); /* Ligeramente distinto al fondo */
            border: none;
            border-radius: 10px;
            padding: 10px;
        }
    </style>
"""
st.markdown(hide_styles, unsafe_allow_html=True)

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
    st.header("Configuración")
    if st.button("⚠️ Reiniciar Base de Datos", type="primary"):
        hoja1.clear(); hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        if hoja_deudas:
            hoja_deudas.clear(); hoja_deudas.append_row(["Fecha", "Persona", "Concepto", "Monto", "Tipo"])
        st.cache_data.clear(); st.success("Datos borrados."); st.rerun()

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

# --- 7. HEADER NATIVO ---
st.title(f"{saludo_dinamico()}, Andrés")
st.caption(f"Resumen a {date.today().strftime('%d/%m/%Y')}")

c1, c2, c3 = st.columns(3)
c1.metric("Disponible", formato_visual(saldo_actual))
c2.metric("Ingresos", formato_visual(ingresos))
c3.metric("Gastos", formato_visual(gastos), delta_color="inverse")

st.divider()

# --- 8. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["Diario", "Reporte", "Metas", "Deudas"])

# PESTAÑA 1: DIARIO
with tab1:
    st.subheader("📝 Nuevo Registro")
    with st.container():
        with st.form("mov", border=False): # border=False para que se funda con el fondo
            c_a, c_b = st.columns(2)
            fecha = c_a.date_input("Fecha")
            monto_txt = c_a.text_input("Cantidad (€)", placeholder="0,00")
            tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
            cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina", "Ropa", "Salud", "Otros"])
            desc = st.text_input("Concepto (Opcional)")
            
            val = procesar_texto_a_numero(monto_txt)
            
            # Botón nativo (se adapta al tema claro/oscuro automáticamente)
            if st.form_submit_button("Guardar Movimiento", use_container_width=True):
                if val > 0:
                    final = -val if tipo == "Gasto" else val
                    hoja1.append_row([fecha.strftime("%d/%m/%Y"), cat, desc, str(final).replace(".", ","), tipo])
                    st.toast("Guardado correctamente")
                    st.cache_data.clear(); st.rerun()
                else: st.warning("Introduce una cantidad válida")

    if not df_movimientos.empty:
        st.markdown("#### Historial")
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
            
            st.info(f"Balance de {datetime(2022, mes, 1).strftime('%B')}: **{formato_visual(ahorro)}**")
            
            df_g = df_m[df_m['Monto_Calc'] < 0].copy()
            if not df_g.empty:
                st.subheader("Gastos por Categoría")
                df_g['Abs'] = df_g['Monto_Calc'].abs()
                fig = px.pie(df_g, values='Abs', names='Categoría', hole=0.5)
                # Esto hace que el gráfico use texto blanco en modo oscuro y negro en modo claro
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else: st.success("Sin gastos este mes")
        else: st.info("No hay datos.")

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
            sueldo = procesar_texto_a_numero(st.text_input("Tu Ingreso Mensual", "200,00"))
            
            for i, r in pd.DataFrame(do).iterrows():
                m = procesar_texto_a_numero(r['Monto_Meta'])
                falta = m - saldo_actual
                dias = (pd.to_datetime(r['Fecha_Limite']).date() - date.today()).days
                meses = max(dias/30.44, 0.1)
                
                # Contenedor nativo (borde sutil, fondo transparente)
                with st.container(border=True):
                    col_txt, col_num, col_del = st.columns([3, 2, 0.5])
                    with col_txt:
                        st.markdown(f"**{r['Objetivo']}**")
                        if falta <= 0: st.success("✅ Conseguido")
                        else: st.caption(f"Faltan: {formato_visual(falta)}")
                    with col_num:
                        if falta > 0 and dias > 0:
                            mensual = falta/meses
                            pct = (mensual/sueldo*100) if sueldo > 0 else 0
                            # Usamos emojis en lugar de colores hardcodeados para mejor compatibilidad
                            alert = "🟢" if pct < 20 else "🟠" if pct < 40 else "🔴"
                            st.write(f"{alert} **{formato_visual(mensual)}/mes**")
                            st.caption(f"{pct:.0f}% del ingreso")
                        elif dias<=0: st.error("Vencida")
                    with col_del:
                        if st.button("✕", key=f"d{i}"):
                            hoja_obj.delete_rows(i+2); st.cache_data.clear(); st.rerun()
                    
                    if falta > 0 and dias > 0:
                        with st.expander("Ver Calendario"):
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
                with st.container(border=True):
                    c1, c2 = st.columns([4,1])
                    with c1:
                        pre = "🔴 Debo a" if r['Tipo']=="DEBO" else "🟢 Me debe"
                        st.markdown(f"{pre} **{r['Persona']}**: {formato_visual(imp)}")
                        st.caption(f"{r['Concepto']} | {r['Fecha']}")
                    with c2:
                        st.write("")
                        if st.button("✅", key=f"s{i}"):
                            hoja_deudas.delete_rows(i+2); st.toast("Saldado"); st.cache_data.clear(); st.rerun()
        else: st.caption("No tienes deudas.")
    except: pass