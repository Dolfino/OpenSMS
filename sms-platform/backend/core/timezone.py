"""
timezone.py - Utilitários de fuso horário brasileiro (America/Sao_Paulo).
Garante que horários comerciais, contadores diários e logs sigam o horário oficial do Brasil.
"""

import datetime

try:
    import zoneinfo
    BRAZIL_TZ = zoneinfo.ZoneInfo("America/Sao_Paulo")
except Exception:
    BRAZIL_TZ = datetime.timezone(datetime.timedelta(hours=-3))


def get_brazil_now() -> datetime.datetime:
    """Retorna o datetime atual com o fuso horário oficial de Brasília/São Paulo."""
    return datetime.datetime.now(BRAZIL_TZ)
