from typing import Self

from abc_.pointers import TablePointer
from abc_.stats import RpgStats
from enums.flags import Alignment
from helpers.bits import find_table_pointer, read_little_int
from helpers.files import read_file, write_file
from helpers.relocate import write_relocatable
from structures.battle_builder import Node, assemble_at
from structures.battlescript import BattleScript, ScriptType, rebase_jumps
from structures.capsule_attack_names import capsule_attack_names
from tables import CapAttackObject, CapsuleLevelObject, CapsuleObject


# Capsule record layout: a 0x2B-byte header, then the attack script, then the reaction script. The
# header ends with two u16 script offsets (relative to the record start): attack at +37 (always 0x2B)
# and reaction at +39. The record table stores u16 offsets relative to its own base, and script jumps
# are record-relative, so a record and everything it reaches must stay inside LoROM bank $97.
CAPSULE_HEADER_SIZE = 0x2B
CAPSULE_REACTION_FIELD = 39
CAPSULE_BANK_END = 0xC0000
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
        # L2BASM scripts (populated by from_table): capsules store an attack- and a
        # reaction-script offset as two u16s at record+37/+39 (see battlescript.py / lufia2.hexpat).
        self.attack_script: BattleScript | None = None
        self.reaction_script: BattleScript | None = None
        # Pending script replacements from set_scripts(); write() assembles them.
        self._attack_node: Node | None = None
        self._reaction_node: Node | None = None

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_table(CapsuleObject.address, index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        # attack_script / reaction_script are built below (read side done).
        # TODO: persist them in write() + stop routing the reaction offset through mana_points. See TODO.md.
        pointer = find_table_pointer(address, index)
        read_file.seek(pointer)

        name = read_file.read(CapsuleObject.name_text).decode()
        _zero = read_little_int(read_file, CapsuleObject.zero)
        class_ = read_little_int(read_file, CapsuleObject.capsule_class)
        alignment = Alignment(read_little_int(read_file, CapsuleObject.alignment))
        start_skills = read_file.read(CapsuleObject.start_skills) # list of 3, TODO figure out how these are stored. (Battle scripts?)
        upgrade_skills = read_file.read(CapsuleObject.upgrade_skills) # list of 3, TODO figure out how these are stored. (Battle scripts?)
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
        _zero = read_little_int(read_file, 1)
        _zero = read_little_int(read_file, 1)
        attack_script_offset = read_little_int(read_file, 1)
        assert attack_script_offset == 0x2B
        _zero = read_little_int(read_file, 1) # 1 Empty Byte
        reaction_script_offset = read_little_int(read_file, 1)
        _zero = read_little_int(read_file, 3) # 3 Empty Bytes
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
        # L2BASM scripts (offsets are relative to the record start == inst.pointer).
        # BattleScript.read follows branches, so the disassembly spans the attack script's
        # handler blocks (Target/Attack, Defend, Flee) that sit between it and the reaction script.
        inst.attack_script = BattleScript(inst, attack_script_offset, ScriptType.ATTACK)
        inst.reaction_script = BattleScript(inst, reaction_script_offset, ScriptType.DEFENSE)
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
            mana_points=reaction_script_offset, # TODO: do capsule monsters even have mana?
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

    def set_scripts(self, attack: Node | None = None, reaction: Node | None = None) -> None:
        """Replace the attack and/or reaction script with builder nodes; ``write()`` assembles and saves them.

        A script left as ``None`` keeps its current bytecode.
        """
        if attack is not None:
            self._attack_node = attack
        if reaction is not None:
            self._reaction_node = reaction

    def write(self) -> None:
        """Write the whole capsule record: header fields, attack script and reaction script.

        The attack script starts at +0x2B and the reaction follows it directly; the header's reaction
        offset is recomputed, and a kept reaction's jumps move with it (``rebase_jumps``). The record is
        rewritten in place when it fits its current footprint in the output (leftover bytes zeroed);
        otherwise it moves to free space in bank $97, its table entry is repointed and the old record is
        zeroed (``helpers.relocate.write_relocatable``). Also writes ``capsule_attack_names`` if and only if
        it changed.
        """
        attack = self._attack_bytes()
        reaction_offset = CAPSULE_HEADER_SIZE + len(attack)
        reaction = self._reaction_bytes(reaction_offset)
        record = self._header(reaction_offset) + attack + reaction

        write_file.flush()
        table_entry = self.address + 2 * self.index
        old = self.address + self._read_output_u16(table_entry)

        def repoint(new: int) -> None:
            write_file.seek(table_entry)
            write_file.write((new - self.address).to_bytes(2, "little"))

        self.pointer = write_relocatable(
            record,
            old,
            self._output_footprint(old),
            repoint=repoint,
            search=(self.address, CAPSULE_BANK_END),
            avoid=self._shop_targets(),
        )
        self.stats.mana_points = reaction_offset
        self._attack_node = None
        self._reaction_node = None
        self.attack_script = BattleScript(self, CAPSULE_HEADER_SIZE, ScriptType.ATTACK)
        self.attack_script.read(source=write_file)
        self.reaction_script = BattleScript(self, reaction_offset, ScriptType.DEFENSE)
        self.reaction_script.read(source=write_file)
        capsule_attack_names.write()

    def _attack_bytes(self) -> bytes:
        if self._attack_node is not None:
            return assemble_at(CAPSULE_HEADER_SIZE, self._attack_node)
        assert self.attack_script
        return self.attack_script.bytecode

    def _reaction_bytes(self, offset: int) -> bytes:
        if self._reaction_node is not None:
            return assemble_at(offset, self._reaction_node)
        assert self.reaction_script
        return rebase_jumps(self.reaction_script.bytecode, self.reaction_script.offset, offset)

    def _header(self, reaction_offset: int) -> bytes:
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
            + CAPSULE_HEADER_SIZE.to_bytes(2, "little")  # attack script offset
            + reaction_offset.to_bytes(2, "little")
            + b"\x00\x00"
        )
        if len(header) != CAPSULE_HEADER_SIZE:
            msg = f"Capsule {self.index} header is {len(header)} bytes, expected {CAPSULE_HEADER_SIZE}."
            raise ValueError(msg)
        return header

    def _read_output_u16(self, address: int) -> int:
        write_file.seek(address)
        return int.from_bytes(write_file.read(2), "little")

    def _output_footprint(self, record: int) -> int:
        """Size of the record in the output: one past the last reachable byte of either script."""
        saved = self.pointer
        self.pointer = record
        try:
            ends = [CAPSULE_HEADER_SIZE]
            for offset, kind in (
                (CAPSULE_HEADER_SIZE, ScriptType.ATTACK),
                (self._read_output_u16(record + CAPSULE_REACTION_FIELD), ScriptType.DEFENSE),
            ):
                script = BattleScript(self, offset, kind)
                script.read(source=write_file)
                ends.append(script.reach_end)
            return max(ends)
        finally:
            self.pointer = saved

    def _shop_targets(self) -> list[int]:
        return [SHOP_TABLE + self._read_output_u16(SHOP_TABLE + 2 * i) for i in range(SHOP_TABLE_MAX_ENTRIES)]

    def fix_animation(self) -> None:
        if self.animation in self.animation_fixes:
            self.animation = self.animation_fixes[self.animation]
