import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Tablero Comercial 2026", layout="wide", page_icon="🚀")
st.title("🚀 Tablero de Control de Ventas - Plan 2026")
st.markdown("---")

# -----------------------------------------------------------------------------
# 2. FUNCIONES DE LIMPIEZA
# -----------------------------------------------------------------------------
def limpiar_moneda(valor):
    """Limpia textos de dinero ($1.000 -> 1000.0)"""
    if isinstance(valor, str):
        limpio = valor.replace('$', '').replace('.', '').replace(' ', '').replace(',', '').strip()
        if not limpio: return 0
        try:
            return float(limpio)
        except:
            return 0
    return valor

# -----------------------------------------------------------------------------
# 3. CONEXIÓN A GOOGLE SHEETS
# -----------------------------------------------------------------------------
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Lectura sin caché
    df_registros = conn.read(worksheet="Registro_Semanal", ttl=0)
    df_metas = conn.read(worksheet="Metas", ttl=0)
    
    # Estandarizar columnas (quitar espacios)
    df_registros.columns = df_registros.columns.str.strip()
    df_metas.columns = df_metas.columns.str.strip()

    # --- LIMPIEZA PROFUNDA DE DATOS ---
    
    # 1. Limpiar Valores Numéricos
    df_registros['Valor'] = df_registros['Valor'].apply(limpiar_moneda)
    df_metas['Meta_Total'] = df_metas['Meta_Total'].apply(limpiar_moneda)

    # 2. Fechas: Convertir a formato fecha real
    # dayfirst=True es clave para fechas latinas (DD/MM/AAAA)
    df_registros['Fecha_Reporte'] = pd.to_datetime(df_registros['Fecha_Reporte'], dayfirst=True, errors='coerce')
    
    # 3. Crear columna "Mes" normalizada (Año-Mes) para unir tablas sin error
    df_registros['Mes_Normalizado'] = df_registros['Fecha_Reporte'].dt.strftime('%Y-%m')
    
    # Limpieza de Metas (Asumiendo que Mes_Objetivo es fecha 1/1/2026)
    df_metas['Mes_Objetivo'] = pd.to_datetime(df_metas['Mes_Objetivo'], dayfirst=True, errors='coerce')
    df_metas['Mes_Normalizado'] = df_metas['Mes_Objetivo'].dt.strftime('%Y-%m')

    # Eliminar filas vacías críticas
    df_registros = df_registros.dropna(subset=['Mes_Normalizado', 'Cliente'])

except Exception as e:
    st.error("⚠️ Error procesando el archivo. Verifica que las fechas tengan formato DD/MM/AAAA.")
    st.code(e)
    st.stop()

# -----------------------------------------------------------------------------
# 4. FILTROS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")
    
    # Filtro Mes
    meses_disponibles = sorted(df_registros['Mes_Normalizado'].unique().tolist())
    mes_seleccionado = st.selectbox("Selecciona Mes", meses_disponibles)
    
    # Filtro Vendedor
    df_registros['Vendedor'] = df_registros['Vendedor'].astype(str).str.strip()
    vendedores = ["Todos"] + sorted(df_registros['Vendedor'].unique().tolist())
    vendedor_sel = st.selectbox("Vendedor", vendedores)

# -----------------------------------------------------------------------------
# 5. LÓGICA "ÚLTIMO MOVIMIENTO" (LA SOLUCIÓN AL 1.5M vs 29M)
# -----------------------------------------------------------------------------

# A. Filtrar todo lo que pasó en el mes seleccionado
df_mes = df_registros[df_registros['Mes_Normalizado'] == mes_seleccionado].copy()

if df_mes.empty:
    st.warning("No hay datos en este mes.")
    st.stop()

# B. Clasificar Estados (OP, Pendiente, Pipeline)
def clasificar_estado(texto):
    t = str(texto).lower()
    if 'op' in t and ('emit' in t or 'gener' in t) and 'pend' not in t: return 'OP Emitida'
    if 'pend' in t or 'pte' in t or 'fend' in t: return 'Pendiente OP'
    if 'pipe' in t: return 'Pipeline'
    return 'Revisar Estado' # Por si escriben algo raro

df_mes['Estado_Limpio'] = df_mes['Estado'].apply(clasificar_estado)

# C. OBTENER LA ÚLTIMA FOTO POR CLIENTE
# Ordenamos por fecha y nos quedamos con el ÚLTIMO registro de cada Cliente
# Así sumamos el estado actual de TODOS los clientes, no solo los del último viernes.
df_actual = df_mes.sort_values('Fecha_Reporte').groupby(['Cliente', 'Vendedor'], as_index=False).last()

# D. Aplicar Filtro de Vendedor sobre la foto actual
if vendedor_sel != "Todos":
    df_actual = df_actual[df_actual['Vendedor'] == vendedor_sel]
    # Meta específica del vendedor
    meta_row = df_metas[
        (df_metas['Mes_Normalizado'] == mes_seleccionado) & 
        (df_metas['Vendedor'].astype(str).str.strip() == vendedor_sel)
    ]
    meta_total = meta_row['Meta_Total'].sum()
else:
    # Meta total del equipo
    meta_row = df_metas[df_metas['Mes_Normalizado'] == mes_seleccionado]
    meta_total = meta_row['Meta_Total'].sum()

# -----------------------------------------------------------------------------
# 6. CÁLCULOS FINALES
# -----------------------------------------------------------------------------

# Sumamos lo que hay en la foto actual (Ahora sí debería dar 29M)
total_proyectado = df_actual['Valor'].sum()
total_op = df_actual[df_actual['Estado_Limpio'] == 'OP Emitida']['Valor'].sum()
total_pendiente = df_actual[df_actual['Estado_Limpio'] == 'Pendiente OP']['Valor'].sum()
total_pipeline = df_actual[df_actual['Estado_Limpio'] == 'Pipeline']['Valor'].sum()

cumplimiento = (total_proyectado / meta_total * 100) if meta_total > 0 else 0

# -----------------------------------------------------------------------------
# 7. VISUALIZACIÓN
# -----------------------------------------------------------------------------

# KPIs Principales
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("🎯 Presupuesto (Meta)", f"${meta_total:,.0f}")
kpi2.metric("📊 Proyección Total", f"${total_proyectado:,.0f}", delta=f"{cumplimiento:.1f}% vs Meta")
kpi3.metric("✅ Facturado (OP)", f"${total_op:,.0f}")
kpi4.metric("⏳ Pendiente + Pipeline", f"${total_pendiente + total_pipeline:,.0f}")

st.markdown("---")

# Gráficos
col_izq, col_der = st.columns([2, 1])

with col_izq:
    st.subheader("💰 Proyección por Cliente (Total acumulado)")
    st.caption("Suma de OP + Pendiente + Pipeline por cada cliente")
    
    # Tabla agrupada por Cliente para ver totales claros
    df_clientes = df_actual.groupby(['Cliente', 'Estado_Limpio'])['Valor'].sum().reset_index()
    
    # Gráfico de barras apiladas por Cliente
    fig_clientes = px.bar(
        df_clientes, 
        x='Valor', y='Cliente', color='Estado_Limpio',
        orientation='h', text_auto='.2s',
        color_discrete_map={'OP Emitida':'#00CC96', 'Pendiente OP':'#EF553B', 'Pipeline':'#636EFA', 'Revisar Estado':'#Gray'},
        title="¿Cuánto esperamos vender por Cliente?"
    )
    st.plotly_chart(fig_clientes, use_container_width=True)

with col_der:
    st.subheader("Estado General")
    # Gráfico de Torta
    df_torta = df_actual.groupby('Estado_Limpio')['Valor'].sum().reset_index()
    if not df_torta.empty:
        fig_pie = px.pie(
            df_torta, values='Valor', names='Estado_Limpio', hole=0.4,
            color='Estado_Limpio',
            color_discrete_map={'OP Emitida':'#00CC96', 'Pendiente OP':'#EF553B', 'Pipeline':'#636EFA'}
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No hay datos")

# Tabla de detalle al final
st.subheader("📋 Detalle de Negocios (Última actualización)")
st.dataframe(
    df_actual[['Fecha_Reporte', 'Cliente', 'Vendedor', 'Estado', 'Valor']]
    .sort_values('Valor', ascending=False)
    .style.format({'Valor': '${:,.0f}', 'Fecha_Reporte': '{:%d-%m-%Y}'}),
    use_container_width=True,
    hide_index=True
)