from helpers.bits import find_table_pointer
from structures.events import MapEvent
from structures.sprites import (
    CapsulePallette,
    CapsuleSprite,
    OverPallette,
    OverSprite,
    SpriteMeta,
    TownSprite,
)
from tables.spekkio import (
    FormationObject,
    MapEventObject,
    EventInstObject,
    ChestObject,
    AncientChest1Object,
    AncientChest2Object,
    TownSpriteObject,
    OverSpriteObject,
    BossFormationObject,
    MapFormationsObject,
    CapsuleObject,
    CharacterObject,
    IPAttackObject,
    ItemObject,
    MonsterObject,
    RoamingNPCObject,
    ShopObject,
    SpriteMetaObject,
    WordObject,
    CapSpritePTRObject,
    SpellObject,
    CapPaletteObject,
    OverPaletteObject
)
from structures.word import Word
from structures.spell import Spell
from structures.shop import Shop

from structures.npc import RoamingNPC
from structures.monster import Monster
from structures.item import Item
from structures.ip_attack import IPAttack
from structures.chest import AddressChest, PointerChest
from structures.character import PlayableCharacter
from structures.capsule import CapsuleMonster
from structures.formation import BattleFormation
from structures.events import Event

from helpers.files import original_file, new_file
from tests.reset_file import test_equal

def test_bosses():
    for i in range(BossFormationObject.count):
        pointer = find_table_pointer(BossFormationObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()
        test_equal()


def test_formations():
    for i in range(FormationObject.count):
        formation = BattleFormation.from_table(FormationObject.address, i)
        formation.write()
        test_equal()


def test_map_formations():
    for i in range(MapFormationsObject.count):
        pointer = find_table_pointer(MapFormationsObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()
        test_equal()


def test_capsules():
    for index in range(CapsuleObject.count):
        inst = CapsuleMonster.from_table(CapsuleObject.address, index)
        inst.write()
        test_equal()


def test_characters():
    for index in range(CharacterObject.count):
        inst = PlayableCharacter.from_table(CharacterObject.address, index)
        inst.write()
        test_equal()


def test_chests():
    for pointer in ChestObject.pointers:
        inst = PointerChest.from_pointer(pointer)
        inst.write()
        test_equal()
    for index in range(AncientChest1Object.count):
        inst = AddressChest.from_table(AncientChest1Object.address, index)
        inst.write()
        test_equal()
    for index in range(AncientChest2Object.count):
        inst = AddressChest.from_table(AncientChest2Object.address, index)
        inst.write()
        test_equal()


def test_events():
    for i in range(EventInstObject.count):
        assert Event.from_index(i)


def test_ip_attacks():
    for pointer in IPAttackObject.pointers:
        inst = IPAttack.from_pointer(pointer)
        inst.write()
        test_equal()


def test_items():
    for index in range(ItemObject.count):
        inst = Item.from_table(ItemObject.address, index)
        inst.write()
        test_equal()


def test_maidens():
    pass


def test_monsters():
    for index in range(MonsterObject.count):
        inst = Monster.from_table(MonsterObject.address, index)
        inst.write()
        test_equal()


def test_npcs():
    for index in range(RoamingNPCObject.count):
        inst = RoamingNPC.from_table(RoamingNPCObject.address, index)
        inst.write()
        test_equal()


def test_priests():
    pass  # TODO: Implement PriestObject/From npc?


def test_rewards():
    pass


def test_shops():
    for index in range(ShopObject.count):
        inst = Shop.from_table(ShopObject.address, index)
        inst.write()
        test_equal()


def test_spells():
    for pointer in SpellObject.pointers:
        inst = Spell.from_pointer(pointer)
        inst.write()
        test_equal()


def test_palettes():
    for i in range(CapPaletteObject.count):
        palette = CapsulePallette.from_index(i)
        palette.write()
    for i in range(OverPaletteObject.count):
        over_pallette = OverPallette.from_index(i)
        over_pallette.write()


def test_sprites():
    for i in range(CapSpritePTRObject.count):
        capsule_sprite = CapsuleSprite.from_index(i)
        capsule_sprite.write()
    for i in range(SpriteMetaObject.count):
        sprite_meta = SpriteMeta.from_index(i)
        sprite_meta.write()
    for i in TownSpriteObject.pointers:
        town_sprite = TownSprite.from_pointer(i)
        town_sprite.write()
    for i in range(OverSpriteObject.count):
        over_sprite = OverSprite.from_index(i)
        over_sprite.write()


def test_maps():
    for i in range(MapEventObject.count):
        assert MapEvent.from_index(i)


def test_words():
    for index in range(WordObject.count):
        inst = Word.from_table(WordObject.address, index)
        inst.write()
        test_equal()
