from helpers.files import read_file, write_file
from typing import Self
from abc_.pointers import AddressPointer, PointerList
from abc_.stats import RpgStats
from helpers.bits import read_little_int
from tables import CharLevelObject, CharacterObject, CharExpObject, InitialEquipObject, CharGrowthObject, ItemObject
from .item import Item


class CharacterLevel(PointerList):
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

    def write(self):
        write_file.seek(self.pointer)
        write_file.write(self.level.to_bytes(CharLevelObject.level, "little"))

class CharacterExperience(PointerList):
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

    def write(self):
        write_file.seek(self.pointer)
        write_file.write(self.xp.to_bytes(CharExpObject.xp, "little"))

class InitialEquipment(PointerList):
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

    def write(self):
        write_file.seek(self.pointer)
        write_file.write(self.weapon.index.to_bytes(InitialEquipObject.weapon, "little"))
        write_file.write(self.armor.index.to_bytes(InitialEquipObject.armor, "little"))
        write_file.write(self.shield.index.to_bytes(InitialEquipObject.shield, "little"))
        write_file.write(self.helmet.index.to_bytes(InitialEquipObject.helmet, "little"))
        write_file.write(self.ring.index.to_bytes(InitialEquipObject.ring, "little"))
        write_file.write(self.jewelry.index.to_bytes(InitialEquipObject.jewel, "little"))

class CharacterGrowth(PointerList):
    def __init__(
        self,
        health_points: int,
        mana_points: int,
        attack: int,
        defense: int,
        agility: int,
        intelligence: int,
        guts: int,
        magic_resistance: int,
    ) -> None:
        self.health_points = health_points
        self.mana_points = mana_points
        self.attack = attack
        self.defense = defense
        self.agility = agility
        self.intelligence = intelligence
        self.guts = guts
        self.magic_resistance = magic_resistance

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

class PlayableCharacter(AddressPointer):
    def __init__(self, name: str) -> None:
        self.name = name
        self.stats = RpgStats()
        self.xp = CharacterExperience(0)
        self.level = CharacterLevel(0)
        self.equipment = InitialEquipment(0, 0, 0, 0, 0, 0)

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

        inst.address = address
        inst.index = index
        inst.pointer = address + index * CHARACTER_SIZE
        return inst

    def write(self):
        # FIXME: some data are shuffled after writing.
        
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
