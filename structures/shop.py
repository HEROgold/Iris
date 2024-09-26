from enum import Enum
from helpers.files import read_file, restore_pointer, write_file
from typing import Any, Generator, Self
from abc_.pointers import TablePointer, Pointer
from enums.flags import ShopIdentifier, ShopTypes
from helpers.bits import find_table_pointer, read_little_int
from structures.item import Item
from structures.spell import Spell
from tables import ShopObject
from logger import iris
from _types.objects import Cache
from args import args


UNUSED_SHOPS = [0x1A, 0x27]


type SectionsType = tuple[Sections, int]


class Sections(Enum):
    DIVIDER = 0x000000.to_bytes(3)
    WEAPON = 0x003800.to_bytes(3)
    ARMOR = 0x00E400.to_bytes(3)
    SPELL = 0x032000.to_bytes(3)  # can also be 0x012000 # FIXME
    SPELL_END = 0xFF.to_bytes(1)  # can also be 0x0000?
    DUMMY = 0xFFFFFF.to_bytes(3)
    SHOP_START = 0xFFFFFE.to_bytes(3)
    ALTERNATIVE_END = 0x0000.to_bytes(2) # Special section, for certain shop endings.


class ShopSection:
    next_: Self | None
    pointer: int

    def __init__(self, section: Sections, start: int, shop: "Shop") -> None:
        self.pointer = start - 3
        self.section = section
        self.start_data = start
        self.items: list[Item | Spell] = []
        self.end_data = self.start_data
        self.next_ = None
        self.shop = shop

    def __repr__(self) -> str:
        return f"<<{self.section.name}: {self.section.value}>, {self.start_data}>"

    @property
    def size(self) -> int:
        return self.end_data - self.start_data

    def _gen_spells(self) -> Generator[tuple[Spell, int], Any, None]:
        next_pointer = self.fix_spell_section(self.start_data)
        for j in range(self.start_data, next_pointer):
            read_file.seek(j)
            yield Spell.from_index(read_little_int(read_file, 1)), j

    def _gen_items(self, next_section: Self) -> Generator[tuple[Item, int], Any, None]:
        next_pointer = next_section.pointer
        assert next_pointer - self.start_data % 2, "Start and next_ should have a even sized gap."
        for j in range(self.start_data, next_pointer, 2):
            read_file.seek(j)
            item_index = read_little_int(read_file, 2)
            yield Item.from_index(item_index), j

    def _find_items(self) -> Generator[tuple[Item | Spell, int], Any, None]:
        if (
            self.section == Sections.SPELL
            or (
                self.section == Sections.SHOP_START
                and self.shop.shop_type == ShopTypes.SPELL
            )
        ):
            yield from self._gen_spells()
            return

        next_section = self.next_
        if next_section is None:
            last_section = (
                self.section == Sections.DIVIDER
                or self.section == Sections.ALTERNATIVE_END
                or self.section == Sections.SHOP_START # Rare case if a shop has only one section. # FIXME: (Index 37, expected to have a divider. )
            )
            assert last_section, "Last section should be a divider."
            return

        yield from self._gen_items(next_section)

    @restore_pointer
    def fix_spell_section(self, start: int):
        """A fix for spell shop sections."""
        j = 0
        read_file.seek(start)
        while read_file.read(1) != Sections.SPELL_END.value:
            j += 1
            pass
        end = start + j
        return end


    def add_item(self, item: Item | Spell) -> None:
        self.items.append(item)
        if isinstance(item, Item):
            self.end_data += 2
        elif isinstance(item, Spell): # type: ignore[reportUnnecessaryIsInstance]
            self.end_data += 1
        else:
            raise ValueError("Item or Spell expected.")


    def remove_item(self, item: Item | Spell) -> None:
        self.items.append(item)
        if isinstance(item, Item):
            self.end_data -= 2
        elif isinstance(item, Spell): # type: ignore[reportUnnecessaryIsInstance]
            self.end_data -= 1
        else:
            raise ValueError("Item or Spell expected.")


    def write(self) -> None:
        tell = write_file.tell()
        if (
            self.section == Sections.SHOP_START
            or self.section == Sections.DUMMY
            or self.section == Sections.SPELL
        ):
            # Dummy sections are just for our code, so we ignore them as we write.
            # Spell sections are (always in vanilla) the same as the shop type.
            # So we can ignore them. TODO: find out if we can create custom shops containing spells and items.
            pass
        else:
            if self.section == Sections.ALTERNATIVE_END:
                write_file.seek(tell)
            else:
                write_file.seek(tell - 1)
            write_file.write(self.section.value)

        for item in self.items:
            if isinstance(item, Item):
                write_file.write(item.index.to_bytes(2, "little"))
            else:
                write_file.write(item.index.to_bytes())


class Shop(TablePointer):
    _cache = Cache[int, Self]()
    identifier: ShopIdentifier
    shop_sections: list[ShopSection]

    def __init__(
        self,
        shop_type: ShopTypes
    ) -> None:
        self.shop_type = shop_type

    @classmethod
    def from_index(cls, index: int) -> Self:
        # LSP thinks they are from kureji. So we ignore some type errors.
        return cls.from_table(ShopObject.address, index)  # type: ignore

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        if inst := cls._cache.from_cache(index):
            return inst

        shop_pointer = find_table_pointer(address, index)
        next_pointer = find_table_pointer(address, index+1)
        read_file.seek(shop_pointer)

        if shop_pointer == address:
            iris.warning(f"Shop pointer for {index} is 0x0000, when reading.")
            inst = cls(ShopTypes(0))
            super().__init__(inst, address, index)
            return inst

        unknown1 = read_file.read(1)
        shop_type = read_file.read(1)
        zero = read_file.read(1)

        assert zero == b"\x00", "ShopObject._zero is not 0x00."

        if index in UNUSED_SHOPS:
            iris.debug(f"Shop {index} is unused.")

        inst = cls(ShopTypes.from_byte(shop_type))
        super().__init__(inst, address, index)
        iris.debug(f"Shop {index=}, {inst.shop_type=}, {unknown1=}")

        inst.shop_sections = []
        for i, shop_section in enumerate(inst._find_shop_sections(shop_pointer, next_pointer)):
            if i > 0:
                inst.shop_sections[i-1].next_ = shop_section
            inst.shop_sections.append(shop_section)

        for section in inst.shop_sections:
            for item, p in section._find_items(): # type: ignore[reportPrivateUsage]
                section.add_item(item)

        inst.identifier = ShopIdentifier.from_byte(unknown1)
        cls._cache.to_cache(index, inst)
        return inst

    @restore_pointer
    def _find_alternative_end(self, start: int, stop: int):
        read_file.seek(stop - 2) # -2 > Length of alternative end.
        read = read_file.read(2)

        try:
            section = Sections(read)
        except ValueError:
            section = None

        if section is Sections.ALTERNATIVE_END:
            start = read_file.tell() - 2 # -2 > Length of alternative end.
            iris.warning(f"Alternative end found at {start}.")
            # Init the section, and patch it to behave as required.
            shop_section = ShopSection(Sections.ALTERNATIVE_END, 0, shop=self)
            shop_section.pointer = start
            shop_section.start_data = start
            shop_section.end_data = start + 2
            return shop_section

    @restore_pointer
    def _find_shop_sections(self, shop_start: int, stop: int) -> Generator[ShopSection, Any, None]:
        offset = 0
        read_file.seek(shop_start)
        while True:
            tell = read_file.tell()
            if tell >= stop:
                break
            read_file.seek(shop_start + offset)
            read = read_file.read(3)

            section_start = read_file.tell() # Start of section. Is behind the divider.
            try:
                section = Sections(read)
            except ValueError:
                section = None

            if section:
                yield ShopSection(Sections(read), section_start, self)
            elif offset == 0:
                yield ShopSection(Sections.SHOP_START, section_start, self)
            offset += 1

        if (
            len(self.shop_sections) > 0
            and self.shop_sections[-1].end_data < stop
            and (alt_end := self._find_alternative_end(shop_start, stop))
        ):
            yield alt_end


    @property
    def next_shop_pointer(self) -> int:
        """This pointer is generated based on the sections of the shop."""
        if len(self.shop_sections) == 0:
            return self.from_index(self.index+1).pointer
        shop_section = self.shop_sections[-1]

        if (
            shop_section.section is Sections.SPELL
            or shop_section.section is Sections.SHOP_START and self.shop_type == ShopTypes.SPELL
        ):
            end = shop_section.fix_spell_section(shop_section.start_data)
            if self.shop_type == ShopTypes.SPELL:
                end += 1
        else:
            end = shop_section.end_data
        return end

    @classmethod
    def fix_next_shop_pointer(cls, index: int) -> None:
        shop = cls.from_index(index)
        next_shop = cls.from_index(index+1)
        if args.debug or args.no_patch: # Test for vanilla. (No randomizing.)
            assert next_shop.pointer == shop.next_shop_pointer, f"Next shop pointer is not correct. {shop.next_shop_pointer}, {next_shop.pointer}"
        next_shop.pointer = shop.next_shop_pointer


    def write(self) -> None:
        write_file.seek(self.pointer)

        if self.pointer == self.address:
            iris.warning(f"Shop pointer for {self.index} is 0x0000, when writing.")
            return

        self.fix_next_shop_pointer(self.index)

        write_file.write(self.identifier.to_bytes())
        write_file.write(self.shop_type.to_bytes())
        write_file.write(b"\x00")

        if self.index in UNUSED_SHOPS:
            iris.debug(f"Shop {self.index} is unused.")

        for section in self.shop_sections:
            section.write()

        iris.debug(f"Shop {self.index} written.")


# TODO: Implement ShopKureji. To match Shop.
class ShopKureji(Pointer):
    """
    Jp and Kureji versions of the shop object.
    """
    unknown1: bytes
    unknown2: bytes

    def __init__(
        self,
        shop_type: ShopTypes,
        shop_index: int,
        item_indices: list[int] | None = None,
    ) -> None:
        self.shop_type = shop_type
        self.index = shop_index
        self.item_indices = item_indices or []

    @classmethod
    def from_pointer(cls, pointer: int, i: int) -> Self: # type: ignore[reportIncompatibleMethodOverride]
        # Extra arg, i. Required to indexing.
        read_file.seek(pointer)

        _unknown1 = read_file.read(ShopObject.unknown0)
        shop_type = ShopTypes.from_byte(read_file.read(1)) # ShopObject.shop_type is bytes, which is only one long. and contains bit values.
        _unknown2 = read_file.read(ShopObject.unknown2)

        inst = cls(
            shop_type,
            shop_index=i,
        )
        inst.unknown1 = _unknown1
        inst.unknown2 = _unknown2
        super().__init__(inst, pointer)
        return inst

    write = Shop.write
