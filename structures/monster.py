from _types.objects import Cache
from helpers.files import read_file, write_file
from typing import Self

from abc_.pointers import TablePointer
from abc_.stats import ScalableRpgStats

from helpers.bits import find_table_pointer, read_little_int
from structures.battlescript import BattleScript, ScriptType
from tables import MonsterObject

from .item import Item
from args import args
from logger import iris



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
        if args.spekkio and 'Lady Spider' in name:
            sprite = 0x89 # Web Spider
        return cls(name, index, sprite)


MONSTER_SIZE: int = sum([
    MonsterObject.name_text, # type: ignore  name_text is actually an int.
    MonsterObject.level,
    MonsterObject.unknown,
    MonsterObject.battle_sprite,
    MonsterObject.palette,
    MonsterObject.hp,
    MonsterObject.mp,
    MonsterObject.attack,
    MonsterObject.defense,
    MonsterObject.agility,
    MonsterObject.intelligence,
    MonsterObject.guts,
    MonsterObject.magic_resistance,
    MonsterObject.xp,
    MonsterObject.gold,
    MonsterObject.misc,
])

class Monster(TablePointer):
    name: str
    index: int
    sprite_index: int
    attack_script: BattleScript | None
    defense_script: BattleScript | None
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
        self.attack_script = None
        self.defense_script = None
        self.scale = 1
        self._scaled = False

    def __repr__(self) -> str:
        return f"<Monster: {self.name}, {self.index}>"

    @classmethod
    def from_index(cls, index: int) -> Self:
        if index > MonsterObject.count:
            raise IndexError(f"Monster index out of range, max: {MonsterObject.count} got {index}")
        return cls.from_table(MonsterObject.address, index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        if inst := cls._cache.from_cache(index):
            return inst

        pointer = find_table_pointer(address, index)
        read_file.seek(pointer)

        name_text = read_file.read(MonsterObject.name_text).decode() # type: ignore

        level = read_little_int(read_file, MonsterObject.level)
        _unknown = read_little_int(read_file, MonsterObject.unknown)
        battle_sprite = read_little_int(read_file, MonsterObject.battle_sprite)
        palette = read_little_int(read_file, MonsterObject.palette)
        hp = read_little_int(read_file, MonsterObject.hp)
        mp = read_little_int(read_file, MonsterObject.mp)
        attack = read_little_int(read_file, MonsterObject.attack)
        defense = read_little_int(read_file, MonsterObject.defense)
        agility = read_little_int(read_file, MonsterObject.agility)
        intelligence = read_little_int(read_file, MonsterObject.intelligence)
        guts = read_little_int(read_file, MonsterObject.guts)
        magic_resistance = read_little_int(read_file, MonsterObject.magic_resistance)
        xp = read_little_int(read_file, MonsterObject.xp)
        gold = read_little_int(read_file, MonsterObject.gold)

        _misc = read_file.read(MonsterObject.misc)

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
            item_low = read_file.read(1) # Item drop index, without high bit.
            item_high = read_little_int(read_file, 1) # 0x01 or 0x00, + DropRate
            inst._drop_item = int.from_bytes(item_low)
            inst._drop_rate = item_high # Also contains the high bit for the item drop.
            if item_high & 0x01 == 1:
                iris.debug(f"{inst} has High bit for item drop set.")
            script = read_file.read(1)
            if script == b"\x07":
                inst.create_attack_script()
            elif script == b"\x08":
                inst.create_defense_script()
        elif _misc == b"\x07":
            inst.create_attack_script()
        elif _misc == b"\x08":
            inst.create_defense_script()

        cls._cache.to_cache(index, inst)
        return inst


    def create_attack_script(self):
        if self.attack_script:
            raise ValueError(f"{self} already has an attack script.")
        self.attack_script_offset = read_little_int(read_file, 2)
        self.attack_script = BattleScript(
            self,
            self.attack_script_offset,
            ScriptType.ATTACK
        )
        self.attack_script.read()
        if read_file.read(1) == b"\x08":
            self.create_defense_script()

    def create_defense_script(self):
        if self.defense_script:
            raise ValueError(f"{self} already has an attack script.")
        self.defense_script_offset = read_little_int(read_file, 2)
        self.defense_script = BattleScript(
            self,
            self.defense_script_offset,
            ScriptType.DEFENSE
        )
        self.defense_script.read()


    def _set_movement(self) -> None:
        if args.aggressive_movement:
            self.movement = 0x1F
        elif args.passive_movement:
            self.movement = 0x1B
        else:
            self.movement = 0x0


    def apply_scale(self) -> None:
        if self._scaled:
            return
        self._scaled = True
        # Scale stats
        self.stats.health_points = self.scale
        self.stats.attack = self.scale
        self.stats.defense = self.scale
        self.stats.agility = self.scale
        self.stats.intelligence = self.scale
        self.stats.guts = self.scale
        self.stats.magic_resistance = self.scale
        # Scale rewards
        self.stats.level = self.scale
        self.stats.xp = self.scale
        self.stats.gold = self.scale

    def undo_scale(self) -> None:
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
    def stats(self):
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
        stats = self.stats.to_int()
        write_file.seek(self.pointer)
        has_end_byte = False

        write_file.write(self.name.encode())
        write_file.write(stats.level.to_bytes(MonsterObject.level, "little"))
        write_file.write(self._unknown.to_bytes(MonsterObject.unknown))
        write_file.write(self.sprite_index.to_bytes(MonsterObject.battle_sprite, "little"))
        write_file.write(self._palette.to_bytes(MonsterObject.palette))
        write_file.write(stats.health_points.to_bytes(MonsterObject.hp, "little"))
        write_file.write(stats.mana_points.to_bytes(MonsterObject.mp, "little"))
        write_file.write(stats.attack.to_bytes(MonsterObject.attack, "little"))
        write_file.write(stats.defense.to_bytes(MonsterObject.defense, "little"))
        write_file.write(stats.agility.to_bytes(MonsterObject.agility, "little"))
        write_file.write(stats.intelligence.to_bytes(MonsterObject.intelligence, "little"))
        write_file.write(stats.guts.to_bytes(MonsterObject.guts, "little"))
        write_file.write(stats.magic_resistance.to_bytes(MonsterObject.magic_resistance, "little"))
        write_file.write(stats.xp.to_bytes(MonsterObject.xp, "little"))
        write_file.write(stats.gold.to_bytes(MonsterObject.gold, "little"))
        if self.can_drop_item:
            assert self._misc == b"\x03"
            write_file.write(self._misc)
            write_file.write(self._drop_item.to_bytes(1))
            write_file.write(self._drop_rate.to_bytes(1))
        if self.attack_script:
            self.attack_script.write()
            has_end_byte = True
        if self.defense_script:
            self.defense_script.write()
            has_end_byte = True
        if not has_end_byte:
            write_file.write(b"\x00")


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
