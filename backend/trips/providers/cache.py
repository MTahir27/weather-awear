"""A small thread-safe, size-bounded cache with per-entry expiry."""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable


class TtlCache[K: Hashable, V]:
    def __init__(
        self,
        ttl_s: float,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_s <= 0 or max_entries <= 0:
            raise ValueError("ttl_s and max_entries must be positive.")
        self._ttl_s = ttl_s
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if self._clock() - stored_at >= self._ttl_s:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            self._entries[key] = (self._clock(), value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
