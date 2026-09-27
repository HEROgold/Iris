from functools import cache
from typing import IO, Literal, Self

from _types.objects import Cache
from abc_.pointers import TablePointer
from abc_.stats import ScalableRpgStats
from args import args
from helpers.bits import find_table_pointer, read_little_int
from helpers.files import read_file, restore_pointer, write_file
from logger import iris
from rom_space.table import Table
from scripting.core import Item as ScriptItem
from scripting.core import Data, Label, Script, assemble
from scripting.l2basm import L2BASM, parse_record
from scripting.l2basm.edit import replace_entry
from scripting.l2basm.helpers import block
from scripting.l2basm.records import (
    MONSTER_HEADER_SIZE,
    RecordSource,
    monster_records,
    read_record,
    table_address,
    table_bound,
)
from structures.subroutine import make_room_in_bank_96
from tables import MonsterObject

from .item import Item


class MonsterSprite:
    def __init__(self, name: str, monster_index: int, sprite_index: int) -> None:
        self.name = name
        self.monster_index = monster_index
        self.sprite_index = sprite_index

    @classmethod
    def from_index(cls, index: int) -> Self:
        if index > MonsterObject.count:
            index = 0xA4 # Red JElly
        name, sprite = MONSTER_SPRITES[index]
        if args.spekkio and "Lady Spider" in name:
            sprite = 0x89 # Web Spider
        return cls(name, index, sprite)


TABLE_SIZE = MonsterObject.count * 2

class Monster(TablePointer):
    name: str
    index: int
    sprite_index: int
    code: Script | None
    """The record's scripts as one body with ``attack``/``defense`` entry labels (they may share blocks)."""
    code_start: int
    """Record offset of the first script byte (the header's length)."""
    external_entries: dict[str, int]
    """Entry offsets that point outside the record's script area (some base patches); written back unchanged."""
    _cache = Cache[int, Self]()
    _drop_item: int
    _drop_rate: int
    _stats: ScalableRpgStats
    sprite: MonsterSprite
    _drop_rate_modifier: int
    _unknown: int
    _palette: int
    _misc: bytes

    def __init__(self, name: str, monster_index: int, sprite_index: int) -> None:
        self.name = name
        self.index = monster_index
        self.sprite_index = sprite_index
        self._drop_item = 0x0
        self._drop_rate = 0x0
        self._stats = ScalableRpgStats()
        self.sprite = MonsterSprite.from_index(monster_index)
        self._drop_rate_modifier = 2
        self.code = None
        self.code_start = 0
        self.external_entries = {}
        self.scale = 1
        self._scaled = False

    def __repr__(self) -> str:
        return f"<Monster: {self.name}, {self.index}>"

    @property
    def total_size(self) -> int:
        return len(self.build())

    @classmethod
    def from_index(cls, index: int) -> Self:
        if index > MonsterObject.count and index != 0xFF:
            msg = f"Monster index out of range, max: {MonsterObject.count} got {index}"
            raise IndexError(msg)
        if index == 0xFF:
            return cls("Dummy", 0xFF, 0x0)
        return cls.from_table(table_address(write_file, "monster"), index)

    @classmethod
    def reread(cls, index: int) -> Self:
        """Drop the cached monsters and read this one again from the output ROM."""
        cls._cache.clear()
        _record_sources.cache_clear()
        return cls.from_index(index)

    @classmethod
    @restore_pointer
    def level_from_index(cls, index: int) -> int:
        """Read just a monster's level byte, without parsing the rest of the record.

        :meth:`from_table` parses the monster's AI scripts. Callers that only need the level
        (encounter scaling, formation ranking) can use this instead of paying for the parser.
        """
        if index == 0xFF:  # empty-slot sentinel; from_index reports it as a level-0 "Dummy"
            return 0
        read_file.seek(find_table_pointer(MonsterObject.address, index) + MonsterObject.name_text)
        return read_little_int(read_file, MonsterObject.level)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        if inst := cls._cache.from_cache(index):
            return inst

        source = write_file  # the output ROM, so base-patch edits are what we read
        pointer = _entry_target(source, address, index)
        source.seek(pointer)

        name_text = source.read(MonsterObject.name_text).decode("latin-1")  # names use non-UTF-8 bytes

        level = read_little_int(source, MonsterObject.level)
        _unknown = read_little_int(source, MonsterObject.unknown)
        battle_sprite = read_little_int(source, MonsterObject.battle_sprite)
        palette = read_little_int(source, MonsterObject.palette)
        hp = read_little_int(source, MonsterObject.hp)
        mp = read_little_int(source, MonsterObject.mp)
        attack = read_little_int(source, MonsterObject.attack)
        defense = read_little_int(source, MonsterObject.defense)
        agility = read_little_int(source, MonsterObject.agility)
        intelligence = read_little_int(source, MonsterObject.intelligence)
        guts = read_little_int(source, MonsterObject.guts)
        magic_resistance = read_little_int(source, MonsterObject.magic_resistance)
        xp = read_little_int(source, MonsterObject.xp)
        gold = read_little_int(source, MonsterObject.gold)

        _misc = source.read(MonsterObject.misc)

        inst = cls(name_text, index, battle_sprite)
        inst.stats = ScalableRpgStats(
            health_points=hp,
            mana_points=mp,
            attack=attack,
            defense=defense,
            agility=agility,  # value*2 > real value (in game)
            intelligence=intelligence,  # value*2 > real value (in game)
            guts=guts,  # value*2 > real value (in game)
            magic_resistance=magic_resistance,  # value*2 > real value (in game)
            level=level,
            xp=xp,
            gold=gold,
        )
        inst.address = address
        inst.index = index
        inst.pointer = pointer
        inst._unknown = _unknown # 0x036 for 'Armor goblin' and 'Regal Goblin', 0x032 for all other monsters > Flag?
        inst._palette = palette

        inst._misc = _misc # Monsters either have a drop item, attack script, or defense script.

        if _misc == b"\x03":
            # "Gift Bytes" L2_MonsterDataFormat.txt
            inst._drop_item = read_little_int(source, 1)  # Item drop index, without high bit.
            inst._drop_rate = read_little_int(source, 1)  # Also contains the high bit for the item drop.
            if inst._drop_rate & 0x01 == 1:
                iris.debug(f"{inst} has High bit for item drop set.")

        inst.code_start = inst._header_size(0)
        rec = _record_sources().get(index)
        if rec is not None:
            inst.external_entries = dict(rec.external)
            record = read_record(source, rec)
            in_region = address <= rec.start < table_bound(source, address)
            if rec.entries:
                parsed = parse_record(record, rec.entries, start=rec.script_start)
                inst.code = parsed.script
                inst.code_start = parsed.start
                if in_region and parsed.end < len(record):  # unreached bytes up to the next record stay as they are
                    inst.code.body.append(Data(record[parsed.end :]))
            elif in_region and rec.script_start is not None and rec.script_start < len(record):
                # Every entry points elsewhere (Spekkio/Kureji share code between records): keep the bytes as they are.
                inst.code = Script(L2BASM, [Data(record[rec.script_start :])])
                inst.code_start = rec.script_start

        cls._cache.to_cache(index, inst)
        return inst

    def header_bytes(self, entry_offsets: dict[str, int]) -> bytes:
        """The record's fixed fields, drop item, ``07``/``08`` script markers and the closing ``00``."""
        stats = self.stats.to_int()
        fields = [
            self.name.encode("latin-1").ljust(MonsterObject.name_text, b" "),
            stats.level.to_bytes(MonsterObject.level, "little"),
            self._unknown.to_bytes(MonsterObject.unknown, "little"),
            self.sprite_index.to_bytes(MonsterObject.battle_sprite, "little"),
            self._palette.to_bytes(MonsterObject.palette, "little"),
            stats.health_points.to_bytes(MonsterObject.hp, "little"),
            stats.mana_points.to_bytes(MonsterObject.mp, "little"),
            stats.attack.to_bytes(MonsterObject.attack, "little"),
            stats.defense.to_bytes(MonsterObject.defense, "little"),
            stats.agility.to_bytes(MonsterObject.agility, "little"),
            stats.intelligence.to_bytes(MonsterObject.intelligence, "little"),
            stats.guts.to_bytes(MonsterObject.guts, "little"),
            stats.magic_resistance.to_bytes(MonsterObject.magic_resistance, "little"),
            stats.xp.to_bytes(MonsterObject.xp, "little"),
            stats.gold.to_bytes(MonsterObject.gold, "little"),
        ]
        if self.can_drop_item:
            fields.append(bytes([0x03, self._drop_item, self._drop_rate]))
        for marker, name in ((0x07, "attack"), (0x08, "defense")):
            if name in entry_offsets:
                fields.append(bytes([marker]) + entry_offsets[name].to_bytes(2, "little"))
        fields.append(b"\x00")
        header = b"".join(fields)
        assert len(header) == self._header_size(len(entry_offsets)), self
        return header

    def _header_size(self, entry_count: int) -> int:
        return MONSTER_HEADER_SIZE + 3 * (int(self.can_drop_item) + entry_count) + 1

    def _entries(self) -> list[str]:
        if self.code is None:
            return []
        names = {item.name for item in self.code.body if isinstance(item, Label)}
        return [name for name in ("attack", "defense") if name in names]

    def build(self) -> bytes:
        """The whole record: header, then the assembled scripts (jumps are record-relative)."""
        entries = self._entries()
        header_size = self._header_size(len(entries) + len(self.external_entries))
        if self.code is None:
            return self.header_bytes(dict(self.external_entries))
        out = assemble(self.code, header_size)
        offsets = {name: header_size + out.labels[name] for name in entries} | self.external_entries
        return self.header_bytes(offsets) + out.data

    def replace_attack(self, items: list[ScriptItem]) -> None:
        """Replace the attack script; blocks the defense script also uses stay."""
        self.replace_script("attack", items)

    def replace_script(self, entry: Literal["attack", "defense"], items: list[ScriptItem]) -> None:
        """Replace one entry's script; blocks the other entry also uses stay.

        A monster without that script gains one: ``build()`` adds its ``07``/``08`` marker, so the record grows.
        """
        self.external_entries.pop(entry, None)
        if self.code is None:
            self.code = Script(L2BASM, [Label(entry), *block(items)])
        elif entry not in self._entries():
            new = [Label(entry), *block(items)]
            self.code.body = [*new, *self.code.body] if entry == "attack" else [*self.code.body, *new]
        else:
            replace_entry(self.code, entry, block(items))

    def _set_movement(self) -> None:
        if args.aggressive_movement:
            self.movement = 0x1F
        elif args.passive_movement:
            self.movement = 0x1B
        else:
            self.movement = 0x0

    def apply_scale(self) -> None:
        # TODO: properly validate scaling behaviour.
        if self._scaled:
            return
        self._scaled = True
        # Scale stats
        self.stats.health_points *= self.scale
        self.stats.attack *= self.scale
        self.stats.defense *= self.scale
        self.stats.agility *= self.scale
        self.stats.intelligence *= self.scale
        self.stats.guts *= self.scale
        self.stats.magic_resistance *= self.scale
        # Scale rewards
        self.stats.level = self.scale
        self.stats.xp = self.scale
        self.stats.gold = self.scale

    def undo_scale(self) -> None:
        # TODO: properly validate scaling behaviour.
        if not self._scaled:
            return
        self._scaled = False
        # Scale stats
        self.stats.health_points *= self.scale
        self.stats.attack /= self.scale
        self.stats.defense /= self.scale
        self.stats.agility /= self.scale
        self.stats.intelligence /= self.scale
        self.stats.guts /= self.scale
        self.stats.magic_resistance /= self.scale
        # Scale rewards
        self.stats.level /= self.scale
        self.stats.xp /= self.scale
        self.stats.gold /= self.scale

    @property
    def stats(self) -> ScalableRpgStats:
        return self._stats

    @stats.setter
    def stats(self, stats: ScalableRpgStats) -> None:
        self._stats = stats
        if args.easy_mode:
            self._stats = ScalableRpgStats(
                health_points = 1,
                attack = 1,
                defense = 1,
                agility = 1,
                intelligence = 1,
                guts = 1,
                magic_resistance = 1,
            )

    @property
    def drop_item(self) -> Item:
        return Item.from_index(self._drop_item)

    @drop_item.setter
    def drop_item(self, item: Item) -> None:
        """
        Sets the item that the monster can drop.

        Parameters
        -----------
        :param:`item`: :class:`Item`
            The item to set as the drop for the monster.
        """
        # Set/delete high bit
        if item.index >= 0xFF:
            self._drop_rate |= 0x01
        else:
            self._drop_rate &= 0xFE
        self._drop_item = item.index % 0xFF

    @property
    def drop_rate(self) -> int:
        """
        The drop rate for the monster.


        Return/Parameter
        -------
        :class:`int`
            the percentage in full ints of the drop rate.
        """
        return (
            self._drop_rate // self._drop_rate_modifier
            - self._drop_item % 2 # Preserve item high bit
        )

    @drop_rate.setter
    def drop_rate(self, rate: int) -> None:
        self._drop_rate = (
            rate * self._drop_rate_modifier
            + self._drop_item % 2 # Preserve item high bit
        )

    @property
    def can_drop_item(self) -> bool:
        return self._misc == b"\x03"
    @can_drop_item.setter
    def can_drop_item(self, value: bool) -> None:
        self._misc = b"\x03" if value else b"\x00"

    def write(self) -> None:
        iris.debug(f"Writing Monster {self.index} {self.name!r}")
        monster_table().write()


def _entry_target(source: IO[bytes], address: int, index: int) -> int:
    """Where entry ``index`` of the table at ``address`` in ``source`` points."""
    source.seek(address + 2 * index)
    return address + int.from_bytes(source.read(2), "little")


@cache
def _record_sources() -> dict[int, RecordSource]:
    return {rec.index: rec for rec in monster_records(write_file)}


@cache
def monster_table() -> Table:
    """Every monster record on ``rom_space.Table``. Growing past bank $96's free space moves the $42 table."""
    address = table_address(write_file, "monster")
    records = [Monster.from_index(i) for i in range(MonsterObject.count)]
    return Table(
        "monsters",
        address,
        records,  # type: ignore[arg-type]
        table_bound(write_file, address),
        make_room=make_room_in_bank_96,
    )


def reset_monster_table() -> None:
    monster_table.cache_clear()
    _record_sources.cache_clear()
    Monster._cache.clear()  # noqa: SLF001


# sprite_index, name
MONSTER_SPRITES: list[tuple[str, int]] = [
    ("Goblin", 0x9D),
    ("Armor goblin", 0x9D),
    ("Regal Goblin", 0x9D),
    ("Goblin Mage", 0x9D),
    ("Troll", 0xA9),
    ("Ork", 0xA5),
    ("Fighter ork", 0xA5),
    ("Ork Mage", 0xA5),
    ("Lizardman", 0x9E),
    ("Skull Lizard", 0x9E),
    ("Armour Dait", 0xEF),
    ("Dragonian", 0xEF),
    ("Cyclops", 0xB9),
    ("Mega Cyclops", 0xB9),
    ("Flame genie", 0xB9),
    ("Well Genie", 0xB9),
    ("Wind Genie", 0xB9),
    ("Earth Genie", 0xB9),
    ("Cobalt", 0xA6),
    ("Merman", 0xAE),
    ("Aqualoi", 0xAE),
    ("Imp", 0xAC),
    ("Fiend", 0xBD),
    ("Archfiend", 0xBD),
    ("Hound", 0x8A),
    ("Doben", 0x8A),
    ("Winger", 0xB1),
    ("Serfaco", 0xE8),
    ("Pug", 0x8D),
    ("Salamander", 0xC1),
    ("Brinz Lizard", 0xEE),
    ("Seahorse", 0x85),
    ("Seirein", 0xAE),
    ("Earth Viper", 0xB3),
    ("Gnome", 0xA5),
    ("Wispy", 0x91),
    ("Thunderbeast", 0x9B),
    ("Lunar bear", 0x9B),
    ("Shadowfly", 0x92),
    ("Shadow", 0xB2),
    ("Lion", 0xB7),
    ("Sphinx", 0xB7),
    ("Mad horse", 0x85),
    ("Armor horse", 0x85),
    ("Buffalo", 0x84),
    ("Bruse", 0x84),
    ("Bat", 0x8F),
    ("Big Bat", 0x8F),
    ("Red Bat", 0x8F),
    ("Eagle", 0xE8),
    ("Hawk", 0xE8),
    ("Crow", 0xB4),
    ("Baby Frog", 0xBE),
    ("King Frog", 0xBE),
    ("Lizard", 0x83),
    ("Newt", 0x83),
    ("Needle Lizard", 0xD6),
    ("Poison Lizard", 0xD6),
    ("Medusa", 0x9C),
    ("Ramia", 0xAE),
    ("Basilisk", 0xB6),
    ("Cokatoris", 0xD2),
    ("Scorpion", 0x8B),
    ("Antares", 0x8B),
    ("Small Crab", 0x87),
    ("Big Crab", 0xD8),
    ("Red Lobster", 0x87),
    ("Spider", 0xD9),
    ("Web Spider", 0x89),
    ("Beetle", 0x86),
    ("Poison Beetle", 0xD7),
    ("Mosquito", 0x92),
    ("Coridras", 0xEA),
    ("Spinner", 0xE9),
    ("Tartona", 0xB8),
    ("Armour Nail", 0xEB),
    ("Moth", 0x93),
    ("Mega  Moth", 0xDC),
    ("Big Bee", 0x98),
    ("Dark Fly", 0x92),
    ("Stinger", 0x98),
    ("Armor Bee", 0x98),
    ("Sentopez", 0xDA),
    ("Cancer", 0x87),
    ("Garbost", 0xD8),
    ("Bolt Fish", 0x80),
    ("Moray", 0xE9),
    ("She Viper", 0xEA),
    ("Angler fish", 0x80),
    ("Unicorn", 0x85),
    ("Evil Shell", 0x81),
    ("Drill Shell", 0x81),
    ("Snell", 0x81),
    ("Ammonite", 0x81),
    ("Evil Fish", 0x80),
    ("Squid", 0x80),
    ("Kraken", 0xBB),
    ("Killer Whale", 0xC2),
    ("White Whale", 0xC2),
    ("Grianos", 0xB6),
    ("Behemoth", 0xB6),
    ("Perch", 0xBB),
    ("Current", 0xBB),
    ("Vampire Rose", 0x96),
    ("Desert Rose", 0x96),
    ("Venus Fly", 0xE0),
    ("Moray Vine", 0x9A),
    ("Torrent", 0x8E),
    ("Mad Ent", 0x8E),
    ("Crow Kelp", 0xBC),
    ("Red Plant", 0xEC),
    ("La Fleshia", 0x97),
    ("Wheel Eel", 0x97),
    ("Skeleton", 0xA0),
    ("Ghoul", 0xE1),
    ("Zombie", 0xA7),
    ("Specter", 0xAD),
    ("Dark Spirit", 0xB5),
    ("Snatcher", 0xA8),
    ("Jurahan", 0xD5),
    ("Demise", 0xE7),
    ("Leech", 0xE7),
    ("Necromancer", 0xAB),
    ("Hade Chariot", 0xBA),
    ("Hades", 0xBA),
    ("Dark Skull", 0xB5),
    ("Hades Skull", 0xB5),
    ("Mummy", 0xA8),
    ("Vampire", 0x9F),
    ("Nosferato", 0x9F),
    ("Ghost Ship", 0xC8),
    ("Deadly Sword", 0x90),
    ("Deadly Armor", 0x99),
    ("T Rex", 0xD3),
    ("Brokion", 0xD3),
    ("Pumpkin Head", 0xAF),
    ("Mad Head", 0xAF),
    ("Snow Gas", 0xD2),
    ("Great Coca", 0xD2),
    ("Gargoyle", 0xC4),
    ("Rogue Shape", 0xC4),
    ("Bone Gorem", 0xA0),
    ("Nuborg", 0xE5),
    ("Wood Gorem", 0xA2),
    ("Mad Gorem", 0xA3),
    ("Green Clay", 0xE6),
    ("Sand Gorem", 0xE4),
    ("Magma Gorem", 0xE3),
    ("Iron Gorem", 0xA1),
    ("Gold Gorem", 0xE2),
    ("Hidora", 0xBF),
    ("Sea Hidora", 0xBF),
    ("High Hidora", 0xBF),
    ("King Hidora", 0xBF),
    ("Orky", 0xBF),
    ("Waiban", 0xC3),
    ("White Dragon", 0xC3),
    ("Red Dragon", 0xC0),
    ("Blue Dragon", 0xC0),
    ("Green Dragon", 0xC0),
    ("Black Dragon", 0xC0),
    ("Copper Dragon", 0xC0),
    ("Silver Dragon", 0xC0),
    ("Gold Dragon", 0xC0),
    ("Red Jelly", 0x94),
    ("Blue Jelly", 0xDD),
    ("Bili Jelly", 0xDE),
    ("Red Core", 0x95),
    ("Blue Core", 0x95),
    ("Green Core", 0x95),
    ("No Core", 0x95),
    ("Mimic", 0xA4),
    ("Blue Mimic", 0xF0),
    ("Ice Roge", 0xBD),
    ("Mushroom", 0x8C),
    ("Big Mushr'm", 0xDB),
    ("Minataurus", 0xAA),
    ("Gorgon", 0xAA),
    ("Ninja", 0x82),
    ("Asashin", 0x82),
    ("Samurai", 0xB0),
    ("Dark Warrior", 0xB0),
    ("Ochi Warrior", 0xB0),
    ("Sly Fox", 0xED),
    ("Tengu", 0xD4),
    ("Warm Eye", 0x88),
    ("Wizard", 0xAB),
    ("Dark Sum'ner", 0xAB),
    ("Big Catfish", 0xC5),
    ("Follower", 0x76),
    ("Tarantula", 0xC6),
    ("Pierre", 0x77),
    ("Daniele", 0x78),
    ("Venge Ghost", 0xD0),
    ("Fire Dragon", 0xC0),
    ("Tank", 0xC7),
    ("Idura", 0x74),
    ("Camu", 0x75),
    ("Gades", 0x7A),
    ("Amon", 0x79),
    ("Erim", 0x7C),
    ("Daos", 0x7B),
    ("Lizard Man", 0x9E),
    ("Goblin", 0x9D),
    ("Skeleton", 0xA0),
    ("Regal Goblin", 0x9D),
    ("Goblin", 0x9D),
    ("Goblin Mage", 0x9D),
    ("Slave", 0x76),
    ("Follower", 0x76),
    ("Groupie", 0x76),
    ("Egg Dragon", 0xC0),
    ("Mummy", 0xA8),
    ("Troll", 0xA9),
    ("Gades", 0x7A),
    ("Idura", 0x74),
    ("Lion", 0xB7),
    ("Rogue Flower", 0x96),
    ("Gargoyle", 0xC4),
    ("Ghost Ship", 0xC8),
    ("Idura", 0x74),
    ("Soldier", 0x18),
    ("Gades", 0x7A),
    ("Master", 0x94),
]
