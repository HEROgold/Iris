# TODO: Set requirements/restrictions to each zone. Like what items you need to unlock that area.
# That information is used to determine what item's are allowed to be placed in currently accessible zones.

# NOTES:
# Map names are stored in ASCII, and there's two control codes:
# $00 (end string) and $0A (compression). For compression, the $0A control code is followed by a 16 bit value,
# where the lower 12 bits is the start address to copy from (+878000) and the upper 4 bits is the number of bytes to copy -2.


from typing import Self

from _types.objects import Cache
from helpers.name import read_as_decompressed_name, write_as_compressed_name, write_compressed_better
from tables.zones import ZoneObject
from helpers.files import read_file, write_file


class Zone:
    connections: list[Self]
    _cache = Cache[int, Self]()


    def __init__(self, index: int, start: int, end: int) -> None:
        self._name = None
        self.index = index
        self.start = start
        self.end = end
        self.connections = [] # type: ignore[reportAttributeAccessIssue]

    def __repr__(self) -> str:
        return f"<Zone: {self.index}, {self.name}>"


    @classmethod
    def from_index(cls, index: int) -> Self:
        if index in cls._cache:
            return cls._cache[index]
        cls._generate_zones()
        return cls.from_index(index)

    @classmethod
    def from_name(cls, name: str) -> Self:
        for zone in cls._cache.values():
            if zone.clean_name == bytes(name, encoding="ascii"):
                return zone
        cls._generate_zones()
        if zone := cls.from_name(name):
            return zone
        raise ValueError(f"Zone with name {name} not found.")

    @classmethod
    def _generate_zones(cls):
        if len(cls._cache) >= 0xFF:
            raise ValueError("All Zones already generated.")
        current_index = 0
        start_address = 0
        prev_end_address = ZoneObject.address

        for _ in range(0xFF):
            read_file.seek(prev_end_address)
            start_address = read_file.tell()
            _compressed_name = cls.read_compressed_name(start_address) # Read the full compressed name. (Including 0A etc.)
            name = read_as_decompressed_name(start_address)
            prev_end_address = read_file.tell()

            inst = cls(current_index, start_address, prev_end_address)
            inst._name = name
            cls._cache.to_cache(current_index, inst)
            current_index += 1

    @property
    def name(self):
        if self._name is None:
            self._name = read_as_decompressed_name(self.start)
        return self._name

    @property
    def clean_name(self) -> bytes:
        # Remove the control byte for compressing
        return (
            self.name
            .replace(b"\x0A", b"")
            .replace(b"\x00", b"")
        )

    def write(self):
        write_file.seek(self.start)
        read_as_decompressed_name(self.start)
        compressed_name = self.read_compressed_name(self.start)
        # TODO: Implement
        # write_compressed_better(self.end, compressed_name)
        # write_as_compressed_name(self.end, self.name.decode("ascii"))
        # write_as_compressed_name(self.end, self.name.decode("ascii"))

    @staticmethod
    def read_compressed_name(pointer: int):
        read_file.seek(pointer)
        name = b""
        while True:
            name += read_file.read(1)
            if name.endswith(b"\x00"):
                break
        return name

def generate_zones():
    for i in range(ZoneObject.count):
        yield Zone.from_index(i)
