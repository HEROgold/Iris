from helpers.files import read_file, write_file
from typing import Self
from abc_.pointers import TablePointer
from abc_.stats import RpgStats
from enums.flags import Alignment
from helpers.bits import find_table_pointer, read_little_int
from tables import CapsuleLevelObject, CapsuleObject, CapAttackObject
# from .sprites import CapsulePallette


class CapsuleLevel(TablePointer):
    def __init__(self, level: int) -> None:
        self.level = level

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_table(CapsuleLevelObject.address, index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        read_file.seek(address + index)
        inst = cls(level=read_little_int(read_file, CapsuleLevelObject.level))
        inst.address = address
        inst.index = index
        inst.pointer = address + index
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.level.to_bytes(1))

class CapsuleAttack(TablePointer):
    unknown: bytes

    def __init__(self, animation: int) -> None:
        self.animation = animation

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        # TODO: confirm this is correct.
        pointer = find_table_pointer(address, index)
        read_file.seek(pointer)

        _unknown = read_file.read(CapAttackObject.unknown)
        animation = read_little_int(read_file, CapAttackObject.animation)

        inst = cls(animation)
        inst.unknown = _unknown
        super().__init__(inst, address, index)
        return inst

    def write(self) -> None:
        # FIXME: Something is wrong here
        write_file.seek(self.pointer)
        write_file.write(self.unknown)
        write_file.write(bytes(self.animation.to_bytes(CapAttackObject.animation, "little")))


class CapsuleMonster(TablePointer):
    # Banned: Fixed
    animation_fixes = {
        0x84: 0x8A,
        0x8D: 0x83,
        0x8E: 0x87,
    }

    def __init__(
        self,
        name: str,
        class_: int,
        alignment: Alignment,
        start_skills: bytes,  # TODO: figure out how to handle this. > probably references CapsuleAttack?
        upgrade_skills: bytes,  # TODO: figure out how to handle this.
    ) -> None:
        self.name = name
        self.class_ = class_
        self.alignment = alignment
        self.start_skills = start_skills
        self.upgrade_skills = upgrade_skills
        self.stats = RpgStats()
        self.hp_factor = -1
        self.strength_factor = -1
        self.agility_factor = -1
        self.intelligence_factor = -1
        self.guts_factor = -1
        self.magic_resistance_factor = -1
        self.strength = -1

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_table(CapsuleObject.address, index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        pointer = find_table_pointer(address, index)
        read_file.seek(pointer)

        name = read_file.read(CapsuleObject.name_text).decode()  # type: ignore
        _zero = read_little_int(read_file, CapsuleObject.zero)
        class_ = read_little_int(read_file, CapsuleObject.capsule_class)
        alignment = Alignment(read_little_int(read_file, CapsuleObject.alignment))
        start_skills = read_file.read(CapsuleObject.start_skills)  # type: ignore # list of 3, TODO figure out how these are stored. (Battle scripts?) 
        upgrade_skills = read_file.read(CapsuleObject.upgrade_skills)  # type: ignore # list of 3, TODO figure out how these are stored. (Battle scripts?) 
        hp = read_little_int(read_file, CapsuleObject.hp)
        attack = read_little_int(read_file, CapsuleObject.attack)
        defense = read_little_int(read_file, CapsuleObject.defense)
        strength = read_little_int(read_file, CapsuleObject.strength)
        agility = read_little_int(read_file, CapsuleObject.agility)
        intelligence = read_little_int(read_file, CapsuleObject.intelligence)
        guts = read_little_int(read_file, CapsuleObject.guts)
        magic_resistance = read_little_int(read_file, CapsuleObject.magic_resistance)
        hp_factor = read_little_int(read_file, CapsuleObject.hp_factor)
        strength_factor = read_little_int(read_file, CapsuleObject.strength_factor)
        agility_factor = read_little_int(read_file, CapsuleObject.agility_factor)
        intelligence_factor = read_little_int(read_file, CapsuleObject.intelligence_factor)
        guts_factor = read_little_int(read_file, CapsuleObject.guts_factor)
        magic_resistance_factor = read_little_int(read_file, CapsuleObject.magic_resistance_factor)
        # Here follow 2 bytes that are always 0x00 0x00.
        # We may want to check if this is always the case.
        # TODO: figure out the following bytes.
        _zero = read_little_int(read_file, 1)
        _zero = read_little_int(read_file, 1)
        _1 = read_little_int(read_file, 1) # 1 Byte with data, Always 0x2B, (BattleScript offset?)
        assert 0x2B == _1
        _zero = read_little_int(read_file, 1) # 1 Empty Byte,
        _2 = read_little_int(read_file, 1) # 1 Byte with data. Mana?
        _zero = read_little_int(read_file, 3) # 3 Empty Bytes,
        # The following sequences were found
        # 00 00 2B 00 > Used by not just capsule monsters, but these values are around
        # the same area in the ROM. It's clearly some indicator of something.
        # 00 00 2B 00 > For every capsule monster. Followed by:
        # 49 00 00 00 > HardHat, ArmorDog
        # 4F 00 00 00 > FoomyS, Shaggy, Raddisher
        # 70 00 00 00 > RedDragon, FireBird
        # 72 00 00 00 > RedFish, Myconido, WingedLion
        # 74 00 00 00 > SkyDragon
        # 76 00 00 00 > GoldFox, BlueTitan, Wolfman, Centaur
        # 78 00 00 00 > FoomyM, Sprite, RedCap
        # 81 00 00 00 > Unicorn,
        # 83 00 00 00 > Toadie, SeaGiant, MiniImp, BigImp, BlazeDragon
        # 85 00 00 00 > FoomyL, Cupid, Stonehead
        # 86 00 00 00 > FishHead,
        # 89 00 00 00 > FoomyH, Giant
        # 7F 00 00 00 > BlueBird, WingedHorse, GreenTitan, WingLizard
        # 9F 00 00 00 > Twinkle,

        # Only 7 different monsters exist, 35 total monsters exist.
        # mod 35/7 = 5
        level = CapsuleLevel.from_table(CapsuleLevelObject.address, index//5)
        # palette = CapsulePallette.from_table(address, offset)  # Pseudo

        inst = cls(
            name=name,
            class_=class_,
            alignment=alignment,
            start_skills=start_skills,
            upgrade_skills=upgrade_skills,
        )
        super().__init__(inst, address, index)
        inst.pointer = pointer
        inst.stats = RpgStats(
            health_points=hp,
            attack=attack,
            defense=defense,
            agility=agility,
            intelligence=intelligence,
            guts=guts,
            magic_resistance=magic_resistance,
            mana_points=_2,
            level=level.level,
            xp=0, # TODO: are these stored somewhere?
            gold=0, # TODO: are these stored somewhere?
        )
        inst.strength = strength  # Affects the damage and defense of the monster.
        inst.hp_factor = hp_factor
        inst.strength_factor = strength_factor
        inst.agility_factor = agility_factor
        inst.intelligence_factor = intelligence_factor
        inst.guts_factor = guts_factor
        inst.magic_resistance_factor = magic_resistance_factor
        return inst

    def write(self):
        write_file.seek(self.pointer)
        write_file.write(self.name.encode())
        write_file.write(b"\x00")
        write_file.write(self.class_.to_bytes())
        write_file.write(self.alignment.to_bytes())
        write_file.write(self.start_skills)
        write_file.write(self.upgrade_skills)
        write_file.write(self.stats.health_points.to_bytes())
        write_file.write(self.stats.attack.to_bytes())
        write_file.write(self.stats.defense.to_bytes())
        write_file.write(self.strength.to_bytes())
        write_file.write(self.stats.agility.to_bytes())
        write_file.write(self.stats.intelligence.to_bytes())
        write_file.write(self.stats.guts.to_bytes())
        write_file.write(self.stats.magic_resistance.to_bytes())
        write_file.write(self.hp_factor.to_bytes())
        write_file.write(self.strength_factor.to_bytes())
        write_file.write(self.agility_factor.to_bytes())
        write_file.write(self.intelligence_factor.to_bytes())
        write_file.write(self.guts_factor.to_bytes())
        write_file.write(self.magic_resistance_factor.to_bytes())
        write_file.write(b"\x00")
        write_file.write(b"\x00")
        write_file.write(b"\x2B")

        write_file.write(b"\x00")
        write_file.write(self.stats.mana_points.to_bytes())
        write_file.write(b"\x00")


    def fix_animation(self) -> None:
        if self.animation in self.animation_fixes:
            self.animation = self.animation_fixes[self.animation]
