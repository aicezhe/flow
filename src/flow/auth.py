"""Токены входа и ограничение частоты. Всё в памяти процесса: после перезапуска
сервера нужно войти заново. Зависит только от стандартной библиотеки."""
import secrets
import time
from collections import defaultdict, deque

TOKEN_TTL = 12 * 3600   # секунд
MAX_ATTEMPTS = 5        # попыток входа
WINDOW = 60             # за столько секунд


class RateLimiter:
    """Скользящее окно: не больше `limit` событий за `window` секунд на ключ (адрес).
    Для входа и для заявок создаются отдельные экземпляры, ведра не смешиваются."""

    def __init__(self, limit: int, window: float, clock=time.monotonic):
        self.limit, self.window, self._clock = limit, window, clock
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        q = self._hits[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


class Auth:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._tokens: dict[str, float] = {}               # токен -> момент истечения
        self._login = RateLimiter(MAX_ATTEMPTS, WINDOW, clock)

    def allow_attempt(self, client: str) -> bool:
        """Считает любую попытку (верную тоже). Шестая за минуту отклоняется."""
        return self._login.allow(client)

    def issue_token(self) -> str:
        now = self._clock()
        self._tokens = {t: exp for t, exp in self._tokens.items() if exp > now}
        token = secrets.token_urlsafe(32)
        self._tokens[token] = now + TOKEN_TTL
        return token

    def is_valid(self, token: str) -> bool:
        exp = self._tokens.get(token)
        if exp is None:
            return False
        if exp <= self._clock():
            del self._tokens[token]
            return False
        return True
