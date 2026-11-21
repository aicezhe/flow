"""Токены входа и ограничение попыток. Всё в памяти процесса: после перезапуска
сервера нужно войти заново. Зависит только от стандартной библиотеки."""
import secrets
import time
from collections import defaultdict, deque

TOKEN_TTL = 12 * 3600   # секунд
MAX_ATTEMPTS = 5        # попыток входа
WINDOW = 60             # за столько секунд


class Auth:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._tokens: dict[str, float] = {}               # токен -> момент истечения
        self._attempts: dict[str, deque] = defaultdict(deque)

    def allow_attempt(self, client: str) -> bool:
        """Считает любую попытку (верную тоже). Шестая за минуту отклоняется."""
        now = self._clock()
        q = self._attempts[client]
        while q and now - q[0] >= WINDOW:
            q.popleft()
        if len(q) >= MAX_ATTEMPTS:
            return False
        q.append(now)
        return True

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
