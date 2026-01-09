import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE LA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Tablero Comercial Pro", layout="wide", page_icon="📈")

st.title("🚀 Tablero de Control de Ventas - Plan 2025")
st.markdown("---")

# -----------------------------------------------------------------------------
# 2. CONEXIÓN A GOOGLE SHEETS
# -----------------------------------------------------------------------------
# Usamos la conexión nativa de Streamlit para GSheets (requiere configurar secrets.toml)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Cargar datos con caché (TTL de 10 min para no saturar la API)
    df_registros = conn.read(worksheet="Registro_Semanal", ttl=600)
    df_metas = conn.read(worksheet="Metas", ttl=600)
    
    # Limpieza básica de datos
    df_registros['Fecha_Reporte'] = pd.to_datetime(df_registros['Fecha_Reporte'])
    df_registros['Valor'] = pd.to_numeric(df_registros['Valor'], errors='coerce').fillna(0)
    
except Exception as e:
    st.error("⚠️ Error conectando a Google Sheets. Asegúrate de configurar los secretos.")
    st.info("Mostrando datos de ejemplo para demostración...")
    
    # DATOS MOCK (Simulación para que veas cómo funciona sin conectar aún)
    df_registros = pd.DataFrame({
        'Fecha_Reporte': pd.to_datetime(['2025-10-04']*5 + ['2025-10-11']*5),
        'Mes_Objetivo': ['2025-10']*10,
        'Vendedor': ['Ana', 'Juan', 'Ana', 'Juan', 'Ana'] * 2,
        'Cliente': ['Cliente A', 'Cliente B', 'Cliente C', 'Cliente B', 'Cliente A'] * 2,
        'Estado': ['OP Emitida', 'Pendiente OP', 'Pipeline', 'OP Emitida', 'Pipeline',
                   'OP Emitida', 'OP Emitida', 'Pipeline', 'OP Emitida', 'Pendiente OP'],
        'Fase_Detalle': ['Cerrado', 'Aprob. Arte', 'Cotización', 'Cerrado', 'Diseño',
                         'Cerrado', 'Cerrado', 'Cotización', 'Cerrado', 'Enviando OC'],
        'Valor': [5000, 3000, 2000, 3000, 1000, 5000, 3500, 1500, 3000, 1200]
    })
    df_metas = pd.DataFrame({
        'Mes_Objetivo': ['2025-10', '2025-10'],
        'Vendedor': ['Ana', 'Juan'],
        'Meta_Total': [10000, 8000]
    })

# -----------------------------------------------------------------------------
# 3. FILTROS LATERALES
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros de Análisis")
    
    # Filtro de Mes Objetivo
    meses_disponibles = df_registros['Mes_Objetivo'].unique()
    mes_seleccionado = st.selectbox("Selecciona Mes a Analizar", meses_disponibles)
    
    # Filtro Vendedor (Opcional)
    vendedores = ["Todos"] + list(df_registros['Vendedor'].unique())
    vendedor_sel = st.selectbox("Filtrar por Vendedor", vendedores)

# -----------------------------------------------------------------------------
# 4. PROCESAMIENTO DE DATOS (LÓGICA DE NEGOCIO)
# -----------------------------------------------------------------------------

# A. Filtrar data por mes
df_mes = df_registros[df_registros['Mes_Objetivo'] == mes_seleccionado].copy()

# B. Obtener la "Foto Más Reciente" (Última semana reportada)
#    Esto es crucial: para los KPI actuales, solo nos importa el último reporte.
fecha_maxima = df_mes['Fecha_Reporte'].max()
df_actual = df_mes[df_mes['Fecha_Reporte'] == fecha_maxima].copy()

if vendedor_sel != "Todos":
    df_actual = df_actual[df_actual['Vendedor'] == vendedor_sel]
    # Filtramos metas también
    meta_total = df_metas[(df_metas['Mes_Objetivo'] == mes_seleccionado) & 
                          (df_metas['Vendedor'] == vendedor_sel)]['Meta_Total'].sum()
else:
    meta_total = df_metas[df_metas['Mes_Objetivo'] == mes_seleccionado]['Meta_Total'].sum()

# Cálculos Totales Actuales
total_proyectado = df_actual['Valor'].sum()
total_op = df_actual[df_actual['Estado'] == 'OP Emitida']['Valor'].sum()
total_pendiente = df_actual[df_actual['Estado'] == 'Pendiente OP']['Valor'].sum()
total_pipeline = df_actual[df_actual['Estado'] == 'Pipeline']['Valor'].sum()

cumplimiento = (total_proyectado / meta_total * 100) if meta_total > 0 else 0

# -----------------------------------------------------------------------------
# 5. VISUALIZACIÓN - KPIs SUPERIORES
# -----------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("Meta del Mes", f"${meta_total:,.0f}")
col2.metric("Proyección Total", f"${total_proyectado:,.0f}", delta=f"{cumplimiento:.1f}% Cumplimiento")
col3.metric("Ya en OP (Cerrado)", f"${total_op:,.0f}")
col4.metric("Pendiente + Pipeline", f"${total_pendiente + total_pipeline:,.0f}")

st.markdown("---")

# -----------------------------------------------------------------------------
# 6. GRÁFICOS PRINCIPALES
# -----------------------------------------------------------------------------

c1, c2 = st.columns([1, 1])

with c1:
    st.subheader(f"🔍 Composición de la Venta (Semana {fecha_maxima.date()})")
    # Agrupamos por estado para el gráfico de torta o barras
    df_estado = df_actual.groupby("Estado")['Valor'].sum().reset_index()
    
    fig_bar = px.bar(df_estado, x='Estado', y='Valor', color='Estado', 
                     text_auto='.2s', title="Desglose: OP vs Pendiente vs Pipeline",
                     color_discrete_map={'OP Emitida':'#00CC96', 'Pendiente OP':'#EF553B', 'Pipeline':'#636EFA'})
    st.plotly_chart(fig_bar, use_container_width=True)

with c2:
    st.subheader("📈 Evolución Semanal de la Proyección")
    # Aquí usamos TODA la historia (df_mes), no solo df_actual
    # Agrupamos por Fecha de Reporte para ver cómo cambió la suma total semana a semana
    if vendedor_sel != "Todos":
        df_evo = df_mes[df_mes['Vendedor'] == vendedor_sel]
    else:
        df_evo = df_mes
        
    df_evo_agg = df_evo.groupby("Fecha_Reporte")['Valor'].sum().reset_index()
    
    fig_line = px.line(df_evo_agg, x='Fecha_Reporte', y='Valor', markers=True,
                       title="¿Cómo ha cambiado nuestra proyección semana a semana?")
    # Añadimos una línea horizontal con la meta
    fig_line.add_hline(y=meta_total, line_dash="dot", annotation_text="Meta", annotation_position="top left", line_color="green")
    
    st.plotly_chart(fig_line, use_container_width=True)

# -----------------------------------------------------------------------------
# 7. ANÁLISIS DETALLADO
# -----------------------------------------------------------------------------

c3, c4 = st.columns([2, 1])

with c3:
    st.subheader("Detalle por Cliente (Status Actual)")
    # Tabla interactiva
    st.dataframe(
        df_actual[['Cliente', 'Vendedor', 'Estado', 'Fase_Detalle', 'Valor']]
        .sort_values(by='Valor', ascending=False)
        .style.format({'Valor': '${:,.0f}'})
        .background_gradient(subset=['Valor'], cmap="Blues"),
        use_container_width=True,
        hide_index=True
    )

with c4:
    st.subheader("Análisis por Fase (Pendientes)")
    # Solo mostramos en qué fase se estancan los pendientes
    df_pending = df_actual[df_actual['Estado'] == 'Pendiente OP']
    if not df_pending.empty:
        fig_pie = px.pie(df_pending, names='Fase_Detalle', values='Valor', hole=0.4,
                         title="¿En qué fase están los pendientes?")
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No hay órdenes pendientes por generar.")