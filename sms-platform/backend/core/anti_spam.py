"""
anti_spam.py - Politicas de Protecao e Evasao de Bloqueios Anti-Spam de Operadoras.
Simula comportamento humano com cadencia variavel e pausas inteligentes.
"""

import random
import datetime
from typing import Tuple


from core.timezone import get_brazil_now


class AntiSpamPolicy:
    def __init__(
        self,
        min_delay_seconds: float = 12.0,
        max_delay_seconds: float = 35.0,
        pause_every_min_msgs: int = 45,
        pause_every_max_msgs: int = 70,
        min_pause_duration_seconds: float = 300.0,  # 5 minutos
        max_pause_duration_seconds: float = 600.0,  # 10 minutos
        daily_limit_per_sim: int = 500,
        allowed_start_hour: int = 8,
        allowed_start_minute: int = 30,
        allowed_end_hour: int = 20,
        allowed_end_minute: int = 30,
        allow_sundays: bool = False
    ):
        self.min_delay = min_delay_seconds
        self.max_delay = max_delay_seconds
        self.pause_every_min = pause_every_min_msgs
        self.pause_every_max = pause_every_max_msgs
        self.min_pause = min_pause_duration_seconds
        self.max_pause = max_pause_duration_seconds
        self.daily_limit = daily_limit_per_sim
        self.allowed_start_hour = allowed_start_hour
        self.allowed_start_minute = allowed_start_minute
        self.allowed_end_hour = allowed_end_hour
        self.allowed_end_minute = allowed_end_minute
        self.allow_sundays = allow_sundays

        # Estado dinâmico do lote
        self.next_batch_pause = random.randint(self.pause_every_min, self.pause_every_max)
        self.sent_since_last_pause = 0
        self.daily_sent_count = 0
        self.last_reset_day = get_brazil_now().date()

    def check_working_hours(self, now: datetime.datetime | None = None) -> Tuple[bool, str]:
        """Verifica se o momento atual esta dentro da janela comercial permitida (Horário de Brasília)."""
        if now is None:
            now = get_brazil_now()

        # Checa domingo (weekday 6)
        if now.weekday() == 6 and not self.allow_sundays:
            return False, "Disparos bloqueados aos domingos para evitar denuncias de spam."

        start_time = datetime.time(self.allowed_start_hour, self.allowed_start_minute)
        end_time = datetime.time(self.allowed_end_hour, self.allowed_end_minute)
        current_time = now.time()

        if not (start_time <= current_time <= end_time):
            return False, f"Fora do horario comercial permitido ({start_time.strftime('%H:%M')} as {end_time.strftime('%H:%M')})."

        return True, "Dentro do horario permitido."

    def calculate_next_delay(self) -> Tuple[float, bool, str]:
        """
        Calcula o proximo delay (em segundos) antes do envio:
        Retorna: (tempo_de_espera, is_long_pause, motivo)
        """
        # Checa reset diário baseado no dia do Brasil
        today = get_brazil_now().date()
        if today != self.last_reset_day:
            self.daily_sent_count = 0
            self.last_reset_day = today

        # Verifica se atingiu limite do dia
        if self.daily_sent_count >= self.daily_limit:
            return 0.0, True, f"Limite diário de segurança por chip atingido ({self.daily_limit} SMS)."

        # Verifica se deve fazer pausa térmica/descanso de lote
        if self.sent_since_last_pause >= self.next_batch_pause:
            pause_time = random.uniform(self.min_pause, self.max_pause)
            self.sent_since_last_pause = 0
            self.next_batch_pause = random.randint(self.pause_every_min, self.pause_every_max)
            return pause_time, True, f"Pausa térmica de descanso do chip ({round(pause_time / 60, 1)} min)."

        # Delay normal entre mensagens com jitter estocástico
        delay = random.uniform(self.min_delay, self.max_delay)
        return delay, False, "Intervalo estocástico entre mensagens."

    def record_send(self):
        """Registra um envio bem-sucedido nos contadores"""
        self.sent_since_last_pause += 1
        self.daily_sent_count += 1
