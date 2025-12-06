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

# Conexión a Deudas (Si no existe, no falla, pero avisa)
try:
    hoja_deudas = libro.worksheet("Deudas")
except:
    st.warning("⚠️ La hoja 'Deudas' no se detecta. El botón de Resetear la creará por ti.")
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

# --- BARRA LATERAL (RESET TOTAL) ---
with st.sidebar:
    st.header("⚙️ Mantenimiento")
    st.info("Usa este botón para actualizar las columnas nuevas en el Excel.")
    
    if st.button("⚠️ BORRAR TODO Y REINICIAR (DIARIO + DEUDAS)", type="primary"):
        # 1. Resetear Diario
        hoja1.clear()
        hoja1.append_row(["Fecha", "Categoría", "Concepto", "Monto", "Tipo"])
        
        # 2. Resetear Deudas (CON LA NUEVA COLUMNA PERSONA)
        if hoja_deudas:
            hoja_deudas.clear()
            hoja_deudas.append_row(["Fecha", "Persona", "Concepto", "Monto", "Tipo"])
            
        st.cache_data.clear()
        st.success("✅ Tablas actualizadas con las nuevas columnas.")
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

# --- INTERFAZ ---
st.title("💰 Mi Cartera Inteligente")

c1, c2, c3 = st.columns(3)
c1.metric("Saldo Disponible", formato_visual(saldo_actual))
c2.metric("Ingresos", formato_visual(ingresos))
c3.metric("Gastos", formato_visual(gastos), delta_color="inverse")

st.divider()

tab1, tab2, tab3 = st.tabs(["📝 Diario", "🎯 Objetivos", "💸 Deudas"])

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
            sueldo_real = procesar_texto_a_numero(st.text_input("Tu Ingreso Mensual", value="200,00"))
            
            for i, r in dfo.iterrows():
                precio_meta = procesar_texto_a_numero(r['Monto_Meta'])
                falta = precio_meta - saldo_actual
                fecha_lim = pd.to_datetime(r['Fecha_Limite']).date()
                dias = (fecha_lim - date.today()).days
                meses = max(dias / 30.44, 0.1)

                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 0.5])
                    with c1:
                        st.markdown(f"### 🚩 {r['Objetivo']}")
                        st.write(f"Precio: **{formato_visual(precio_meta)}**")
                        if falta <= 0: st.success("🎉 ¡Conseguido con tu saldo!")
                        else: st.write(f"Te faltan: **{formato_visual(falta)}**")
                    with c2:
                        if falta > 0 and dias > 0:
                            ahorro = falta / meses
                            pct = (ahorro / sueldo_real * 100) if sueldo_real > 0 else 0
                            st.metric("Ahorro Mensual", formato_visual(ahorro))
                            if pct > 40: st.warning(f"⚠️ {pct:.0f}% de tu ingreso")
                            else: st.success(f"✅ {pct:.0f}% de tu ingreso")
                        elif dias <= 0: st.error("¡Vencida!")
                    with c3:
                        if st.button("🗑️", key=f"d_m_{i}"):
                            hoja_obj.delete_rows(i + 2)
                            st.cache_data.clear()
                            st.rerun()
    except: st.info("No hay metas.")

# === PESTAÑA 3: DEUDAS (ACTUALIZADA) ===
with tab3:
    st.header("💸 Blog de Deudas")
    
    if hoja_deudas:
        with st.expander("➕ Apuntar Nueva Deuda", expanded=True):
            with st.form("deuda"):
                # AQUI ESTÁ EL CAMBIO: SEPARADO PERSONA Y CONCEPTO
                col_d1, col_d2 = st.columns(2)
                
                with col_d1:
                    persona = st.text_input("👤 Persona / Entidad", placeholder="Ej: Juan, Banco")
                    monto_deuda = st.text_input("Importe (€)", placeholder="Ej: 50,00")
                
                with col_d2:
                    concepto = st.text_input("📝 Concepto (Motivo)", placeholder="Ej: Cena, Préstamo")
                    tipo_deuda = st.radio("Situación:", ["🔴 Tengo que pagar (DEBO)", "🟢 Me tienen que pagar (ME DEBEN)"])
                
                val_deuda = procesar_texto_a_numero(monto_deuda)
                
                if st.form_submit_button("Anotar Deuda") and val_deuda > 0:
                    tipo_guardar = "DEBO" if "🔴" in tipo_deuda else "ME DEBEN"
                    val_excel = str(val_deuda).replace(".", ",")
                    # Guardamos la nueva estructura: Fecha, Persona, Concepto, Monto, Tipo
                    hoja_deudas.append_row([str(date.today()), persona, concepto, val_excel, tipo_guardar])
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
                    persona = r['Persona']
                    motivo = r['Concepto']
                    
                    with st.container(border=True):
                        c_info, c_action = st.columns([4, 1])
                        
                        with c_info:
                            if tipo == "DEBO":
                                st.error(f"🔴 **DEBO** a **{persona}**: {formato_visual(importe)}")
                                st.caption(f"Motivo: {motivo} | Fecha: {r['Fecha']}")
                            else:
                                st.success(f"🟢 **ME DEBE** **{persona}**: {formato_visual(importe)}")
                                st.caption(f"Motivo: {motivo} | Fecha: {r['Fecha']}")
                        
                        with c_action:
                            st.write("")
                            if st.button("✅ Saldar", key=f"saldar_{i}", help="Borrar deuda"):
                                hoja_deudas.delete_rows(i + 2)
                                st.toast("¡Deuda saldada!")
                                st.cache_data.clear()
                                st.rerun()
            else:
                st.info("¡Estás en paz! No hay deudas pendientes.")
                
        except Exception as e:
            st.info("No hay deudas registradas aún.")