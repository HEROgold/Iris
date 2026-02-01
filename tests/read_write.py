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
from structures.events import Event, EventScript, MapEvent
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


def read_write_all() -> None:
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
        test_map_events,
        test_map_meta,
        test_events,
        test_monster_moves,
        # /\ Debugs. \/ Finished.
        test_ancient_chests,
        test_ancient_chests2,
        test_blue_chests,
        test_pointer_chests,
        test_boss_formations,
        test_battle_formations,
        test_map_formations,
        test_cap_attacks,
        test_ip_attacks,
        test_capsule_pallette,
        test_over_pallette,
        test_capsule_sprites,
        test_sprite_meta,
        test_town_sprites,
        test_over_sprites,
        test_capsule_levels,
        test_capsule_monsters,
        test_playable_characters,
        test_character_exps,
        test_character_growths,
        test_character_levels,
        test_initial_equipment,
        test_item_names,
        test_items,
        test_roaming_npc,
        test_zones,
        test_monsters,
        test_shops,
        test_spells,
        test_words,
        test_zones,
    ]:
        try:
            i()
        except NotImplementedError:
            log.exception(f"{i.__name__} not implemented.")

        verify_files(f"Files are not the same. after {i}")


def verify_files(msg: str) -> None:
    with original_file.open("rb") as o, new_file.open("rb") as n:
        if o.read() != n.read():
            log.critical(msg)

def assert_files_are_same(location: object = None) -> None:
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
            msg = f"Files are not the same.\nLocation: {location!r}"
            raise AssertionError(msg)

def test_words() -> None:
    for i in range(WordObject.count):
        word = Word.from_index(i)
        word.write()
        assert_files_are_same(word)


def test_spells() -> None:
    for i in SpellObject.pointers:
        spell = Spell.from_pointer(i)
        spell.write()
        assert_files_are_same(spell)


def test_shops() -> None:
    for i in range(ShopObject.count):
        shop = Shop.from_index(i)
        shop.write()
        assert_files_are_same(shop)
    for i, pointer in enumerate(ShopObjectKureji.pointers):
        msg = "Kureji Shop Object not implemented."
        raise NotImplementedError(msg)
        shop = ShopKureji.from_pointer(pointer, i)
        shop.write()
        assert_files_are_same(shop)


def test_monsters() -> None:
    for i in range(MonsterObject.count):
        monster = Monster.from_index(i)
        monster.write()
        assert_files_are_same(monster)


def test_map_meta() -> None:
    # TODO: This needs to be created, and then tested.
    for _i in range(MapMetaObject.count):
        msg = ""
        raise NotImplementedError(msg)

def test_monster_moves() -> None:
    # TODO: This needs to be created, and then tested.
    for _i in range(MonsterMoveObject.count):
        msg = ""
        raise NotImplementedError(msg)

def test_roaming_npc() -> None:
    for i in range(RoamingNPCObject.count):
        npc = RoamingNPC.from_index(i)
        npc.write()
        assert_files_are_same()

def test_events() -> None:
    # FIXME
    for i in range(EventInstObject.count):
        event = Event.from_index(i)
        event.write()
        assert_files_are_same()

def test_zones() -> None:
    for i in range(ZoneObject.count):
        zone = Zone.from_index(i)
        zone.write()
        assert_files_are_same(zone)


def test_initial_equipment() -> None:
    for i in InitialEquipObject.pointers:
        equip = InitialEquipment.from_pointer(i)
        equip.write()
        assert_files_are_same(equip)


def test_items() -> None:
    for i in range(ItemObject.count):
        item = Item.from_index(i)
        item.write()
        assert_files_are_same(item)

def test_item_names() -> None:
    for i in range(ItemNameObject.count):
        name = Item.from_index(i)
        name.write()
        assert_files_are_same(name)



def test_capsule_levels() -> None:
    for i in range(CapsuleLevelObject.count):
        level = CapsuleLevel.from_table(CapsuleLevelObject.address, i)
        level.write()
        assert_files_are_same(level)

def test_capsule_monsters() -> None:
    for i in range(CapsuleObject.count):
        capsule = CapsuleMonster.from_table(CapsuleObject.address, i)
        capsule.write()
        assert_files_are_same(capsule)


def test_over_pallette() -> None:
    for i in range(OverPaletteObject.count):
        over_pallette = OverPallette.from_index(i)
        over_pallette.write()
        assert_files_are_same(over_pallette)

def test_capsule_pallette() -> None:
    for i in range(CapPaletteObject.count):
        palette = CapsulePallette.from_index(i)
        palette.write()
        assert_files_are_same(palette)


def test_capsule_sprites() -> None:
    for i in range(CapSpritePTRObject.count):
        capsule_sprite = CapsuleSprite.from_index(i)
        capsule_sprite.write()
        assert_files_are_same(capsule_sprite)

def test_sprite_meta() -> None:
    for i in range(SpriteMetaObject.count):
        sprite_meta = SpriteMeta.from_index(i)
        sprite_meta.write()
        assert_files_are_same(sprite_meta)

def test_town_sprites() -> None:
    for i in TownSpriteObject.pointers:
        town_sprite = TownSprite.from_pointer(i)
        town_sprite.write()
        assert_files_are_same(town_sprite)

def test_over_sprites() -> None:
    for i in range(OverSpriteObject.count):
        over_sprite = OverSprite.from_index(i)
        over_sprite.write()
        assert_files_are_same(over_sprite)



def test_playable_characters() -> None:
    for i in range(CharacterObject.count):
        character = PlayableCharacter.from_table(CharacterObject.address, i)
        character.write()
        assert_files_are_same(character)

def test_character_exps() -> None:
    for i in CharExpObject.pointers:
        xp = CharacterExperience.from_pointer(i)
        xp.write()
        assert_files_are_same(xp)

def test_character_growths() -> None:
    for i in CharGrowthObject.pointers:
        growth = CharacterGrowth.from_pointer(i)
        growth.write()
        assert_files_are_same(growth)

def test_character_levels() -> None:
    for i in CharLevelObject.pointers:
        level = CharacterLevel.from_pointer(i)
        level.write()
        assert_files_are_same(level)


def test_cap_attacks() -> None:
    for i in range(CapAttackObject.count):
        capsule_attack = CapsuleAttack.from_table(CapAttackObject.address, i)
        capsule_attack.write()
        assert_files_are_same(capsule_attack)

def test_ip_attacks() -> None:
    for i in IPAttackObject.pointers:
        ip_attack = IPAttack.from_pointer(i)
        ip_attack.write()
        assert_files_are_same(ip_attack)


def test_map_formations() -> None:
    for i in range(MapFormationsObject.count):
        pointer = find_table_pointer(MapFormationsObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()
        assert_files_are_same(formation)

def test_battle_formations() -> None:
    for i in range(FormationObject.count):
        formation = BattleFormation.from_table(FormationObject.address, i)
        formation.write()
        assert_files_are_same(formation)

def test_boss_formations() -> None:
    for i in range(BossFormationObject.count):
        pointer = find_table_pointer(BossFormationObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()
        assert_files_are_same(formation)


def test_pointer_chests() -> None:
    for i in ChestObject.pointers:
        chest = PointerChest.from_pointer(i)
        chest.write()
        assert_files_are_same(chest)

def test_blue_chests() -> None:
    for i in range(BlueChestObject.count):
        chest = AddressChest.from_table(BlueChestObject.address, i)
        chest.write()
        assert_files_are_same(chest)

def test_ancient_chests2() -> None:
    for i in range(AncientChest2Object.count):
        chest = AddressChest.from_table(AncientChest2Object.address, i)
        chest.write()
        assert_files_are_same(chest)

def test_ancient_chests() -> None:
    for i in range(AncientChest1Object.count):
        chest = AddressChest.from_table(AncientChest1Object.address, i)
        chest.write()
        assert_files_are_same(chest)


def test_map_events() -> None:
    # FIXME
    # EventScript(0x3B21B).read()
    for i in range(MapEventObject.count):
        event = MapEvent.from_index(i)
        event.write() # FIXME: i=1, diff data at 0x38000
        assert_files_are_same(event)
