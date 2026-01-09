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
# 2. FUNCIONES DE LIMPIEZA (LA MAGIA)
# -----------------------------------------------------------------------------
def limpiar_moneda(valor):
    """Convierte textos como '$1.500.000' a números reales 1500000"""
    if isinstance(valor, str):
        # Quitamos $, puntos y espacios
        limpio = valor.replace('$', '').replace('.', '').replace(' ', '').strip()
        # Si queda vacío, es 0
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
    
    # Leemos las pestañas sin caché (ttl=0)
    df_registros = conn.read(worksheet="Registro_Semanal", ttl=0)
    df_metas = conn.read(worksheet="Metas", ttl=0)
    
    # --- LIMPIEZA DE COLUMNAS ---
    df_registros.columns = df_registros.columns.str.strip()
    df_metas.columns = df_metas.columns.str.strip()

    # --- LIMPIEZA DE DATOS (AQUI SOLUCIONAMOS TUS ERRORES) ---
    
    # 1. Limpiar Dinero (Quitar $)
    df_registros['Valor'] = df_registros['Valor'].apply(limpiar_moneda)
    df_metas['Meta_Total'] = df_metas['Meta_Total'].apply(limpiar_moneda)

    # 2. Arreglar Fechas y Meses
    # Convertimos la columna fecha a formato Fecha Real
    df_registros['Fecha_Reporte'] = pd.to_datetime(df_registros['Fecha_Reporte'], dayfirst=True, errors='coerce')
    
    # TRUCO: Creamos una columna nueva "Mes_Normalizado" (Ej: 2026-01) 
    # Usamos esto para unir las tablas, ignorando si escribiste "Ene" o "Fe" mal.
    df_registros['Mes_Normalizado'] = df_registros['Fecha_Reporte'].dt.strftime('%Y-%m')
    
    # Hacemos lo mismo con la hoja de Metas
    # Asumimos que la columna Mes_Objetivo en Metas es una fecha (1/1/2026)
    df_metas['Mes_Objetivo'] = pd.to_datetime(df_metas['Mes_Objetivo'], dayfirst=True, errors='coerce')
    df_metas['Mes_Normalizado'] = df_metas['Mes_Objetivo'].dt.strftime('%Y-%m')

    # Eliminamos filas sin fecha válida
    df_registros = df_registros.dropna(subset=['Mes_Normalizado'])

except Exception as e:
    st.error("⚠️ Error técnico leyendo el archivo.")
    st.code(e)
    st.stop()

# -----------------------------------------------------------------------------
# 4. FILTROS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")
    
    # Filtro de Mes (Usamos el normalizado para que sea perfecto)
    meses_disponibles = sorted(df_registros['Mes_Normalizado'].unique().tolist())
    mes_seleccionado = st.selectbox("Selecciona Mes (Año-Mes)", meses_disponibles)
    
    # Filtro Vendedor (Limpiamos espacios por si acaso)
    df_registros['Vendedor'] = df_registros['Vendedor'].astype(str).str.strip()
    vendedores = ["Todos"] + sorted(df_registros['Vendedor'].unique().tolist())
    vendedor_sel = st.selectbox("Vendedor", vendedores)

# -----------------------------------------------------------------------------
# 5. LÓGICA DE NEGOCIO
# -----------------------------------------------------------------------------

# A. Filtrar por mes
df_mes = df_registros[df_registros['Mes_Normalizado'] == mes_seleccionado].copy()

if df_mes.empty:
    st.warning("No hay datos para este mes.")
    st.stop()

# B. Foto más reciente (Última semana)
fecha_maxima = df_mes['Fecha_Reporte'].max()
df_actual = df_mes[df_mes['Fecha_Reporte'] == fecha_maxima].copy()

# C. Filtrar Vendedor
if vendedor_sel != "Todos":
    df_actual = df_actual[df_actual['Vendedor'] == vendedor_sel]
    # Buscamos la meta usando el mes normalizado y el nombre limpio
    meta_filtrada = df_metas[
        (df_metas['Mes_Normalizado'] == mes_seleccionado) & 
        (df_metas['Vendedor'].astype(str).str.strip() == vendedor_sel)
    ]
    meta_total = meta_filtrada['Meta_Total'].sum()
else:
    # Meta de todos para ese mes
    meta_filtrada = df_metas[df_metas['Mes_Normalizado'] == mes_seleccionado]
    meta_total = meta_filtrada['Meta_Total'].sum()

# D. CLASIFICACIÓN INTELIGENTE (Detecta "Fendiente" y errores)
def clasificar_estado(texto):
    texto = str(texto).lower()
    if 'op' in texto and 'pend' not in texto and 'fend' not in texto: 
        return 'Cerrado (OP)' # Si dice OP y no dice pendiente
    elif 'pend' in texto or 'pte' in texto or 'fend' in texto: 
        return 'Pendiente'    # Si dice Pendiente, PTE o Fendiente
    elif 'pipe' in texto: 
        return 'Pipeline'
    else: 
        return 'Otros'

df_actual['Estado_Limpio'] = df_actual['Estado'].apply(clasificar_estado)

# Sumas
total_proyectado = df_actual['Valor'].sum()
total_op = df_actual[df_actual['Estado_Limpio'] == 'Cerrado (OP)']['Valor'].sum()
total_pendiente = df_actual[df_actual['Estado_Limpio'] == 'Pendiente']['Valor'].sum()
total_pipeline = df_actual[df_actual['Estado_Limpio'] == 'Pipeline']['Valor'].sum()

cumplimiento = (total_proyectado / meta_total * 100) if meta_total > 0 else 0

# -----------------------------------------------------------------------------
# 6. VISUALIZACIÓN
# -----------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Objetivo", f"${meta_total:,.0f}")
c2.metric("Proyección", f"${total_proyectado:,.0f}", delta=f"{cumplimiento:.1f}%")
c3.metric("Ya Facturado (OP)", f"${total_op:,.0f}")
c4.metric("En Gestión", f"${total_pendiente + total_pipeline:,.0f}")

st.markdown("---")

col_izq, col_der = st.columns([2, 1])

with col_izq:
    st.subheader("📋 Detalle de Negocios")
    st.dataframe(
        df_actual[['Cliente', 'Vendedor', 'Estado', 'Valor']]
        .sort_values('Valor', ascending=False)
        .style.format({'Valor': '${:,.0f}'}),
        use_container_width=True,
        hide_index=True
    )

with col_der:
    st.subheader("Estado de la Cartera")
    # Gráfica simple de torta
    df_pie = df_actual.groupby('Estado_Limpio')['Valor'].sum().reset_index()
    if not df_pie.empty:
        fig = px.pie(df_pie, values='Valor', names='Estado_Limpio', 
                     color='Estado_Limpio',
                     color_discrete_map={'Cerrado (OP)':'#00cc96', 'Pendiente':'#ef553b', 'Pipeline':'#636efa'})
        st.plotly_chart(fig, use_container_width=True)