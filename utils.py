import json
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def load_daily_cache(filename: str):
    """
    Intenta cargar datos cacheados si pertenecen al día de hoy.
    Retorna None si el archivo no existe o es de una fecha anterior.
    """
    if not os.path.exists(filename):
        return None
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            
        cached_date = cache_data.get('date')
        today = datetime.now().strftime("%Y-%m-%d")
        
        if cached_date == today:
            logger.info(f"✅ Usando caché del día para {filename}")
            return cache_data.get('data')
        else:
            logger.info(f"⚠️ Caché expirado para {filename} (Fecha: {cached_date})")
            return None
            
    except Exception as e:
        logger.error(f"Error leyendo caché {filename}: {e}")
        return None

def save_daily_cache(filename: str, data: list):
    """Guarda los datos en un JSON con la fecha de hoy."""
    today = datetime.now().strftime("%Y-%m-%d")
    cache_structure = {
        "date": today,
        "data": data
    }
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(cache_structure, f, ensure_ascii=False, indent=4)
        logger.info(f"💾 Datos guardados en {filename}")
    except Exception as e:
        logger.error(f"Error guardando caché {filename}: {e}")