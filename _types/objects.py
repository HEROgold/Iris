class Cache[K, V]:
    def __init__(self) -> None:
        self._cache: dict[K, V] = {}

    def from_cache(self, key: K) -> V | None:
        if key in self._cache:
            return self._cache[key]
        return None

    def to_cache(self, key: K, value: V) -> None:
        self._cache[key] = value

    def keys(self):
        return self._cache.keys()

    def values(self):
        return self._cache.values()

    def __contains__(self, key: K) -> bool:
        return key in self._cache

    def __getitem__(self, key: K) -> V:
        return self._cache[key]

    def __setitem__(self, key: K, value: V) -> None:
        self._cache[key] = value

    def __len__(self) -> int:
        return len(self._cache)
