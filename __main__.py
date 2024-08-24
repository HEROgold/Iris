import logging
from typing import TYPE_CHECKING, Any

from args import args
from enums.flags import Flags
from enums.patches import Patch
from helpers.bits import read_little_int
from patcher import (
    apply_game_genie_codes,
    apply_patch,
    max_world_clock,
    open_world_base,
    apply_patch_name,
    set_spawn_location,
    skip_tutorial,
    start_engine,
    test_translate_genie_code_chars,
    treadool_warp,
)
from patches.custom import arty_to_artea, ax_to_axe, gorem_to_golem, randomize_all_items, randomize_all_monsters, randomize_all_spells, randomize_chest_items, randomize_starting_equipment, set_rom_name, shuffle_chest_items, shuffle_items, shuffle_monsters, swap_pierre_danielle_sprites
from structures import (
    AddressChest,
    BattleFormation,
    CapsuleMonster,
    Item,
    Monster,
    Shop,
    Spell,
)
from structures.capsule import CapsuleAttack
from structures.character import PlayableCharacter
from structures.chest import PointerChest
from structures.ip_attack import IPAttack
from structures.shop import ShopKureji
from structures.word import Word

from structures.zone import Zone
from tables import CharExpObject
from tables.zones import ZoneObject


if TYPE_CHECKING:
    from src._types.objects import all_table_objects
else:
    from _types.objects import all_table_objects
from helpers.files import read_file, write_file, new_file, original_file

from config import ASCII_ART_COLORIZED, PROJECT_NAME, VERSION
from logger import iris, dump
from tables import (
    AncientChest1Object,
    AncientChest2Object,
    BlueChestObject,
    BossFormationObject,
    CapAttackObject,
    CapsuleLevelObject,
    CapsuleObject,
    CharacterObject,
    CharGrowthObject,
    ChestObject,
    FormationObject,
    InitialEquipObject,
    IPAttackObject,
    ItemNameObject,
    ItemObject,
    MapFormationsObject,
    MonsterObject,
    ShopObject,
    SpellObject,
    WordObject,
)

# Some arrays with byte data for the "PATCH" and "EOF" of the IPS
patch_magic = [0x50, 0x41, 0x54, 0x43, 0x48]
eof_magic = [0x45, 0x4F, 0x46]
objects: list[Any] = []
active_flags = Flags(0)
selected_flags = Flags(0)

flags = Flags(0)
if args.character:
    flags += Flags.CHARACTER
if args.item:
    flags += Flags.ITEMS
if args.spell:
    flags += Flags.SPELLS
if args.monster:
    flags += Flags.MONSTERS
if args.movement:
    flags += Flags.MONSTER_MOVEMENT
if args.capsule:
    flags += Flags.CAPSULES
if args.shop:
    flags += Flags.SHOPS
if args.treasure:
    flags += Flags.TREASURE
if args.world:
    flags += Flags.WORLD


def gather_objects():
    for cls in all_table_objects:
        cls = cls()
        log = logging.getLogger(f"{iris.name}.Gathering.{cls.__class__.__name__}")
        log.debug(f"Reading {cls.__class__.__name__}")
        if isinstance(cls, ChestObject):
            for pointer in cls.pointers:
                chest = PointerChest.from_pointer(pointer)
                objects.append(chest)
                chest.write()
        elif isinstance(cls, IPAttackObject): 
            for pointer in cls.pointers: 
                ip_attack = IPAttack.from_pointer(pointer)
                objects.append(ip_attack) 
                ip_attack.write()
        elif isinstance(cls, (AncientChest1Object, AncientChest2Object, BlueChestObject)):
            for offset in range(cls.count):
                chest = AddressChest.from_table(cls.address, offset)
                objects.append(chest)
                chest.write()
        elif isinstance(cls, FormationObject):
            for offset in range(cls.count):
                formation = BattleFormation.from_table(cls.address, offset)
                objects.append(formation)
                formation.write()
        elif isinstance(cls, CapsuleObject):
            for offset in range(cls.count):
                capsule = CapsuleMonster.from_table(cls.address, offset)
                objects.append(capsule)
                capsule.write()
        elif isinstance(cls, CharacterObject):
            for offset in range(cls.count):
                character = PlayableCharacter.from_table(cls.address, offset)
                objects.append(character)
                character.write()
        elif isinstance(cls, ItemObject): 
            for offset in range(cls.count): 
                item = Item.from_index(offset)
                objects.append(item) 
                item.write()
        elif isinstance(cls, MonsterObject):
            for offset in range(cls.count):
                monster = Monster.from_index(offset)
                objects.append(monster)
                monster.write()
        elif isinstance(cls, ShopObject): # TODO
            if args.selected_patch == Patch.KUREJI: # type: ignore
                for i, pointer in enumerate(cls.pointers):
                    shop = ShopKureji.from_pointer(pointer, i)
                    objects.append(shop)
                    shop.write()
            else:
                # LSP thinks they are from kureji. So we ignore some type errors.
                for offset in range(cls.count): # type: ignore
                    shop = Shop.from_index(offset) # type: ignore
                    objects.append(shop)
                    shop.write()
        elif isinstance(cls, SpellObject):
            for pointer in cls.pointers:
                spell = Spell.from_pointer(pointer)
                objects.append(spell)
                spell.write()
        elif isinstance(cls, WordObject):
            for offset in range(cls.count):
                word = Word.from_table(WordObject.address, offset)
                objects.append(word)
                word.write()
        elif isinstance(cls, CapAttackObject):
            for offset in range(cls.count):
                capsule_attack = CapsuleAttack.from_table(cls.address, offset)
                objects.append(capsule_attack)
                capsule_attack.write()
        elif isinstance(cls, ZoneObject):
            for offset in range(cls.count):
                zone = Zone.from_index(offset)
                objects.append(zone)
                zone.write()
        elif isinstance(cls, (
                ItemNameObject,  # Implemented in Items
                CapsuleLevelObject,  # implemented in Capsules
                BossFormationObject,  # implemented in Formations
                MapFormationsObject,  # implemented in Formations
                CharExpObject,  # implemented in PlayableCharacter
                CharGrowthObject,  # implemented in PlayableCharacter
                InitialEquipObject,  # implemented in PlayableCharacter
            )
        ):
            pass
        else:
            msg = f"Table {cls.__class__.__name__} not implemented."
            if args.debug:
                log.warning(msg)
            else:
                raise NotImplementedError(msg)
        # Check if the read and write files are the same (As expected without randomization)
        with original_file.open("rb") as f1, new_file.open("rb") as f2:
            if f1.readlines() != f2.readlines():
                log.critical(f"Read and write files are not the same, after {cls.__class__.__name__}")


def main() -> None:
    print(ASCII_ART_COLORIZED)
    print(f"You are using the Lufia II randomizer {PROJECT_NAME} version {VERSION}.\n")

    if args.debug:
        iris.setLevel("DEBUG")

    apply_patch(args.selected_patch) # TODO: test with others besides Vanilla.
    if args.no_patch:
        # Reads > immediately writes, after this, new file and original file are the exact same. (for debugging/testing purposes)
        gather_objects()
        for obj in objects:
            dump.info(f"{obj.__class__.__name__}.pre: {obj.__dict__}")

    # Rom identification
    set_rom_name()

    if args.debug:
        test_translate_genie_code_chars()
        apply_game_genie_codes("206A-4FAA")  # Enable Debug Mode (For Debug Menu)
        # CB81-CD0A > Start ancient cave with 99 floors
        # 1481-CD6A > Unknown
        # DDAD-30B8 > Ancient Cave Boss Dies From 1 Hit (Necessary,
        # DDAD-3028 > unless you think you can beat the boss at level 1 with no items)
        apply_game_genie_codes("DDAD-30B8", "DDAD-3028")
        # BAC2-44AD > Enable All Ancient Dungeon Trophies
        # (Keep talking to the person below the lowest level of the bar to keep
        # receiving trophies. The trophies will be displayed temporarily if you don't
        # talk to the person there, and will stay displayed if you do talk to them)
        # 1DE6-3DDC > Dont need Scenario items (1)
        apply_game_genie_codes("1DE6-3DDC") 
        # 1DB8-CD9C, C2B2-3FFB > Airship anywhere, anytime
        apply_game_genie_codes("1DB8-CD9C", "C2B2-3FFB") 
        # 6DE9-3F01, D2E9-3F61 > Monsters always drop items.
        apply_game_genie_codes("6DE9-3F01", "D2E9-3F61")  
        # 04E1-3761, A1E1-3761 > Always drop 33 or 99. Use only one.
        # apply_game_genie_codes("04E1-3761") 
        # 6DA0-C7AB > Capsule monsters like all food a lot
        apply_game_genie_codes("6DA0-C7AB")
        # D5C5-3F6D > Talk To A Priest To Get A Report
        # (Can't Exit The Report, but it's normally only accessible from the end of the game)
        # 88A6-4FFA > See "end of game" report on Elcid sign
        apply_game_genie_codes("88A6-4FFA")
        # Unlock all warp locations.
        # FIXME: Doesn't apply to ROM. > Verify
        # apply_game_genie_codes(
        #     "7E097BFF","7E097CFF","7E097DFF","7E097EFF",
        #     "7E097FFF","7E0980FF","7E0981FF","7E0982FF",
        #     "7E0983FF" ,"7E0986FF","7E0988FF","7E0989FF",
        #     "7E098AFF","7E098BFF","7E098CFF","7E098DFF",
        #     "7E098EFF","7E098FFF","7E0990FF","7E0991FF",
        #     "7E0992FF","7E0996FF",
        # )

    apply_game_genie_codes(*args.game_genie_codes)

    # Apply Event patches
    # TODO: Implement EventParser
    # if args.max_world_clock:
    #     max_world_clock()
    # if args.open_world_base:
    #     open_world_base()
    # if args.skip_tutorial:
    #     skip_tutorial()
    # if args.treadool_warp:
    #     treadool_warp()

    # Apply Randomizer patches
    if args.capsule_feeding_bonus:
        apply_patch_name("capsule_feeding_bonus")
    if args.clear_initial_spells:
        apply_patch_name("clear_initial_spells")
    if args.eat_dragon_eggs:
        apply_patch_name("eat_dragon_eggs")
    if args.no_boat_encounters:
        apply_patch_name("no_boat_encounters")
    if args.secondary_tool:
        apply_patch_name("secondary_tool")
    if args.unlock_gift_mode:
        apply_patch_name("unlock_gift_mode")
    if args.custom_spawn_city:
        set_spawn_location(Zone.from_name("Elcid"), 0x02)
        # set_spawn_location(ZoneObject.from_name(args.spawn_location))
    if args.start_engine:
        start_engine()

    # Apply Fixing patches
    # if args.ancient_cave_music:
        # patch_name("ac_music_hack")  # Won't be implemented
    if args.capsule_master_select:
        apply_patch_name("capsule_master_select")
    if args.capsule_tag:
        apply_patch_name("capsule_tag")
    if args.ancient_cave_items:
        apply_patch_name("fix_ac_items")
    if args.no_maxim_boat:
        apply_patch_name("maximless_boat_fix")
    if args.no_maxim_warp:
        apply_patch_name("maximless_warp_animation_fix")
    if args.no_submarine:
        apply_patch_name("no_submarine")
    if args.spell_target_limit:
        apply_patch_name("spell_target_limit")
    if args.zero_capsule_command:
        apply_patch_name("zero_capsule_command")
    if args.zero_gold_command:
        apply_patch_name("zero_gold_command")

    # TODO: Then implement a route finder, which will place required items (arrow, hook, scenario items.)
    # gather_objects()

    for obj in objects:
        dump.info(f"{obj.__class__.__name__}.pre: {obj.__dict__}")

    # Apply custom patches
    ax_to_axe()
    arty_to_artea()
    gorem_to_golem()
    swap_pierre_danielle_sprites()

    # Randomize the game
    # randomize_all_spells()
    # randomize_all_items() # Causes issues bc random bits are set (works in theory, crashes in practice.)
    # shuffle_items()
    # randomize_all_monsters() # Causes issues bc random bits are set (works in theory, crashes in practice.)
    # shuffle_monsters()
    # shuffle_chest_items()
    # randomize_chest_items()

    # TODO: For this to work, we need to re-read all objects from the new file.
    # for obj in objects:
        # dump.info(f"{obj.__class__.__name__}.post: {obj.__dict__}")


if __name__ == "__main__":
    main()

read_file.close()
write_file.close()

# TODO: Implement the following:
# Create own rom extractor, which can and should extract data from the rom. > well on its way
# This **SHOULD** work for different versions of the rom.
# The extractor should find pointers, addresses etc. and create a json file with all the data.
# This json file will be used to create the objects.
# TODO: Add some form of caching to avoid cloning?
