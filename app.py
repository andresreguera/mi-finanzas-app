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

# --- FUNCIONES DE LIMPIEZA ---

def procesar_texto_a_numero(valor):
    """
    Convierte texto "4.139,14" -> Número 4139.14
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
    # Formato bonito: 4.139,14 €
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

# --- CÁLCULOS GLOBALES (Antes de las pestañas) ---
# Necesitamos saber el saldo ANTES de entrar a Objetivos para hacer la resta.

saldo_actual = 0.0
ingresos_totales = 0.0
gastos_totales = 0.0
df_movimientos = pd.DataFrame()

try:
    # 1. Leemos Movimientos
    data = hoja1.get_all_records(numericise_ignore=['all'])
    df_movimientos = pd.DataFrame(data)

    if not df_movimientos.empty and 'Monto' in df_movimientos.columns:
        # Convertimos columna Monto
        df_movimientos['Monto_Calc'] = df_movimientos['Monto'].apply(procesar_texto_a_numero)
        
        ingresos_totales = df_movimientos[df_movimientos['Monto_Calc'] > 0]['Monto_Calc'].sum()
        gastos_totales = df_movimientos[df_movimientos['Monto_Calc'] < 0]['Monto_Calc'].sum()
        saldo_actual = df_movimientos['Monto_Calc'].sum()
except Exception as e:
    st.error(f"Error al calcular saldo: {e}")


# --- INTERFAZ ---
st.title("💰 Mi Cartera Inteligente")

# Mostramos el resumen arriba del todo para tenerlo siempre presente
c1, c2, c3 = st.columns(3)
c1.metric("Saldo Disponible", formato_visual(saldo_actual))
c2.metric("Ingresos Totales", formato_visual(ingresos_totales))
c3.metric("Gastos Totales", formato_visual(gastos_totales), delta_color="inverse")

st.divider()

tab1, tab2 = st.tabs(["📝 Registro Diario", "🎯 Calculadora de Metas"])

# === PESTAÑA 1: DIARIO ===
with tab1:
    st.subheader("Nuevo Movimiento")
    with st.form("mov"):
        c_a, c_b = st.columns(2)
        fecha = c_a.date_input("Fecha")
        monto_txt = c_a.text_input("Cantidad (€)", placeholder="Ej: 50,00")
        
        tipo = c_b.selectbox("Tipo", ["Gasto", "Ingreso", "Sueldo"])
        cat = c_b.selectbox("Categoría", ["Comida", "Transporte", "Casa", "Ocio", "Ahorro", "Nómina"])
        desc = st.text_input("Concepto")
        
        val_guardar = procesar_texto_a_numero(monto_txt)
        
        if monto_txt:
            st.caption(f"🔢 Se guardará como: {val_guardar}")

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

    # Tabla Historial
    if not df_movimientos.empty:
        df_show = df_movimientos.copy()
        df_show['Monto'] = df_show['Monto_Calc'].apply(formato_visual)
        cols = [c for c in ['Fecha', 'Categoría', 'Monto', 'Concepto'] if c in df_show.columns]
        st.dataframe(df_show[cols].tail(5).sort_index(ascending=False), use_container_width=True, hide_index=True)

# === PESTAÑA 2: OBJETIVOS (LA LÓGICA NUEVA) ===
with tab2:
    st.header("🎯 Planificador de Metas")
    
    st.info(f"💡 El sistema usará tu saldo disponible (**{formato_visual(saldo_actual)}**) para reducir lo que necesitas ahorrar.")

    # Formulario Crear Meta
    with st.expander("➕ Crear Nueva Meta"):
        with st.form("obj"):
            nom = st.text_input("Nombre de la meta", placeholder="Ej: Coche Nuevo")
            cant = st.text_input("Precio Total (€)", placeholder="Ej: 15000,00")
            fin = st.date_input("Fecha Límite")
            val = procesar_texto_a_numero(cant)
            
            if st.form_submit_button("Guardar Meta") and val > 0:
                val_excel = str(val).replace(".", ",")
                hoja_obj.append_row([nom, val_excel, str(fin), str(date.today())])
                st.rerun()

    # CÁLCULOS
    try:
        do = hoja_obj.get_all_records(numericise_ignore=['all'])
        dfo = pd.DataFrame(do)
        
        if not dfo.empty:
            st.divider()
            
            # Input de Sueldo para calcular esfuerzo
            sueldo_input = st.text_input("💰 Tu Ingreso Mensual (para calcular esfuerzo)", value="1500")
            sueldo_mensual = procesar_texto_a_numero(sueldo_input)

            st.subheader("Tu Plan de Ahorro")

            for i, r in dfo.iterrows():
                precio_meta = procesar_texto_a_numero(r['Monto_Meta'])
                
                # --- AQUÍ ESTÁ LA NUEVA FÓRMULA ---
                # Restamos lo que ya tienes ahorrado al precio de la meta
                falta_por_ahorrar = precio_meta - saldo_actual
                
                # Fechas
                dias_restantes = (pd.to_datetime(r['Fecha_Limite']).date() - date.today()).days
                meses_restantes = max(dias_restantes / 30, 0.1) # Evitar división por cero

                with st.container(border=True):
                    col_izq, col_der = st.columns([3, 1])
                    
                    col_izq.markdown(f"### {r['Objetivo']}")
                    col_izq.write(f"Precio Total: **{formato_visual(precio_meta)}**")
                    
                    if falta_por_ahorrar <= 0:
                        # Si tu saldo ya cubre la meta
                        col_izq.success(f"🎉 ¡Felicidades! Tienes **{formato_visual(saldo_actual)}**, suficiente para pagar esto.")
                    
                    elif dias_restantes > 0:
                        # Cálculo mensual basado en LO QUE FALTA
                        ahorro_mensual = falta_por_ahorrar / meses_restantes
                        
                        col_izq.markdown(f"Te faltan: **{formato_visual(falta_por_ahorrar)}** (Usando tu saldo actual)")
                        
                        # Análisis de esfuerzo según tu sueldo
                        pct_esfuerzo = 0
                        if sueldo_mensual > 0:
                            pct_esfuerzo = (ahorro_mensual / sueldo_mensual) * 100
                        
                        msg = f"Debes ahorrar **{formato_visual(ahorro_mensual)} / mes**"
                        
                        if pct_esfuerzo > 50:
                            col_izq.error(f"{msg} (⚠️ {pct_esfuerzo:.0f}% de tu ingreso)")
                        elif pct_esfuerzo > 20:
                            col_izq.warning(f"{msg} (📊 {pct_esfuerzo:.0f}% de tu ingreso)")
                        else:
                            col_izq.success(f"{msg} (✅ {pct_esfuerzo:.0f}% de tu ingreso)")
                            
                        col_der.metric("Meses", f"{meses_restantes:.1f}")
                    else:
                        col_izq.error("¡La fecha límite ha pasado!")

    except Exception as e:
        st.info("No hay metas creadas todavía.")