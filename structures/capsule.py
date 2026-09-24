from functools import cache
from typing import Self

from abc_.pointers import TablePointer
from abc_.stats import RpgStats
from enums.flags import Alignment
from helpers.bits import find_table_pointer, read_little_int
from helpers.files import read_file, write_file
from rom_space.table import Table
from scripting.core import Item, Script, assemble
from scripting.l2basm import parse_record
from scripting.l2basm.edit import replace_entry
from scripting.l2basm.helpers import block
from scripting.l2basm.records import capsule_records, read_record, table_address
from structures.capsule_attack_names import capsule_attack_names
from tables import CapAttackObject, CapsuleLevelObject, CapsuleObject


# Capsule record layout: a 0x2B-byte header, then the attack script, then the reaction script. The
# header ends with two u16 script offsets (relative to the record start): attack at +37 (always 0x2B)
# and reaction at +39. The record table stores u16 offsets relative to its own base, and script jumps
# are record-relative, so a record and everything it reaches must stay inside LoROM bank $97.
CAPSULE_HEADER_SIZE = 0x2B
# The shop pointer table follows the last capsule record. Its trailing zero space is the only free
# space in the bank; Spekkio/Kureji put extra shop data there, so relocation skips every shop target.
SHOP_TABLE = 0xBEE9F
SHOP_TABLE_MAX_ENTRIES = 80


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
        # Both L2BASM scripts as one body with ``attack``/``reaction`` entry labels (populated by from_table).
        # The record header stores their offsets as two u16s at record+37/+39.
        self.code: Script | None = None

    _cache: "dict[int, CapsuleMonster]" = {}  # noqa: RUF012 (per-class cache shared by capsule_table)

    @classmethod
    def from_index(cls, index: int) -> Self:
        if index in cls._cache:
            return cls._cache[index]  # type: ignore[return-value]
        return cls.from_table(table_address(write_file, "capsule"), index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        source = write_file  # the output ROM, so base-patch edits are what we read
        source.seek(address + 2 * index)
        pointer = address + int.from_bytes(source.read(2), "little")
        source.seek(pointer)

        name = source.read(CapsuleObject.name_text).decode()
        _zero = read_little_int(source, CapsuleObject.zero)
        class_ = read_little_int(source, CapsuleObject.capsule_class)
        alignment = Alignment(read_little_int(source, CapsuleObject.alignment))
        start_skills = source.read(CapsuleObject.start_skills) # list of 3, TODO figure out how these are stored. (Battle scripts?)
        upgrade_skills = source.read(CapsuleObject.upgrade_skills) # list of 3, TODO figure out how these are stored. (Battle scripts?)
        hp = read_little_int(source, CapsuleObject.hp)
        attack = read_little_int(source, CapsuleObject.attack)
        defense = read_little_int(source, CapsuleObject.defense)
        strength = read_little_int(source, CapsuleObject.strength)
        agility = read_little_int(source, CapsuleObject.agility)
        intelligence = read_little_int(source, CapsuleObject.intelligence)
        guts = read_little_int(source, CapsuleObject.guts)
        magic_resistance = read_little_int(source, CapsuleObject.magic_resistance)
        hp_factor = read_little_int(source, CapsuleObject.hp_factor)
        strength_factor = read_little_int(source, CapsuleObject.strength_factor)
        agility_factor = read_little_int(source, CapsuleObject.agility_factor)
        intelligence_factor = read_little_int(source, CapsuleObject.intelligence_factor)
        guts_factor = read_little_int(source, CapsuleObject.guts_factor)
        magic_resistance_factor = read_little_int(source, CapsuleObject.magic_resistance_factor)
        # Here follow 2 bytes that are always 0x00 0x00.
        _zero = read_little_int(source, 1)
        _zero = read_little_int(source, 1)
        _attack_script_offset = read_little_int(source, 2)  # the entry offsets come from capsule_records below
        _reaction_script_offset = read_little_int(source, 2)
        _zero = read_little_int(source, 2) # 2 Empty Bytes
        # The following sequences were found
        # 00 00 2B 00 > Used by not just capsule monsters, but these values are around
        # the same area in the ROM. It's clearly some indicator of something.
        # Seems like an attack script offset pattern? (at least for cap monsters it is.)
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
        # Both scripts parse into one body: the attack script's handler blocks (Target/Attack, Defend, Flee,
        # learnable attacks) sit between it and the reaction script and are reached only through jumps.
        rec = capsule_records(source)[index]
        parsed = parse_record(read_record(source, rec), rec.entries, start=CAPSULE_HEADER_SIZE)
        inst.code = parsed.script
        # TODO: Add a CapsuleStats class to hold hp, attack, defense, agility, intelligence, guts, magic_resistance
        # They don't seem to contain any mana, level are stored on CapsuleLevel, xp and gold aren't present on capsule monsters.
        # Would also simplify with self.stats.write(), rather than writing each stat individually.
        # Should also include self.strength
        inst.stats = RpgStats(
            health_points=hp,
            attack=attack,
            defense=defense,
            agility=agility,
            intelligence=intelligence,
            guts=guts,
            magic_resistance=magic_resistance,
            mana_points=0,  # capsules have no MP
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
        cls._cache[index] = inst
        return inst

    def set_scripts(self, attack: list[Item] | None = None, reaction: list[Item] | None = None) -> None:
        """Replace the attack and/or reaction script; ``write()`` saves them. ``None`` keeps a script.

        Blocks the other script still reaches stay.
        """
        assert self.code is not None
        if attack is not None:
            replace_entry(self.code, "attack", block(attack))
        if reaction is not None:
            replace_entry(self.code, "reaction", block(reaction))

    def build(self) -> bytes:
        """The whole record: header, then both scripts (jumps are record-relative)."""
        assert self.code is not None
        out = assemble(self.code, CAPSULE_HEADER_SIZE)
        attack = CAPSULE_HEADER_SIZE + out.labels["attack"]
        reaction = CAPSULE_HEADER_SIZE + out.labels["reaction"]
        return self._header(attack, reaction) + out.data

    def write(self) -> None:
        """Write every capsule record that changed (in place, or moved inside bank $97), then the attack names."""
        table = capsule_table()
        table.write()
        self.pointer = table.starts()[self.index]
        capsule_attack_names.write()

    def _header(self, attack_offset: int, reaction_offset: int) -> bytes:
        """The 0x2B-byte record header built from this instance's fields."""
        fields = [
            self.class_, self.alignment, *self.start_skills, *self.upgrade_skills,
            self.stats.health_points, self.stats.attack, self.stats.defense, self.strength,
            self.stats.agility, self.stats.intelligence, self.stats.guts, self.stats.magic_resistance,
            self.hp_factor, self.strength_factor, self.agility_factor,
            self.intelligence_factor, self.guts_factor, self.magic_resistance_factor,
        ]
        header = (
            self.name.encode()
            + b"\x00"
            + bytes(int(field) for field in fields)
            + b"\x00\x00"  # always zero; purpose unknown
            + attack_offset.to_bytes(2, "little")
            + reaction_offset.to_bytes(2, "little")
            + b"\x00\x00"
        )
        if len(header) != CAPSULE_HEADER_SIZE:
            msg = f"Capsule {self.index} header is {len(header)} bytes, expected {CAPSULE_HEADER_SIZE}."
            raise ValueError(msg)
        return header

    def fix_animation(self) -> None:
        if self.animation in self.animation_fixes:
            self.animation = self.animation_fixes[self.animation]


def _shop_targets() -> set[int]:
    """Addresses the shop table points at. Spekkio and Kureji put shop data in bank $97's free gap."""
    targets = set()
    for i in range(SHOP_TABLE_MAX_ENTRIES):
        write_file.seek(SHOP_TABLE + 2 * i)
        targets.add(SHOP_TABLE + int.from_bytes(write_file.read(2), "little"))
    return targets


@cache
def capsule_table() -> Table:
    """Every capsule record on ``rom_space.Table``. Records move only within bank $97 (HER-200 moves the table)."""
    address = table_address(write_file, "capsule")
    records = [CapsuleMonster.from_index(i) for i in range(CapsuleObject.count)]
    return Table("capsules", address, records, SHOP_TABLE, pinned=_shop_targets())  # type: ignore[arg-type]


def reset_capsule_table() -> None:
    capsule_table.cache_clear()
    CapsuleMonster._cache.clear()  # noqa: SLF001
