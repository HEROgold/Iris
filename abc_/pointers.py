import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Self

from helpers.bits import find_table_pointer
from logger import iris


type LocationArgs = Sequence[int] | int

class Pointer(ABC):
    pointer: int

    def __init__(self, pointer: int) -> None:
        log = logging.getLogger(f"{iris.name}.PointerList.{self.__class__.__name__}")
        log.debug(f"Creating {type(self).__name__} from {pointer=}")
        self.pointer = pointer

    @classmethod
    @abstractmethod
    def from_pointer(cls, pointer: int) -> Self:
        pass


class TablePointer(ABC):
    address: int
    index: int
    pointer: int

    def __init__(self, address: int, index: int) -> None:
        log = logging.getLogger(f"{iris.name}.AddressPointer.{self.__class__.__name__}")
        log.debug(f"Creating {type(self).__name__} from {address=} + {index=}")
        self.address = address
        self.index = index
        self.pointer = find_table_pointer(address, index)

    @classmethod
    @abstractmethod
    def from_table(cls, address: int, index: int) -> Self:
        pass

class ReferencePointer(ABC):
    address: int
    index: int
    pointer: int
    size: int

    def __init__(self, address: int, index: int, size: int) -> None:
        log = logging.getLogger(f"{iris.name}.ReferencePointer.{self.__class__.__name__}")
        log.debug(f"Creating {type(self).__name__} from {address=} + {index=} > {size=}")
        self.address = address
        self.index = index
        self.pointer = address + index * size
        self.size = size

    @classmethod
    @abstractmethod
    def from_reference(cls, address: int, index: int, size: int) -> Self:
        pass
