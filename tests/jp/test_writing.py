from helpers.bits import find_table_pointer
from tables.jp import (
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
)
from structures.word import Word
from structures.spell import Spell
from structures.shop import Shop
from structures.reward import RewardItem
from structures.npc import RoamingNPC
from structures.monster import Monster
from structures.maiden import Lisa, Marie, Clare
from structures.item import Item
from structures.ip_attack import IPAttack
from structures.chest import AddressChest, PointerChest
from structures.character import PlayableCharacter
from structures.capsule import CapsuleMonster
from structures.formation import BattleFormation

from helpers.files import original_file, new_file


def test_bosses():
    for i in range(BossFormationObject.count):
        pointer = find_table_pointer(BossFormationObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_formations():
    for i in range(FormationObject.count):
        formation = BattleFormation.from_table(FormationObject.address, i)
        formation.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_map_formations():
    for i in range(MapFormationsObject.count):
        pointer = find_table_pointer(MapFormationsObject.address, i)
        formation = BattleFormation.from_pointer(pointer)
        formation.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_capsules():
    for index in range(CapsuleObject.count):
        inst = CapsuleMonster.from_table(CapsuleObject.address, index)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_characters():
    for index in range(CharacterObject.count):
        inst = PlayableCharacter.from_table(CharacterObject.address, index)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_chests():
    for pointer in ChestObject.pointers:
        inst = PointerChest.from_pointer(pointer)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()
    for index in range(AncientChest1Object.count):
        inst = AddressChest.from_table(AncientChest1Object.address, index)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()
    for index in range(AncientChest2Object.count):
        inst = AddressChest.from_table(AncientChest2Object.address, index)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_events():
    pass


def test_ip_attacks():
    for pointer in IPAttackObject.pointers:
        inst = IPAttack.from_pointer(pointer)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_items():
    for index in range(ItemObject.count):
        inst = Item.from_table(ItemObject.address, index)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_maidens():
    pass


def test_monsters():
    for index in range(MonsterObject.count):
        inst = Monster.from_table(MonsterObject.address, index)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_npcs():
    for index in range(RoamingNPCObject.count):
        inst = RoamingNPC.from_table(RoamingNPCObject.address, index)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_priests():
    pass  # TODO: Implement PriestObject/From npc?


def test_rewards():
    pass


def test_shops():
    for index in range(ShopObject.count):
        inst = Shop.from_table(ShopObject.address, index)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_spells():
    for pointer in SpellObject.pointers:
        inst = Spell.from_pointer(pointer)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()


def test_sprites():
    pass


def test_words():
    for index in range(WordObject.count):
        inst = Word.from_table(WordObject.address, index)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()
