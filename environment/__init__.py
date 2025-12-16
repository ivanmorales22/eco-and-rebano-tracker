"""
Módulo de datos ambientales para GDL_Insight
"""
from .data import (
    get_air_quality_zmg,
    get_air_quality_zmg_stations,
    get_water_levels_history_mock,
    plot_water_levels,          # Ahora sí existe gracias al paso 1
    EnvironmentVisualizations,
    get_chapala_level,
    get_env_news
)

__all__ = [
    'get_air_quality_zmg',
    'get_air_quality_zmg_stations',
    'get_water_levels_history_mock',
    'plot_water_levels',
    'EnvironmentVisualizations',
    'get_chapala_level',
    'get_env_news'
]
