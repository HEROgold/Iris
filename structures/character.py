from collections.abc import Iterable, MutableSequence
from typing import Self, overload

from abc_.pointers import Pointer, TablePointer
from abc_.stats import RpgStats
from helpers.bits import read_little_int
from helpers.files import read_file, write_file
from tables import CharacterObject, CharExpObject, CharGrowthObject, CharLevelObject, InitialEquipObject

from .item import Item
from .spell import Spell


# Bytes between a character's level offset and the start of the spell list:
# level(1) + status(1) + unknown $7E:1854 (2). The list itself is 0xFF-terminated spell indices.
STARTING_SPELLS_GAP = 4
SPELL_TERMINATOR = 0xFF
# A template record's tail, counted from its first equipment byte: 6 equipment slots (12) +
# dungeon item (2) + a 0x00 record separator (1). Used to find the end of the last record.
RECORD_TAIL_AFTER_EQUIP = 15


class CharacterLevel(Pointer):
    def __init__(self, level: int) -> None:
        self.level = level

    def __repr__(self) -> str:
        return f"<CharacterLevel: {self.level}>"

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        read_file.seek(pointer)
        level = read_little_int(read_file, CharLevelObject.level)
        inst = cls(level)
        super().__init__(inst, pointer)
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.level.to_bytes(CharLevelObject.level, "little"))

class CharacterExperience(Pointer):
    def __init__(self, xp: int) -> None:
        self.xp = xp

    def __repr__(self) -> str:
        return f"<CharacterExperience: {self.xp}>"

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        read_file.seek(pointer)
        xp = read_little_int(read_file, CharExpObject.xp)
        inst = cls(xp)
        super().__init__(inst, pointer)
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.xp.to_bytes(CharExpObject.xp, "little"))

class InitialEquipment(Pointer):
    def __init__(self, weapon: int, armor: int, shield: int, helmet: int, ring: int, jewelry: int) -> None:
        self.weapon = Item.from_index(weapon)
        self.armor = Item.from_index(armor)
        self.shield = Item.from_index(shield)
        self.helmet = Item.from_index(helmet)
        self.ring = Item.from_index(ring)
        self.jewelry = Item.from_index(jewelry)

    def __repr__(self) -> str:
        return f"<InitialEquipment: {self.weapon}, {self.armor}, {self.shield}, {self.helmet}, {self.ring}, {self.jewelry}>"

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        read_file.seek(pointer)
        weapon_pointer = read_little_int(read_file, InitialEquipObject.weapon)
        armor_pointer = read_little_int(read_file, InitialEquipObject.armor)
        shield_pointer = read_little_int(read_file, InitialEquipObject.shield)
        helmet_pointer = read_little_int(read_file, InitialEquipObject.helmet)
        ring_pointer = read_little_int(read_file, InitialEquipObject.ring)
        jewelry_pointer = read_little_int(read_file, InitialEquipObject.jewel)
        inst = cls(weapon_pointer, armor_pointer, shield_pointer, helmet_pointer, ring_pointer, jewelry_pointer)
        super().__init__(inst, pointer)
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.weapon.index.to_bytes(InitialEquipObject.weapon, "little"))
        write_file.write(self.armor.index.to_bytes(InitialEquipObject.armor, "little"))
        write_file.write(self.shield.index.to_bytes(InitialEquipObject.shield, "little"))
        write_file.write(self.helmet.index.to_bytes(InitialEquipObject.helmet, "little"))
        write_file.write(self.ring.index.to_bytes(InitialEquipObject.ring, "little"))
        write_file.write(self.jewelry.index.to_bytes(InitialEquipObject.jewel, "little"))

class StartingSpells(MutableSequence[Spell], Pointer):
    """A character's new-game spell list: the ``0xFF``-terminated block in the party template.

    Behaves like a ``list[Spell]`` -- iterate, index, slice, ``append``, etc. -- while validating that every
    element is a :class:`Spell`. Internally it stores only the raw spell *indices* and builds
    :class:`Spell` objects lazily, so merely constructing one (e.g. for every character in
    :meth:`PlayableCharacter.from_table`) never decodes a spell. Nothing touches the ROM until :meth:`write`.
    """

    def __init__(self, spells: Iterable[Spell]) -> None:
        self._indices: list[int] = [self._validated(spell).index for spell in spells]
        # Byte length of the pristine on-ROM list (spell indices + the 0xFF terminator). Kept separate from
        # the in-memory list so write() can reflow later records against the ORIGINAL length; overwritten by
        # from_pointer to the value actually read from the ROM.
        self._rom_length = len(self._indices) + 1

    def __repr__(self) -> str:
        return f"<StartingSpells: {self._indices}>"

    @property
    def spells(self) -> list[Spell]:
        """The spells as :class:`Spell` objects (built on demand from the stored indices)."""
        return [Spell.from_index(index) for index in self._indices]

    @staticmethod
    def _validated(spell: Spell) -> Spell:
        if not isinstance(spell, Spell):
            msg = f"starting spell must be a Spell, got {type(spell).__name__}"
            raise TypeError(msg)
        return spell

    @overload
    def __getitem__(self, index: int) -> Spell: ...
    @overload
    def __getitem__(self, index: slice) -> list[Spell]: ...
    def __getitem__(self, index: int | slice) -> Spell | list[Spell]:
        if isinstance(index, slice):
            return [Spell.from_index(i) for i in self._indices[index]]
        return Spell.from_index(self._indices[index])

    @overload
    def __setitem__(self, index: int, value: Spell) -> None: ...
    @overload
    def __setitem__(self, index: slice, value: Iterable[Spell]) -> None: ...
    def __setitem__(self, index: int | slice, value: Spell | Iterable[Spell]) -> None:
        if isinstance(index, slice):
            self._indices[index] = [self._validated(spell).index for spell in value]  # type: ignore[union-attr]
        else:
            self._indices[index] = self._validated(value).index  # type: ignore[union-attr]

    def __delitem__(self, index: int | slice) -> None:
        del self._indices[index]

    def __len__(self) -> int:
        return len(self._indices)

    def insert(self, index: int, value: Spell) -> None:
        self._indices.insert(index, self._validated(value).index)

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        read_file.seek(pointer)
        indices: list[int] = []
        while (value := read_file.read(1)[0]) != SPELL_TERMINATOR:
            indices.append(value)
        inst = cls([])
        inst._indices = indices
        inst._rom_length = len(indices) + 1
        Pointer.__init__(inst, pointer)
        return inst

    def write(self) -> None:
        """Replace this character's new-game spell list in the output ROM, reflowing the records after it.

        The seven characters' template records are packed back-to-back and the game parses them
        sequentially, so a spell list that changes length shifts every byte after it -- this character's
        own EXP/equipment and every later character's record. We reproduce that shift in the output ROM;
        any growth is absorbed by the unused padding after the last record.

        This is a **terminal write** for the party-template block: it copies the record tail from the
        pristine source ROM, so it must run BEFORE the fixed-offset EXP/equipment writers in
        :meth:`PlayableCharacter.write` (otherwise it would clobber their values back to vanilla). Grow at
        most one spell list per run; growing a list moves Iris' read-side EXP/equipment offsets out of sync
        with the shifted layout, so a grown character's other template fields can no longer be written.
        """
        list_start = self.pointer
        old_len = self._rom_length  # pristine list length read from the source ROM (+ 0xFF terminator)
        new_bytes = bytes(self._indices) + bytes([SPELL_TERMINATOR])

        block_end = InitialEquipObject.pointers[-1] + RECORD_TAIL_AFTER_EQUIP  # end of last record (exclusive)
        read_file.seek(list_start + old_len)
        tail = read_file.read(block_end - (list_start + old_len))  # this + later characters, shifted

        write_file.seek(list_start)
        write_file.write(new_bytes + tail)

class CharacterGrowth(Pointer):
    def __init__(
        self,
        health_points: int,
        mana_points: int,
        strength: int,
        agility: int,
        intelligence: int,
        guts: int,
        magic_resistance: int,
        unk: int,
    ) -> None:
        self.health_points = health_points
        self.mana_points = mana_points
        self.attack = strength
        self.agility = agility
        self.intelligence = intelligence
        self.guts = guts
        self.magic_resistance = magic_resistance
        self.unk = unk

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        read_file.seek(pointer)
        inst = cls(
            read_little_int(read_file, CharGrowthObject.hp),
            read_little_int(read_file, CharGrowthObject.mp),
            read_little_int(read_file, CharGrowthObject.str),
            read_little_int(read_file, CharGrowthObject.agl),
            read_little_int(read_file, CharGrowthObject.int),
            read_little_int(read_file, CharGrowthObject.gut),
            read_little_int(read_file, CharGrowthObject.mgr),
            read_little_int(read_file, CharGrowthObject.unk),
        )
        super().__init__(inst, pointer)
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.health_points.to_bytes(CharGrowthObject.hp, "little"))
        write_file.write(self.mana_points.to_bytes(CharGrowthObject.mp, "little"))
        write_file.write(self.attack.to_bytes(CharGrowthObject.str, "little"))
        write_file.write(self.agility.to_bytes(CharGrowthObject.agl, "little"))
        write_file.write(self.intelligence.to_bytes(CharGrowthObject.int, "little"))
        write_file.write(self.guts.to_bytes(CharGrowthObject.gut, "little"))
        write_file.write(self.magic_resistance.to_bytes(CharGrowthObject.mgr, "little"))
        write_file.write(self.unk.to_bytes(CharGrowthObject.unk, "little"))

NAME_LENGTH = 6
CHARACTER_SIZE = sum([
    CharacterObject.hp,
    CharacterObject.mp,
    CharacterObject.str,
    CharacterObject.agl,
    CharacterObject.int,
    CharacterObject.gut,
    CharacterObject.mgr,
])

class PlayableCharacter(TablePointer):
    def __init__(self, name: str) -> None:
        self.name = name
        self.stats = RpgStats()
        self.xp = CharacterExperience(0)
        self.level = CharacterLevel(0)
        self.equipment = InitialEquipment(0, 0, 0, 0, 0, 0)
        self.starting_spells = StartingSpells([])

    def __repr__(self) -> str:
        return f"<PlayableCharacter: {self.name}>"

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_table(CharacterObject.address, index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        level_start = CharLevelObject.pointers[index]
        name_start = level_start - NAME_LENGTH
        read_file.seek(name_start)

        name = read_file.read(NAME_LENGTH).decode("ascii")
        name = name.split("\0")[0]

        inst = cls(name)

        read_file.seek(CharacterObject.address + index * CHARACTER_SIZE)

        inst.stats = RpgStats(
            health_points = read_little_int(read_file, CharacterObject.hp),
            mana_points = read_little_int(read_file, CharacterObject.mp),
            attack = read_little_int(read_file, CharacterObject.str),
            agility = read_little_int(read_file, CharacterObject.agl),
            intelligence = read_little_int(read_file, CharacterObject.int),
            guts = read_little_int(read_file, CharacterObject.gut),
            magic_resistance = read_little_int(read_file, CharacterObject.mgr),
            defense=0, # Unset values
            level=0, # Unset values
            xp=0, # Unset values
            gold=0, # Unset values
        )
        inst.xp = CharacterExperience.from_pointer(CharExpObject.pointers[index])
        inst.level = CharacterLevel.from_pointer(CharLevelObject.pointers[index])
        inst.equipment = InitialEquipment.from_pointer(InitialEquipObject.pointers[index])
        inst.starting_spells = StartingSpells.from_pointer(CharLevelObject.pointers[index] + STARTING_SPELLS_GAP)

        inst.address = address
        inst.index = index
        inst.pointer = address + index * CHARACTER_SIZE
        return inst

    def write(self) -> None:
        # FIXME: some data are shuffled after writing.

        # Reflow the party-template block FIRST: it copies this record's tail (incl. EXP/equipment) from the
        # pristine ROM, so the fixed-offset xp/equipment writers below must run afterwards to keep their values.
        self.starting_spells.write()

        level_start = CharLevelObject.pointers[self.index]
        name_start = level_start - NAME_LENGTH
        write_file.seek(name_start)
        write_file.write(self.name.encode("ascii"))

        write_file.seek(CharacterObject.address + self.index * CHARACTER_SIZE)
        write_file.write(self.stats.health_points.to_bytes(CharacterObject.hp, "little"))
        write_file.write(self.stats.mana_points.to_bytes(CharacterObject.mp, "little"))
        write_file.write(self.stats.attack.to_bytes(CharacterObject.str, "little"))
        write_file.write(self.stats.agility.to_bytes(CharacterObject.agl, "little"))
        write_file.write(self.stats.intelligence.to_bytes(CharacterObject.int, "little"))
        write_file.write(self.stats.guts.to_bytes(CharacterObject.gut, "little"))
        write_file.write(self.stats.magic_resistance.to_bytes(CharacterObject.mgr, "little"))
        self.xp.write()
        self.level.write()
        self.equipment.write()

    # stolen code that should fix item icons
    # def set_appropriate_item_icon(self: Self):
    #     item_index = int(self.item_index, 0x10)
    #     if self.icon_code == "default":
    #         item = Items.get(item_index)
    #         assert not item.sprite & 0x80
    #         if item.sprite & 0x40:
    #             sprite_class = 0x18
    #         else:
    #             sprite_class = 0x0A
    #         self.icon_code = f"{sprite_class:0>2X}-{item.sprite & 0x3F:0>2x}"
    #     return self
