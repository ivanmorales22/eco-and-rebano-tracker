"""
Módulo para obtener y procesar noticias de Chivas de Guadalajara
Utiliza feedparser para RSS y Google AI Studio (Gemini) para filtrar sensacionalismo
"""

import feedparser
import google.generativeai as genai
from typing import List, Dict, Optional
import logging
from datetime import datetime
import os
import re

# Intentar cargar variables de entorno desde archivo .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv no está instalado, continuar sin él
    pass

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

class ChivasConfig:
    """Configuración para el módulo de noticias de Chivas"""
    # URL del RSS feed de Google News para Chivas
    RSS_URL = "https://news.google.com/rss/search?q=Chivas+Guadalajara&hl=es&gl=MX&ceid=MX:es"
    
    # Número de noticias a obtener
    MAX_NEWS = 5


# ============================================================================
# CONFIGURAR GOOGLE AI (GEMINI)
# ============================================================================

# Asegúrate de tener tu API KEY configurada en alguna de estas variables:
# - GOOGLE_API_KEY (recomendado, como en Google AI Studio)
# - GOOGLE_AI_API_KEY
# - GEMINI_API_KEY
_api_key = (
    os.getenv("GOOGLE_API_KEY")
    or os.getenv("GOOGLE_AI_API_KEY")
    or os.getenv("GEMINI_API_KEY")
)
if _api_key:
    try:
        genai.configure(api_key=_api_key)
    except Exception as _e:
        logger.error(f"Error configurando Google AI: {_e}")
else:
    logger.warning(
        "No se encontró GOOGLE_API_KEY / GOOGLE_AI_API_KEY / GEMINI_API_KEY en variables de entorno"
    )


# ============================================================================
# FUNCIÓN PRINCIPAL DE RESUMEN CON IA (SEGÚN ESPECIFICACIÓN DEL USUARIO)
# ============================================================================

def resumir_noticia_con_ia(titulo: str, descripcion: str) -> str:
    """
    Usa Gemini para resumir una noticia de Chivas eliminando sensacionalismo y clickbait.
    Intenta primero con gemini-1.5-flash (o 2.5-flash), y si falla, hace fallback a gemini-pro.
    """
    # Prompt según la especificación del usuario
    prompt = f"""
Actúa como un analista deportivo objetivo.
Analiza esta noticia sobre Chivas:
Título: {titulo}
Descripción: {descripcion}

Tu tarea:
1. Elimina el clickbait y el sensacionalismo.
2. Resume la noticia en una o dos frases concisas, con la información más importante.
""".strip()

    # Intento 1: modelo rápido (flash)
    try:
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
        response = model.generate_content(prompt)
        return (response.text or "").strip()
    except Exception as e:
        logger.error(f"Error con modelo flash, intentando con gemini-2.5-flash: {e}")

    # Fallback: gemini-2.5-flash
    try:
        model_backup = genai.GenerativeModel("gemini-2.5-flash")
        response = model_backup.generate_content(prompt)
        return (response.text or "").strip()
    except Exception as e2:
        logger.error(f"Error con gemini-2.5-flash al resumir noticia: {e2}")
        return f"Error resumiendo noticia: {e2}"


# ============================================================================
# OBTENCIÓN DE NOTICIAS RSS
# ============================================================================

def get_chivas_news_rss(max_items: int = None) -> List[Dict]:
    """
    Obtiene las últimas noticias de Chivas desde Google News RSS.
    
    Args:
        max_items: Número máximo de noticias a obtener (default: ChivasConfig.MAX_NEWS)
        
    Returns:
        Lista de diccionarios con información de noticias
    """
    max_items = max_items or ChivasConfig.MAX_NEWS
    
    try:
        logger.info(f"Obteniendo noticias de Chivas desde RSS: {ChivasConfig.RSS_URL}")
        feed = feedparser.parse(ChivasConfig.RSS_URL)
        
        if feed.bozo:
            logger.warning(f"Error parseando RSS feed: {feed.bozo_exception}")
        
        news_list = []
        
        for entry in feed.entries[:max_items]:
            # Limpiar HTML de la descripción si existe
            description = entry.get('summary', entry.get('description', ''))
            # Remover tags HTML básicos
            description = re.sub(r'<[^>]+>', '', description)
            description = description.strip()
            
            news_item = {
                'title': entry.get('title', 'Sin título'),
                'description': description,
                'link': entry.get('link', ''),
                'published': entry.get('published', ''),
                'source': entry.get('source', {}).get('title', 'Fuente desconocida') if hasattr(entry, 'source') else 'Fuente desconocida'
            }
            news_list.append(news_item)
        
        logger.info(f"Se obtuvieron {len(news_list)} noticias de Chivas")
        return news_list
        
    except Exception as e:
        logger.error(f"Error obteniendo noticias RSS: {e}")
        return []


# ============================================================================
# PROCESAMIENTO CON GOOGLE AI (GEMINI)
# ============================================================================

def process_news_with_ai(news_item: Dict) -> Dict:
    """
    Procesa una noticia con Google AI (Gemini) para eliminar sensacionalismo y generar
    un resumen conciso (1–2 frases) con la información más importante.
    Usa internamente la función `resumir_noticia_con_ia`.
    """
    try:
        resumen = resumir_noticia_con_ia(
            news_item.get("title", ""),
            news_item.get("description", ""),
        )

        return {
            **news_item,
            "ai_summary": resumen,
            "is_rumor": False,
            "processed": True,
            "error": None,
        }
    except Exception as e:
        logger.error(f"Error procesando noticia con IA: {e}")
        return {
            **news_item,
            "ai_summary": news_item.get("description", "")[:200] + "...",
            "is_rumor": False,
            "processed": False,
            "error": str(e),
        }


def process_all_news(news_list: List[Dict], use_ai: bool = True) -> List[Dict]:
    """
    Procesa todas las noticias con IA.
    
    Args:
        news_list: Lista de noticias a procesar
        use_ai: Si True, usa Google AI para procesar. Si False, retorna noticias sin procesar.
        
    Returns:
        Lista de noticias procesadas
    """
    if not use_ai:
        logger.info("Procesamiento con IA deshabilitado")
        return [
            {
                **news,
                "ai_summary": news.get("description", ""),
                "is_rumor": False,
                "processed": False,
            }
            for news in news_list
        ]

    processed_news = []

    for news in news_list:
        processed = process_news_with_ai(news)
        processed_news.append(processed)

    return processed_news


# ============================================================================
# FUNCIONES DE INTERFAZ
# ============================================================================

def get_chivas_news(max_items: int = None, use_ai: bool = True) -> List[Dict]:
    """
    Función principal para obtener y procesar noticias de Chivas.
    
    Args:
        max_items: Número máximo de noticias a obtener
        use_ai: Si True, procesa las noticias con IA
        
    Returns:
        Lista de noticias procesadas
    """
    # Obtener noticias del RSS
    news_list = get_chivas_news_rss(max_items=max_items)
    
    if not news_list:
        logger.warning("No se obtuvieron noticias del RSS")
        return []
    
    # Procesar con IA si está habilitado
    if use_ai:
        processed_news = process_all_news(news_list, use_ai=True)
    else:
        processed_news = news_list
    
    return processed_news