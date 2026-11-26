from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = max(1, limit)
        self.window = max(1, window_seconds)
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            cutoff = now - self.window
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry = max(1, math.ceil(self.window - (now - events[0])))
                return False, retry
            events.append(now)
            return True, 0
