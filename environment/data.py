"""
Módulo mejorado para scraping y procesamiento de datos ambientales de la ZMG:
- Calidad del aire (IMECA) desde aire.jalisco.gob.mx
- Niveles del Lago de Chapala (cota) desde CEA Jalisco
- Noticias de medio ambiente para la ZMG, resumidas con IA (Gemini)
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
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
    # Continuar sin .env si no está disponible
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
    """Configuración centralizada para el módulo."""

    AIR_QUALITY_URL = "https://aire.jalisco.gob.mx/"
    CHAPALA_LEVEL_URL = "https://www.ceajalisco.gob.mx/contenido/chapala/chapala/cota.html"
    REQUEST_TIMEOUT = 10
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # segundos
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    # Rangos IMECA válidos
    IMECA_MIN = 0
    IMECA_MAX = 200
    IMECA_GOOD = 50
    IMECA_BAD = 100

    # Estados válidos
    VALID_STATUSES = ["Buena", "Regular", "Mala", "Muy Mala"]


# Coordenadas aproximadas de estaciones de monitoreo de la ZMG
STATION_COORDS: Dict[str, Dict[str, float]] = {
    "Las Pintas": {"lat": 20.5689, "lon": -103.3064},
    "Centro": {"lat": 20.6744, "lon": -103.3464},
    "Miravalle": {"lat": 20.6325, "lon": -103.3300},
    "Tlaquepaque": {"lat": 20.6400, "lon": -103.3120},
    "Vallarta": {"lat": 20.6736, "lon": -103.3914},
    "Oblatos": {"lat": 20.6786, "lon": -103.2939},
    "Águilas": {"lat": 20.6800, "lon": -103.4300},
}


# ============================================================================
# CONFIGURACIÓN GOOGLE AI (GEMINI) PARA NOTICIAS
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
        logging.getLogger(__name__).error(f"Error configurando Google AI (env): {_e}")
else:
    logging.getLogger(__name__).warning(
        "No se encontró GOOGLE_API_KEY / GOOGLE_AI_API_KEY / GEMINI_API_KEY para noticias ambientales"
    )


# ============================================================================
# VALIDACIÓN DE DATOS
# ============================================================================

def validate_imeca_data(data: Dict) -> Tuple[bool, Optional[str]]:
    """
    Valida que los datos de IMECA tengan el formato correcto.
    
    Args:
        data: Diccionario con datos de IMECA
        
    Returns:
        Tuple (es_válido, mensaje_error)
    """
    if not isinstance(data, dict):
        return False, "Los datos deben ser un diccionario"
    
    if 'imeca' not in data:
        return False, "Falta el campo 'imeca'"
    
    imeca = data['imeca']
    if not isinstance(imeca, (int, float)):
        return False, f"IMECA debe ser numérico, recibido: {type(imeca)}"
    
    if not Config.IMECA_MIN <= imeca <= Config.IMECA_MAX:
        return False, f"IMECA fuera de rango válido ({Config.IMECA_MIN}-{Config.IMECA_MAX})"
    
    if 'status' in data and data['status'] not in Config.VALID_STATUSES:
        logger.warning(f"Estado no estándar: {data['status']}")
    
    return True, None


# ============================================================================
# SCRAPER DE CALIDAD DEL AIRE
# ============================================================================

class AirQualityScraper:
    """Clase para scraping de datos de calidad del aire de la ZMG"""
    
    def __init__(self, url: str = None, timeout: int = None):
        self.url = url or Config.AIR_QUALITY_URL
        self.timeout = timeout or Config.REQUEST_TIMEOUT
        self.headers = {
            "User-Agent": Config.USER_AGENT
        }
    
    def scrape(self, use_mock_on_error: bool = True) -> Dict:
        """
        Realiza el scraping de calidad del aire con reintentos.
        
        Args:
            use_mock_on_error: Si True, retorna datos mock en caso de error
            
        Returns:
            Diccionario con datos de calidad del aire
        """
        for attempt in range(Config.MAX_RETRIES):
            try:
                logger.info(f"Intento {attempt + 1} de scraping de calidad del aire")
                data = self._fetch_data()
                
                # Validar datos
                is_valid, error_msg = validate_imeca_data(data)
                if is_valid:
                    logger.info(f"Datos obtenidos exitosamente: IMECA={data['imeca']}")
                    return data
                else:
                    logger.warning(f"Datos inválidos: {error_msg}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout en intento {attempt + 1}")
                if attempt < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
                    
            except requests.exceptions.HTTPError as e:
                logger.error(f"Error HTTP {e.response.status_code}: {e}")
                if e.response.status_code == 404:
                    logger.error("URL no encontrada, verificar configuración")
                    break
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error de conexión: {e}")
                if attempt < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
                    
            except Exception as e:
                logger.error(f"Error inesperado: {type(e).__name__}: {e}")
                break
        
        # Si llegamos aquí, todos los intentos fallaron
        if use_mock_on_error:
            logger.warning("Usando datos mock debido a errores en scraping")
            return self._generate_mock_data()
        else:
            raise Exception("No se pudo obtener datos después de múltiples intentos")
    
    def _fetch_data(self) -> Dict:
        """
        Realiza la request HTTP y parsea el HTML.
        
        Returns:
            Diccionario con datos parseados
        """
        response = requests.get(
            self.url, 
            headers=self.headers, 
            timeout=self.timeout
        )
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        return self._parse_html(soup)
    
    def _parse_html(self, soup: BeautifulSoup) -> Dict:
        """
        Parsea el HTML para extraer datos de IMECA desde aire.jalisco.gob.mx
        
        Basado en la estructura real del sitio web que contiene:
        - Texto: "Nivel máximo registrado X puntos IMECA en [Estación]"
        - Elementos h1/h2 con el valor numérico grande
        - Estado de calidad del aire (Buena, Regular, Mala, Muy Mala)
        - Fecha y hora de actualización
        
        Args:
            soup: Objeto BeautifulSoup con el HTML parseado
            
        Returns:
            Diccionario con datos de IMECA
        """
        try:
            # Obtener todo el texto de la página
            page_text = soup.get_text()
            logger.debug(f"Longitud del texto de la página: {len(page_text)} caracteres")
            
            imeca_value = None
            
            # Método 1: Buscar el patrón "X puntos IMECA en [Estación]"
            # Ejemplo: "Nivel máximo registrado 105 puntos IMECA en Las Pintas"
            imeca_pattern = r'(\d+)\s*puntos?\s*IMECA'
            match = re.search(imeca_pattern, page_text, re.IGNORECASE)
            
            if match:
                imeca_value = int(match.group(1))
            else:
                # Método 2: Buscar números grandes en elementos h1, h2, h3
                # El sitio muestra el IMECA como un número grande
                headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                for header in headers:
                    header_text = header.get_text(strip=True)
                    # Buscar números entre 0-200 (rango válido de IMECA)
                    number_match = re.search(r'\b(\d{1,3})\b', header_text)
                    if number_match:
                        value = int(number_match.group(1))
                        if 0 <= value <= 200:
                            imeca_value = value
                            break
                
                # Método 3: Buscar en elementos con clases comunes
                if imeca_value is None:
                    imeca_elements = soup.find_all(['div', 'span', 'p'], 
                                                   class_=re.compile(r'imeca|valor|nivel|index', re.I))
                    for elem in imeca_elements:
                        elem_text = elem.get_text(strip=True)
                        number_match = re.search(r'\b(\d{1,3})\b', elem_text)
                        if number_match:
                            value = int(number_match.group(1))
                            if 0 <= value <= 200:
                                imeca_value = value
                                break
                
                # Método 4: Buscar cualquier número entre 50-200 que aparezca cerca de "IMECA"
                if imeca_value is None:
                    # Buscar contexto alrededor de la palabra IMECA
                    imeca_context_pattern = r'IMECA[^0-9]*(\d{1,3})|(\d{1,3})[^0-9]*IMECA'
                    context_match = re.search(imeca_context_pattern, page_text, re.IGNORECASE)
                    if context_match:
                        value = int(context_match.group(1) or context_match.group(2))
                        if 0 <= value <= 200:
                            imeca_value = value
            
            if imeca_value is None:
                raise ValueError("No se encontró el valor IMECA en el HTML")
            
            # Buscar la estación en el texto
            # Patrón: "X puntos IMECA en [Estación]" o "en la estación: [Estación]"
            station_patterns = [
                r'puntos?\s+IMECA\s+en\s+([A-Za-z\s]+?)(?:\s|\.|$|puntos|07)',
                r'estaci[óo]n[:\s]+([A-Za-z\s]+?)(?:\s|\.|$)',
                r'en\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:puntos|estaci)',
            ]
            
            station = None
            for pattern in station_patterns:
                station_match = re.search(pattern, page_text, re.IGNORECASE)
                if station_match:
                    station = station_match.group(1).strip()
                    # Limpiar el nombre de la estación
                    station = re.sub(r'\s+', ' ', station)
                    # Validar que no sea solo una palabra común
                    if len(station) > 2 and station.lower() not in ['en', 'la', 'el', 'de', 'del']:
                        break
            
            if not station:
                # Buscar estaciones conocidas en el texto
                known_stations = ['Las Pintas', 'COUNTRY', 'Centro', 'Miravalle', 
                                 'Tlaquepaque', 'Vallarta', 'Oblatos', 'Águilas']
                for known_station in known_stations:
                    if known_station.lower() in page_text.lower():
                        station = known_station
                        break
                
                if not station:
                    station = "ZMG"
            
            # Buscar el estado de calidad del aire
            # El sitio muestra estados como: "Buena", "Regular", "Mala", "Muy Mala"
            # También aparece como "MALA" en mayúsculas o "Índice AIRE Y SALUD: Mala"
            status_patterns = [
                r'Índice\s+AIRE\s+Y\s+SALUD[:\s]+([A-Za-z\s]+?)(?:\s|\.|$)',
                r'Índice\s+AIRE\s+&\s+SALUD[:\s]+([A-Za-z\s]+?)(?:\s|\.|$)',
                r'Estado[:\s]+([A-Za-z\s]+?)(?:\s|\.|$)',
                r'(?:^|\n|\s)(BUENA|REGULAR|MALA|MUY\s+MALA)(?:\s|$|\.)',
                r'(?:^|\n|\s)(Buena|Regular|Mala|Muy\s+Mala)(?:\s|$|\.)',
            ]
            
            status = None
            for pattern in status_patterns:
                status_match = re.search(pattern, page_text, re.IGNORECASE | re.MULTILINE)
                if status_match:
                    status_text = status_match.group(1).strip()
                    # Normalizar el estado
                    status_text = re.sub(r'\s+', ' ', status_text)
                    status_text_lower = status_text.lower()
                    
                    # Mapear a nuestros estados estándar
                    if 'muy mala' in status_text_lower or status_text_lower == 'muy mala':
                        status = "Muy Mala"
                    elif 'mala' in status_text_lower and 'muy' not in status_text_lower:
                        status = "Mala"
                    elif 'regular' in status_text_lower:
                        status = "Regular"
                    elif 'buena' in status_text_lower:
                        status = "Buena"
                    
                    if status:
                        break
            
            # Si no encontramos el estado en el texto, calcularlo según IMECA
            if not status:
                status = self._determine_status(imeca_value)
            
            # Buscar fecha y hora de actualización
            # Patrón: "HH:MM a.m./p.m. - DÍA, DD DE MES DE AÑO"
            time_patterns = [
                r'(\d{1,2}:\d{2}\s*[ap]\.?m\.?)\s*-\s*[A-ZÁÉÍÓÚÑ\s,]+',
                r'(\d{1,2}:\d{2})\s*-\s*[A-ZÁÉÍÓÚÑ\s,]+',
            ]
            
            last_update = datetime.now().strftime("%H:%M")
            for pattern in time_patterns:
                time_match = re.search(pattern, page_text, re.IGNORECASE)
                if time_match:
                    time_str = time_match.group(1).strip()
                    # Intentar parsear la hora
                    try:
                        # Convertir formato 12h a 24h si es necesario
                        if 'p.m.' in time_str.lower() or 'pm' in time_str.lower():
                            hour_match = re.search(r'(\d{1,2}):(\d{2})', time_str)
                            if hour_match:
                                hour = int(hour_match.group(1))
                                minute = hour_match.group(2)
                                if hour != 12:
                                    hour += 12
                                last_update = f"{hour:02d}:{minute}"
                        elif 'a.m.' in time_str.lower() or 'am' in time_str.lower():
                            hour_match = re.search(r'(\d{1,2}):(\d{2})', time_str)
                            if hour_match:
                                hour = int(hour_match.group(1))
                                minute = hour_match.group(2)
                                if hour == 12:
                                    hour = 0
                                last_update = f"{hour:02d}:{minute}"
                        else:
                            # Formato 24h
                            hour_match = re.search(r'(\d{1,2}):(\d{2})', time_str)
                            if hour_match:
                                last_update = hour_match.group(0)
                    except Exception as e:
                        logger.debug(f"No se pudo parsear la hora: {e}")
                    break
            
            logger.info(f"Datos parseados exitosamente: IMECA={imeca_value}, Estación={station}, Estado={status}, Hora={last_update}")
            
            return {
                "imeca": int(imeca_value),
                "status": status,
                "station": station,
                "last_update": last_update,
                "source": "real"
            }
            
        except Exception as e:
            logger.error(f"Error parseando HTML: {e}")
            logger.debug(f"Contenido HTML (primeros 1000 caracteres): {str(soup)[:1000]}")
            raise ValueError(f"No se pudo extraer datos IMECA del HTML: {str(e)}")
    
    def _determine_status(self, imeca: float) -> str:
        """Determina el estado de calidad del aire según IMECA"""
        if imeca <= Config.IMECA_GOOD:
            return "Buena"
        elif imeca <= Config.IMECA_BAD:
            return "Regular"
        elif imeca <= 150:
            return "Mala"
        else:
            return "Muy Mala"
    
    def _generate_mock_data(self) -> Dict:
        """Genera datos mock para desarrollo/testing"""
        current_imeca = np.random.randint(45, 115)
        status = self._determine_status(current_imeca)
        
        return {
            "imeca": current_imeca,
            "status": status,
            "station": "Las Pintas (Simulado)",
            "last_update": datetime.now().strftime("%H:%M"),
            "source": "mock",
        }

    def _parse_all_stations(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Parsea el HTML para extraer IMECA por estación en la ZMG.

        Retorna una lista de diccionarios con:
            - station
            - imeca
            - status
            - lat, lon (si se conocen)
            - last_update
            - source
        """
        page_text = soup.get_text(" ", strip=True)

        # Buscar hora de actualización similar a _parse_html
        time_patterns = [
            r"(\d{1,2}:\d{2}\s*[ap]\.?m\.?)\s*-\s*[A-ZÁÉÍÓÚÑ\s,]+",
            r"(\d{1,2}:\d{2})\s*-\s*[A-ZÁÉÍÓÚÑ\s,]+",
        ]
        last_update = datetime.now().strftime("%H:%M")
        for pattern in time_patterns:
            time_match = re.search(pattern, page_text, re.IGNORECASE)
            if time_match:
                time_str = time_match.group(1).strip()
                try:
                    if "p.m." in time_str.lower() or "pm" in time_str.lower():
                        hour_match = re.search(r"(\\d{1,2}):(\\d{2})", time_str)
                        if hour_match:
                            hour = int(hour_match.group(1))
                            minute = hour_match.group(2)
                            if hour != 12:
                                hour += 12
                            last_update = f"{hour:02d}:{minute}"
                    elif "a.m." in time_str.lower() or "am" in time_str.lower():
                        hour_match = re.search(r"(\\d{1,2}):(\\d{2})", time_str)
                        if (hour_match):
                            hour = int(hour_match.group(1))
                            minute = hour_match.group(2)
                            if hour == 12:
                                hour = 0
                            last_update = f"{hour:02d}:{minute}"
                    else:
                        hour_match = re.search(r"(\\d{1,2}):(\\d{2})", time_str)
                        if hour_match:
                            last_update = hour_match.group(0)
                except Exception as e:
                    logger.debug(f"No se pudo parsear la hora (estaciones): {e}")
                break

        # Buscar patrones tipo "Nivel máximo registrado 105 puntos IMECA en Las Pintas"
        station_pattern = r"Nivel\s+m[aá]ximo\s+registrado\s+(\d{1,3})\s*puntos?\s*IMECA\s+en\s+([A-Za-zÁÉÍÓÚÑñ ]+)"
        matches = re.findall(station_pattern, page_text, flags=re.IGNORECASE)

        stations: List[Dict] = []
        for imeca_str, station_name in matches:
            try:
                imeca_value = int(imeca_str)
            except ValueError:
                continue

            station_clean = re.sub(r"\s+", " ", station_name).strip()
            status = self._determine_status(float(imeca_value))
            coords = STATION_COORDS.get(station_clean)
            stations.append(
                {
                    "station": station_clean,
                    "imeca": imeca_value,
                    "status": status,
                    "lat": coords["lat"] if coords else None,
                    "lon": coords["lon"] if coords else None,
                    "last_update": last_update,
                    "source": "real",
                }
            )

        return stations

    def _generate_mock_stations(self) -> List[Dict]:
        """Genera datos simulados de IMECA para cada estación conocida."""
        stations: List[Dict] = []
        for name, coords in STATION_COORDS.items():
            imeca_val = int(np.random.randint(40, 140))
            stations.append(
                {
                    "station": name,
                    "imeca": imeca_val,
                    "status": self._determine_status(float(imeca_val)),
                    "lat": coords.get("lat"),
                    "lon": coords.get("lon"),
                    "last_update": datetime.now().strftime("%H:%M"),
                    "source": "mock",
                }
            )
        return stations

    def scrape_all_stations(self, use_mock_on_error: bool = True) -> List[Dict]:
        """
        Obtiene el listado de estaciones de la ZMG con su IMECA estimado.
        """
        for attempt in range(Config.MAX_RETRIES):
            try:
                logger.info(
                    f"Intento {attempt + 1} de scraping de todas las estaciones de calidad del aire"
                )
                resp = requests.get(self.url, headers=self.headers, timeout=self.timeout)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.content, "html.parser")
                stations = self._parse_all_stations(soup)
                if stations:
                    logger.info(
                        f"Se obtuvieron {len(stations)} estaciones de calidad del aire"
                    )
                    return stations
                raise ValueError("No se encontraron estaciones en el HTML")
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout en intento {attempt + 1} (estaciones)")
                if attempt < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
            except requests.exceptions.HTTPError as e:
                logger.error(
                    f"Error HTTP al obtener estaciones {e.response.status_code}: {e}"
                )
                if e.response.status_code == 404:
                    logger.error("URL de estaciones no encontrada, verificar configuración")
                    break
            except requests.exceptions.RequestException as e:
                logger.error(f"Error de conexión al obtener estaciones: {e}")
                if attempt < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
            except Exception as e:
                logger.error(f"Error inesperado al obtener estaciones: {e}")
                break

        if use_mock_on_error:
            logger.warning("Usando datos mock de estaciones debido a errores en scraping")
            return self._generate_mock_stations()
        raise Exception("No se pudieron obtener datos de estaciones después de múltiples intentos")


# ============================================================================
# FUNCIONES DE DATOS DE AGUA
# ============================================================================

class WaterLevelProcessor:
    """Clase para procesar datos de niveles de agua (Chapala, presas).
    
    Nota: el histórico sigue siendo simulado, pero complementaremos con
    una cota actual real desde CEA Jalisco (get_chapala_level_real).
    """
    
    @staticmethod
    def generate_mock_history(days: int = 180) -> pd.DataFrame:
        """
        Genera un DataFrame con datos históricos simulados.
        
        Args:
            days: Número de días de historia a generar
            
        Returns:
            DataFrame con columnas 'Fecha' y 'Nivel (%)'
        """
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        
        # Simulación de tendencia realista
        base_level = 60.0
        trend = np.linspace(-5, 8, days)  # De bajar 5% a subir 8%
        noise = np.random.normal(0, 0.2, days)
        
        levels = base_level + trend + noise
        levels = np.clip(levels, 0, 100)
        
        df = pd.DataFrame({
            "Fecha": dates,
            "Nivel (%)": levels
        })
        
        return df


# ============================================================================
# SCRAPER NIVEL LAGO DE CHAPALA (REAL TIME) - CEA JALISCO
# ============================================================================

def get_chapala_level_real(use_mock_on_error: bool = True) -> Dict:
    """
    Obtiene la cota actual del Lago de Chapala desde CEA Jalisco.
    
    Fuente:
        https://www.ceajalisco.gob.mx/contenido/chapala/chapala/cota.html
    
    Returns:
        dict con:
            - level_msnm: nivel en metros sobre el nivel del mar (float)
            - unit: 'msnm'
            - last_update: str (HH:MM)
            - source: 'real' o 'mock'
            - raw_snippet: texto donde se encontró el dato (opcional)
    """
    url = Config.CHAPALA_LEVEL_URL
    headers = {"User-Agent": Config.USER_AGENT}

    try:
        resp = requests.get(url, headers=headers, timeout=Config.REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "html.parser")
        page_text = soup.get_text(" ", strip=True)

        # Buscar patrones típicos de cota, por ejemplo:
        # "cota 94.56 msnm", "Cota: 94.56 m.s.n.m.", etc.
        patterns = [
            r"[Cc]ota[:\s]+(\d{2,3}\.\d{2})\s*(?:m\.?s\.?n\.?m\.?|msnm|m)",
            r"(\d{2,3}\.\d{2})\s*(?:m\.?s\.?n\.?m\.?|msnm|m)\s*[Cc]ota",
        ]

        level_value = None
        raw_snippet = None

        for pat in patterns:
            m = re.search(pat, page_text)
            if m:
                level_value = float(m.group(1))
                # Guardar pequeño snippet alrededor para depuración
                start = max(m.start() - 30, 0)
                end = min(m.end() + 30, len(page_text))
                raw_snippet = page_text[start:end]
                break

        if level_value is None:
            raise ValueError("No se encontró la cota del lago en el HTML de CEA")

        return {
            "level_msnm": level_value,
            "unit": "msnm",
            "last_update": datetime.now().strftime("%H:%M"),
            "source": "real",
            "raw_snippet": raw_snippet,
        }

    except Exception as e:
        logger.error(f"Error obteniendo cota real de Chapala: {e}")
        if not use_mock_on_error:
            raise

        # Fallback simple: valor simulado razonable
        mock_level = 94.50  # valor típico aproximado
        return {
            "level_msnm": mock_level,
            "unit": "msnm",
            "last_update": datetime.now().strftime("%H:%M"),
            "source": "mock",
            "raw_snippet": None,
        }


# ============================================================================
# FUNCIONES DE VISUALIZACIÓN
# ============================================================================

class EnvironmentVisualizations:
    """Clase para crear visualizaciones de datos ambientales"""
    
    @staticmethod
    def plot_water_levels(df: pd.DataFrame, title: str = None) -> go.Figure:
        """
        Crea un gráfico de líneas para niveles de agua.
        
        Args:
            df: DataFrame con columnas 'Fecha' y 'Nivel (%)'
            title: Título personalizado (opcional)
            
        Returns:
            Figura de Plotly
        """
        if title is None:
            title = "Histórico Nivel Lago de Chapala (6 Meses)"
        
        fig = px.line(
            df, 
            x="Fecha", 
            y="Nivel (%)", 
            title=title,
            labels={"Nivel (%)": "Capacidad (%)"},
            template="plotly_white"  # Cambiado a 'white' para mejor legibilidad
        )
        
        fig.update_traces(line_color='#00CC96', line_width=3)
        fig.add_hrect(
            y0=0, 
            y1=40, 
            line_width=0, 
            fillcolor="red", 
            opacity=0.1, 
            annotation_text="Nivel Crítico"
        )
        
        fig.update_layout(
            hovermode='x unified',
            xaxis_title="Fecha",
            yaxis_title="Capacidad (%)",
            height=400
        )
        
        return fig
    
    @staticmethod
    def plot_imeca_gauge(imeca_value: int, status: str) -> go.Figure:
        """
        Crea un gráfico de gauge (velocímetro) para mostrar IMECA.
        
        Args:
            imeca_value: Valor de IMECA
            status: Estado de calidad del aire
            
        Returns:
            Figura de Plotly
        """
        # Determinar color según estado
        color_map = {
            'Buena': 'green',
            'Regular': 'yellow',
            'Mala': 'orange',
            'Muy Mala': 'red'
        }
        color = color_map.get(status, 'gray')
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = imeca_value,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"IMECA - {status}"},
            delta = {'reference': 50},
            gauge = {
                'axis': {'range': [None, 200]},
                'bar': {'color': color},
                'steps': [
                    {'range': [0, 50], 'color': "lightgreen"},
                    {'range': [50, 100], 'color': "yellow"},
                    {'range': [100, 150], 'color': "orange"},
                    {'range': [150, 200], 'color': "red"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 100
                }
            }
        ))
        
        fig.update_layout(height=300)
        return fig


# ============================================================================
# FUNCIONES DE INTERFAZ (para compatibilidad con código existente)
# ============================================================================

def get_air_quality_zmg(use_mock_on_error: bool = True) -> Dict:
    """
    Función de interfaz para obtener calidad del aire.
    Mantiene compatibilidad con código existente.
    
    Args:
        use_mock_on_error: Si True, retorna datos mock en caso de error
        
    Returns:
        Diccionario con datos de calidad del aire
    """
    scraper = AirQualityScraper()
    return scraper.scrape(use_mock_on_error=use_mock_on_error)


def get_air_quality_zmg_stations(use_mock_on_error: bool = True) -> List[Dict]:
    """
    Obtiene la lista de estaciones de la ZMG con su IMECA y ubicación.
    """
    scraper = AirQualityScraper()
    return scraper.scrape_all_stations(use_mock_on_error=use_mock_on_error)


def get_water_levels_history_mock(days: int = 180) -> pd.DataFrame:
    """
    Función de interfaz para obtener datos históricos de niveles de agua.
    
    Args:
        days: Número de días de historia
        
    Returns:
        DataFrame con datos históricos
    """
    return WaterLevelProcessor.generate_mock_history(days)


def plot_water_levels(df: pd.DataFrame) -> go.Figure:
    """
    Función de interfaz para crear gráfico de niveles de agua.
    
    Args:
        df: DataFrame con datos
        
    Returns:
        Figura de Plotly
    """
    return EnvironmentVisualizations.plot_water_levels(df)


def get_chapala_level(use_mock_on_error: bool = True) -> Dict:
    """
    Función de interfaz para obtener la cota actual del Lago de Chapala.

    Args:
        use_mock_on_error: Si True, retorna un valor simulado si falla el scraping.
    """
    return get_chapala_level_real(use_mock_on_error=use_mock_on_error)


# ============================================================================
# NOTICIAS DE MEDIO AMBIENTE (ZMG) + IA (GEMINI)
# ============================================================================


class EnvNewsConfig:
    """Configuración para noticias de medio ambiente en la ZMG."""

    RSS_URL = (
        "https://news.google.com/rss/search"
        "?q=Medio+ambiente+Zona+Metropolitana+de+Guadalajara&hl=es&gl=MX&ceid=MX:es"
    )
    MAX_NEWS = 5

    PROMPT_TEMPLATE = """Actúa como un analista ambiental objetivo.
Analiza la siguiente noticia sobre medio ambiente en la Zona Metropolitana de Guadalajara.

Título: {title}
Descripción: {description}

Tu tarea:
1. Elimina el sensacionalismo y el alarmismo.
2. Resume la noticia en 1 o 2 frases claras que expliquen qué ocurre y su impacto ambiental.
3. Enfócate en los hechos clave (qué, dónde, cuándo y consecuencias)."""


def get_env_news_rss(max_items: Optional[int] = None) -> List[Dict]:
    """Obtiene las últimas noticias de medio ambiente en la ZMG desde Google News RSS."""
    max_items = max_items or EnvNewsConfig.MAX_NEWS
    try:
        logger.info(
            f"Obteniendo noticias de medio ambiente desde RSS: {EnvNewsConfig.RSS_URL}"
        )
        feed = feedparser.parse(EnvNewsConfig.RSS_URL)

        if getattr(feed, "bozo", False):
            logger.warning(
                f"Error parseando RSS feed medio ambiente: "
                f"{getattr(feed, 'bozo_exception', '')}"
            )

        news_list: List[Dict] = []

        for entry in getattr(feed, "entries", [])[:max_items]:
            description = entry.get("summary", entry.get("description", "")) or ""
            # Remover tags HTML básicos
            description = re.sub(r"<[^>]+>", "", description).strip()

            source_title = "Fuente desconocida"
            src = getattr(entry, "source", None)
            if isinstance(src, dict):
                source_title = src.get("title", "Fuente desconocida")

            news_item = {
                "title": entry.get("title", "Sin título"),
                "description": description,
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": source_title,
            }
            news_list.append(news_item)

        logger.info(f"Se obtuvieron {len(news_list)} noticias de medio ambiente ZMG")
        return news_list
    except Exception as e:
        logger.error(f"Error obteniendo noticias RSS de medio ambiente: {e}")
        return []


def resumir_noticia_medio_ambiente_con_ia(titulo: str, descripcion: str) -> str:
    """Genera un resumen conciso de 1–2 frases sobre una noticia ambiental usando Gemini."""
    prompt = EnvNewsConfig.PROMPT_TEMPLATE.format(
        title=titulo or "",
        description=descripcion or "",
    )

    if not _ENV_GEMINI_API_KEY:
        # Sin clave de API: devolvemos una versión truncada de la descripción
        texto = descripcion or ""
        return (texto[:200] + "...") if len(texto) > 200 else texto

    # Intento con modelo rápido (flash)
    try:
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
        response = model.generate_content(prompt)
        return (response.text or "").strip()
    except Exception as e:
        logger.error(
            f"Error en Gemini flash para noticia ambiental, fallback a gemini-2.5-flash: {e}"
        )
        try:
            model_backup = genai.GenerativeModel("gemini-2.5-flash")
            response = model_backup.generate_content(prompt)
            return (response.text or "").strip()
        except Exception as e2:
            logger.error(f"Error en Gemini pro para noticia ambiental: {e2}")
            texto = descripcion or ""
            return (texto[:200] + "...") if len(texto) > 200 else texto


def process_env_news_with_ai(news_item: Dict) -> Dict:
    """Procesa una noticia de medio ambiente con IA para obtener un resumen conciso."""
    try:
        summary = resumir_noticia_medio_ambiente_con_ia(
            news_item.get("title", ""),
            news_item.get("description", ""),
        )
        return {
            **news_item,
            "ai_summary": summary,
            "processed": bool(_ENV_GEMINI_API_KEY),
            "error": None,
        }
    except Exception as e:
        logger.error(f"Error procesando noticia ambiental con IA: {e}")
        texto = news_item.get("description", "") or ""
        return {
            **news_item,
            "ai_summary": (texto[:200] + "...") if len(texto) > 200 else texto,
            "processed": False,
            "error": str(e),
        }


def get_env_news(max_items: Optional[int] = None, use_ai: bool = True) -> List[Dict]:
    """Obtiene y opcionalmente procesa con IA noticias de medio ambiente en la ZMG."""
    news_list = get_env_news_rss(max_items=max_items)
    if not news_list:
        return []

    if not use_ai:
        return [
            {
                **n,
                "ai_summary": n.get("description", ""),
                "processed": False,
                "error": None,
            }
            for n in news_list
        ]

    return [process_env_news_with_ai(n) for n in news_list]