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
from structures.sprites import CapsulePallette, CapsuleSprite, OverPallette, OverSprite, SpriteMeta, TownSprite
from structures.word import Word
from structures.zone import Zone
from structures.events import Event

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
        test_palettes,
        test_sprites,
        test_capsules,
        test_characters,
        test_initial_equipment,
        test_items_full,
        test_maps, # FIXME
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

def assert_files_are_same():
    """
    This is a IO intensive function!
    It compares the original file with the new file, and raises an AssertionError if they are not the same.
    
    Raises
    ------
    :class:`AssertionError`
        When the files are not the same.
    """
    with original_file.open("rb") as o, new_file.open("rb") as n:
        if o.read() != n.read():
            raise AssertionError("Files are not the same.")

def test_words():
    for i in range(WordObject.count):
        word = Word.from_index(i)
        word.write()
        assert_files_are_same()


def test_spells():
    for i in SpellObject.pointers:
        spell = Spell.from_pointer(i)
        spell.write()
        assert_files_are_same()


def test_shops():
    for i in range(ShopObject.count):
        shop = Shop.from_index(i)
        shop.write()
        assert_files_are_same()
    for i, pointer in enumerate(ShopObjectKureji.pointers):
        raise NotImplementedError("Kureji Shop Object not implemented.")
        shop = ShopKureji.from_pointer(pointer, i)
        shop.write()
        assert_files_are_same()


def test_monsters():
    for i in range(MonsterObject.count):
        monster = Monster.from_index(i)
        monster.write()
        assert_files_are_same()


def test_maps():
    # test_map_meta()
    # test_monster_moves()
    test_roaming_npc()
    test_events()
    test_map_events()
    test_zones()

def test_map_meta():
    # TODO: This needs to be created, and then tested.
    for i in range(MapMetaObject.count):
        raise NotImplementedError("")

def test_monster_moves():
    # TODO: This needs to be created, and then tested.
    for i in range(MonsterMoveObject.count):
        raise NotImplementedError("")

def test_roaming_npc():
    for i in range(RoamingNPCObject.count):
        npc = RoamingNPC.from_index(i)
        npc.write()
        assert_files_are_same()

def test_events():
    for i in range(EventInstObject.count):
        event = Event.from_index(i)
        event.write()
        assert_files_are_same()

def test_zones():
    for i in range(ZoneObject.count):
        zone = Zone.from_index(i)
        zone.write()
        assert_files_are_same()


def test_initial_equipment():
    for i in InitialEquipObject.pointers:
        equip = InitialEquipment.from_pointer(i)
        equip.write()
        assert_files_are_same()


def test_items_full():
    test_item_names()
    test_items()

def test_items():
    for i in range(ItemObject.count):
        item = Item.from_index(i)
        item.write()
        assert_files_are_same()

def test_item_names():
    for i in range(ItemNameObject.count):
        name = Item.from_index(i)
        name.write()
        assert_files_are_same()


def test_capsules():
    test_capsule_levels()
    test_capsule_monsters()

def test_capsule_levels():
    for i in range(CapsuleLevelObject.count):
        level = CapsuleLevel.from_table(CapsuleLevelObject.address, i)
        level.write()
        assert_files_are_same()

def test_capsule_monsters():
    for i in range(CapsuleObject.count):
        capsule = CapsuleMonster.from_table(CapsuleObject.address, i)
        capsule.write()
        assert_files_are_same()


def test_palettes():
    test_capsule_pallette()
    test_over_pallette()

def test_over_pallette():
    for i in range(OverPaletteObject.count):
        over_pallette = OverPallette.from_index(i)
        over_pallette.write()
        assert_files_are_same()

def test_capsule_pallette():
    for i in range(CapPaletteObject.count):
        palette = CapsulePallette.from_index(i)
        palette.write()
        assert_files_are_same()


def test_sprites():
    test_capsule_sprites()
    test_sprite_meta()
    test_town_sprites()
    test_over_sprites()

def test_capsule_sprites():
    for i in range(CapSpritePTRObject.count):
        capsule_sprite = CapsuleSprite.from_index(i)
        capsule_sprite.write()
        assert_files_are_same()

def test_sprite_meta():
    for i in range(SpriteMetaObject.count):
        sprite_meta = SpriteMeta.from_index(i)
        sprite_meta.write()
        assert_files_are_same()

def test_town_sprites():
    for i in TownSpriteObject.pointers:
        town_sprite = TownSprite.from_pointer(i)
        town_sprite.write()
        assert_files_are_same()

def test_over_sprites():
    for i in range(OverSpriteObject.count):
        over_sprite = OverSprite.from_index(i)
        over_sprite.write()
        assert_files_are_same()


def test_characters():
    test_playable_characters()
    test_character_exps()
    test_character_growths()
    test_character_levels()

def test_playable_characters():
    for i in range(CharacterObject.count):
        character = PlayableCharacter.from_table(CharacterObject.address, i)
        character.write()
        assert_files_are_same()

def test_character_exps():
    for i in CharExpObject.pointers:
        xp = CharacterExperience.from_pointer(i)
        xp.write()
        assert_files_are_same()

def test_character_growths():
    for i in CharGrowthObject.pointers:
        growth = CharacterGrowth.from_pointer(i)
        growth.write()
        assert_files_are_same()

def test_character_levels():
    for i in CharLevelObject.pointers:
        level = CharacterLevel.from_pointer(i)
        level.write()
        assert_files_are_same()


def test_attacks():
    test_cap_attacks()
    test_ip_attacks()

def test_cap_attacks():
    for i in range(CapAttackObject.count):
        capsule_attack = CapsuleAttack.from_table(CapAttackObject.address, i)
        capsule_attack.write()
        assert_files_are_same()

def test_ip_attacks():
    for i in IPAttackObject.pointers:
        ip_attack = IPAttack.from_pointer(i)
        ip_attack.write()
        assert_files_are_same()


def test_formations():
    test_boss_formations()
    test_battle_formations()
    test_map_formations()

def test_map_formations():
    for i in range(MapFormationsObject.count):
        pointer = find_table_pointer(MapFormationsObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()
        assert_files_are_same()

def test_battle_formations():
    for i in range(FormationObject.count):
        formation = BattleFormation.from_table(FormationObject.address, i)
        formation.write()
        assert_files_are_same()

def test_boss_formations():
    for i in range(BossFormationObject.count):
        pointer = find_table_pointer(BossFormationObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()
        assert_files_are_same()


def test_chests():
    test_ancient_chests()
    test_ancient_chests2()
    test_blue_chests()
    test_pointer_chests()

def test_pointer_chests():
    for i in ChestObject.pointers:
        chest = PointerChest.from_pointer(i)
        chest.write()
        assert_files_are_same()

def test_blue_chests():
    for i in range(BlueChestObject.count):
        chest = AddressChest.from_table(BlueChestObject.address, i)
        chest.write()
        assert_files_are_same()

def test_ancient_chests2():
    for i in range(AncientChest2Object.count):
        chest = AddressChest.from_table(AncientChest2Object.address, i)
        chest.write()
        assert_files_are_same()

def test_ancient_chests():
    for i in range(AncientChest1Object.count):
        chest = AddressChest.from_table(AncientChest1Object.address, i)
        chest.write()
        assert_files_are_same()


def test_map_events():
    # EventScript(0x3B21B).read()
    for i in range(MapEventObject.count):
        event = MapEvent.from_index(i)
        print(event.clean_map_name)
