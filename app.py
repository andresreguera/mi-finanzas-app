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

# --- NUEVO: CONEXIÓN A LA HOJA DE DEUDAS ---
try:
    hoja_deudas = libro.worksheet("Deudas")
except:
    st.error("⚠️ Falta la hoja 'Deudas'. Por favor créala en el Excel.")
    st.stop()

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
    if st.button("🔄 RECARGAR DATOS", type="primary"):
        st.cache_data.clear()
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
        ingresos = df_movimientos[df_movimientos['Monto_Calc'] > 0]['Monto_Calc'].sum()
        gastos = df_movimientos[df_movimientos['Monto_Calc'] < 0]['Monto_Calc'].sum()
        saldo_actual = df_movimientos['Monto_Calc'].sum()
except: pass

# --- INTERFAZ PRINCIPAL ---
st.title("💰 Mi Cartera Inteligente")

c1, c2, c3 = st.columns(3)
c1.metric("Saldo Disponible", formato_visual(saldo_actual))
c2.metric("Ingresos", formato_visual(ingresos))
c3.metric("Gastos", formato_visual(gastos), delta_color="inverse")

st.divider()

# AHORA TENEMOS 3 PESTAÑAS
tab1, tab2, tab3 = st.tabs(["📝 Diario", "🎯 Objetivos", "💸 Deudas y Préstamos"])

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

# === PESTAÑA 2: OBJETIVOS ===
with tab2:
    st.header("🎯 Metas")
    
    with st.expander("➕ Crear Nueva Meta", expanded=False):
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
            
            col_s_in, col_s_info = st.columns([1, 2])
            sueldo_txt = col_s_in.text_input("Tu Ingreso Mensual", value="200,00")
            sueldo_real = procesar_texto_a_numero(sueldo_txt)
            col_s_info.info(f"Cálculos basados en: **{formato_visual(sueldo_real)}**")

            st.markdown("---")

            for i, r in dfo.iterrows():
                precio_meta = procesar_texto_a_numero(r['Monto_Meta'])
                falta_por_ahorrar = precio_meta - saldo_actual
                fecha_limite = pd.to_datetime(r['Fecha_Limite']).date()
                dias_restantes = (fecha_limite - date.today()).days
                meses_restantes = max(dias_restantes / 30.44, 0.1)

                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 0.5])
                    
                    with c1:
                        st.markdown(f"### 🚩 {r['Objetivo']}")
                        st.write(f"Precio: **{formato_visual(precio_meta)}**")
                        
                        if saldo_actual > 0 and precio_meta > 0:
                            progreso = min(saldo_actual / precio_meta, 1.0)
                            st.progress(progreso)
                        
                        if falta_por_ahorrar <= 0:
                            st.success(f"🎉 ¡Objetivo cubierto!")
                        else:
                            st.write(f"Te faltan: **{formato_visual(falta_por_ahorrar)}**")

                    with c2:
                        if falta_por_ahorrar > 0 and dias_restantes > 0:
                            ahorro_necesario = falta_por_ahorrar / meses_restantes
                            pct = (ahorro_necesario / sueldo_real * 100) if sueldo_real > 0 else 0
                            
                            st.metric("Ahorro Mensual", formato_visual(ahorro_necesario))
                            
                            if pct > 100: st.error(f"⚠️ Imposible ({pct:.0f}%)")
                            elif pct > 40: st.warning(f"⚠️ Duro ({pct:.0f}%)")
                            else: st.success(f"✅ Factible ({pct:.0f}%)")
                        elif dias_restantes <= 0:
                            st.error("¡Vencida!")

                    with c3:
                        if st.button("🗑️", key=f"del_meta_{i}"):
                            hoja_obj.delete_rows(i + 2)
                            st.cache_data.clear()
                            st.rerun()

    except:
        st.info("No hay metas.")

# === PESTAÑA 3: DEUDAS (NUEVA) ===
with tab3:
    st.header("💸 Blog de Deudas")
    
    # Formulario Deudas
    with st.expander("➕ Apuntar Nueva Deuda", expanded=True):
        with st.form("deuda"):
            col_d1, col_d2 = st.columns(2)
            concepto_deuda = col_d1.text_input("¿Quién/Qué?", placeholder="Ej: Juan, Cena, Banco")
            monto_deuda_txt = col_d1.text_input("Importe (€)", placeholder="Ej: 50,00")
            
            tipo_deuda = col_d2.radio("Situación:", ["🔴 Tengo que pagar (DEBO)", "🟢 Me tienen que pagar (ME DEBEN)"])
            
            val_deuda = procesar_texto_a_numero(monto_deuda_txt)
            
            if st.form_submit_button("Anotar Deuda") and val_deuda > 0:
                # Guardamos si es "DEBO" o "ME DEBEN" simplificado
                tipo_guardar = "DEBO" if "🔴" in tipo_deuda else "ME DEBEN"
                val_excel = str(val_deuda).replace(".", ",")
                
                hoja_deudas.append_row([concepto_deuda, val_excel, tipo_guardar, str(date.today())])
                st.success("Anotado.")
                st.cache_data.clear()
                st.rerun()

    st.divider()

    # Listado de Deudas
    try:
        dd = hoja_deudas.get_all_records(numericise_ignore=['all'])
        df_deudas = pd.DataFrame(dd)
        
        if not df_deudas.empty:
            st.subheader("Lista Pendiente")
            
            for i, r in df_deudas.iterrows():
                importe = procesar_texto_a_numero(r['Monto'])
                tipo = r['Tipo']
                
                # Diseño visual según el tipo
                with st.container(border=True):
                    c_info, c_action = st.columns([4, 1])
                    
                    with c_info:
                        if tipo == "DEBO":
                            st.error(f"🔴 **DEBO** a {r['Concepto']}: **{formato_visual(importe)}**")
                        else:
                            st.success(f"🟢 **ME DEBE** {r['Concepto']}: **{formato_visual(importe)}**")
                        st.caption(f"Fecha: {r['Fecha']}")
                    
                    with c_action:
                        # Botón para saldar la deuda (borrarla)
                        st.write("")
                        if st.button("✅ Saldar", key=f"saldar_{i}", help="Marcar como resuelto y borrar"):
                            hoja_deudas.delete_rows(i + 2)
                            st.toast("¡Deuda saldada!")
                            st.cache_data.clear()
                            st.rerun()
        else:
            st.info("¡Estás en paz! No hay deudas pendientes.")
            
    except Exception as e:
        st.info("No hay deudas registradas aún.")