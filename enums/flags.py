from enum import Enum, IntFlag, auto
from typing import Literal, Self, SupportsIndex


class IntFlagOperations(IntFlag):
    def __contains__(self, other: Self) -> bool:
        return self & other == other

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

    def to_bytes(
        self,
        length: SupportsIndex = 1,
        byteorder: Literal["little", "big"] = "big",
        *,
        signed: bool = False,
    ) -> bytes:
        return self.value.to_bytes(length, byteorder, signed=signed)

    @classmethod
    def from_byte(cls, byte: bytes) -> Self:
        assert len(byte) == 1
        return cls(int.from_bytes(byte))


class SingleByteEnum(IntFlagOperations):
    ALL = 0xFF


class TwoByteEnum(IntFlagOperations):
    ALL = 0xFFFF


class EquipTypes(SingleByteEnum):
    WEAPON = auto()
    ARMOR = auto()
    SHIELD = auto()
    HELMET = auto()
    RING = auto()
    JEWEL = auto()
    U66 = auto()  # Arrow, Bomb, Fire arrow, Hook and hammer
    U67 = auto()


class EquipableCharacter(SingleByteEnum):
    MAXIM = auto()
    SELAN = auto()
    GUY = auto()
    ARTEA = auto()
    TIA = auto()
    DEKAR = auto()
    LEXIS = auto()
    U77 = auto()


class Usability(SingleByteEnum):
    CONSUMABLE = auto()
    EQUIPABLE = auto()
    U02 = auto()
    CURSED = auto()
    FRUIT = auto()
    UNSELLABLE = auto()
    USABLE_MENU = auto()
    USABLE_BATTLE = auto()


class ShopIdentifier(SingleByteEnum):
    # TODO: Investigate more, get more information.
    # Pretty sure these identifiers are correct.
    # (100% certain for Spells, 80% sure for Combat)
    GENERIC = 0x00
    COMBAT = 0x01
    UNUSED = 0x02  # Most shops with 0x02 are unused. (Not all though, like Bound Kingdom, and Tia's shop.)
    SPELL = 0x03


class ShopTypes(SingleByteEnum):
    PAWN = auto()
    COIN = auto()
    ITEM = auto()
    WEAPON = auto()
    ARMOR = auto()
    SPELL = auto()
    UNK16 = auto()
    SELL = auto()


class CastableSpells(SingleByteEnum):
    MAXIM = auto()
    SELAN = auto()
    GUY = auto()
    ARTEA = auto()
    TIA = auto()
    DEKAR = auto()
    LEXIS = auto()
    U37 = auto()

    ARTY = ARTEA


class Alignment(SingleByteEnum):
    NEUTRAL = 0
    LIGHT = auto()
    WIND = auto()
    WATER = auto()
    DARK = auto()
    SOIL = auto()
    FIRE = auto()


class ItemTypes(SingleByteEnum):
    BANNED_ANCIENT_CAVE = 0x10
    SUPER = 0x20
    POWER = 0x40  # Ip Attack, Elemental power, ...
    BLUE_CHEST = 0x60  # Not limited to blue chest items + (Curselifter, Providence, Tag Candy)
    PEARL_SET = 0x70  # Egg sword, Pearl armor, Pearl shield, Pearl helmet, Egg ring
    FRUIT = 0x80
    REST = 0x00


class ItemEffects(TwoByteEnum):
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


class Targeting(SingleByteEnum):
    NO_TARGET = 0
    ONE_OR_MORE = auto()
    ONLY_ONE_ALLY = auto()
    ONE_OR_MORE_ENEMY = 0x81
    ONLY_ONE_ENEMY = 0x82


class MenuIcon(SingleByteEnum):
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
