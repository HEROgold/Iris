# TODO: This file is a WIP, and is currently used in the randomizer for manual testing
# TODO: We wan't to move this to a pytest suite. That can also include patches like kureji etc.


import logging

from helpers.bits import find_table_pointer
from helpers.files import new_file, original_file
from logger import iris
from structures.capsule import CapsuleAttack, CapsuleLevel, CapsuleMonster
from structures.character import (
    CharacterExperience,
    CharacterGrowth,
    CharacterLevel,
    InitialEquipment,
    PlayableCharacter,
)
from structures.chest import AddressChest, PointerChest
from structures.events import MapEvent
from structures.formation import BattleFormation
from structures.ip_attack import IPAttack
from structures.item import Item
from structures.monster import Monster
from structures.npc import RoamingNPC
from structures.shop import Shop, ShopKureji
from structures.spell import Spell
from structures.sprites import CapsulePallette
from structures.word import Word
from structures.zone import Zone

from tables import (
    ZoneObject,
)
from tables.kureji import ShopObject as ShopObjectKureji
from tables.vanilla import (
    AncientChest1Object,
    AncientChest2Object,
    BlueChestObject,
    BossFormationObject,
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
)

log = logging.getLogger(f"{iris.name}.WriteTest")


def read_write_all():
    """
    Reads > immediately writes.
    after this, new file and original file are the exact same.

    (for debugging/testing purposes)


    Raises
    ------
    :class:`NotImplementedError`
        When a object/table is not implemented in the randomizer.
    """
    for i in [
        test_chests,
        test_formations,
        test_attacks,
        # test_palettes, # FIXME
        # test_sprites, # FIXME
        test_capsules,
        test_characters,
        test_initial_equipment,
        test_items,
        # test_maps, # FIXME
        test_monsters,
        test_shops,
        test_spells,
        test_words,
    ]:
        try:
            i()
        except NotImplementedError:
            log.error(f"{i.__name__} not implemented.")

        verify_files(f"Files are not the same. after {i}")


def verify_files(msg: str):
    with original_file.open("rb") as o, new_file.open("rb") as n:
        if o.read() != n.read():
            log.critical(msg)


def test_words():
    for i in range(WordObject.count):
        word = Word.from_index(i)
        word.write()


def test_spells():
    for i in SpellObject.pointers:
        spell = Spell.from_pointer(i)
        spell.write()


def test_shops():
    for i in range(ShopObject.count):
        shop = Shop.from_index(i)
        shop.write()
    for i, pointer in enumerate(ShopObjectKureji.pointers):
        raise NotImplementedError("Kureji Shop Object not implemented.")
        shop = ShopKureji.from_pointer(pointer, i)
        shop.write()


def test_monsters():
    for i in range(MonsterObject.count):
        monster = Monster.from_index(i)
        monster.write()


def test_maps():
    # TODO: This needs to be created, and then tested.
    for i in range(ZoneObject.count):
        zone = Zone.from_index(i)
        zone.write()
    for i in range(EventInstObject.count):
        raise NotImplementedError("")
    for i in range(MapEventObject.count):
        raise NotImplementedError("")
        map_event = MapEvent.from_index(i)
        map_event.write()
    for i in range(MapMetaObject.count):
        raise NotImplementedError("")
    for i in range(MonsterMoveObject.count):
        raise NotImplementedError("")
    for i in range(RoamingNPCObject.count):
        npc = RoamingNPC.from_index(i)
        npc.write()


def test_initial_equipment():
    for i in InitialEquipObject.pointers:
        equip = InitialEquipment.from_pointer(i)
        equip.write()


def test_items():
    for i in range(ItemNameObject.count):
        name = Item.from_index(i)
        name.write()
    for i in range(ItemObject.count):
        item = Item.from_index(i)
        item.write()


def test_capsules():
    for i in range(CapsuleLevelObject.count):
        level = CapsuleLevel.from_table(CapsuleLevelObject.address, i)
        level.write()
    for i in range(CapsuleObject.count):
        capsule = CapsuleMonster.from_table(CapsuleObject.address, i)
        capsule.write()


def test_palettes():
    for i in range(CapPaletteObject.count):
        palette = CapsulePallette.from_table(CapPaletteObject.address, i)
        palette.write()
    for i in range(OverPaletteObject.count):
        raise NotImplementedError("")


def test_sprites():
    for _i in range(CapSpritePTRObject.count):
        raise NotImplementedError("")
    for _i in range(SpriteMetaObject.count):
        raise NotImplementedError("")
    for _i in TownSpriteObject.pointers:
        raise NotImplementedError("")
    for _i in range(OverSpriteObject.count):
        raise NotImplementedError("")


def test_characters():
    for i in range(CharacterObject.count):
        character = PlayableCharacter.from_table(CharacterObject.address, i)
        character.write()
    for i in CharExpObject.pointers:
        xp = CharacterExperience.from_pointer(i)
        xp.write()
    for i in CharGrowthObject.pointers:
        growth = CharacterGrowth.from_pointer(i)
        growth.write()
    for i in CharLevelObject.pointers:
        level = CharacterLevel.from_pointer(i)
        level.write()


def test_attacks():
    for i in range(CapAttackObject.count):
        capsule_attack = CapsuleAttack.from_table(CapAttackObject.address, i)
        capsule_attack.write()
    for i in IPAttackObject.pointers:
        ip_attack = IPAttack.from_pointer(i)
        ip_attack.write()


def test_formations():
    for i in range(BossFormationObject.count):
        pointer = find_table_pointer(BossFormationObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()
    for i in range(FormationObject.count):
        formation = BattleFormation.from_table(FormationObject.address, i)
        formation.write()
    for i in range(MapFormationsObject.count):
        pointer = find_table_pointer(MapFormationsObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()


def test_chests():
    for i in range(AncientChest1Object.count):
        chest = AddressChest.from_table(AncientChest1Object.address, i)
        chest.write()
    for i in range(AncientChest2Object.count):
        chest = AddressChest.from_table(AncientChest2Object.address, i)
        chest.write()
    for i in range(BlueChestObject.count):
        chest = AddressChest.from_table(BlueChestObject.address, i)
        chest.write()
    for i in ChestObject.pointers:
        chest = PointerChest.from_pointer(i)
        chest.write()


def test_map_events():
    # EventScript(0x3B21B).read()
    for i in range(MapEventObject.count):
        event = MapEvent.from_index(i)
        print(event.clean_map_name)
