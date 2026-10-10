import pytest

from trips.providers.cache import TtlCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_returns_stored_values_until_they_expire() -> None:
    clock = FakeClock()
    cache: TtlCache[str, int] = TtlCache(ttl_s=60, max_entries=10, clock=clock)

    cache.set("a", 1)
    clock.now = 59.9
    assert cache.get("a") == 1

    clock.now = 60
    assert cache.get("a") is None
    assert len(cache) == 0


def test_missing_keys_return_none() -> None:
    assert TtlCache[str, int](ttl_s=1, max_entries=1).get("nope") is None


def test_evicts_least_recently_used_when_full() -> None:
    cache: TtlCache[str, int] = TtlCache(ttl_s=60, max_entries=2, clock=FakeClock())

    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # "b" is now least recently used
    cache.set("c", 3)

    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_setting_again_refreshes_the_entry() -> None:
    clock = FakeClock()
    cache: TtlCache[str, int] = TtlCache(ttl_s=60, max_entries=10, clock=clock)

    cache.set("a", 1)
    clock.now = 50
    cache.set("a", 2)
    clock.now = 100

    assert cache.get("a") == 2


@pytest.mark.parametrize(("ttl", "size"), [(0, 1), (1, 0)])
def test_rejects_invalid_configuration(ttl: float, size: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        TtlCache[str, int](ttl_s=ttl, max_entries=size)
