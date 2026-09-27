from collections.abc import Iterator
from functools import cache
from typing import Literal, Self

from _types.objects import Cache
from abc_.pointers import TablePointer
from args import args
from enums.flags import EquipableCharacter, EquipTypes, ItemEffects, ItemTypes, MenuIcon, Targeting, Usability
from helpers.bits import find_table_pointer
from helpers.files import read_file, write_file
from logger import iris
from rom_space.table import Table
from scripting.core import Data, Label, Script, assemble
from scripting.core import Item as ScriptItem
from scripting.l2basm import L2BASM, parse_record
from scripting.l2basm.edit import replace_entry
from scripting.l2basm.helpers import block
from scripting.l2basm.records import (
    ITEM_FLAGS,
    ITEM_SCRIPT_BITS,
    ITEM_WORDS,
    RecordSource,
    item_sources,
    read_record,
    table_address,
    table_bound,
)
from structures.subroutine import make_room_in_bank_96
from structures.word import Word
from tables import ItemNameObject, ItemObject


type ItemScript = Literal["menu", "battle", "weapon", "armor"]
_ITEM_SCRIPTS: tuple[ItemScript, ...] = ("menu", "battle", "weapon", "armor")  # flag bits 0-3
_SCRIPT_BIT_NAMES = {bit: name for name, bit in ITEM_SCRIPT_BITS.items()}


class ItemName(TablePointer):
    def __init__(self, address: int, index: int) -> None:
        self.address = address
        self.index = index
        self.pointer = self.address + self.index * ItemNameObject.name_text # type: ignore
        self.name = self.read()

    def __repr__(self) -> str:
        return f"<ItemName: {self.name}, {self.index}>"

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        return cls(address, index)

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls(ItemNameObject.address, index) # type: ignore

    def read(self) -> str:
        read_file.seek(self.pointer)
        return read_file.read(ItemNameObject.name_text).decode("ascii") # type: ignore

    def write(self) -> None:
        iris.debug(f"Writing ItemName {self.name!r} → {self.pointer=:#08x}")
        write_file.seek(self.pointer)
        write_file.write(self.name.encode("ascii"))


class Item(TablePointer):
    """One item record (table 0xB4F69, $96:CF69, 467 records) on ``rom_space.Table``.

    A record is 13 common bytes, then one u16 property word per set bit of the flag word at bytes 9-10 (in bit order),
    then the L2BASM scripts. Bits 0-3 announce the ``menu``, ``battle``, ``weapon`` and ``armor`` scripts: their words
    are record-relative script offsets, built from the labels in ``code``. Bits 4-15 are stat increases, the battle
    animation and the IP effect (an IP number, not a pointer); their words live in ``properties``.
    """

    price: int
    equip_types: EquipTypes
    usability: Usability
    targeting: Targeting
    icon: MenuIcon
    equipability: EquipableCharacter
    item_types: ItemTypes
    # Writing data.
    unknown2: bytes
    code: Script | None
    """The record's scripts as one body with ``menu``/``battle``/``weapon``/``armor`` entry labels."""
    properties: dict[int, int]
    """Flag bit (4-15) to its u16 property word."""
    external_entries: dict[str, int]
    """Script words pointing outside this record (shared code in some base patches), kept as raw values."""

    _cache = Cache[int, Self]()

    dev_items = [
        454,  # Key26       #
        455,  # Key27       #
        456,  # Key28       #
        457,  # Key29       #
        458,  # Key30       #
        461,  # PURIFIA     #
        462,  # Tag ring    #
        463,  # Tag ring    #
        464,  # RAN-RAN step#
        465,  # Tag candy   #
        466,  # Last        #
    ]

    def __init__(self, name: ItemName, item_index: int, sprite_index: int) -> None:
        self.name_pointer = name
        self.index = item_index
        self.sprite_index = sprite_index
        self.code = None
        self.properties = {}
        self.external_entries = {}

    def __repr__(self) -> str:
        return f"<Item: {self.name_pointer}, {self.index}>"

    def __bytes__(self) -> bytes:
        """Return the index of any item, without 0x00 bytes."""
        return self.index.to_bytes(2, "little").strip(b"\x00")

    def _validate_requirements(self) -> None:
        assert self.price is not None
        assert self.equip_types is not None
        assert self.usability is not None
        assert self.targeting is not None
        assert self.icon is not None
        assert self.equipability is not None
        assert self.item_types is not None
        self.description

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_table(ItemObject.address, index)

    @classmethod
    def reread(cls, index: int) -> Self:
        """Drop the cached items and read this one again from the output ROM."""
        reset_item_table()
        return cls.from_index(index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        if inst := cls._cache.from_cache(index):
            return inst
        rec = _item_sources()[index]
        record = read_record(write_file, rec)  # the output ROM, so base-patch edits are what we read
        inst = cls(ItemName.from_index(index), index, record[4])  # sprite: 00 for no-chest items, and coins.
        TablePointer.__init__(inst, address, index)
        inst.pointer = rec.start

        if args.equip_everyone:
            inst.equipability = EquipableCharacter(EquipableCharacter.ALL)
        if args.equip_anywhere:
            inst.equip_types = EquipTypes(EquipTypes.ALL)

        inst.usability = Usability.from_byte(record[0:1])
        inst.item_types = ItemTypes.from_byte(record[1:2])
        inst.targeting = Targeting.from_byte(record[2:3])
        inst.icon = MenuIcon.from_byte(record[3:4])
        inst.price = int.from_bytes(record[5:7], "little")
        inst.equip_types = EquipTypes.from_byte(record[7:8])
        inst.equipability = EquipableCharacter.from_byte(record[8:9])
        inst.unknown2 = record[11:13]  # 0x0000 for all items.
        flags = int.from_bytes(record[ITEM_FLAGS : ITEM_FLAGS + 2], "little")
        bits = [bit for bit in range(16) if flags >> bit & 1]
        words = [int.from_bytes(record[ITEM_WORDS + 2 * i : ITEM_WORDS + 2 * i + 2], "little") for i in range(len(bits))]
        inst.properties = {bit: word for bit, word in zip(bits, words, strict=True) if bit not in _SCRIPT_BIT_NAMES}
        inst.external_entries = dict(rec.external)
        in_region = rec.start < table_bound(write_file, table_address(write_file, "item"))
        if rec.entries:
            parsed = parse_record(record, rec.entries, start=rec.script_start)
            inst.code = parsed.script
            if in_region and parsed.end < len(record):  # unreached bytes up to the next record stay as they are
                inst.code.body.append(Data(record[parsed.end :]))
        elif in_region and rec.script_start is not None and rec.script_start < len(record):
            inst.code = Script(L2BASM, [Data(record[rec.script_start :])])
        inst._validate_requirements()
        cls._cache.to_cache(index, inst)
        return inst

    @property
    def description(self) -> str:
        """
        [0xB8200 -> 0xB85FF]:  pointers to item descriptions (2 bytes, little-endian)
        [0xB87B4 -> 0xBB2A0]:  item/spell/IP descriptions
        """
        return ""
        # TODO: Figure out how descriptions are stored.
        # TODO: Figure out how to decompress the descriptions.
        pointer_table = 0xB8200 # until 0xB85FF
        description_table_start = 0xB87B4
        description_table_end = 0xBB2A0
        pointer = find_table_pointer(pointer_table, self.index)
        # one pointer hit 0xC0000?
        assert description_table_start <= pointer <= description_table_end
        read_file.seek(pointer)
        # Clueless from here.
        description = read_file.read(2)
        Word.from_index(int.from_bytes(description))
        return None

    # -- flags, property words and scripts ------------------------------------------------------------------------

    def entries(self) -> list[ItemScript]:
        """The scripts this item has, in flag-bit order."""
        names = set() if self.code is None else {item.name for item in self.code.body if isinstance(item, Label)}
        return [name for name in _ITEM_SCRIPTS if name in names or name in self.external_entries]

    def flags(self) -> int:
        """The flag word at bytes 9-10: script bits from the scripts, property bits from ``properties``."""
        bits = [ITEM_SCRIPT_BITS[name] for name in self.entries()] + list(self.properties)
        return sum(1 << bit for bit in bits)

    @property
    def item_effects(self) -> ItemEffects:
        return ItemEffects(self.flags())

    @item_effects.setter
    def item_effects(self, value: ItemEffects | int) -> None:
        """Set the property bits (4-15): a new bit gets a zero word, a cleared bit loses its word.

        The script bits (0-3) follow the scripts; use ``replace_script`` and ``remove_script`` for those.
        """
        value = int(value)
        for bit in range(len(ITEM_SCRIPT_BITS), 16):
            if value >> bit & 1:
                self.properties.setdefault(bit, 0)
            else:
                self.properties.pop(bit, None)
        self.properties = dict(sorted(self.properties.items()))
        scripts = sum(1 << ITEM_SCRIPT_BITS[name] for name in self.entries())
        if value & 0xF != scripts:
            iris.warning(f"{self}: script flag bits {value & 0xF:#x} ignored, the scripts give {scripts:#x}.")

    def script_origin(self) -> int:
        """Record offset of the first script byte (right after the property words)."""
        return ITEM_WORDS + 2 * self.flags().bit_count()

    def script_word(self, name: ItemScript) -> int:
        """The record-relative offset ``build()`` writes for script ``name``."""
        record = self.build()
        slot = ITEM_WORDS + 2 * (self.flags() & ((1 << ITEM_SCRIPT_BITS[name]) - 1)).bit_count()
        return int.from_bytes(record[slot : slot + 2], "little")

    def replace_script(self, entry: ItemScript, items: list[ScriptItem]) -> None:
        """Replace one script, or add it if the item had none; blocks another script also uses stay.

        Adding a script sets its flag bit and inserts its word, so the record grows by the word and the script.
        """
        self.external_entries.pop(entry, None)
        if self.code is None:
            self.code = Script(L2BASM, [Label(entry), *block(items)])
        elif entry not in self.entries():
            self.code.body = [*self.code.body, Label(entry), *block(items)]
        else:
            replace_entry(self.code, entry, block(items))

    def remove_script(self, entry: ItemScript) -> None:
        """Drop one script: its flag bit and word go, and so does code only it reaches."""
        self.external_entries.pop(entry, None)
        if self.code is None or entry not in self.entries():
            return
        replace_entry(self.code, entry, [])
        self.code.body = [item for item in self.code.body if not (isinstance(item, Label) and item.name == entry)]

    def header_bytes(self, words: list[int]) -> bytes:
        return b"".join([
            self.usability.to_bytes(),
            self.item_types.to_bytes(),
            self.targeting.to_bytes(),
            self.icon.to_bytes(),
            self.sprite_index.to_bytes(),
            self.price.to_bytes(ItemObject.price, "little"),
            self.equip_types.to_bytes(),
            self.equipability.to_bytes(),
            self.flags().to_bytes(2, "little"),
            self.unknown2,
            *(word.to_bytes(2, "little") for word in words),
        ])

    def build(self) -> bytes:
        """The whole record: common bytes, property words in bit order, then the scripts (record-relative jumps)."""
        origin = self.script_origin()
        out = assemble(self.code, origin) if self.code is not None else None
        words = []
        for bit in range(16):
            name = _SCRIPT_BIT_NAMES.get(bit)
            if bit in self.properties:
                words.append(self.properties[bit])
            elif name is not None and name in self.external_entries:
                words.append(self.external_entries[name])
            elif name is not None and name in self.entries():
                assert out is not None, self
                words.append(origin + out.labels[name])
        return self.header_bytes(words) + (out.data if out is not None else b"")

    def get_effects(self) -> Iterator[tuple[bytes]]:
        """The property words (bits 4-15) in bit order, as the 2 bytes the record holds."""
        for bit, word in self.properties.items():
            self._warn_extra_increases(ItemEffects(1 << bit))
            yield (word.to_bytes(2, "little"),)

    def _warn_extra_increases(self, item_flag: ItemEffects) -> None:
        if ItemEffects.INCREASE_STR in item_flag:
            iris.warning(f"{item_flag=} also increases ATP (increases STR).")
        if ItemEffects.INCREASE_STR in item_flag:
            iris.warning(f"{item_flag=} also increases DFP (increases STR).")
        if ItemEffects.INCREASE_AGL in item_flag:
            iris.warning(f"{item_flag=} also increases DFP (increases AGL).")

    @property
    def is_coin_set(self) -> bool:
        return 0x18a <= self.index <= 0x18d

    def write(self) -> None:
        iris.debug(f"Writing Item {self.index} {self.name_pointer.name!r}")
        self.name_pointer.write()
        table = item_table()
        table.records[self.index] = self  # a copy (deepcopy in the item randomizers) replaces the cached record
        Item._cache.to_cache(self.index, self)
        table.write()


@cache
def _item_sources() -> list[RecordSource]:
    return item_sources(write_file)


@cache
def item_table() -> Table:
    """Every item record on ``rom_space.Table``. Growing past bank $96's free space moves the $42 table."""
    address = table_address(write_file, "item")
    records = [Item.from_index(i) for i in range(ItemObject.count)]
    return Table(
        "items",
        address,
        records,  # type: ignore[arg-type]
        table_bound(write_file, address),
        make_room=make_room_in_bank_96,
    )


def reset_item_table() -> None:
    item_table.cache_clear()
    _item_sources.cache_clear()
    Item._cache.clear()  # noqa: SLF001
