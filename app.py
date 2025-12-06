import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
from dateutil.relativedelta import relativedelta # Librería para cálculo de fechas

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Finanzas Pro", page_icon="💰", layout="centered")

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

# --- FUNCIONES DE LIMPIEZA BLINDADAS ---

def procesar_texto_a_numero(valor):
    """
    Convierte texto del Excel o Input (formato español) a número Python.
    "1.500,00" -> 1500.0
    "4139,14" -> 4139.14
    """
    texto = str(valor).strip()
    if not texto: return 0.0
    try:
        # Quitamos puntos de miles y cambiamos coma a punto
        texto = texto.replace(".", "").replace(",", ".")
        return float(texto)
    except:
        return 0.0

def formato_visual(numero):
    # Formato español bonito: 4.139,14 €
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

tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos y Planificación"])

# === PESTAÑA DIARIO ===
with tab1:
    # 1. Cargar Datos
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
        monto_txt = c_a.text_input("Cantidad (€)", placeholder="Ej: 4139,14")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        val_guardar = procesar_texto_a_numero(monto_txt)
        if monto_txt: st.info(f"🔢 Se guardará: **{val_guardar}**")

        if st.form_submit_button("Guardar"):
            if val_guardar > 0:
                final = -val_guardar if tipo == "Gasto" else val_guardar
                valor_excel = str(final).replace(".", ",")
                hoja1.append_row([str(fecha), cat, desc, valor_excel, tipo])
                st.success("Guardado.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Introduce cantidad válida.")

    if not df.empty:
        df_show = df.copy()
        df_show['Monto'] = df_show['Monto_Calc'].apply(formato_visual)
        cols = [c for c in ['Fecha', 'Categoría', 'Monto', 'Concepto'] if c in df_show.columns]
        st.dataframe(df_show[cols].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# === PESTAÑA OBJETIVOS (CALENDARIO 2026) ===
with tab2:
    st.header("🎯 Metas y Calendario")
    
    # Formulario Crear
    with st.expander("➕ Crear Nueva Meta", expanded=False):
        with st.form("obj"):
            nom = st.text_input("Meta")
            cant = st.text_input("Cantidad Total (€)", placeholder="Ej: 15000,00")
            fin = st.date_input("Fecha Límite (Ej: 2026)")
            val = procesar_texto_a_numero(cant)
            
            if st.form_submit_button("Crear") and val > 0:
                val_excel = str(val).replace(".", ",")
                hoja_obj.append_row([nom, val_excel, str(fin), str(date.today())])
                st.success("Meta creada.")
                st.cache_data.clear()
                st.rerun()

    # Listado
    try:
        do = hoja_obj.get_all_records(numericise_ignore=['all'])
        dfo = pd.DataFrame(do)
        
        if not dfo.empty:
            st.divider()
            
            # --- CORRECCIÓN DEL SUELDO ---
            st.markdown("### ⚙️ Tu Capacidad de Ahorro")
            col_sueldo, col_info = st.columns([1, 2])
            
            with col_sueldo:
                # Texto libre para evitar problemas de formato
                sueldo_txt = st.text_input("Tu Sueldo Mensual (€)", value="1.500,00")
                sueldo_real = procesar_texto_a_numero(sueldo_txt)
            
            with col_info:
                # Feedback visual inmediato para que sepas qué lee el sistema
                st.info(f"El sistema calcula usando un sueldo de: **{formato_visual(sueldo_real)}**")

            st.divider()

            # --- TARJETAS DE METAS ---
            for i, r in dfo.iterrows():
                m = procesar_texto_a_numero(r['Monto_Meta'])
                fecha_limite = pd.to_datetime(r['Fecha_Limite']).date()
                hoy = date.today()
                
                # Calculamos meses reales restantes
                dias_restantes = (fecha_limite - hoy).days
                meses_restantes = max(dias_restantes / 30.44, 0.1) # 30.44 es la media de días por mes
                
                ahorro_necesario = m / meses_restantes

                with st.container(border=True):
                    col_izq, col_der, col_borrar = st.columns([3, 2, 0.5])
                    
                    with col_izq:
                        st.markdown(f"### 🚩 {r['Objetivo']}")
                        st.write(f"Meta Total: **{formato_visual(m)}**")
                        st.write(f"Fecha límite: **{fecha_limite.strftime('%d/%m/%Y')}**")

                    with col_der:
                        if dias_restantes > 0:
                            pct = (ahorro_necesario / sueldo_real * 100) if sueldo_real > 0 else 0
                            
                            st.metric("Ahorro Mensual Necesario", formato_visual(ahorro_necesario))
                            
                            if pct > 40:
                                st.error(f"⚠️ ¡Duro! Es el {pct:.0f}% de tu sueldo")
                            elif pct > 20:
                                st.warning(f"📊 Es el {pct:.0f}% de tu sueldo")
                            else:
                                st.success(f"✅ Fácil: {pct:.0f}% de tu sueldo")
                        else:
                            st.error("¡Fecha vencida!")

                    with col_borrar:
                        if st.button("🗑️", key=f"del_{i}"):
                            hoja_obj.delete_rows(i + 2)
                            st.cache_data.clear()
                            st.rerun()
                    
                    # --- EL CALENDARIO SOLICITADO ---
                    with st.expander(f"📅 Ver Calendario de Pagos para {r['Objetivo']}"):
                        if dias_restantes > 0:
                            st.write(f"Si empiezas el mes que viene, este es tu plan para llegar a los **{formato_visual(m)}**:")
                            
                            # Generamos la tabla de meses futuros
                            fechas_futuras = pd.date_range(start=hoy, end=fecha_limite, freq='ME') # Fin de mes
                            
                            if len(fechas_futuras) > 0:
                                cuota_exacta = m / len(fechas_futuras)
                                
                                # Creamos el DataFrame del plan
                                df_plan = pd.DataFrame({
                                    "Fecha de Ahorro": fechas_futuras,
                                    "Cuota Mensual": [cuota_exacta] * len(fechas_futuras)
                                })
                                
                                # Calculamos acumulado
                                df_plan['Acumulado Total'] = df_plan['Cuota Mensual'].cumsum()
                                
                                # Formateamos visualmente
                                df_visual_plan = df_plan.copy()
                                df_visual_plan['Fecha de Ahorro'] = df_visual_plan['Fecha de Ahorro'].dt.strftime('%B %Y') # Ej: Enero 2026
                                df_visual_plan['Cuota Mensual'] = df_visual_plan['Cuota Mensual'].apply(formato_visual)
                                df_visual_plan['Acumulado Total'] = df_visual_plan['Acumulado Total'].apply(formato_visual)
                                
                                st.dataframe(df_visual_plan, use_container_width=True, hide_index=True)
                            else:
                                st.warning("La fecha es este mismo mes. ¡Tienes que ahorrarlo todo ya!")
                        else:
                            st.warning("No se puede generar calendario para fechas pasadas.")

        else:
            st.info("No hay metas activas.")
            
    except Exception as e: 
        st.error(f"Error cargando metas: {e}")