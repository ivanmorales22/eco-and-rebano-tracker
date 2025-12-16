"""
GDL_Insight - Dashboard de Streamlit
Dashboard para monitorear noticias sobre el Medio Ambiente en la ZMG y Chivas de Guadalajara
"""

import streamlit as st
import pandas as pd
# Asegúrate de que el nombre del archivo coincida (data o data_improved)

from environment.data import (
    get_air_quality_zmg,
    get_air_quality_zmg_stations,
    get_water_levels_history_mock,
    plot_water_levels,            # Ya no dará error
    EnvironmentVisualizations,
    get_chapala_level,
    get_env_news
)

from chivas.data import get_chivas_news

# Configuración de la página
st.set_page_config(
    page_title="GDL_Insight",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para un diseño moderno y limpio
st.markdown("""
    <style>
    /* Estilos generales */
    .main {
        padding-top: 2rem;
    }
    
    /* Título principal */
    h1 {
        color: #1f77b4;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    
    /* Estilos para las pestañas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: #f0f2f6;
        padding: 0.5rem;
        border-radius: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 10px 20px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 1rem;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #1f77b4;
        color: white;
    }
    
    /* Contenedor principal */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Sidebar */
    .css-1d391kg {
        padding-top: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# Título principal
st.title("📊 GDL_Insight")
st.markdown("---")

# Crear las pestañas
tab1, tab2 = st.tabs(["🌱 Medio Ambiente", "🐐 Chivas de Guadalajara"])

# Pestaña 1: Medio Ambiente
with tab1:
    st.markdown("### 🌱 Monitor Ambiental - Zona Metropolitana de Guadalajara")
    st.markdown("---")
    
    # ----------------------------------------------------------------------------
    # 1. CARGA DE DATOS (CON CACHÉ)
    # ----------------------------------------------------------------------------
    
    # Importar función para obtener TODAS las estaciones
    from environment.data import (
        get_air_quality_zmg_stations, 
        get_chapala_level, 
        get_env_news, 
        get_water_levels_history_mock,
        EnvironmentVisualizations
    )

    @st.cache_data(ttl=300) 
    def get_cached_stations_data():
        """Obtiene datos de todas las estaciones de calidad del aire"""
        return get_air_quality_zmg_stations(use_mock_on_error=True)
    
    @st.cache_data(ttl=300)
    def get_cached_chapala_level():
        """Obtiene la cota actual del Lago de Chapala"""
        return get_chapala_level(use_mock_on_error=True)
    
    @st.cache_data(ttl=3600)
    def get_cached_water_history(days=180):
        return get_water_levels_history_mock(days=days)

    @st.cache_data(ttl=1800)
    def get_cached_env_news_data(use_ai=True):
        return get_env_news(max_items=5, use_ai=use_ai)

    try:
        # Cargar datos principales
        with st.spinner("Conectando con red de monitoreo atmosférico..."):
            stations_list = get_cached_stations_data()
            
        # ----------------------------------------------------------------------------
        # 2. SECCIÓN SUPERIOR: MAPA DE CALIDAD DEL AIRE
        # ----------------------------------------------------------------------------
        st.markdown("#### 🗺️ Mapa de Calidad del Aire en Tiempo Real")
        
        col_map, col_kpi = st.columns([2, 1])
        
        with col_map:
            if stations_list:
                map_fig = EnvironmentVisualizations.plot_zmg_map(stations_list)
                st.plotly_chart(map_fig, width='stretch')
            else:
                st.warning("No hay datos de estaciones disponibles.")

        with col_kpi:
            st.markdown("##### Resumen ZMG")
            if stations_list:
                # Calcular promedio y peor estación
                imecas = [s['imeca'] for s in stations_list]
                avg_imeca = int(sum(imecas) / len(imecas))
                worst_station = sorted(stations_list, key=lambda x: x['imeca'], reverse=True)[0]
                
                st.metric("IMECA Promedio ZMG", f"{avg_imeca} pts")
                st.metric("Punto más crítico", worst_station['station'], 
                         f"{worst_station['imeca']} IMECA", delta_color="inverse")
                
                st.info(f"📅 Última act: {worst_station['last_update']}")
            
        st.markdown("---")

        # ----------------------------------------------------------------------------
        # 3. SECCIÓN DETALLE: SELECTOR DE ESTACIÓN
        # ----------------------------------------------------------------------------
        st.subheader("🔍 Detalle por Estación")
        
        if stations_list:
            station_names = [s['station'] for s in stations_list]
            selected_name = st.selectbox("Selecciona una estación:", station_names)
            
            # Filtrar datos de la estación seleccionada
            selected_data = next((s for s in stations_list if s['station'] == selected_name), None)
            
            if selected_data:
                d_col1, d_col2 = st.columns([1, 1])
                
                with d_col1:
                    gauge_fig = EnvironmentVisualizations.plot_imeca_gauge(
                        selected_data['imeca'], 
                        selected_data['status']
                    )
                    st.plotly_chart(gauge_fig, width='stretch')
                    
                with d_col2:
                    st.success(f"Estación: **{selected_data['station']}**")
                    st.markdown(f"""
                    - **Estado:** {selected_data['status']}
                    - **IMECA:** {selected_data['imeca']}
                    - **Fuente:** {selected_data.get('source', 'Desconocida')}
                    """)
                    
                    if selected_data['imeca'] > 100:
                        st.warning("⚠️ Calidad del aire mala. Evita actividades vigorosas al aire libre.")
                    elif selected_data['imeca'] > 50:
                        st.info("⚠️ Calidad regular. Personas sensibles deben cuidarse.")
                    else:
                        st.success("✅ Calidad buena. Disfruta el aire libre.")

        st.markdown("---")

        # ----------------------------------------------------------------------------
        # 4. SECCIÓN LAGO DE CHAPALA
        # ----------------------------------------------------------------------------
        st.markdown("#### 💧 Nivel del Lago de Chapala")
        
        chapala_data = get_cached_chapala_level()
        water_history = get_cached_water_history()
        
        c_col1, c_col2 = st.columns([1, 2])
        
        with c_col1:
            st.metric(
                "Cota Actual (msnm)", 
                f"{chapala_data.get('level_msnm', 0):.2f}",
                help="Fuente: CEA Jalisco"
            )
            st.caption(f"Actualizado: {chapala_data.get('last_update')}")
        
        with c_col2:
            chart = EnvironmentVisualizations.plot_water_levels(water_history)
            st.plotly_chart(chart, width='stretch')

        st.markdown("---")

        # ----------------------------------------------------------------------------
        # 5. SECCIÓN NOTICIAS AMBIENTALES
        # ----------------------------------------------------------------------------
        st.markdown("#### 🌍 Noticias Ambientales ZMG (Filtradas con IA)")
        
        use_ai_news = st.checkbox("✨ Usar IA para resumir noticias", value=True, key="env_ai_check")
        
        with st.spinner("Analizando noticias..."):
            env_news = get_cached_env_news_data(use_ai=use_ai_news)
            
        if env_news:
            for news in env_news:
                with st.expander(f"{'🤖 ' if news.get('processed') else '📰 '} {news['title']}"):
                    st.write(f"**Resumen:** {news.get('ai_summary', news['description'])}")
                    st.caption(f"Fuente: {news['source']} | [Leer original]({news['link']})")
        else:
            st.info("No hay noticias ambientales recientes.")

    except Exception as e:
        st.error(f"Error cargando módulo ambiental: {e}")

# Pestaña 2: Chivas
with tab2:
    st.markdown("### 🐐 Chivas de Guadalajara")
    st.markdown("---")
    
    # Información sobre el procesamiento de noticias
    st.info("📰 Las noticias son procesadas por IA (Google AI Studio/Gemini) para eliminar sensacionalismo y clickbait. Se requiere configuración de GOOGLE_AI_API_KEY.")
    
    # Cachear noticias para evitar múltiples requests
    @st.cache_data(ttl=1800)  # Cache por 30 minutos
    def get_cached_chivas_news(use_ai: bool = True):
        """Obtiene noticias de Chivas con caché"""
        return get_chivas_news(max_items=5, use_ai=use_ai)
    
    # Checkbox para habilitar/deshabilitar IA
    use_ai = st.checkbox("✨ Usar IA para filtrar noticias", value=True, help="Si está desactivado, se mostrarán las noticias originales sin procesar")
    
    # Obtener noticias
    try:
        with st.spinner("Obteniendo y procesando noticias de Chivas..."):
            news_list = get_cached_chivas_news(use_ai=use_ai)
        
        if not news_list:
            st.warning("⚠️ No se encontraron noticias recientes de Chivas.")
        else:
            st.markdown(f"#### 📰 Últimas {len(news_list)} Noticias")
            st.markdown("---")
            
            for idx, news in enumerate(news_list, 1):
                # Contenedor para cada noticia
                with st.container():
                    # Encabezado de la noticia
                    col1, col2 = st.columns([1, 20])
                    
                    with col1:
                        # Ícono fijo de noticia
                        st.markdown("📰")
                    
                    with col2:
                        # Título original (tachado o pequeño)
                        if news.get('processed', False):
                            st.markdown(f"<small><s>{news.get('title', 'Sin título')}</s></small>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<small>{news.get('title', 'Sin título')}</small>", unsafe_allow_html=True)
                    
                    # Resumen generado por IA (en negritas)
                    if news.get('processed', False) and news.get('ai_summary'):
                        st.markdown(f"**Resumen:** {news.get('ai_summary', '')}", unsafe_allow_html=True)
                    else:
                        # Si no se procesó con IA, mostrar descripción original
                        st.markdown(f"**Descripción:** {news.get('description', 'Sin descripción')[:200]}...")
                        if news.get('error'):
                            st.caption(f"⚠️ Error al procesar: {news.get('error')}")
                    
                    # Información adicional
                    info_col1, info_col2, info_col3 = st.columns(3)
                    
                    with info_col1:
                        if news.get('source'):
                            st.caption(f"📰 {news.get('source', 'Fuente desconocida')}")
                    
                    with info_col2:
                        if news.get('published'):
                            st.caption(f"📅 {news.get('published', '')}")
                    
                    with info_col3:
                        if news.get('link'):
                            st.markdown(f"[🔗 Leer más]({news.get('link', '')})", unsafe_allow_html=True)
                    
                    # Separador entre noticias
                    if idx < len(news_list):
                        st.markdown("---")
            
            # Información sobre el procesamiento
            if use_ai:
                processed_count = sum(1 for news in news_list if news.get('processed', False))
                
                st.markdown("---")
                st.caption(f"📊 Estadísticas: {processed_count}/{len(news_list)} noticias procesadas con IA")
        
    except Exception as e:
        st.error(f"❌ Error al obtener noticias: {str(e)}")
        st.info("💡 Asegúrate de tener configurada la variable de entorno GOOGLE_AI_API_KEY si deseas usar el procesamiento con IA.")
        
        # Mostrar instrucciones para configurar API key
        with st.expander("ℹ️ ¿Cómo configurar GOOGLE_AI_API_KEY?"):
            st.markdown("""
            Para usar el procesamiento de noticias con IA, necesitas configurar tu API key de Google AI Studio:
            
            1. Obtén tu API key en: https://aistudio.google.com/app/apikey
            2. Configura la variable de entorno:
               - **Windows (PowerShell):** `$env:GOOGLE_AI_API_KEY="tu-api-key"`
               - **Linux/Mac:** `export GOOGLE_AI_API_KEY="tu-api-key"`
            3. O crea un archivo `.env` en la raíz del proyecto con:
               ```
               GOOGLE_AI_API_KEY=tu-api-key
               ```
            
            También puedes usar `GEMINI_API_KEY` como nombre alternativo.
            
            Sin la API key, las noticias se mostrarán sin procesar.
            """)

