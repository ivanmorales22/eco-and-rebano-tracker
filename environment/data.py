"""
Módulo de datos ambientales ZMG mejorado (13 Estaciones + Chapala + Noticias)
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import logging
from typing import Dict, List
import re
import feedparser
import google.generativeai as genai
import os
from utils import load_daily_cache, save_daily_cache

ENV_CACHE_FILE = "cache_env_news.json"

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Config:
    AIR_QUALITY_URL = "https://aire.jalisco.gob.mx/"
    CHAPALA_LEVEL_URL = "https://www.ceajalisco.gob.mx/contenido/chapala/chapala/cota.html"
    REQUEST_TIMEOUT = 10
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    COLORS = {
        "Buena": "#00E400",       # Verde
        "Regular": "#FFFF00",     # Amarillo
        "Mala": "#FF7E00",        # Naranja
        "Muy Mala": "#FF0000",    # Rojo
        "Extremadamente Mala": "#7E0023" # Morado
    }

# ============================================================================
# 1. COORDENADAS COMPLETAS (13 ESTACIONES ZMG)
# ============================================================================
# Nota: "Vallarta" se refiere a la estación Vallarta en GDL (cerca de Los Cubos/Gran Plaza), no al puerto.

STATION_COORDS: Dict[str, Dict[str, float]] = {
    "Las Pintas":      {"lat": 20.5768, "lon": -103.3265},
    "Miravalle":       {"lat": 20.6120, "lon": -103.3430},
    "Centro":          {"lat": 20.6736, "lon": -103.3440},
    "Tlaquepaque":     {"lat": 20.6409, "lon": -103.3125},
    "Vallarta":        {"lat": 20.6775, "lon": -103.4323}, # Av. Vallarta GDL
    "Oblatos":         {"lat": 20.6923, "lon": -103.2974},
    "Aguilas":         {"lat": 20.6350, "lon": -103.4150},
    "Loma Dorada":     {"lat": 20.6280, "lon": -103.2530},
    "Santa Fe":        {"lat": 20.5310, "lon": -103.3830}, # Tlajomulco
    "Santa Anita":     {"lat": 20.5515, "lon": -103.4470},
    "Atemajac":        {"lat": 20.7160, "lon": -103.3560},
    "Santa Margarita": {"lat": 20.7300, "lon": -103.4150}, # Zapopan Norte
    "Country":         {"lat": 20.6950, "lon": -103.3750}  # Zona Country Club
}

# ============================================================================
# 2. CONFIGURACIÓN IA
# ============================================================================
_ENV_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if _ENV_GEMINI_API_KEY:
    try:
        genai.configure(api_key=_ENV_GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Error AI Config: {e}")

# ============================================================================
# 3. SCRAPER CALIDAD DEL AIRE
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
        """
        Genera datos simulados para TODAS las 13 estaciones.
        Garantiza que el mapa siempre se vea lleno.
        """
        stations = []
        for name, coords in STATION_COORDS.items():
            # Simulamos realidad: Sur (Pintas, Miravalle, Santa Fe) suele estar peor
            if name in ["Las Pintas", "Miravalle", "Santa Fe", "Tlaquepaque"]:
                base = 105 # Mala
                std = 15
            elif name in ["Vallarta", "Country", "Santa Margarita"]:
                base = 45  # Buena
                std = 10
            else:
                base = 70  # Regular
                std = 20
                
            imeca = int(np.random.normal(base, std))
            imeca = max(10, min(190, imeca))
            
            stations.append({
                "station": name,
                "imeca": imeca,
                "status": self._determine_status(imeca),
                "lat": coords["lat"],
                "lon": coords["lon"],
                "last_update": datetime.now().strftime("%H:%M"),
                "source": "mock" # Indica que es simulado
            })
        return stations

    def scrape_all_stations(self, use_mock_on_error: bool = True) -> List[Dict]:
        """
        Intenta obtener datos reales. Si falla o encuentra muy pocos, rellena con Mock.
        """
        found_stations = []
        try:
            resp = requests.get(self.url, headers=self.headers, timeout=Config.REQUEST_TIMEOUT)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "html.parser")
                page_text = soup.get_text(" ", strip=True)
                
                # Buscamos en el texto de la página por CADA estación conocida
                for official_name, coords in STATION_COORDS.items():
                    # Regex busca el nombre de la estación y un número cercano (IMECA)
                    # Ej: "Las Pintas 105" o "105 puntos en Las Pintas"
                    # Usamos un rango de búsqueda laxo
                    pattern = re.compile(
                        rf"{official_name}.{{0,30}}?(\d{{1,3}})|(\d{{1,3}}).{{0,30}}?{official_name}", 
                        re.IGNORECASE
                    )
                    match = pattern.search(page_text)
                    
                    if match:
                        # Extraer el grupo que no sea None
                        val_str = match.group(1) or match.group(2)
                        try:
                            val = int(val_str)
                            if 0 <= val <= 300: # Validación básica de rango
                                found_stations.append({
                                    "station": official_name,
                                    "imeca": val,
                                    "status": self._determine_status(val),
                                    "lat": coords["lat"],
                                    "lon": coords["lon"],
                                    "last_update": datetime.now().strftime("%H:%M"),
                                    "source": "real"
                                })
                        except ValueError:
                            pass
        except Exception as e:
            logger.error(f"Error scraping: {e}")

        # Si encontramos pocas estaciones (menos de 5), asumimos que el scraper falló 
        # (o el sitio cambió) y usamos el Mock para que el mapa no se vea vacío.
        if len(found_stations) < 5 and use_mock_on_error:
            logger.warning("Scraping insuficiente, usando datos simulados completos.")
            return self._generate_mock_stations()
            
        return found_stations

# ============================================================================
# 4. DATOS CHAPALA + NOTICIAS (Sin cambios mayores)
# ============================================================================

def get_chapala_level_real(use_mock_on_error: bool = True) -> Dict:
    # Intenta scraping real, fallback a mock
    try:
        resp = requests.get(Config.CHAPALA_LEVEL_URL, headers={"User-Agent": Config.USER_AGENT}, timeout=5)
        if resp.status_code == 200:
            match = re.search(r"(\d{2}\.\d{2})", resp.text)
            if match:
                return {"level_msnm": float(match.group(1)), "unit": "msnm", "last_update": datetime.now().strftime("%H:%M"), "source": "real"}
    except: pass
    return {"level_msnm": 94.50, "unit": "msnm", "last_update": datetime.now().strftime("%H:%M"), "source": "mock"}

def get_water_levels_history_mock(days: int = 180) -> pd.DataFrame:
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    levels = np.clip(60.0 + np.linspace(-5, 8, days) + np.random.normal(0, 0.2, days), 0, 100)
    return pd.DataFrame({"Fecha": dates, "Nivel (%)": levels})

class EnvNewsConfig:
    RSS_URL = "https://news.google.com/rss/search?q=Medio+ambiente+Guadalajara&hl=es&gl=MX&ceid=MX:es"

def resumir_noticia_medio_ambiente_con_ia(titulo: str, descripcion: str) -> str:
    """Resumen usando Gemini 2.5 Flash"""
    # Si no hay API Key, devolvemos el texto original cortado
    if not _ENV_GEMINI_API_KEY:
        return (descripcion[:200] + "...") if descripcion else "Sin descripción"

    prompt = f"""Actúa como analista ambiental. Resume esta noticia de GDL en 1 frase clara y un parrafo conciso para analizar el contenido:
    Título: {titulo}
    Texto: {descripcion}"""

    try:
        # Usamos 2.5-flash 
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error Gemini: {e}")
        # Fallback simple si falla la IA
        return (descripcion[:200] + "...") if descripcion else "Sin descripción"

def get_env_news(max_items: int = 5, use_ai: bool = True) -> List[Dict]:
    # 1. Intentar cargar del JSON local primero
    cached_news = load_daily_cache(ENV_CACHE_FILE)
    if cached_news:
        return cached_news

    # 2. Fetch con Requests (Para evitar bloqueo de Google)
    try:
        # Usamos requests para simular un navegador real
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(EnvNewsConfig.RSS_URL, headers=headers, timeout=10)
        
        # Le pasamos el contenido XML crudo a feedparser
        feed = feedparser.parse(response.content)
        
        news = []
        for entry in feed.entries[:max_items]:
            desc = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()
            
            item = {
                "title": entry.get("title", "Sin título"),
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
                
            news.append(item)
        
        # 3. Guardar en JSON solo si encontramos algo
        if news:
            save_daily_cache(ENV_CACHE_FILE, news)
        else:
            logger.warning("Google News devolvió una lista vacía.")
            
        return news

    except Exception as e:
        logger.error(f"Error descargando noticias RSS: {e}")
        return []
# ============================================================================
# 5. VISUALIZACIONES & WRAPPERS
# ============================================================================

class EnvironmentVisualizations:
    @staticmethod
    def plot_zmg_map(stations_data: List[Dict]) -> go.Figure:
        if not stations_data: return go.Figure()
        df = pd.DataFrame(stations_data)
        df['size'] = df['imeca'].apply(lambda x: 15 + (x/8)) # Puntos visibles
        
        fig = px.scatter_mapbox(
            df, lat="lat", lon="lon", color="status", size="size",
            hover_name="station", hover_data={"imeca": True, "lat": False, "lon": False, "size": False},
            color_discrete_map=Config.COLORS,
            zoom=10.5, center={"lat": 20.65, "lon": -103.35},
            mapbox_style="carto-positron", title="Red de Monitoreo Atmosférico ZMG"
        )
        fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0}, height=500)
        return fig

    @staticmethod
    def plot_imeca_gauge(imeca_value: int, status: str) -> go.Figure:
        color = Config.COLORS.get(status, "gray")
        fig = go.Figure(go.Indicator(
            mode = "gauge+number", value = imeca_value,
            title = {'text': f"Calidad: {status}"},
            gauge = {
                'axis': {'range': [None, 200]}, 'bar': {'color': color},
                'steps': [{'range': [0, 50], 'color': "#00E400"}, {'range': [50, 100], 'color': "#FFFF00"},
                          {'range': [100, 150], 'color': "#FF7E00"}, {'range': [150, 200], 'color': "#FF0000"}],
                'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': imeca_value}
            }
        ))
        fig.update_layout(height=300, margin={'t':0,'b':0})
        return fig
    
    @staticmethod
    def plot_water_levels(df):
        fig = px.line(df, x="Fecha", y="Nivel (%)", title="Nivel Chapala (Simulado)", template="plotly_white")
        fig.add_hrect(y0=0, y1=40, line_width=0, fillcolor="red", opacity=0.1)
        return fig

# Wrappers para compatibilidad con app.py
def get_air_quality_zmg_stations(use_mock_on_error: bool = True) -> List[Dict]:
    scraper = AirQualityScraper()
    return scraper.scrape_all_stations(use_mock_on_error)

def get_air_quality_zmg(use_mock_on_error: bool = True) -> Dict:
    s = get_air_quality_zmg_stations(use_mock_on_error)
    return sorted(s, key=lambda x: x['imeca'], reverse=True)[0] if s else {}

def plot_water_levels(df): return EnvironmentVisualizations.plot_water_levels(df)
def get_chapala_level(use_mock_on_error=True): return get_chapala_level_real(use_mock_on_error)