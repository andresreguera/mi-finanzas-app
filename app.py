import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Mi Finanzas", page_icon="💰", layout="centered")

# --- 🎨 TRUCO DE DISEÑO: MODO LIMPIO (SIN BARRAS NI MENÚS) ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

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

# --- BARRA LATERAL (VISIBLE SOLO AL DESLIZAR) ---
with st.sidebar:
    st.header("⚙️ Mantenimiento")
    if st.button("⚠️ BORRAR TODO Y REINICIAR", type="primary"):
        hoja1.clear()
        hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        if hoja_deudas:
            hoja_deudas.clear()
            hoja_deudas.append_row(["Fecha", "Persona", "Concepto", "Monto", "Tipo"])
        st.cache_data.clear()
        st.success("Tablas reiniciadas.")
        st.rerun()

# --- CÁLCULOS GLOBALES ---
saldo_actual = 0.0
ingresos = 0.0
gastos = 0.0
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

tab1, tab2, tab3, tab4 = st.tabs(["📝 Diario", "📊 Reporte", "🎯 Objetivos", "💸 Deudas"])

# === PESTAÑA 1: DIARIO ===
with tab1:
    st.subheader("Nuevo Movimiento")
    with st.form("mov"):
        c_a, c_b = st.columns(2)
        fecha = c_a.date_input("Fecha")
        monto_txt = c_a.text_input("Cantidad (€)", placeholder="Ej: 45,50")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina", "Ropa", "Salud", "Otros"])
        desc = st.text_input("Concepto")
        
        val_guardar = procesar_texto_a_numero(monto_txt)
        if monto_txt: st.caption(f"🔢 Se guardará: **{val_guardar}**")

        if st.form_submit_button("Guardar"):
            if val_guardar > 0:
                final = -val_guardar if tipo == "Gasto" else val_guardar
                fecha_str = fecha.strftime("%d/%m/%Y")
                val_excel = str(final).replace(".", ",")
                hoja1.append_row([fecha_str, cat, desc, val_excel, tipo])
                st.success("Guardado.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Cantidad incorrecta.")

    if not df_movimientos.empty:
        df_show = df_movimientos.copy()
        df_show['Monto'] = df_show['Monto_Calc'].apply(formato_visual)
        cols = [c for c in ['Fecha', 'Categoría', 'Monto', 'Concepto'] if c in df_show.columns]
        st.dataframe(df_show[cols].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# === PESTAÑA 2: REPORTE MENSUAL ===
with tab2:
    st.header("📊 Análisis del Mes")
    if not df_movimientos.empty:
        hoy = date.today()
        col_m, col_y = st.columns(2)
        mes_sel = col_m.selectbox("Mes", range(1, 13), index=hoy.month - 1, format_func=lambda x: datetime(2022, x, 1).strftime('%B'))
        anio_sel = col_y.number_input("Año", value=hoy.year)
        
        df_mes = df_movimientos[
            (df_movimientos['Fecha_Dt'].dt.month == mes_sel) & 
            (df_movimientos['Fecha_Dt'].dt.year == anio_sel)
        ].copy()
        
        if not df_mes.empty:
            ing_mes = df_mes[df_mes['Monto_Calc'] > 0]['Monto_Calc'].sum()
            gas_mes = df_mes[df_mes['Monto_Calc'] < 0]['Monto_Calc'].sum()
            ahorro_mes = ing_mes + gas_mes
            
            cm1, cm2, cm3 = st.columns(3)
            cm1.metric("Ahorro", formato_visual(ahorro_mes), delta=formato_visual(ahorro_mes))
            cm2.metric("Entradas", formato_visual(ing_mes))
            cm3.metric("Salidas", formato_visual(gas_mes), delta_color="inverse")
            
            st.divider()
            
            df_gastos = df_mes[df_mes['Monto_Calc'] < 0].copy()
            if not df_gastos.empty:
                st.subheader(f"Gastos de {datetime(2022, mes_sel, 1).strftime('%B')}")
                df_gastos['Monto_Abs'] = df_gastos['Monto_Calc'].abs()
                fig_pie = px.pie(df_gastos, values='Monto_Abs', names='Categoría', hole=0.4, 
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_pie, use_container_width=True)
                
                st.subheader("Evolución Diaria")
                df_diario = df_mes.groupby('Fecha_Dt')['Monto_Calc'].sum().reset_index()
                fig_bar = px.bar(df_diario, x='Fecha_Dt', y='Monto_Calc', color='Monto_Calc', color_continuous_scale=['red', 'green'])
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Sin gastos este mes.")
        else:
            st.info(f"Sin datos en {mes_sel}/{anio_sel}.")

# === PESTAÑA 3: OBJETIVOS ===
with tab3:
    st.header("🎯 Metas")
    with st.expander("➕ Crear Meta"):
        with st.form("obj"):
            nom = st.text_input("Meta")
            cant = st.text_input("Coste Total (€)", placeholder="Ej: 1500,00")
            fin = st.date_input("Fecha Límite")
            val = procesar_texto_a_numero(cant)
            if st.form_submit_button("Crear") and val > 0:
                val_excel = str(val).replace(".", ",")
                hoja_obj.append_row([nom, val_excel, str(fin), str(date.today())])
                st.cache_data.clear()
                st.rerun()

    try:
        do = hoja_obj.get_all_records(numericise_ignore=['all'])
        dfo = pd.DataFrame(do)
        if not dfo.empty:
            st.divider()
            sueldo_real = procesar_texto_a_numero(st.text_input("Ingreso Mensual", value="200,00"))
            
            for i, r in dfo.iterrows():
                precio = procesar_texto_a_numero(r['Monto_Meta'])
                falta = precio - saldo_actual
                fecha_lim = pd.to_datetime(r['Fecha_Limite']).date()
                dias = (fecha_lim - date.today()).days
                meses = max(dias/30.44, 0.1)

                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 0.5])
                    with c1:
                        st.markdown(f"### 🚩 {r['Objetivo']}")
                        st.write(f"Precio: **{formato_visual(precio)}**")
                        if falta <= 0: st.success("🎉 ¡Conseguido!")
                        else: st.write(f"Faltan: **{formato_visual(falta)}**")
                    with c2:
                        if falta > 0 and dias > 0:
                            ahorro = falta / meses
                            st.metric("Ahorro Mensual", formato_visual(ahorro))
                            # Calendario desplegable
                            with st.expander("📅 Ver Plan"):
                                fechas = pd.date_range(start=date.today(), end=fecha_lim, freq='ME')
                                if len(fechas) > 0:
                                    cuota = falta / len(fechas)
                                    df_plan = pd.DataFrame({"Fecha": fechas, "Cuota": [cuota]*len(fechas)})
                                    df_plan['Acumulado'] = df_plan['Cuota'].cumsum() + saldo_actual
                                    df_plan['Fecha'] = df_plan['Fecha'].dt.strftime('%B %Y')
                                    df_plan['Cuota'] = df_plan['Cuota'].apply(formato_visual)
                                    df_plan['Acumulado'] = df_plan['Acumulado'].apply(formato_visual)
                                    st.dataframe(df_plan, use_container_width=True, hide_index=True)
                        elif dias <= 0: st.error("¡Vencida!")
                    with c3:
                        if st.button("🗑️", key=f"del_{i}"):
                            hoja_obj.delete_rows(i + 2)
                            st.cache_data.clear()
                            st.rerun()
    except: pass

# === PESTAÑA 4: DEUDAS ===
with tab4:
    st.header("💸 Deudas")
    if hoja_deudas:
        with st.expander("➕ Nueva Deuda"):
            with st.form("deuda"):
                c1, c2 = st.columns(2)
                persona = c1.text_input("Persona")
                monto = c1.text_input("Importe (€)")
                concepto = c2.text_input("Concepto")
                tipo = c2.radio("Tipo", ["🔴 DEBO", "🟢 ME DEBEN"])
                val = procesar_texto_a_numero(monto)
                if st.form_submit_button("Anotar") and val > 0:
                    t_guardar = "DEBO" if "🔴" in tipo else "ME DEBEN"
                    v_excel = str(val).replace(".", ",")
                    hoja_deudas.append_row([date.today().strftime("%d/%m/%Y"), persona, concepto, v_excel, t_guardar])
                    st.cache_data.clear()
                    st.rerun()
        
        try:
            dd = hoja_deudas.get_all_records(numericise_ignore=['all'])
            df_d = pd.DataFrame(dd)
            if not df_d.empty:
                st.divider()
                for i, r in df_d.iterrows():
                    imp = procesar_texto_a_numero(r['Monto'])
                    with st.container(border=True):
                        ci, ca = st.columns([4,1])
                        with ci:
                            if r['Tipo'] == "DEBO": st.error(f"🔴 Debo a **{r['Persona']}**: {formato_visual(imp)}")
                            else: st.success(f"🟢 Me debe **{r['Persona']}**: {formato_visual(imp)}")
                            st.caption(f"{r['Concepto']} | {r['Fecha']}")
                        with ca:
                            st.write("")
                            if st.button("✅ Saldar", key=f"pay_{i}"):
                                hoja_deudas.delete_rows(i + 2)
                                st.cache_data.clear()
                                st.rerun()
        except: pass