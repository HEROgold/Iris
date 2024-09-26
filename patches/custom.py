import random
from copy import deepcopy

from enums.flags import (
    Alignment,
    CastableSpells,
    EquipableCharacter,
    ItemEffects,
    MenuIcon,
    Targeting,
    Usability,
)
from helpers.bits import bytes_overwrite
from helpers.files import write_file
from logger import iris
from structures import Item, Monster, Spell
from structures.character import InitialEquipment, PlayableCharacter
from structures.chest import AddressChest, PointerChest
from structures.ip_attack import IPAttack
from structures.item import ItemName

from tables import (
    AncientChest1Object,
    AncientChest2Object,
    BlueChestObject,
    ChestObject,
    IPAttackObject,
    ItemObject,
    MonsterObject,
    SpellObject,
)


def get_items():
    return [
        Item.from_index(i)
        for i in range(ItemObject.count)
    ]
def get_spells():
    return [
        Spell.from_pointer(pointer)
        for pointer in SpellObject.pointers
    ]
def get_chests():
    return (
        [PointerChest.from_pointer(i) for i in ChestObject.pointers] +
        [AddressChest.from_table(BlueChestObject.address, i * BlueChestObject.item_index) for i in range(BlueChestObject.count)] +
        [AddressChest.from_table(AncientChest1Object.address, i * AncientChest1Object.item_index) for i in range(AncientChest1Object.count)] +
        [AddressChest.from_table(AncientChest2Object.address, i * AncientChest2Object.item_index) for i in range(AncientChest2Object.count)]
    )
def get_monsters():
    return [
        Monster.from_index(i)
        for i in range(MonsterObject.count)
    ]


def start_char_with_equipment(char: PlayableCharacter, equipment: InitialEquipment):
    iris.info(f"Starting {char.name} with {equipment=}.")
    char.equipment = equipment
    char.equipment.write()


def randomize_starting_equipment(char: PlayableCharacter):
    iris.info(f"Randomizing starting equipment for {char=}.")
    char.equipment.weapon = Item.from_index(random.randint(0 ,466))
    char.equipment.armor = Item.from_index(random.randint(0 ,466))
    char.equipment.shield = Item.from_index(random.randint(0 ,466))
    char.equipment.helmet = Item.from_index(random.randint(0 ,466))
    char.equipment.ring = Item.from_index(random.randint(0 ,466))
    char.equipment.jewelry = Item.from_index(random.randint(0 ,466))
    char.equipment.write()
    return char


def randomize_all_spells():
    iris.info("Randomizing spells.")
    spells = get_spells()
    for spell in deepcopy(spells):
        spell.name = random.choice(spells).name
        spell.unk1
        spell.element = int(random.choice([
            Alignment.NEUTRAL,
            Alignment.LIGHT,
            Alignment.WIND,
            Alignment.WATER,
            Alignment.DARK,
            Alignment.SOIL,
            Alignment.FIRE,
        ]))
        spell.characters = CastableSpells(random.randint(0, CastableSpells.ALL))
        spell.unk4
        spell.mp_cost = random.randint(0, 0xFF)
        spell.price = random.randint(0, 0xFFFF)
        spell.write()


def randomize_all_items():
    iris.info("Randomizing items.")
    items = get_items()
    for item in deepcopy(items):
        item.name_pointer = random.choice(items).name_pointer
        item.price = random.randint(0, 0xFFFF)
        item.equip_types
        item.usability = Usability(random.randint(0, Usability.ALL))
        item.targeting = Targeting(random.randint(0, 0xFF))
        item.icon = MenuIcon(random.choice([MenuIcon.ALL]))
        item.equipability = EquipableCharacter(random.randint(0, EquipableCharacter.ALL))
        item.item_effects = ItemEffects(random.randint(0, ItemEffects.ALL))
        item.item_effects = ItemEffects(random.randint(0, ItemEffects.ALL))
        item.item_types
        item.unknown2
        item.write()


def randomize_all_monsters():
    iris.info("Randomizing monsters.")
    monsters = get_monsters()
    for monster in deepcopy(monsters):
        monster.name = random.choice(monsters).name
        monster.stats.health_points = random.randint(0, 0xFFFF)
        monster.stats.mana_points = random.randint(0, 0xFFFF)
        monster.stats.attack = random.randint(0, 0xFFFF)
        monster.stats.defense = random.randint(0, 0xFFFF)
        monster.stats.agility = random.randint(0, 0xFF)
        monster.stats.intelligence = random.randint(0, 0xFF)
        monster.stats.guts = random.randint(0, 0xFF)
        monster.stats.magic_resistance = random.randint(0, 0xFF)
        monster.stats.xp = random.randint(0, 0xFFFF)
        monster.stats.gold = random.randint(0, 0xFF)
        monster.write()


def randomize_chest_items():
    iris.warning("Randomizing chest items will overwrite the current chest items.")
    chests = get_chests()
    for chest in deepcopy(chests):
        chest.item = Item.from_index(random.randint(0, 466))
        chest.write()


def shuffle_chest_items():
    # TODO: Find out what an item contains, that causes some chests to appear
    # as if they're opened already. When they still contain an item.
    iris.info("Shuffling chest items.")
    chests = get_chests()
    items = [
        i.item
        for i in chests
    ]

    random.shuffle(items)

    for chest in deepcopy(chests):
        chest.item = items.pop(0)
        chest.write()

def shuffle_items():
    """Effectively shuffles all items in the entire game.
    Regardless of where they are pointed from."""
    iris.info("Shuffling items.")
    items = get_items()
    shuffled = deepcopy(items)
    random.shuffle(shuffled)

    for item in shuffled:
        item.name_pointer = shuffled.pop(0).name_pointer
        item.equip_types = shuffled.pop(0).equip_types
        item.usability = shuffled.pop(0).usability
        item.targeting = shuffled.pop(0).targeting
        item.icon = shuffled.pop(0).icon
        item.equipability = shuffled.pop(0).equipability
        item.item_effects = shuffled.pop(0).item_effects
        item.item_effects = shuffled.pop(0).item_effects
        item.item_types = shuffled.pop(0).item_types
        item.unknown2 = shuffled.pop(0).unknown2
        item.write()

def shuffle_monsters():
    iris.info("Shuffling monsters.")
    monsters = get_monsters()
    shuffled = deepcopy(monsters)
    random.shuffle(shuffled)

    for monster in shuffled:
        monster.name = shuffled.pop(0).name
        monster.stats.health_points = shuffled.pop(0).stats.health_points
        monster.stats.mana_points = shuffled.pop(0).stats.mana_points
        monster.stats.attack = shuffled.pop(0).stats.attack
        monster.stats.defense = shuffled.pop(0).stats.defense
        monster.stats.agility = shuffled.pop(0).stats.agility
        monster.stats.intelligence = shuffled.pop(0).stats.intelligence
        monster.stats.guts = shuffled.pop(0).stats.guts
        monster.stats.magic_resistance = shuffled.pop(0).stats.magic_resistance
        monster.stats.xp = shuffled.pop(0).stats.xp
        monster.stats.gold = shuffled.pop(0).stats.gold
        monster.write()


def arty_to_artea():
    """Change Arty to Artea, and Arty's bow to Artea's Bow."""
    iris.info("Changing Arty to Artea.")
    artea = PlayableCharacter.from_index(3)
    item_name = ItemName.from_index(163)

    artea.name = "Artea"
    item_name.name = "Artea's Bow"

    artea.write()
    item_name.write()


def ax_to_axe():
    """Rename all items with "ax" in their name to "axe"."""
    iris.info("Renaming 'ax' to 'axe'.")
    for index in range(ItemObject.count):
        item = Item.from_index(index)
        if "ax" in item.name_pointer.name:
            # Include the spaces to avoid overwriting big names
            item.name_pointer.name = item.name_pointer.name.replace(" ax ", " axe")
            iris.info(f"Renamed to: {item.name_pointer}.")
            item.write()
    
    ax_attack = IPAttack.from_pointer(IPAttackObject.pointers[164])
    ax_attack.name = ax_attack.name.replace("ax ", "axe")
    iris.info(f"Renamed to: {ax_attack.name}.")


def swap_pierre_danielle_sprites():
    """Swap the sprites of Piere and Danielle.
    Reflects their damage type with their colors, rather than weakness type."""
    iris.info("Swapping sprites for Pierre and Danielle.")
    pierre = Monster.from_index(191)
    danielle = Monster.from_index(192)

    pierre.sprite_index, danielle.sprite_index = danielle.sprite_index, pierre.sprite_index
    pierre.write()
    danielle.write()


def guy_the_mage():
    guy = PlayableCharacter.from_index(1)
    guy.stats.mana_points = 0xFFFF

    for spell in get_spells():
        spell.characters += CastableSpells.GUY
        spell.write()


def gorem_to_golem():
    for monster in get_monsters():
        if "Gorem" in monster.name:
            monster.name = monster.name.replace("Gorem", "Golem")
            monster.write()

def set_rom_name(name: bytes):
    write_file.seek(0x007FC0)
    empty_name = bytes(21)
    assert len(name) <= len(empty_name)
    write_file.write(name)

def fix_boltfish():
    """Fix the boltfish attack script to avoid softlocks.
    This sets 2 offsets to 0x45.
    Previously they pointed to itself (0x3b)."""
    bolt_fish = Monster.from_index(85)
    assert bolt_fish.attack_script
    code = bolt_fish.attack_script.bytecode
    patch = b"\x45"
    patched_code = bytes_overwrite(code, 0x15, patch)
    patched_code = bytes_overwrite(patched_code, 0x1A, patch)
    bolt_fish.attack_script.bytecode = patched_code
    bolt_fish.write()
    bolt_fish.attack_script.read()
