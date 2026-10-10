from enum import Enum, IntEnum, IntFlag, auto
from typing import Self


class IntFlagOperations(IntFlag):
    def __add__(self, other: Self) -> Self:  # type: ignore[reportIncompatibleMethodOverride]
        """Same as __or__."""
        return self | other

    def __sub__(self, value: int) -> Self:
        """
        Almost same as __xor__.
        This doesn't add a value if the original didn't have it.
        Should be used to remove a specific flag or set of flags from the first element.
        """
        old_value = self
        new_value = self ^ value
        if new_value <= old_value:
            return self ^ value
        return self

    @classmethod
    def from_byte(cls, byte: bytes) -> Self:
        assert len(byte) == 1
        return cls(int.from_bytes(byte))


class SingleByteEnum:
    ALL = 0xFF


class TwoByteEnum:
    ALL = 0xFFFF


class EquipTypes(SingleByteEnum, IntFlagOperations):
    WEAPON = auto()
    ARMOR = auto()
    SHIELD = auto()
    HELMET = auto()
    RING = auto()
    JEWEL = auto()
    U66 = auto()  # Arrow, Bomb, Fire arrow, Hook and hammer
    U67 = auto()


class EquipableCharacter(SingleByteEnum, IntFlagOperations):
    MAXIM = auto()
    SELAN = auto()
    GUY = auto()
    ARTEA = auto()
    TIA = auto()
    DEKAR = auto()
    LEXIS = auto()
    U77 = auto()


class Usability(SingleByteEnum, IntFlagOperations):
    CONSUMABLE = auto()
    EQUIPABLE = auto()
    U02 = auto()
    CURSED = auto()
    FRUIT = auto()
    UNSELLABLE = auto()
    USABLE_MENU = auto()
    USABLE_BATTLE = auto()


class ShopIdentifier(SingleByteEnum, IntFlagOperations):
    # TODO: Investigate more, get more information.
    # Pretty sure these identifiers are correct.
    # (100% certain for Spells, 80% sure for Combat)
    GENERIC = 0x00
    COMBAT = 0x01
    UNUSED = 0x02  # Most shops with 0x02 are unused. (Not all though, like Bound Kingdom, and Tia's shop.)
    SPELL = 0x03


class ShopTypes(SingleByteEnum, IntFlagOperations):
    PAWN = auto()
    COIN = auto()
    ITEM = auto()
    WEAPON = auto()
    ARMOR = auto()
    SPELL = auto()
    UNK16 = auto()
    SELL = auto()


class CastableSpells(SingleByteEnum, IntFlagOperations):
    MAXIM = auto()
    SELAN = auto()
    GUY = auto()
    ARTEA = auto()
    TIA = auto()
    DEKAR = auto()
    LEXIS = auto()
    U37 = auto()

    ARTY = ARTEA


class Alignment(SingleByteEnum, IntFlagOperations):
    NEUTRAL = 0
    LIGHT = auto()
    WIND = auto()
    WATER = auto()
    DARK = auto()
    SOIL = auto()
    FIRE = auto()


class ItemTypes(SingleByteEnum, IntFlagOperations):
    BANNED_ANCIENT_CAVE = 0x10
    SUPER = 0x20
    POWER = 0x40  # Ip Attack, Elemental power, ...
    BLUE_CHEST = 0x60  # Not limited to blue chest items + (Curselifter, Providence, Tag Candy)
    PEARL_SET = 0x70  # Egg sword, Pearl armor, Pearl shield, Pearl helmet, Egg ring
    FRUIT = 0x80
    REST = 0x00


class ItemEffects(TwoByteEnum, IntFlagOperations):
    MENU_EFFECT = auto()
    BATTLE_EFFECT = auto()
    WEAPON_EFFECT = auto()
    ARMOR_EFFECT = auto()
    INCREASE_ATP = auto()
    INCREASE_DFP = auto()
    INCREASE_STR = auto()
    INCREASE_AGL = auto()
    INCREASE_INT = auto()
    INCREASE_GUT = auto()
    INCREASE_MGR = auto()
    U93 = auto()
    U94 = auto()
    BATTLE_ANIMATION = auto()
    U96 = auto()
    IP_EFFECT = auto()


class Targeting(SingleByteEnum, IntFlagOperations):
    NO_TARGET = 0
    ONE_OR_MORE = auto()
    ONLY_ONE_ALLY = auto()
    ONE_OR_MORE_ENEMY = 0x81
    ONLY_ONE_ENEMY = 0x82


class MenuIcon(SingleByteEnum, IntFlagOperations):
    NO_ICON = 0x10
    SWORD = 0xE0
    ARMOR = 0xE1
    SHIELD = 0xE2
    HELMET = 0xE3
    SHOE = 0xE4  # (not used by any existing item)
    RING = 0xE5
    POTION = 0xE6
    KEY = 0xE7
    WHIP = 0xE8
    STAFF = 0xE9
    SPEAR = 0xEA
    ARROW = 0xEB  # (for bows and boomerangs)
    JEWEL = 0xEC
    AX = 0xED
    BALL = 0xEE  # ('Sleep ball', 'Confuse ball', ...)
    WRENCH = 0xEF  # (for tools)


class ItemSprites(Enum):
    """Incomplete list of item sprites."""

    COINS = 0x00  # => Coins ('1 coin', used for some items not found in chests, like the 'Dual blade')
    SWORD = 0x01  # => Sword ('Gladius', ...)
    ARMOR = 0x02  # => Armor ('Metal mail', ...)
    SHIELD = 0x03  # => Shield
    HELMET = 0x04  # => Helmet
    VIP_CARD = 0x05  # => VIP card
    RING = 0x06  # => Ring
    KEY = 0x08  # => Key
    WHIP = 0x09  # => Whip
    ROD = 0x0A  # => Rod
    SPEAR = 0x0B  # => Spear
    BRACELET = 0x0C  # => Bracelet
    JEWEL = 0x0D  # => Jewel ('Evil jewel', 'Magma rock', ...)
    AX = 0x0E  # => Ax
    BALL = 0x0F  # => Ball
    WRENCH = 0x10  # => Wrench
    GLOVES = 0x11  # => Gloves
    DRAGON_EGG = 0x12  # => Dragon Egg
    MACE = 0x13  # => Mace ('Morning star', ...)
    BOOMERANG = 0x15  # => Boomerang
    FRUIT = 0x17  # => Fruit
    BOW = 0x18  # => Bow
    DRESS = 0x1B  # => Dress ('Quilted silk', ...)
    SCROLL = 0x1C  # => Scroll (for spells in the Ancient Cave. Not used for items)
    HAT = 0x1D  # => Hat ('Blue beret')
    WING = 0x20  # => Wing ('Escape', 'Warp', 'Providence')
    TIARA = 0x21  # => Tiara ('Fury ribbon', ...)
    KNIFE = 0x22  # => Knife
    BOMB = 0x40  # => Bomb
    HOOK = 0x41  # => Hook
    HAMMER = 0x42  # => Hammer
    ARROW = 0x43  # => Arrow
    FIRE = 0x44  # => Fire arrow
    HOURGLASS = 0x45  # => Hourglass ('Reset' spell. Not used for items)


class TargetingCursor(Enum):
    MENU_HAND = 0x00
    SWORD = 0x01
    STAFF = 0x02
    POUCH = 0x03
    CHAR_CHANGE_ARROW = 0x04
    INVISIBLE = 0xFF


# The game tracks exactly 256 event bits (0..255).
EVENT_FLAG_COUNT = 256


class EventFlag(IntEnum):
    """The game's 256 event bits (a.k.a. EV flags), named from the TCRF notes for Lufia II.

    Source: the "EV(ent) Flags" table on https://tcrf.net/Notes:Lufia_II:_Rise_of_the_Sinistrals .
    Numbering is decimal, 0..255. Only the *known* flags are enum members; unnamed/blank flags are not
    members and surface through :meth:`name_of` / :meth:`all_flags` / :meth:`free_flags` (generated on
    access) as ``FREE_XX``.

    Party membership (2-7 / 1 for Maxim) is authoritative here and, notably, is **not** ``index + 1`` for
    Tia and Dekar: flag ``5`` is Dekar and flag ``6`` is Tia. :attr:`PlayableCharacter.party_flag` maps a
    character index to the correct member via ``_PARTY_FLAG_BY_INDEX``.

    ``FOUND_*`` (242-248) are new flags introduced by Iris' party-toggle patch (they occupy blank TCRF
    slots): a character is "found/unlocked" once discovered in the story. 249 is left spare; 250-255 are
    volatile post-boss dungeon flags and must not be reused; 240/241 are the Undo-magic flags.
    """

    # 1-7: "the respective character is in your party" (2-7 per TCRF, 1 = Maxim / new game).
    MAXIM_IN_PARTY = 1
    SELAN_IN_PARTY = 2
    GUY_IN_PARTY = 3
    ARTEA_IN_PARTY = 4
    DEKAR_IN_PARTY = 5  # NB: Dekar is flag 5, Tia is flag 6 -- NOT index + 1 for these two.
    TIA_IN_PARTY = 6
    LEXIS_IN_PARTY = 7

    # 8-16: capsule monsters joining the party.
    JELZE_JOINED = 8  # Jelze (Foomy)
    FLASH_JOINED = 9  # Flash (Shaggy)
    NEW_GAME_STARTED = 10
    GUSTO_JOINED = 12  # Gusto (Hard hat)
    ZAPPY_JOINED = 13  # Zappy (Red Fish)
    SULLY_JOINED = 15  # Sully (Radisher)
    BLAZE_JOINED = 16  # Blaze (Armor Dog)

    # 21-118: main story triggers.
    FINISHED_TUTORIAL = 21
    DINER_WITH_TIA_ELCID = 22
    MET_IRIS_ELCID_CAVE = 23
    SAVED_TIA_LAKE_CAVE = 24
    KILLED_FISH_LAKE_CAVE = 25
    TALKED_KING_ALUNZE = 26
    PICKED_UP_CROWN = 27
    RETURNED_CROWN_ALUNZE = 28
    KILLED_REGAL_GOBLIN = 29
    GUY_JOINED_STORY = 30
    DEFEATED_CAMU = 31
    RETURNED_HILDA_TANBEL = 32
    TALKED_ROCHY_CLAMENTO = 33
    KILLED_SPIDER_RUBY_CAVE = 35
    RECEIVED_RUBY_APPLE = 36
    DELIVERED_RUBY_APPLE = 37
    FIRST_VISIT_PARCELYTE = 38
    PARCELYTE_CASTLE_FIGHT = 39
    SELAN_JOINED_STORY = 40
    KILLED_PIERRE_FIRST = 41
    KILLED_DANIELLE_FIRST = 42
    SELAN_CLONES_TALK = 43
    DEFEATED_PIERRE_DANIELLE = 44
    TALKED_KING_GORDOVAN = 45
    PASSED_GADES_GORDOVAN = 46
    TALKED_KING_PARCELYTE = 47
    DESTROYED_CRYSTAL_MERIX = 48
    REPAIRED_BRIDGE_MERIX = 49
    TALKED_KING_BOUND = 50
    SAVED_PRINCE_BOUND = 51
    DEKAR_GUY_JOINED_BOUND = 52
    SUNDLETAN_EARTHQUAKE = 53
    IDURA_KIDNAPPED_JEROS = 55
    SAVED_JEROS = 57
    TALKED_JYAD_PHANTOM_TREE = 58
    PORTED_JYAD_ALEYN = 59
    RESTED_TWICE_ALEYN = 60
    NARCYSUS_WOMEN_FLEE = 62
    NARCYSUS_WOMEN_FLEE_ALT = 63
    IDURA_DEFEATED_SACRIFICE = 64
    FINISHED_KARLLOON_TEMPLE = 65
    TALKED_LEXIS_ASSISTANT_TREADOOL = 66
    TALKED_LEXIS_LAB = 67
    TALKED_SHIPBUILDER_ALEYN = 68
    TALKED_FLOWER_GIRL_TREADOOL = 69
    RECEIVED_PRETTY_FLOWER = 70
    DELIVERED_PRIPHEA_LEFFA = 71
    TALKED_KING_DANKIRK = 72
    RUBY_ICON_MISSING = 73
    TALKED_JAFFY_RUBY_ICON = 74
    DELIVERED_RUBY_ICON_ALEX = 75
    RETURNED_REAL_RUBY_ICON = 76
    OPENED_WATER_GATE_AURALIO = 77
    TALKED_FERIM_JEWEL = 78
    MET_AMON_FIRST = 79
    RETURNED_FERIM_KING = 80
    TALKED_IRIS_AGURIO = 81
    KIRMO_LAB_YES = 83
    SAVED_MILKA = 84
    AMON_DEFEATED_DIVINE = 85
    GOT_SUBMARINE = 86
    DEFEATED_GHOST_VENGEANCE = 87
    TALKED_IRIS_BARNAN = 88
    FINISHED_TOWER_OF_TRUTH = 89
    FINISHED_DRAGON_MOUNTAIN = 90
    TALKED_MERMAID_QUEEN = 92
    DEFEATED_DOOM_SHIP = 93
    TALKED_MERMAIDS_TEMPLE = 94
    CHAED_DESTROYED = 95
    TALKED_LEXIS_ENGINE = 96
    KILLED_PRISON_SOLDIERS = 97
    GOT_ENGINE = 98
    GOT_AIRSHIP = 99
    TALKED_NARVICK_1 = 100
    NARVICK_FIRST_MAID = 101
    GADES_DEFEATED = 102
    TALKED_NARVICK_2 = 103
    NARVICK_SECOND_MAID = 104
    AMON_DEFEATED = 105
    TALKED_NARVICK_3 = 106
    NARVICK_THIRD_MAID = 107
    OBTAINED_DUAL_BLADE = 108
    PORTED_PORTRAVIA = 109
    PORTRAVIA_CONVERSATION = 110
    TALKED_LEXIS_FINAL = 111
    GADES_DEFEATED_FINAL = 112
    AMON_DEFEATED_FINAL = 113
    ERIM_DEFEATED = 114
    DAOS_DEFEATED = 115
    FIRST_STONE_DESTROYED = 116
    SECOND_STONE_DESTROYED = 117
    THIRD_STONE_DESTROYED = 118  # destroying the third stone starts the credits/outro

    # 119-219: secondary triggers, tutorial steps, Ancient Cave / Iris treasures.
    TUTORIAL_INITIALIZED = 119
    GUY_LEFT_PARCELYTE = 120
    RESTED_TWICE_ALEYN_ALT = 121
    TALKED_KING_ALUNZE_ALT = 124
    OPENED_SHRINE_HILDA = 125
    IRIS_JOINED_KARLLOON = 126
    RECEIVED_SHIP_TREADOOL = 127
    TALKED_IRIS_AGURIO_ALT = 128
    DAOS_TELEPORTER_2 = 130
    IDURA_KIDNAPPED_JEROS_ALT = 132
    DEFEATED_GADES_ANCIENT_TOWER = 133
    THIEVES_OPENED_PRISON = 134
    TALKED_ROCHY_CLAMENTO_ALT = 136
    MERIX_CAVE_CUTSCENE = 137
    BOUND_ENTRANCE_CUTSCENE = 138
    TALKED_JYAD_PHANTOM_TREE_ALT = 140
    KILLED_LIONS_PHANTOM_TREE = 141
    KILLED_IDURA_KARLLOON = 142
    RECEIVED_PRETTY_FLOWER_ALT = 143
    AMON_DEFEATED_DIVINE_ALT = 144
    AMON_DEFEATED_DIVINE_ALT2 = 146
    INSIDE_ANCIENT_CAVE = 147
    OPENED_WATER_GATE_AURALIO_ALT = 148
    OPENED_WATER_GATE_AURALIO_ALT2 = 149
    KEY_GONE_ELCID = 150
    ALUNZE_SEWER_SCENE = 151
    TALKED_HILDA_TANBEL = 152
    USED_SHIP_ALEYN = 153
    TALKED_DEKAR_FIRST = 154
    BOUND_GUARD_GADES = 155
    IDURA_KIDNAPPED_JEROS_ALT2 = 156
    DEKAR_GUY_JOINED_SHRINE = 157
    TUTORIAL_CAVE_OLD_GUY = 158
    TUTORIAL_JELLY_BEATEN = 159
    TUTORIAL_MOVE_PILLAR = 160
    TUTORIAL_JUMP_DOWN = 161
    TUTORIAL_KILL_ALL = 162
    TUTORIAL_CUT_GRASS = 163
    ALUNZE_PASSED_OUT_GUY = 164
    PICOLINA_AFTER_MILKA = 167
    TALKED_ABEL_ALUNZE = 169
    PICKED_UP_CROWN_ALT = 170
    TUTORIAL_R_BUTTON = 171
    TUTORIAL_UNDO_MAGIC = 172
    KILLED_CLOWNS_SWORD_SHRINE = 177
    DEKAR_GUY_JOINED_BOUND_ALT = 178
    TALKED_BOY_TREBLE = 183
    TALKED_GIRL_FOOMY = 185
    DIVINE_POWER_PLATFORM = 186
    FINISHED_KARLLOON_TEMPLE_ALT = 190
    KILLED_EGG_DRAGON = 193
    ANCIENT_CAVE_BOSS_KILLED = 195
    GIFT_MODE = 196  # party members standing in the pub of Gruberik (works in standard + Retry mode)
    DESTROYED_STATUES_ANCIENT_TOWER = 199
    IRIS_TREASURE_01 = 200
    IRIS_TREASURE_02 = 201
    IRIS_TREASURE_03 = 202
    IRIS_TREASURE_04 = 203
    IRIS_TREASURE_05 = 204
    IRIS_TREASURE_06 = 205
    IRIS_TREASURE_07 = 206
    IRIS_TREASURE_08 = 207
    IRIS_TREASURE_09 = 208
    IRIS_TREASURE_10 = 209
    RETURNED_IRIS_SWORD = 210
    RETURNED_IRIS_SHIELD = 211
    RETURNED_IRIS_HELMET = 212
    RETURNED_IRIS_ARMOR = 213
    RETURNED_IRIS_RING = 214
    RETURNED_IRIS_JEWEL = 215
    RETURNED_IRIS_STAFF = 216
    RETURNED_IRIS_POT = 217
    RETURNED_IRIS_TIARA = 218
    RETURNED_ANCIENT_CAVE_BOSS = 219

    # 240/241: Undo magic (turned off again on leaving the dungeon).
    UNDO_MAGIC_RECEIVED = 240
    UNDO_MAGIC_RECEIVED_ALT = 241

    # 242-248: Iris' "found/unlocked" flags (new; occupy blank TCRF slots). 249 spare.
    FOUND_MAXIM = 242
    FOUND_SELAN = 243
    FOUND_GUY = 244
    FOUND_ARTEA = 245
    FOUND_TIA = 246
    FOUND_DEKAR = 247
    FOUND_LEXIS = 248

    @classmethod
    def name_of(cls, index: int) -> str:
        """Return the flag's name, or a generated ``FREE_XX`` for an unnamed/blank flag."""
        try:
            return cls(index).name
        except ValueError:
            return f"FREE_{index:02X}"

    @classmethod
    def all_flags(cls) -> dict[int, str]:
        """The full ``0..255`` table: named where known, generated (``FREE_XX``) otherwise."""
        return {index: cls.name_of(index) for index in range(EVENT_FLAG_COUNT)}

    @classmethod
    def free_flags(cls) -> list[int]:
        """Every flag index in ``0..255`` with no named member (candidate free slots)."""
        known = {int(member) for member in cls}
        return [index for index in range(EVENT_FLAG_COUNT) if index not in known]
