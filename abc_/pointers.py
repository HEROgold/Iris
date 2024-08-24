from abc import ABC, abstractmethod
import logging

from typing import Self, Sequence

from helpers.bits import find_table_pointer
from logger import iris


type LocationArgs = Sequence[int] | int

class PointerList(ABC):
    pointer: int

    def __init__(self, pointer: int) -> None:
        log = logging.getLogger(f"{iris.name}.PointerList.{self.__class__.__name__}")
        log.debug(f"Creating {type(self).__name__} from {pointer=}")
        self.pointer = pointer

    @classmethod
    @abstractmethod
    def from_pointer(cls, pointer: int) -> Self:
        pass


class AddressPointer(ABC):
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


class ReferencePointer(AddressPointer):
    # TODO: Completely replace this with AddressPointer.
    reference_pointer: int

    def __init__(self, address: int, offset: int) -> None:
        self.address = address
        self.index = offset
        self.pointer = find_table_pointer(address, offset)
