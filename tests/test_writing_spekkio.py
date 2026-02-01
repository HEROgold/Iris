from helpers.bits import find_table_pointer
from structures.capsule import CapsuleMonster
from structures.character import PlayableCharacter
from structures.chest import AddressChest, PointerChest
from structures.events import Event, MapEvent
from structures.formation import BattleFormation
from structures.ip_attack import IPAttack
from structures.item import Item
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
from tables.spekkio import (
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
from tests.reset_file import test_equal


def test_bosses() -> None:
    for i in range(BossFormationObject.count):
        pointer = find_table_pointer(BossFormationObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()
        test_equal()


def test_formations() -> None:
    for i in range(FormationObject.count):
        formation = BattleFormation.from_table(FormationObject.address, i)
        formation.write()
        test_equal()


def test_map_formations() -> None:
    for i in range(MapFormationsObject.count):
        pointer = find_table_pointer(MapFormationsObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()
        test_equal()


def test_capsules() -> None:
    for index in range(CapsuleObject.count):
        inst = CapsuleMonster.from_table(CapsuleObject.address, index)
        inst.write()
        test_equal()


def test_characters() -> None:
    for index in range(CharacterObject.count):
        inst = PlayableCharacter.from_table(CharacterObject.address, index)
        inst.write()
        test_equal()


def test_chests() -> None:
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


def test_events() -> None:
    for i in range(EventInstObject.count):
        assert Event.from_index(i)


def test_ip_attacks() -> None:
    for pointer in IPAttackObject.pointers:
        inst = IPAttack.from_pointer(pointer)
        inst.write()
        test_equal()


def test_items() -> None:
    for index in range(ItemObject.count):
        inst = Item.from_table(ItemObject.address, index)
        inst.write()
        test_equal()


def test_maidens() -> None:
    pass


def test_monsters() -> None:
    for index in range(MonsterObject.count):
        inst = Monster.from_table(MonsterObject.address, index)
        inst.write()
        test_equal()


def test_npcs() -> None:
    for index in range(RoamingNPCObject.count):
        inst = RoamingNPC.from_reference(RoamingNPCObject.address, index)
        inst.write()
        test_equal()


def test_priests() -> None:
    pass  # TODO: Implement PriestObject/From npc?


def test_rewards() -> None:
    pass


def test_shops() -> None:
    for index in range(ShopObject.count):
        inst = Shop.from_table(ShopObject.address, index)
        inst.write()
        test_equal()


def test_spells() -> None:
    for pointer in SpellObject.pointers:
        inst = Spell.from_pointer(pointer)
        inst.write()
        test_equal()


def test_palettes() -> None:
    for i in range(CapPaletteObject.count):
        palette = CapsulePallette.from_index(i)
        palette.write()
    for i in range(OverPaletteObject.count):
        over_pallette = OverPallette.from_index(i)
        over_pallette.write()


def test_sprites() -> None:
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


def test_maps() -> None:
    for i in range(MapEventObject.count):
        assert MapEvent.from_index(i)


def test_words() -> None:
    for index in range(WordObject.count):
        inst = Word.from_table(WordObject.address, index)
        inst.write()
        test_equal()
