import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE LA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Tablero Comercial Pro", layout="wide", page_icon="📈")

st.title("🚀 Tablero de Control de Ventas - Plan 2025")
st.markdown("---")

# -----------------------------------------------------------------------------
# 2. CONEXIÓN A GOOGLE SHEETS (CON CORRECCIÓN DE ERRORES)
# -----------------------------------------------------------------------------
try:
    # Conectamos con la hoja
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Leemos las pestañas. ttl=0 significa que no guarda caché (actualiza al instante)
    df_registros = conn.read(worksheet="Registro_Semanal", ttl=0)
    df_metas = conn.read(worksheet="Metas", ttl=0)
    
    # --- LIMPIEZA AUTOMÁTICA DE NOMBRES DE COLUMNA ---
    # Esto elimina espacios invisibles al principio o final (ej: "Mes_Objetivo " -> "Mes_Objetivo")
    df_registros.columns = df_registros.columns.str.strip()
    df_metas.columns = df_metas.columns.str.strip()

    # --- VERIFICACIÓN DE SEGURIDAD ---
    # Comprobamos que las columnas existan antes de seguir para evitar pantallas de error feas
    if 'Mes_Objetivo' not in df_metas.columns:
        st.error(f"⚠️ ERROR: No encuentro la columna 'Mes_Objetivo' en la hoja 'Metas'. Las columnas que veo son: {list(df_metas.columns)}")
        st.info("Por favor, ve a tu Google Sheet, pestaña Metas, y revisa que en la fila 1 diga exactamente 'Mes_Objetivo' (sin espacios).")
        st.stop() # Detiene la app aquí para no romper nada más
        
    if 'Mes_Objetivo' not in df_registros.columns:
        st.error(f"⚠️ ERROR: No encuentro la columna 'Mes_Objetivo' en la hoja 'Registro_Semanal'.")
        st.stop()

    # --- FORMATEO DE DATOS ---
    # Convertimos fechas y números para que Python los entienda
    df_registros['Fecha_Reporte'] = pd.to_datetime(df_registros['Fecha_Reporte'], errors='coerce')
    df_registros['Valor'] = pd.to_numeric(df_registros['Valor'], errors='coerce').fillna(0)
    
    # Eliminamos filas vacías si las hubiera
    df_registros = df_registros.dropna(subset=['Fecha_Reporte'])

except Exception as e:
    st.error("⚠️ Ocurrió un error al conectar con Google Sheets.")
    st.code(e) # Muestra el error técnico
    st.stop()

# -----------------------------------------------------------------------------
# 3. FILTROS LATERALES
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros de Análisis")
    
    # Filtro de Mes Objetivo (Ordenado)
    meses_disponibles = sorted(df_registros['Mes_Objetivo'].unique().tolist())
    if not meses_disponibles:
        st.warning("No hay datos de meses en la hoja.")
        st.stop()
        
    mes_seleccionado = st.selectbox("Selecciona Mes a Analizar", meses_disponibles)
    
    # Filtro Vendedor
    vendedores = ["Todos"] + sorted(df_registros['Vendedor'].unique().tolist())
    vendedor_sel = st.selectbox("Filtrar por Vendedor", vendedores)

# -----------------------------------------------------------------------------
# 4. PROCESAMIENTO DE DATOS (LÓGICA DE NEGOCIO)
# -----------------------------------------------------------------------------

# A. Filtrar data por mes seleccionado
df_mes = df_registros[df_registros['Mes_Objetivo'] == mes_seleccionado].copy()

if df_mes.empty:
    st.info(f"No hay registros para el mes {mes_seleccionado}.")
    st.stop()

# B. Obtener la "Foto Más Reciente" (Última semana reportada)
#    Esto es crucial: para los KPI actuales, solo nos importa el último reporte disponible.
fecha_maxima = df_mes['Fecha_Reporte'].max()
df_actual = df_mes[df_mes['Fecha_Reporte'] == fecha_maxima].copy()

# C. Aplicar filtro de vendedor si es necesario
if vendedor_sel != "Todos":
    df_actual = df_actual[df_actual['Vendedor'] == vendedor_sel]
    df_evo = df_mes[df_mes['Vendedor'] == vendedor_sel] # Para la gráfica de evolución
    
    # Filtrar meta específica
    meta_filtrada = df_metas[(df_metas['Mes_Objetivo'] == mes_seleccionado) & 
                             (df_metas['Vendedor'] == vendedor_sel)]
    if not meta_filtrada.empty:
        meta_total = meta_filtrada['Meta_Total'].sum()
    else:
        meta_total = 0
else:
    df_evo = df_mes # Para la gráfica de evolución (todos)
    # Meta total del mes (suma de todos los vendedores)
    meta_filtrada = df_metas[df_metas['Mes_Objetivo'] == mes_seleccionado]
    meta_total = meta_filtrada['Meta_Total'].sum()

# D. Cálculos de Totales (KPIs)
total_proyectado = df_actual['Valor'].sum()

# Filtramos por Estado exacto (Asegúrate que en el Excel escriban esto tal cual)
total_op = df_actual[df_actual['Estado'] == 'OP Emitida']['Valor'].sum()
total_pendiente = df_actual[df_actual['Estado'] == 'Pendiente OP']['Valor'].sum()
total_pipeline = df_actual[df_actual['Estado'] == 'Pipeline']['Valor'].sum()

# Cálculo de cumplimiento
cumplimiento = (total_proyectado / meta_total * 100) if meta_total > 0 else 0

# -----------------------------------------------------------------------------
# 5. VISUALIZACIÓN - KPIs SUPERIORES
# -----------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("🎯 Meta del Mes", f"${meta_total:,.0f}")
col2.metric("💰 Proyección Total", f"${total_proyectado:,.0f}", delta=f"{cumplimiento:.1f}% Cumplimiento")
col3.metric("✅ Ya en OP (Cerrado)", f"${total_op:,.0f}")
col4.metric("⏳ Pendiente + Pipeline", f"${total_pendiente + total_pipeline:,.0f}")

st.markdown("---")

# -----------------------------------------------------------------------------
# 6. GRÁFICOS PRINCIPALES
# -----------------------------------------------------------------------------

c1, c2 = st.columns([1, 1])

with c1:
    st.subheader(f"🔍 Composición de la Venta (Semana {fecha_maxima.date()})")
    
    # Agrupamos por estado
    df_estado = df_actual.groupby("Estado")['Valor'].sum().reset_index()
    
    if not df_estado.empty:
        fig_bar = px.bar(df_estado, x='Estado', y='Valor', color='Estado', 
                         text_auto='.2s', title="Desglose: OP vs Pendiente vs Pipeline",
                         color_discrete_map={'OP Emitida':'#00CC96', 'Pendiente OP':'#EF553B', 'Pipeline':'#636EFA'})
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No hay datos para graficar composición.")

with c2:
    st.subheader("📈 Evolución Semanal de la Proyección")
    
    # Agrupamos por Fecha de Reporte para ver la historia
    df_evo_agg = df_evo.groupby("Fecha_Reporte")['Valor'].sum().reset_index()
    
    if not df_evo_agg.empty:
        fig_line = px.line(df_evo_agg, x='Fecha_Reporte', y='Valor', markers=True,
                           title="Variación de la proyección semana a semana")
        # Añadimos línea de meta
        fig_line.add_hline(y=meta_total, line_dash="dot", annotation_text="Meta", annotation_position="top left", line_color="green")
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("Faltan datos históricos para mostrar la línea de tiempo.")

# -----------------------------------------------------------------------------
# 7. ANÁLISIS DETALLADO
# -----------------------------------------------------------------------------

c3, c4 = st.columns([2, 1])

with c3:
    st.subheader("📋 Detalle por Cliente (Status Actual)")
    
    # Mostramos tabla limpia
    if not df_actual.empty:
        df_tabla = df_actual[['Cliente', 'Vendedor', 'Estado', 'Fase_Detalle', 'Valor']].copy()
        df_tabla = df_tabla.sort_values(by='Valor', ascending=False)
        
        st.dataframe(
            df_tabla.style.format({'Valor': '${:,.0f}'}).background_gradient(subset=['Valor'], cmap="Blues"),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.write("Sin datos para mostrar en tabla.")

with c4:
    st.subheader("⚠️ Fases de Estancamiento")
    # Filtramos solo lo que está pendiente
    df_pending = df_actual[df_actual['Estado'] == 'Pendiente OP']
    
    if not df_pending.empty:
        fig_pie = px.pie(df_pending, names='Fase_Detalle', values='Valor', hole=0.4,
                         title="¿Qué detiene los pedidos pendientes?")
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.success("¡Excelente! No hay órdenes pendientes por generar.")