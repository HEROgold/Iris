from bitstring import BitArray
from enums.flags import ItemFlags1, MenuIcon, Targeting
from config import BYTE_LENGTH, MAX_2_BYTE, SHIFT_BYTE
from helpers.files import read_file, write_file
from typing import Self
from abc_.flags import Usable
from abc_.flags import Equipable
from structures.word import Word
from tables import ItemObject
from enums.flags import EquipTypes, EquipableCharacter, ItemFlags2, Usability
from abc_.pointers import AddressPointer
from helpers.bits import find_table_pointer, read_little_int
from tables import ItemNameObject
from logger import iris

ITEM_SIZE = sum(
    [
        1,  #ItemObject.usability,
        1,  #ItemObject.unknown,
        ItemObject.targetting,
        ItemObject.icon,
        ItemObject.sprite,
        ItemObject.price,
        1,  #ItemObject.item_type,
        1,  #ItemObject.equipability,
        1,  #ItemObject.misc1,
        1,  #ItemObject.misc2,
        ItemObject.zero,
    ]
)

class Item(AddressPointer, Equipable, Usable):
    price: int
    equip_types: EquipTypes
    usability: Usability
    targeting: Targeting
    icon: MenuIcon
    equipability: EquipableCharacter
    item_flags1: ItemFlags1
    item_flags2: ItemFlags2
    # Writing data.
    unknown2: bytes

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

    def __init__(self, name: str, item_index: int, sprite_index: int) -> None:
        self.name = name
        self.index = item_index
        self.sprite_index = sprite_index

    def __repr__(self) -> str:
        return f"<Item: {self.name}, {self.index}>"

    def __bytes__(self) -> bytes:
        """Return the index of any item, without 0x00 bytes."""
        return self.index.to_bytes(2, "little").strip(b"\x00")

    def _validate_requirements(self):
        assert self.price is not None
        assert self.equip_types is not None
        assert self.usability is not None
        assert self.targeting is not None
        assert self.icon is not None
        assert self.equipability is not None
        assert self.item_flags1 is not None
        assert self.item_flags2 is not None
        self._validate_effects()
        self.description

    def _validate_effects(self):
        effects = list(self.get_effects())
        effect_validity = (bool(effects) == (bool(self.item_flags2)))
        assert effect_validity

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_table(ItemObject.address, index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        pointer = find_table_pointer(ItemObject.address, index)
        read_file.seek(pointer)

        usability = Usability.from_byte(read_file.read(1))
        misc1 = read_file.read(1)
        targeting = read_file.read(ItemObject.targetting)
        icon = read_file.read(ItemObject.icon)
        sprite = read_little_int(read_file, ItemObject.sprite)  # 00 for no-chest items, and coins.
        price = read_little_int(read_file, ItemObject.price)
        item_type = EquipTypes.from_byte(read_file.read(1))
        equipability = EquipableCharacter.from_byte(read_file.read(1))
        misc2 = read_file.read(2)
        unknown2 = read_file.read(ItemObject.zero)

        if index <= ItemNameObject.count:
            name_pointer = ItemNameObject.address + index * ItemNameObject.name_text # type: ignore name_text is actually an int.
            read_file.seek(name_pointer) # type: ignore name_text is actually an int.
            name = read_file.read(ItemNameObject.name_text).decode("ascii") # type: ignore name_text is actually an int.
        else:
            name = f"UnkItem {index}"
            iris.warning(f"Item name not found for {index=}")

        inst = cls(name, index, sprite)
        AddressPointer.__init__(inst, address, index)
        Equipable.__init__(inst, item_type)
        Usable.__init__(inst, usability)
        inst.pointer = pointer

        inst.equip_types = item_type
        inst.item_flags1 = ItemFlags1.from_byte(misc1)
        inst.item_flags2 = ItemFlags2.from_bytes(misc2)
        inst.targeting = Targeting.from_byte(targeting)
        inst.icon = MenuIcon.from_byte(icon)
        inst.price = price
        inst.equipability = equipability
        inst.unknown2 = unknown2 # 0x0000 for all items.
        inst._validate_requirements()
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


    def get_misc_pointers(self) -> list[int]:
        """Get the pointers to the item's effect bytes"""
        # TODO: Verify, seems to work (correct addresses from reference L2ItemDataFormat.txt)
        table_address = 0xB551C
        # For each bit that is set, 2 extra bytes exist.
        offset = BitArray(self.item_flags2.to_bytes(2))
        # right to left in binary, offset is the position of every bit set (*2, pointers are 2 bytes).
        offsets = [
            i
            for i in range(16)
            if offset.uint & (1 << i & 0xFFFF)
        ]
        effect_pointers = [
            table_address + i
            for i in offsets
        ]
        return effect_pointers

    def get_effect_bytes(self):
        """Get the bytes defining the item's effect.
        The found values correspond to the item's effect,
        - increase stat by found value
        - IP attack index
        - animation index
        - etc..."""
        # TODO: Verify, seems to work (correct addresses from reference L2ItemDataFormat.txt)
        effect_pointers = self.get_misc_pointers()
        for effect in effect_pointers:
            read_file.seek(effect)
            effect_bytes = read_file.read(2)  # Assuming 2 bytes per effect
            yield effect_bytes

    def get_effects(self):
        """Get the effect values and definitions for the item."""
        # For each bit that is set, a effect is returned.
        bits = BitArray(self.item_flags2.to_bytes(2))
        effects = self.get_effect_bytes()
        for i, bit in enumerate(reversed(bits.bin)):
            if bit == "1":
                value = 1 << i
                item_flag = ItemFlags2(value) if value < 0x0F else ItemFlags2(value >> 4)
                self._warn_extra_increases(item_flag)
                yield next(effects),

    def _warn_extra_increases(self, item_flag: ItemFlags2):
        if ItemFlags2.INCREASE_STR in item_flag:
            iris.warning(f"{item_flag=} also increases ATP (increases STR).")
        if ItemFlags2.INCREASE_STR in item_flag:
            iris.warning(f"{item_flag=} also increases DFP (increases STR).")
        if ItemFlags2.INCREASE_AGL in item_flag:
            iris.warning(f"{item_flag=} also increases DFP (increases AGL).") 

    @property
    def is_coin_set(self):
        return 0x18a <= self.index <= 0x18d

    def write(self) -> None:
        write_file.seek(ItemNameObject.address + self.index * ItemNameObject.name_text) # type: ignore[reportOperatorIssue]
        write_file.write(self.name.encode("ascii"))

        write_file.seek(self.pointer)
        write_file.write(self.usability.to_bytes())
        write_file.write(self.item_flags1.to_bytes())
        write_file.write(self.targeting.to_bytes())
        write_file.write(self.icon.to_bytes())
        write_file.write(self.sprite_index.to_bytes())
        write_file.write(self.price.to_bytes(ItemObject.price, "little"))
        write_file.write(self.equip_types.to_bytes())
        write_file.write(self.equipability.to_bytes())
        write_file.write(self.item_flags2.to_bytes(2, "little")[::-1]) # Might need to swap the bytes first?
        write_file.write(self.unknown2)
