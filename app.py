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

# --- 2. ESTILO NATIVO (MODO CLARO/OSCURO) ---
hide_styles = """
    <style>
        /* Ocultamos header y footer para estilo App */
        header {visibility: hidden !important; height: 0px !important;}
        div[data-testid="stToolbar"] {display: none !important; visibility: hidden !important;}
        div[data-testid="stDecoration"] {display: none !important; height: 0px !important;}
        footer {display: none !important;}
        #MainMenu {visibility: hidden !important;}
        
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 5rem !important;
        }
        
        div[data-testid="stExpander"], div.stContainer {
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 10px;
            background-color: transparent;
        }
        div[data-testid="metric-container"] {
            background-color: rgba(128, 128, 128, 0.05);
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

# Intento de conexión a Deudas con aviso visible
try:
    hoja_deudas = libro.worksheet("Deudas")
except:
    hoja_deudas = None

# --- 4. FUNCIONES ---
def procesar_texto_a_numero(valor):
    texto = str(valor).strip()
    if not texto: return 0.0
    try:
        texto = texto.replace(".", "").replace(",", ".")
        return float(texto)
    except:
        return 0.0

def formato_visual(numero):
    try: return "{:,.2f} €".format(float(numero)).replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00 €"

def saludo_dinamico():
    h = datetime.now().hour
    if 6 <= h < 12: return "Buenos días"
    elif 12 <= h < 20: return "Buenas tardes"
    else: return "Buenas noches"

# --- 5. CÁLCULOS ---
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

# --- 6. HEADER ---
st.title(f"{saludo_dinamico()}, Andrés")

# --- MENÚ DE CONFIGURACIÓN (VISIBLE EN LA PÁGINA PRINCIPAL) ---
with st.expander("⚙️ Configuración y Reinicio"):
    st.write("Si las deudas no aparecen o los saldos están mal, pulsa aquí:")
    if st.button("⚠️ REINICIAR TABLAS Y ARREGLAR TODO", type="primary"):
        # Reset Diario
        hoja1.clear()
        hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        # Reset Deudas (Crear si no existe)
        if hoja_deudas:
            hoja_deudas.clear()
            hoja_deudas.append_row(["Fecha", "Persona", "Concepto", "Monto", "Tipo"])
        else:
            libro.add_worksheet(title="Deudas", rows="100", cols="5")
            hoja_deudas = libro.worksheet("Deudas")
            hoja_deudas.append_row(["Fecha", "Persona", "Concepto", "Monto", "Tipo"])
            
        st.cache_data.clear()
        st.success("✅ Sistema reparado. Recargando...")
        st.rerun()

c1, c2, c3 = st.columns(3)
c1.metric("Disponible", formato_visual(saldo_actual))
c2.metric("Ingresos", formato_visual(ingresos))
c3.metric("Gastos", formato_visual(gastos), delta_color="inverse")

st.divider()

# --- 7. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["Diario", "Reporte", "Metas", "Deudas"])

# PESTAÑA 1: DIARIO
with tab1:
    st.subheader("📝 Nuevo Registro")
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
                    val_excel = str(final).replace(".", ",")
                    hoja1.append_row([fecha.strftime("%d/%m/%Y"), cat, desc, val_excel, tipo])
                    st.toast("Guardado")
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
            st.info(f"Balance de {datetime(2022, mes, 1).strftime('%B')}: **{formato_visual(i_m + g_m)}**")
            
            df_g = df_m[df_m['Monto_Calc'] < 0].copy()
            if not df_g.empty:
                st.subheader("Gastos por Categoría")
                df_g['Abs'] = df_g['Monto_Calc'].abs()
                fig = px.pie(df_g, values='Abs', names='Categoría', hole=0.5)
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
                
                with st.container():
                    c1, c2 = st.columns([3,1])
                    c1.write(f"**{r['Objetivo']}** | Faltan: {formato_visual(falta)}")
                    if falta > 0 and dias > 0:
                        men = falta/meses
                        pct = (men/sueldo*100) if sueldo > 0 else 0
                        al = "🟢" if pct < 20 else "🟠" if pct < 40 else "🔴"
                        st.write(f"{al} **{formato_visual(men)}/mes** ({pct:.0f}%)")
                    if c2.button("🗑️", key=f"d{i}"):
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

# PESTAÑA 4: DEUDAS (REPARADA)
with tab4:
    if not hoja_deudas:
        st.error("⚠️ La hoja de Deudas no existe. Pulsa el botón 'REINICIAR TABLAS' arriba para crearla.")
    else:
        with st.expander("➕ Apuntar Deuda"):
            with st.form("new_deuda"):
                c1, c2 = st.columns(2)
                p = c1.text_input("Persona / Entidad")
                m = c1.text_input("Importe (€)", placeholder="50,00")
                c = c2.text_input("Motivo")
                t = c2.radio("Tipo", ["🔴 DEBO", "🟢 ME DEBEN"])
                v = procesar_texto_a_numero(m)
                if st.form_submit_button("Guardar", use_container_width=True) and v>0:
                    tg = "DEBO" if "🔴" in t else "ME DEBEN"
                    val_excel = str(v).replace(".", ",")
                    hoja_deudas.append_row([date.today().strftime("%d/%m/%Y"), p, c, val_excel, tg])
                    st.toast("Anotado")
                    st.cache_data.clear(); st.rerun()
        
        try:
            # LEEMOS TODO COMO TEXTO PARA EVITAR ERRORES
            dd = hoja_deudas.get_all_records(numericise_ignore=['all'])
            
            if dd:
                st.markdown("#### Lista Pendiente")
                for i, r in pd.DataFrame(dd).iterrows():
                    # Check de seguridad por si faltan columnas
                    if 'Monto' not in r or 'Persona' not in r:
                        st.error("⚠️ Error en formato de datos. Pulsa 'Reiniciar Tablas' arriba.")
                        continue
                        
                    imp = procesar_texto_a_numero(r['Monto'])
                    with st.container():
                        c1, c2 = st.columns([4,1])
                        with c1:
                            if r['Tipo'] == "DEBO": 
                                st.error(f"🔴 Debo a **{r['Persona']}**: {formato_visual(imp)}")
                            else: 
                                st.success(f"🟢 Me debe **{r['Persona']}**: {formato_visual(imp)}")
                            st.caption(f"{r['Concepto']} | {r['Fecha']}")
                        with c2:
                            st.write("")
                            if st.button("✅", key=f"s{i}", help="Marcar como cumplida"):
                                hoja_deudas.delete_rows(i+2)
                                st.balloons()
                                st.cache_data.clear()
                                st.rerun()
            else:
                st.info("No tienes deudas pendientes.")
        except Exception as e:
            st.error(f"Error al leer deudas: {e}")
            st.info("💡 Prueba a pulsar el botón 'REINICIAR TABLAS' en Configuración.")