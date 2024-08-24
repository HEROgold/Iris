from typing import Any



class classproperty(property):
    def __get__(self, instance: Any, owner: type | None = None, /) -> Any:
        return self.fget(owner) # type: ignore


class ClassCached:
    _class_property_cache: dict[str, Any]


def class_cached_property(fn: Any):
    @classproperty
    def inner(self: ClassCached):
        if not hasattr(self, '_class_property_cache'):
            self._class_property_cache = {} # type: ignore[reportPrivateUsage]
        if fn.__name__ not in self._class_property_cache: # type: ignore[reportPrivateUsage]
            self._class_property_cache[fn.__name__] = fn(self) # type: ignore[reportPrivateUsage]
        return self._class_property_cache[fn.__name__] # type: ignore[reportPrivateUsage]
    return inner