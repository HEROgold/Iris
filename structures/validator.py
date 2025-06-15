from abc import ABCMeta, abstractmethod
from typing import cast


class ABCValidator[VT](metaclass=ABCMeta):
    def __init__(self, default: VT | None = None) -> None:
        self._default = default

    def __set_name__(self, owner: type, name: str):
        self.name = name
        self.private = "_" + name

    def __get__(self, obj: object, obj_type: object):
        # obj_type is the class in which the variable is defined
        # so it can be different than type of T
        return cast("VT", getattr(obj, self.private, self._default))

    @abstractmethod
    def __set__(self, obj: object, value: VT) -> None:
        setattr(obj, self.private, value)


class ExistsValidator[T](ABCValidator[T]):
    def __get__(self, obj: object, obj_type: object):
        value = super().__get__(obj, obj_type)
        if value is None:
            msg = f"{self.name!r} cannot be None"
            raise ValueError(msg)
        return value

    def __set__(self, obj: object, value: object | None = None) -> None:
        if value is None:
            msg = f"{self.name!r} cannot be None"
            raise ValueError(msg)
        setattr(obj, self.private, value)


class PositiveValidator[T: float | int](ABCValidator[T]):
    def __set__(self, obj: object, value: T) -> None:
        if value < 0:
            msg = f"{self.name!r} must be a positive number"
            raise ValueError(msg)
        setattr(obj, self.private, value)


class NegativeValidator[T: float | int](ABCValidator[T]):
    def __set__(self, obj: object, value: T) -> None:
        if value > 0:
            msg = f"{self.name!r} must be a negative number"
            raise ValueError(msg)
        setattr(obj, self.private, value)
