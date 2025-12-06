import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

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

# --- FUNCIONES BLINDADAS ---
def procesar_texto_a_numero(valor):
    texto = str(valor).strip()
    if not texto: return 0.0
    try:
        # Formato español: quitamos punto de mil, cambiamos coma a decimal
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

# --- CÁLCULOS GLOBALES (LO PRIMERO DE TODO) ---
# Calculamos el saldo AQUÍ para usarlo en todas partes
saldo_actual = 0.0
ingresos = 0.0
gastos = 0.0
df_movimientos = pd.DataFrame()

try:
    data = hoja1.get_all_records(numericise_ignore=['all'])
    df_movimientos = pd.DataFrame(data)
    
    if not df_movimientos.empty and 'Monto' in df_movimientos.columns:
        df_movimientos['Monto_Calc'] = df_movimientos['Monto'].apply(procesar_texto_a_numero)
        ingresos = df_movimientos[df_movimientos['Monto_Calc'] > 0]['Monto_Calc'].sum()
        gastos = df_movimientos[df_movimientos['Monto_Calc'] < 0]['Monto_Calc'].sum()
        saldo_actual = df_movimientos['Monto_Calc'].sum()
except: pass

# --- INTERFAZ ---
st.title("💰 Mi Cartera Inteligente")

# Tarjetas KPI (Siempre visibles arriba)
c1, c2, c3 = st.columns(3)
c1.metric("Saldo Disponible", formato_visual(saldo_actual))
c2.metric("Ingresos", formato_visual(ingresos))
c3.metric("Gastos", formato_visual(gastos), delta_color="inverse")

st.divider()

tab1, tab2 = st.tabs(["📝 Diario", "🎯 Objetivos y Planificación"])

# === PESTAÑA 1: DIARIO ===
with tab1:
    st.subheader("Nuevo Movimiento")
    with st.form("mov"):
        c_a, c_b = st.columns(2)
        fecha = c_a.date_input("Fecha")
        monto_txt = c_a.text_input("Cantidad (€)", placeholder="Ej: 4139,14")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        val_guardar = procesar_texto_a_numero(monto_txt)
        if monto_txt: st.caption(f"🔢 Se guardará: **{val_guardar}**")

        if st.form_submit_button("Guardar"):
            if val_guardar > 0:
                final = -val_guardar if tipo == "Gasto" else val_guardar
                valor_excel = str(final).replace(".", ",")
                hoja1.append_row([str(fecha), cat, desc, valor_excel, tipo])
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

# === PESTAÑA 2: OBJETIVOS (LÓGICA CORREGIDA) ===
with tab2:
    st.header("🎯 Metas")
    st.info(f"💡 El sistema descontará tu saldo actual (**{formato_visual(saldo_actual)}**) de tus metas.")

    with st.expander("➕ Crear Nueva Meta", expanded=False):
        with st.form("obj"):
            nom = st.text_input("Meta")
            cant = st.text_input("Coste Total (€)", placeholder="Ej: 15000,00")
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
            
            # Input de Sueldo (con feedback visual)
            col_s_in, col_s_info = st.columns([1, 2])
            sueldo_txt = col_s_in.text_input("Tu Ingreso Mensual", value="1.500,00")
            sueldo_real = procesar_texto_a_numero(sueldo_txt)
            col_s_info.info(f"Calculando esfuerzo sobre: **{formato_visual(sueldo_real)}**")

            st.markdown("---")

            for i, r in dfo.iterrows():
                precio_meta = procesar_texto_a_numero(r['Monto_Meta'])
                
                # --- LA CORRECCIÓN MATEMÁTICA ---
                # Falta = Precio - Lo que ya tengo
                falta_por_ahorrar = precio_meta - saldo_actual
                
                # Fechas
                fecha_limite = pd.to_datetime(r['Fecha_Limite']).date()
                hoy = date.today()
                dias_restantes = (fecha_limite - hoy).days
                meses_restantes = max(dias_restantes / 30.44, 0.1)

                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 0.5])
                    
                    with c1:
                        st.markdown(f"### 🚩 {r['Objetivo']}")
                        st.write(f"Precio: **{formato_visual(precio_meta)}**")
                        
                        # Barra de progreso visual
                        if saldo_actual > 0 and precio_meta > 0:
                            progreso = min(saldo_actual / precio_meta, 1.0)
                            st.progress(progreso)
                        
                        if falta_por_ahorrar <= 0:
                            st.success(f"🎉 ¡Objetivo cubierto! Tienes {formato_visual(saldo_actual)}")
                        else:
                            st.write(f"Te faltan: **{formato_visual(falta_por_ahorrar)}**")

                    with c2:
                        if falta_por_ahorrar > 0 and dias_restantes > 0:
                            # Ahorro mensual basado en LO QUE FALTA
                            ahorro_necesario = falta_por_ahorrar / meses_restantes
                            pct = (ahorro_necesario / sueldo_real * 100) if sueldo_real > 0 else 0
                            
                            st.metric("Ahorro Mensual Real", formato_visual(ahorro_necesario))
                            
                            if pct > 40: st.error(f"⚠️ {pct:.0f}% de tu sueldo")
                            elif pct > 20: st.warning(f"📊 {pct:.0f}% de tu sueldo")
                            else: st.success(f"✅ {pct:.0f}% de tu sueldo")
                        elif dias_restantes <= 0 and falta_por_ahorrar > 0:
                            st.error("¡Fecha vencida!")
                        elif falta_por_ahorrar <= 0:
                            st.balloons()

                    with c3:
                        if st.button("🗑️", key=f"del_{i}"):
                            hoja_obj.delete_rows(i + 2)
                            st.cache_data.clear()
                            st.rerun()

                    # --- CALENDARIO CORREGIDO ---
                    # Solo muestra calendario si aún te falta dinero
                    if falta_por_ahorrar > 0 and dias_restantes > 0:
                        with st.expander(f"📅 Ver Plan para los {formato_visual(falta_por_ahorrar)} restantes"):
                            fechas = pd.date_range(start=hoy, end=fecha_limite, freq='ME')
                            if len(fechas) > 0:
                                # Repartimos LO QUE FALTA, no el total
                                cuota = falta_por_ahorrar / len(fechas)
                                
                                df_plan = pd.DataFrame({
                                    "Fecha": fechas,
                                    "Poner al mes": [cuota] * len(fechas)
                                })
                                # Acumulado empieza en tu saldo actual
                                df_plan['Acumulado'] = df_plan['Poner al mes'].cumsum() + saldo_actual
                                
                                # Formato visual
                                df_ver = df_plan.copy()
                                df_ver['Fecha'] = df_ver['Fecha'].dt.strftime('%B %Y')
                                df_ver['Poner al mes'] = df_ver['Poner al mes'].apply(formato_visual)
                                df_ver['Acumulado'] = df_ver['Acumulado'].apply(formato_visual)
                                
                                st.dataframe(df_ver, use_container_width=True, hide_index=True)
                            else:
                                st.warning("Queda menos de un mes. ¡Ahorra todo ya!")

    except Exception as e:
        st.info("No hay metas.")