"""
Модуль для управления rate limiting при запросах к API.
"""
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter с фиксированной задержкой между запросами.
    
    Обеспечивает concurrency = 1 (последовательная обработка).
    """
    
    def __init__(self, delay_seconds: float = 1.5):
        """
        Инициализирует rate limiter.
        
        Args:
            delay_seconds: Задержка между запросами в секундах
        """
        self.delay_seconds = delay_seconds
        self._last_request_time: Optional[float] = None
    
    def wait_if_needed(self) -> None:
        """
        Ждет, если необходимо, чтобы соблюсти rate limit.
        
        Вызывается перед каждым запросом к API.
        """
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.delay_seconds:
                sleep_time = self.delay_seconds - elapsed
                logger.debug(f"Rate limit: ожидание {sleep_time:.2f} сек")
                time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def reset(self) -> None:
        """Сбрасывает таймер последнего запроса."""
        self._last_request_time = None

