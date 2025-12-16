"""
Módulo de noticias de Chivas de Guadalajara
"""

from .data import (
    get_chivas_news,
    get_chivas_news_rss,
    process_news_with_ai,
    process_all_news,
    resumir_noticia_con_ia
)

__all__ = [
    'get_chivas_news',
    'get_chivas_news_rss',
    'process_news_with_ai',
    'process_all_news',
    'resumir_noticia_con_ia'
]