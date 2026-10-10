"""
The ROM table layouts, for the selected patch.

Each patch only lists the tables that differ from the one below it (Kureji only lists what differs from Frue), so a
table is looked up from the most difficult patch down: Kureji or Spekkio > Frue > Vanilla.

The names exported here are proxies: ``MonsterObject.address`` reads the table of whichever patch :func:`select`
picked last, so importing this package doesn't need the command line. The default is vanilla.
"""

from types import ModuleType
from typing import TYPE_CHECKING, Any

from enums.patches import Patch
from tables import frue, kureji, spekkio, vanilla


_LAYERS: dict[Patch, tuple[ModuleType, ...]] = {
    Patch.VANILLA: (vanilla,),
    Patch.FRUE: (frue, vanilla),
    Patch.SPEKKIO: (spekkio, frue, vanilla),
    Patch.KUREJI: (kureji, frue, vanilla),
}
_selected = Patch.VANILLA


def select(patch: Patch) -> None:
    """Make ``patch``'s tables the ones every structure reads."""
    global _selected  # noqa: PLW0603
    _selected = patch


def selected() -> Patch:
    """The patch whose tables are in use."""
    return _selected


def resolve(name: str) -> type:
    """The selected patch's table class called ``name``."""
    for layer in _LAYERS[_selected]:
        if hasattr(layer, name):
            return getattr(layer, name)
    msg = f"No table {name!r} for {_selected.name}."
    raise AttributeError(msg)


class _TableProxy(type):
    """Forwards attribute reads on a proxy class to the selected patch's table class of the same name."""

    def __getattr__(cls, attribute: str) -> Any:  # noqa: ANN401 - table fields have mixed types
        return getattr(resolve(cls.__name__), attribute)

    def __repr__(cls) -> str:
        return f"<table {cls.__name__} for {_selected.name}>"


def _proxy(name: str) -> type:
    return _TableProxy(name, (), {"__module__": __name__})


if TYPE_CHECKING:
    from tables.vanilla import (
        AncientChest1Object,
        AncientChest2Object,
        BlueChestObject,
        BossFormationObject,
        CapAttackNameObject,
        CapAttackObject,
        CapPaletteObject,
        CapSpritePTRObject,
        CapsuleLevelObject,
        CapsuleObject,
        CharacterObject,
        CharExpObject,
        CharGrowthObject,
        CharLevelObject,
        ChestObject,
        EventInstObject,
        FormationObject,
        InitialEquipObject,
        IPAttackObject,
        ItemNameObject,
        ItemObject,
        MapEventObject,
        MapFormationsObject,
        MapMetaObject,
        MonsterMoveObject,
        MonsterObject,
        OverPaletteObject,
        OverSpriteObject,
        RoamingNPCObject,
        ShopObject,
        SpellObject,
        SpriteMetaObject,
        TownSpriteObject,
        WordObject,
        ZoneObject,
    )
else:
    AncientChest1Object = _proxy("AncientChest1Object")
    AncientChest2Object = _proxy("AncientChest2Object")
    BlueChestObject = _proxy("BlueChestObject")
    BossFormationObject = _proxy("BossFormationObject")
    CapAttackNameObject = _proxy("CapAttackNameObject")
    CapAttackObject = _proxy("CapAttackObject")
    CapPaletteObject = _proxy("CapPaletteObject")
    CapSpritePTRObject = _proxy("CapSpritePTRObject")
    CapsuleLevelObject = _proxy("CapsuleLevelObject")
    CapsuleObject = _proxy("CapsuleObject")
    CharacterObject = _proxy("CharacterObject")
    CharExpObject = _proxy("CharExpObject")
    CharGrowthObject = _proxy("CharGrowthObject")
    CharLevelObject = _proxy("CharLevelObject")
    ChestObject = _proxy("ChestObject")
    EventInstObject = _proxy("EventInstObject")
    FormationObject = _proxy("FormationObject")
    InitialEquipObject = _proxy("InitialEquipObject")
    IPAttackObject = _proxy("IPAttackObject")
    ItemNameObject = _proxy("ItemNameObject")
    ItemObject = _proxy("ItemObject")
    MapEventObject = _proxy("MapEventObject")
    MapFormationsObject = _proxy("MapFormationsObject")
    MapMetaObject = _proxy("MapMetaObject")
    MonsterMoveObject = _proxy("MonsterMoveObject")
    MonsterObject = _proxy("MonsterObject")
    OverPaletteObject = _proxy("OverPaletteObject")
    OverSpriteObject = _proxy("OverSpriteObject")
    RoamingNPCObject = _proxy("RoamingNPCObject")
    ShopObject = _proxy("ShopObject")
    SpellObject = _proxy("SpellObject")
    SpriteMetaObject = _proxy("SpriteMetaObject")
    TownSpriteObject = _proxy("TownSpriteObject")
    WordObject = _proxy("WordObject")
    ZoneObject = _proxy("ZoneObject")

__all__ = [
    "AncientChest1Object",
    "AncientChest2Object",
    "BlueChestObject",
    "BossFormationObject",
    "CapAttackNameObject",
    "CapAttackObject",
    "CapPaletteObject",
    "CapSpritePTRObject",
    "CapsuleLevelObject",
    "CapsuleObject",
    "CharExpObject",
    "CharGrowthObject",
    "CharLevelObject",
    "CharacterObject",
    "ChestObject",
    "EventInstObject",
    "FormationObject",
    "IPAttackObject",
    "InitialEquipObject",
    "ItemNameObject",
    "ItemObject",
    "MapEventObject",
    "MapFormationsObject",
    "MapMetaObject",
    "MonsterMoveObject",
    "MonsterObject",
    "OverPaletteObject",
    "OverSpriteObject",
    "RoamingNPCObject",
    "ShopObject",
    "SpellObject",
    "SpriteMetaObject",
    "TownSpriteObject",
    "WordObject",
    "ZoneObject",
    "resolve",
    "select",
    "selected",
]
