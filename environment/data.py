"""
Módulo mejorado para scraping y procesamiento de datos ambientales de la ZMG:
- Calidad del aire (IMECA) por estaciones desde aire.jalisco.gob.mx
- Niveles del Lago de Chapala (cota) desde CEA Jalisco
- Noticias de medio ambiente para la ZMG, resumidas con IA (Gemini)
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import logging
from typing import Dict, Optional, Tuple, List
import time
import re
import feedparser
import google.generativeai as genai
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
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

class Config:
    AIR_QUALITY_URL = "https://aire.jalisco.gob.mx/"
    CHAPALA_LEVEL_URL = "https://www.ceajalisco.gob.mx/contenido/chapala/chapala/cota.html"
    REQUEST_TIMEOUT = 10
    MAX_RETRIES = 3
    RETRY_DELAY = 2  
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    # Colores para mapa y gráficas
    COLORS = {
        "Buena": "#00E400",       # Verde
        "Regular": "#FFFF00",     # Amarillo
        "Mala": "#FF7E00",        # Naranja
        "Muy Mala": "#FF0000",    # Rojo
        "Extremadamente Mala": "#7E0023" # Morado
    }

# Coordenadas aproximadas de estaciones de monitoreo de la ZMG
STATION_COORDS: Dict[str, Dict[str, float]] = {
    "Las Pintas": {"lat": 20.5768, "lon": -103.3265},
    "Centro": {"lat": 20.6736, "lon": -103.3440},
    "Miravalle": {"lat": 20.6120, "lon": -103.3430},
    "Tlaquepaque": {"lat": 20.6409, "lon": -103.3125},
    "Vallarta": {"lat": 20.6775, "lon": -103.4323},
    "Oblatos": {"lat": 20.6923, "lon": -103.2974},
    "Águilas": {"lat": 20.6350, "lon": -103.4150},
    "Loma Dorada": {"lat": 20.6280, "lon": -103.2530},
    "Santa Fe": {"lat": 20.5310, "lon": -103.3830}
}

# ============================================================================
# CONFIGURACIÓN GOOGLE AI (GEMINI)
# ============================================================================

_ENV_GEMINI_API_KEY = (
    os.getenv("GOOGLE_API_KEY")
    or os.getenv("GOOGLE_AI_API_KEY")
    or os.getenv("GEMINI_API_KEY")
)

if _ENV_GEMINI_API_KEY:
    try:
        genai.configure(api_key=_ENV_GEMINI_API_KEY)
    except Exception as _e:
        logger.error(f"Error configurando Google AI (env): {_e}")
else:
    logger.warning("No se encontró API KEY para Gemini.")


# ============================================================================
# SCRAPER DE CALIDAD DEL AIRE
# ============================================================================

class AirQualityScraper:
    def __init__(self):
        self.url = Config.AIR_QUALITY_URL
        self.headers = {"User-Agent": Config.USER_AGENT}

    def _determine_status(self, imeca: float) -> str:
        if imeca <= 50: return "Buena"
        elif imeca <= 100: return "Regular"
        elif imeca <= 150: return "Mala"
        elif imeca <= 200: return "Muy Mala"
        else: return "Extremadamente Mala"

    def _generate_mock_stations(self) -> List[Dict]:
        """Genera datos simulados para todas las estaciones configuradas"""
        stations = []
        for name, coords in STATION_COORDS.items():
            # Las Pintas y Miravalle suelen tener valores más altos
            base = 90 if name in ["Las Pintas", "Miravalle"] else 45
            imeca = int(np.random.normal(base, 15))
            imeca = max(10, min(200, imeca)) # Clip entre 10 y 200
            
            stations.append({
                "station": name,
                "imeca": imeca,
                "status": self._determine_status(imeca),
                "lat": coords["lat"],
                "lon": coords["lon"],
                "last_update": datetime.now().strftime("%H:%M"),
                "source": "mock"
            })
        return stations

    def scrape_all_stations(self, use_mock_on_error: bool = True) -> List[Dict]:
        """Obtiene lista de estaciones con IMECA y Coordenadas"""
        try:
            resp = requests.get(self.url, headers=self.headers, timeout=Config.REQUEST_TIMEOUT)
            
            if resp.status_code != 200:
                raise Exception(f"Status code {resp.status_code}")
                
            soup = BeautifulSoup(resp.content, "html.parser")
            page_text = soup.get_text(" ", strip=True)
            
            # Buscamos patrones: "105 puntos IMECA en Las Pintas"
            # Ajustamos regex para ser flexible con espacios y mayúsculas
            station_pattern = r"(?:registrado|nivel|de)\s+(\d{1,3})\s*puntos?\s*IMECA\s+en\s+([A-Za-zÁÉÍÓÚÑñ\s]+)"
            matches = re.findall(station_pattern, page_text, flags=re.IGNORECASE)
            
            found_stations = []
            
            for imeca_str, station_raw in matches:
                try:
                    val = int(imeca_str)
                    # Limpieza de nombre
                    name_clean = station_raw.strip()
                    # Mapeo simple para encontrar coordenadas
                    matched_coords = None
                    
                    for key, coords in STATION_COORDS.items():
                        if key.lower() in name_clean.lower():
                            name_clean = key # Usamos el nombre oficial
                            matched_coords = coords
                            break
                    
                    if matched_coords:
                        found_stations.append({
                            "station": name_clean,
                            "imeca": val,
                            "status": self._determine_status(val),
                            "lat": matched_coords["lat"],
                            "lon": matched_coords["lon"],
                            "last_update": datetime.now().strftime("%H:%M"),
                            "source": "real"
                        })
                except ValueError:
                    continue
            
            if not found_stations:
                logger.warning("No se encontraron estaciones con Regex, usando mock.")
                if use_mock_on_error: return self._generate_mock_stations()
                return []
                
            return found_stations

        except Exception as e:
            logger.error(f"Error scraping estaciones: {e}")
            if use_mock_on_error: return self._generate_mock_stations()
            return []

# ============================================================================
# DATOS DE AGUA (CHAPALA)
# ============================================================================

def get_chapala_level_real(use_mock_on_error: bool = True) -> Dict:
    url = Config.CHAPALA_LEVEL_URL
    try:
        resp = requests.get(url, headers={"User-Agent": Config.USER_AGENT}, timeout=Config.REQUEST_TIMEOUT)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser")
            text = soup.get_text()
            # Patrón para buscar cota: "94.56"
            match = re.search(r"(\d{2}\.\d{2})", text)
            if match:
                return {
                    "level_msnm": float(match.group(1)),
                    "unit": "msnm",
                    "last_update": datetime.now().strftime("%H:%M"),
                    "source": "real"
                }
    except Exception as e:
        logger.error(f"Error Chapala: {e}")
    
    # Fallback Mock
    return {
        "level_msnm": 94.50,
        "unit": "msnm",
        "last_update": datetime.now().strftime("%H:%M"),
        "source": "mock"
    }

def get_water_levels_history_mock(days: int = 180) -> pd.DataFrame:
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    base = 60.0
    trend = np.linspace(-5, 8, days)
    noise = np.random.normal(0, 0.2, days)
    levels = np.clip(base + trend + noise, 0, 100)
    return pd.DataFrame({"Fecha": dates, "Nivel (%)": levels})


# ============================================================================
# VISUALIZACIÓN (MAPA Y GRÁFICAS)
# ============================================================================

class EnvironmentVisualizations:
    
    @staticmethod
    def plot_zmg_map(stations_data: List[Dict]) -> go.Figure:
        """
        Genera el mapa de puntos IMECA para la ZMG usando Plotly Mapbox.
        """
        if not stations_data:
            return go.Figure()
            
        df = pd.DataFrame(stations_data)
        
        # Tamaño del punto basado en contaminación
        df['size'] = df['imeca'].apply(lambda x: 12 + (x/10))
        
        fig = px.scatter_mapbox(
            df,
            lat="lat",
            lon="lon",
            color="status",
            size="size",
            hover_name="station",
            hover_data={"imeca": True, "lat": False, "lon": False, "size": False},
            color_discrete_map=Config.COLORS,
            zoom=10,
            center={"lat": 20.6597, "lon": -103.3496}, # Centro GDL
            mapbox_style="carto-positron",
            title="Monitoreo de Calidad del Aire ZMG"
        )
        fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0}, height=450)
        return fig

    @staticmethod
    def plot_imeca_gauge(imeca_value: int, status: str) -> go.Figure:
        color = Config.COLORS.get(status, "gray")
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = imeca_value,
            title = {'text': f"Calidad: {status}"},
            gauge = {
                'axis': {'range': [None, 200]},
                'bar': {'color': color},
                'steps': [
                    {'range': [0, 50], 'color': "#00E400"}, # Verde
                    {'range': [50, 100], 'color': "#FFFF00"}, # Amarillo
                    {'range': [100, 150], 'color': "#FF7E00"}, # Naranja
                    {'range': [150, 200], 'color': "#FF0000"}  # Rojo
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'thickness': 0.75,
                    'value': imeca_value
                }
            }
        ))
        fig.update_layout(height=250, margin={'t':0,'b':0})
        return fig

    @staticmethod
    def plot_water_levels(df: pd.DataFrame) -> go.Figure:
        fig = px.line(
            df, x="Fecha", y="Nivel (%)", 
            title="Histórico Nivel Lago Chapala (Simulado)",
            labels={"Nivel (%)": "Capacidad (%)"},
            template="plotly_white"
        )
        fig.update_traces(line_color='#00CC96', line_width=3)
        fig.add_hrect(y0=0, y1=40, line_width=0, fillcolor="red", opacity=0.1, annotation_text="Crítico")
        fig.update_layout(height=350)
        return fig


# ============================================================================
# NOTICIAS AMBIENTALES + IA
# ============================================================================

class EnvNewsConfig:
    RSS_URL = "https://news.google.com/rss/search?q=Medio+ambiente+Zona+Metropolitana+de+Guadalajara&hl=es&gl=MX&ceid=MX:es"
    MAX_NEWS = 5

def resumir_noticia_medio_ambiente_con_ia(titulo: str, descripcion: str) -> str:
    """Resumen usando Gemini 1.5 Flash (Más estable)"""
    if not _ENV_GEMINI_API_KEY:
        return descripcion[:200] + "..."

    prompt = f"""Actúa como analista ambiental. Resume esta noticia de GDL en 1 frase clara:
    Título: {titulo}
    Texto: {descripcion}"""

    try:    
        # Usamos 2.5-flash-lite
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        # Fallback a 2.5-flash si 2.5-flash-lite falla
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            return response.text.strip()
        except:
            logger.error("Error con gemini-2.5-flash para noticia ambiental.")
            return descripcion[:200] + "..."

def get_env_news(max_items: int = 5, use_ai: bool = True) -> List[Dict]:
    try:
        feed = feedparser.parse(EnvNewsConfig.RSS_URL)
        news_list = []
        for entry in feed.entries[:max_items]:
            desc = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()
            item = {
                "title": entry.get("title", ""),
                "description": desc,
                "link": entry.get("link", ""),
                "source": entry.get("source", {}).get("title", "Google News")
            }
            
            if use_ai:
                item["ai_summary"] = resumir_noticia_medio_ambiente_con_ia(item["title"], desc)
                item["processed"] = True
            else:
                item["ai_summary"] = desc
                item["processed"] = False
                
            news_list.append(item)
        return news_list
    except Exception as e:
        logger.error(f"Error noticias RSS: {e}")
        return []

# ============================================================================
# INTERFAZ PÚBLICA (EXPORTS)
# ============================================================================

def get_air_quality_zmg_stations(use_mock_on_error: bool = True) -> List[Dict]:
    scraper = AirQualityScraper()
    return scraper.scrape_all_stations(use_mock_on_error)

def get_air_quality_zmg(use_mock_on_error: bool = True) -> Dict:
    # Retorna la peor estación para el KPI general
    stations = get_air_quality_zmg_stations(use_mock_on_error)
    if stations:
        # Ordenar por IMECA descendente
        worst = sorted(stations, key=lambda x: x['imeca'], reverse=True)[0]
        return worst
    return {}

def plot_water_levels(df):
    """Wrapper para compatibilidad con imports antiguos"""
    return EnvironmentVisualizations.plot_water_levels(df)

def get_chapala_level(use_mock_on_error: bool = True) -> Dict:
    """Wrapper para compatibilidad con nombre antiguo"""
    return get_chapala_level_real(use_mock_on_error)