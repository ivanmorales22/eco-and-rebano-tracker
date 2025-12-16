"""
GDL_Insight - Dashboard de Streamlit
Dashboard para monitorear noticias sobre el Medio Ambiente en la ZMG y Chivas de Guadalajara
"""

import streamlit as st

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
    st.markdown("### 🌱 Medio Ambiente")
    st.markdown("---")
    st.write("Hola Mundo")

# Pestaña 2: Chivas
with tab2:
    st.markdown("### 🐐 Chivas de Guadalajara")
    st.markdown("---")
    st.write("Hola Mundo")

