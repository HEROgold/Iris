from typing import Self

from abc_.pointers import ReferencePointer
from helpers.addresses import address_from_lorom, address_to_lorom
from helpers.bits import read_little_int
from helpers.files import read_file, write_file
from structures.zone import ZoneData
from tables import MapMetaObject


class MapMeta(ReferencePointer):
    """One entry of the ZoneData pointer table (``0x27FCBC``): the 3-byte LoROM address of a
    map's ZoneData blob, decoded to its headerless PC offset (see structures.zone.ZoneData)."""

    zone_data_pointer: int

    def __init__(self, zone_data_pointer: int) -> None:
        self.zone_data_pointer = zone_data_pointer

    def __repr__(self) -> str:
        return f"<MapMeta: {self.index}, {self.zone_data_pointer=:#08x}>"

    @property
    def zone_data(self) -> ZoneData:
        """This entry's ZoneData blob (the map's object data: exits, NPCs, chests, ...).

        Cached by ``ZoneData.from_pointer``, so mutating it through this property is what
        :meth:`write` picks up.
        """
        return ZoneData.from_pointer(self.zone_data_pointer)

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_reference(MapMetaObject.address, index, MapMetaObject.reference_pointer)

    @classmethod
    def from_reference(cls, address: int, index: int, size: int) -> Self:
        read_file.seek(address + index * size)
        inst = cls(address_from_lorom(read_little_int(read_file, size)))
        super().__init__(inst, address, index, size)
        return inst

    def write(self) -> None:
        """Write the ZoneData (in place when every section keeps its length, else relocated), then the pointer."""
        zone_data = self.zone_data
        if zone_data.fits_in_place():
            zone_data.write()
        else:
            zone_data.write_relocated(self.index)
        self.zone_data_pointer = zone_data.start
        write_file.seek(self.pointer)
        write_file.write(address_to_lorom(self.zone_data_pointer).to_bytes(self.size, "little"))
