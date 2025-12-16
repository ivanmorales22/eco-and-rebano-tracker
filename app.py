"""
GDL_Insight - Dashboard de Streamlit
Dashboard para monitorear noticias sobre el Medio Ambiente en la ZMG y Chivas de Guadalajara
"""

import streamlit as st
import pandas as pd
from environment.data import (
    get_air_quality_zmg,
    get_air_quality_zmg_stations,
    get_water_levels_history_mock,
    plot_water_levels,
    EnvironmentVisualizations,
    get_chapala_level,
    get_env_news,
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
    st.markdown("### 🌱 Medio Ambiente - Zona Metropolitana de Guadalajara")
    st.markdown("---")
    
    # Cachear datos para evitar múltiples requests
    @st.cache_data(ttl=300)  # Cache por 5 minutos
    def get_cached_air_quality():
        """Obtiene datos de calidad del aire con caché"""
        return get_air_quality_zmg(use_mock_on_error=True)
    
    @st.cache_data(ttl=3600)  # Cache por 1 hora (datos históricos)
    def get_cached_water_levels(days=180):
        """Obtiene datos históricos de niveles de agua con caché"""
        return get_water_levels_history_mock(days=days)

    @st.cache_data(ttl=300)  # Cache de cota de Chapala por 5 minutos
    def get_cached_chapala_level():
        """Obtiene la cota actual del Lago de Chapala con caché"""
        return get_chapala_level(use_mock_on_error=True)

    @st.cache_data(ttl=1800)  # Cache de noticias ambientales por 30 minutos
    def get_cached_env_news(use_ai: bool = True):
        """Obtiene noticias de medio ambiente de la ZMG con caché"""
        return get_env_news(max_items=5, use_ai=use_ai)
    
    # Obtener datos
    try:
        with st.spinner("Obteniendo datos de calidad del aire..."):
            air_data = get_cached_air_quality()
        
        # Sección de Calidad del Aire
        st.markdown("#### 🌬️ Calidad del Aire - IMECA")
        
        # Crear columnas para el layout
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Gráfico gauge de IMECA
            imeca_gauge = EnvironmentVisualizations.plot_imeca_gauge(
                air_data['imeca'], 
                air_data['status']
            )
            st.plotly_chart(imeca_gauge, width='stretch')
        
        with col2:
            # Métricas y información
            st.metric(
                label="IMECA Actual",
                value=air_data['imeca'],
                delta=f"Estado: {air_data['status']}"
            )
            
            st.info(f"📍 **Estación:** {air_data['station']}")
            st.info(f"🕐 **Última actualización:** {air_data['last_update']}")
            
            # Indicador de fuente de datos
            if air_data.get('source') == 'mock':
                st.warning("⚠️ Mostrando datos simulados")
            else:
                st.success("✅ Datos en tiempo real")
            
            # Información sobre IMECA
            with st.expander("ℹ️ ¿Qué es el IMECA?"):
                st.markdown("""
                El **Índice Metropolitano de la Calidad del Aire (IMECA)** es un indicador 
                que mide la calidad del aire en la Zona Metropolitana de Guadalajara.
                
                **Escala:**
                - **0-50:** Buena ✅
                - **51-100:** Regular ⚠️
                - **101-150:** Mala 🟠
                - **151-200:** Muy Mala 🔴
                """)
        
        st.markdown("---")
        
        # Sección de Niveles de Agua y Cota de Chapala
        st.markdown("#### 💧 Nivel del Lago de Chapala")

        # Datos de cota actual (tiempo casi real) desde CEA Jalisco
        chapala_col1, chapala_col2 = st.columns([1, 3])
        with chapala_col1:
            with st.spinner("Consultando cota actual del Lago de Chapala..."):
                chapala = get_cached_chapala_level()
            st.metric(
                label="Cota actual (msnm)",
                value=f"{chapala.get('level_msnm', 0):.2f} {chapala.get('unit', '')}",
                help="Cota medida en metros sobre el nivel del mar (fuente: CEA Jalisco)",
            )
            fuente = chapala.get("source", "desconocida")
            st.caption(f"Fuente: CEA Jalisco ({'dato real' if fuente == 'real' else 'valor simulado'})")
            if chapala.get("raw_snippet"):
                with st.expander("Ver fragmento de texto detectado"):
                    st.write(chapala.get("raw_snippet"))

        with chapala_col2:
            # Selector de días históricos (datos simulados)
            days_history = st.selectbox(
                "Histórico estimado de nivel (%) del lago (simulación):",
                options=[90, 180, 365],
                index=1,  # Por defecto 180 días
                format_func=lambda x: f"{x} días ({x//30} meses)",
            )

            # Obtener datos históricos simulados
            with st.spinner(f"Generando datos históricos simulados de {days_history} días..."):
                water_df = get_cached_water_levels(days=days_history)

            # Calcular métricas sobre el porcentaje de llenado simulado
            current_level = float(water_df["Nivel (%)"].iloc[-1])
            previous_level = float(water_df["Nivel (%)"].iloc[-2]) if len(water_df) > 1 else current_level
            delta_level = current_level - previous_level
            min_level = float(water_df["Nivel (%)"].min())
            max_level = float(water_df["Nivel (%)"].max())
            avg_level = float(water_df["Nivel (%)"].mean())

            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

            with metric_col1:
                st.metric(
                    label="Nivel actual (%)",
                    value=f"{current_level:.1f}%",
                    delta=f"{delta_level:+.1f}%",
                )

            with metric_col2:
                st.metric(label="Nivel mínimo", value=f"{min_level:.1f}%")

            with metric_col3:
                st.metric(label="Nivel máximo", value=f"{max_level:.1f}%")

            with metric_col4:
                st.metric(label="Promedio", value=f"{avg_level:.1f}%")

            # Gráfico de niveles simulados
            water_chart = plot_water_levels(water_df)
            st.plotly_chart(water_chart, width="stretch")

        # Información adicional
        with st.expander("ℹ️ Información sobre el Lago de Chapala"):
            st.markdown("""
            El **Lago de Chapala** es el lago más grande de México y una fuente vital 
            de agua para la Zona Metropolitana de Guadalajara.
            
            **Niveles de referencia (orientativos):**
            - **Nivel crítico:** Por debajo del 40% de capacidad
            - **Nivel óptimo:** Entre 60-80% de capacidad
            
            La cota actual se obtiene en tiempo (casi) real desde la [CEA Jalisco](https://www.ceajalisco.gob.mx/contenido/chapala/chapala/cota.html).
            El histórico de porcentaje de llenado mostrado es una simulación para efectos visuales.
            """)

        st.markdown("---")

        # Sección de noticias de medio ambiente (ZMG)
        st.markdown("#### 🌍 Noticias recientes de medio ambiente en la ZMG")

        env_use_ai = st.checkbox(
            "✨ Usar IA para resumir noticias ambientales",
            value=True,
            help="Si está desactivado, se mostrarán las descripciones originales del feed.",
        )

        with st.spinner("Obteniendo y procesando noticias ambientales..."):
            env_news = get_cached_env_news(use_ai=env_use_ai)

        if not env_news:
            st.warning("⚠️ No se encontraron noticias recientes sobre medio ambiente en la ZMG.")
        else:
            st.markdown(f"#### 📰 Últimas {len(env_news)} noticias ambientales")
            st.markdown("---")

            for idx, item in enumerate(env_news, 1):
                with st.container():
                    ncol1, ncol2 = st.columns([1, 20])

                    with ncol1:
                        st.markdown("🌱")

                    with ncol2:
                        st.markdown(f"<small>{item.get('title', 'Sin título')}</small>", unsafe_allow_html=True)

                    if item.get("ai_summary"):
                        st.markdown(f"**Resumen:** {item.get('ai_summary', '')}", unsafe_allow_html=True)
                    else:
                        desc = item.get("description", "Sin descripción")
                        st.markdown(f"**Descripción:** {desc[:200]}{'...' if len(desc) > 200 else ''}")

                    info1, info2, info3 = st.columns(3)
                    with info1:
                        if item.get("source"):
                            st.caption(f"🏙️ {item.get('source', 'Fuente desconocida')}")
                    with info2:
                        if item.get("published"):
                            st.caption(f"📅 {item.get('published', '')}")
                    with info3:
                        link = item.get("link")
                        if link:
                            st.markdown(f"[🔗 Leer más]({link})", unsafe_allow_html=True)

                    if idx < len(env_news):
                        st.markdown("---")
        
    except Exception as e:
        st.error(f"❌ Error al obtener datos: {str(e)}")
        st.info("Por favor, verifica la conexión o intenta más tarde.")

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

