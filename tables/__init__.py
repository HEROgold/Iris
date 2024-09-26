"""
Always load the patches from the bottom up,
so that the most difficult patch is loaded last.
IE: Vanilla > Frue > Spekkio or Kureji

This ensures the correct table objects are known.
Not all patches include all objects, some only include the one's that differ.
(Kureji only includes the objects that are different from Frue)
"""

# TODO: Currently there's no real support for anything besides vanilla.

from args import args
from enums.patches import Patch

from .zones import ZoneObject




if args.selected_patch.value >= Patch.VANILLA.value:
    from .vanilla import (
        EventInstObject,
        IPAttackObject,
        CharLevelObject,
        CharExpObject,
        InitialEquipObject,
        OverPaletteObject,
        OverSpriteObject,
        MapEventObject,
        RoamingNPCObject,
        ChestObject,
        CapsuleLevelObject,
        WordObject,
        AncientChest2Object,
        BlueChestObject,
        AncientChest1Object,
        SpellObject,
        MonsterObject,
        ItemObject,
        CharGrowthObject,
        CharacterObject,
        MapFormationsObject,
        FormationObject,
        BossFormationObject,
        SpriteMetaObject,
        CapPaletteObject,
        CapsuleObject,
        ShopObject,
        CapAttackObject,
        ItemNameObject,
        CapSpritePTRObject,
        TownSpriteObject,
        MonsterMoveObject,
        MapMetaObject,
    )  # noqa: F401  # type: ignore[UnusedImport]

if args.selected_patch.value >= Patch.FRUE.value:
    from .frue import (
        EventInstObject,
        IPAttackObject,
        CharLevelObject,
        CharExpObject,
        InitialEquipObject,
        OverPaletteObject,
        OverSpriteObject,
        MapEventObject,
        RoamingNPCObject,
        ChestObject,
        CapsuleLevelObject,
        WordObject,
        AncientChest2Object,
        BlueChestObject,
        AncientChest1Object,
        SpellObject,
        MonsterObject,
        ItemObject,
        CharGrowthObject,
        CharacterObject,
        MapFormationsObject,
        FormationObject,
        BossFormationObject,
        SpriteMetaObject,
        CapPaletteObject,
        CapsuleObject,
        ShopObject,
        CapAttackObject,
        ItemNameObject,
        CapSpritePTRObject,
        TownSpriteObject,
        MonsterMoveObject,
        MapMetaObject,
    )  # noqa: F401  # type: ignore[UnusedImport]

if args.selected_patch.value is Patch.SPEKKIO:
    from .spekkio import (
        EventInstObject,
        IPAttackObject,
        CharLevelObject,
        CharExpObject,
        InitialEquipObject,
        OverPaletteObject,
        OverSpriteObject,
        MapEventObject,
        RoamingNPCObject,
        ChestObject,
        CapsuleLevelObject,
        WordObject,
        AncientChest2Object,
        BlueChestObject,
        AncientChest1Object,
        SpellObject,
        MonsterObject,
        ItemObject,
        CharGrowthObject,
        CharacterObject,
        MapFormationsObject,
        FormationObject,
        BossFormationObject,
        SpriteMetaObject,
        CapPaletteObject,
        CapsuleObject,
        ShopObject,
        CapAttackObject,
        ItemNameObject,
        CapSpritePTRObject,
        TownSpriteObject,
        MonsterMoveObject,
        MapMetaObject,
    )  # noqa: F401  # type: ignore[UnusedImport]

if args.selected_patch is Patch.KUREJI:
    from .kureji import (
        ChestObject,
        AncientChest2Object,
        BlueChestObject,
        AncientChest1Object,
        SpellObject,
        MonsterObject,
        ItemObject,
        CharGrowthObject,
        CharacterObject,
        CapPaletteObject,
        CapsuleObject,
        ShopObject,
        ItemNameObject,
        CapSpritePTRObject,
        MonsterMoveObject,
    )  # noqa: F401  # type: ignore[UnusedImport]

__all__ = [
    "EventInstObject",
    "IPAttackObject",
    "CharLevelObject",
    "CharExpObject",
    "InitialEquipObject",
    "OverPaletteObject",
    "OverSpriteObject",
    "MapEventObject",
    "RoamingNPCObject",
    "ChestObject",
    "CapsuleLevelObject",
    "WordObject",
    "AncientChest2Object",
    "BlueChestObject",
    "AncientChest1Object",
    "SpellObject",
    "MonsterObject",
    "ItemObject",
    "CharGrowthObject",
    "CharacterObject",
    "MapFormationsObject",
    "FormationObject",
    "BossFormationObject",
    "SpriteMetaObject",
    "CapPaletteObject",
    "CapsuleObject",
    "ShopObject",
    "CapAttackObject",
    "ItemNameObject",
    "CapSpritePTRObject",
    "TownSpriteObject",
    "MonsterMoveObject",
    "MapMetaObject",
    "ZoneObject",
]
