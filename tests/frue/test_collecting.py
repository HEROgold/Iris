from helpers.bits import find_table_pointer
from structures.capsule import CapsuleMonster
from structures.character import PlayableCharacter
from structures.chest import AddressChest, PointerChest
from structures.events import Event, MapEvent
from structures.formation import BattleFormation
from structures.ip_attack import IPAttack
from structures.item import Item
from structures.maiden import Clare, Lisa, Marie
from structures.monster import Monster
from structures.npc import RoamingNPC
from structures.shop import Shop
from structures.spell import Spell
from structures.sprites import (
    CapsulePallette,
    CapsuleSprite,
    OverPallette,
    OverSprite,
    SpriteMeta,
    TownSprite,
)
from structures.word import Word
from tables.frue import (
    AncientChest1Object,
    AncientChest2Object,
    BossFormationObject,
    CapPaletteObject,
    CapSpritePTRObject,
    CapsuleObject,
    CharacterObject,
    ChestObject,
    EventInstObject,
    FormationObject,
    IPAttackObject,
    ItemObject,
    MapEventObject,
    MapFormationsObject,
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


def test_capsules():
    for index in range(CapsuleObject.count):
        assert CapsuleMonster.from_table(CapsuleObject.address, index)


def test_characters():
    for index in range(CharacterObject.count):
        assert PlayableCharacter.from_table(CharacterObject.address, index)


def test_chests():
    for pointer in ChestObject.pointers:
        assert PointerChest.from_pointer(pointer)
    for index in range(AncientChest1Object.count):
        assert AddressChest.from_table(AncientChest1Object.address, index)
    for index in range(AncientChest2Object.count):
        assert AddressChest.from_table(AncientChest2Object.address, index)


def test_events():
    for i in range(EventInstObject.count):
        assert Event.from_index(i)


def test_bosses():
    for i in range(BossFormationObject.count):
        pointer = find_table_pointer(BossFormationObject.address, i)
        assert BattleFormation.from_pointer(pointer)


def test_formations():
    for i in range(FormationObject.count):
        assert BattleFormation.from_table(FormationObject.address, i)


def test_map_formations():
    for i in range(MapFormationsObject.count):
        pointer = find_table_pointer(MapFormationsObject.address, i)
        assert BattleFormation.from_pointer(pointer)


def test_ip_attacks():
    for pointer in IPAttackObject.pointers:
        assert IPAttack.from_pointer(pointer)


def test_items():
    for index in range(ItemObject.count):
        assert Item.from_table(ItemObject.address, index)


def test_maidens():
    assert Lisa
    assert Marie
    assert Clare


def test_monsters():
    for index in range(MonsterObject.count):
        assert Monster.from_table(MonsterObject.address, index)


def test_npcs():
    for index in range(RoamingNPCObject.count):
        assert RoamingNPC.from_table(RoamingNPCObject.address, index)


def test_priests():
    pass  # TODO: Implement PriestObject/From npc?


def test_rewards():
    pass


def test_shops():
    for index in range(ShopObject.count):
        assert Shop.from_table(ShopObject.address, index)


def test_spells():
    for pointer in SpellObject.pointers:
        assert Spell.from_pointer(pointer)


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
        assert Word.from_table(WordObject.address, index)
