from args import args
from patcher import (
    apply_game_genie_codes,
    apply_patch,
    apply_absynnonym_patch,
    set_spawn_location,
    start_engine,
)
from patches.RealCritical import ac_more_enemies, fix_cave_chest_table, fix_menu, jelly_damage_display, killer_names
from patches.HEROgold import arty_to_artea, ax_to_axe, fix_boltfish, gorem_to_golem, guy_the_mage, set_rom_name, swap_pierre_danielle_sprites

from patches.RealCritical.sprites import bunny_girls, fix_shrine_tile_set
from structures.zone import Zone

from helpers.files import read_file, write_file
from tests.read_write import read_write_all

from constants import ASCII_ART_COLORIZED, PROJECT_NAME, VERSION
from logger import iris


def main() -> None:
    print(ASCII_ART_COLORIZED)
    print(f"You are using the Lufia II randomizer {PROJECT_NAME} version {VERSION}.\n")

    if args.debug:
        iris.setLevel("DEBUG")

    if args.no_patch:
        read_write_all()

    set_rom_name(b"Lufia II (Iris patch)") # For identification purposes.

    apply_patch(args.selected_patch) # TODO: test with others besides Vanilla.
    if args.fix_softlocks:
        fix_boltfish()

    if args.debug:
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
        # FIXME: Doesn't apply to ROM. > Figure out why.
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
        apply_absynnonym_patch("capsule_feeding_bonus")
    if args.clear_initial_spells:
        apply_absynnonym_patch("clear_initial_spells")
    if args.eat_dragon_eggs:
        apply_absynnonym_patch("eat_dragon_eggs")
    if args.no_boat_encounters:
        apply_absynnonym_patch("no_boat_encounters")
    if args.secondary_tool:
        apply_absynnonym_patch("secondary_tool")
    if args.unlock_gift_mode:
        apply_absynnonym_patch("unlock_gift_mode")
    # if args.custom_spawn_city:
    #     set_spawn_location(Zone.from_name("Elcid"), entrance_cutscene=0x02) # TODO: Investigate and fix (event) script loading.
        # set_spawn_location(ZoneObject.from_name(args.spawn_location))
    if args.start_engine:
        start_engine()

    if args.capsule_master_select:
        apply_absynnonym_patch("capsule_master_select")
    if args.capsule_tag:
        apply_absynnonym_patch("capsule_tag")
    if args.ancient_cave_items:
        apply_absynnonym_patch("fix_ac_items")
    if args.no_maxim_boat:
        apply_absynnonym_patch("maximless_boat_fix")
    if args.no_maxim_warp:
        apply_absynnonym_patch("maximless_warp_animation_fix")
    if args.no_submarine:
        apply_absynnonym_patch("no_submarine")
    if args.spell_target_limit:
        apply_absynnonym_patch("spell_target_limit")
    if args.zero_capsule_command:
        apply_absynnonym_patch("zero_capsule_command")
    if args.zero_gold_command:
        apply_absynnonym_patch("zero_gold_command")

    # TODO: Implement a route finder, which will place required items (arrow, hook, scenario items.)

    # Apply custom patches
    ax_to_axe()
    arty_to_artea()
    gorem_to_golem()
    swap_pierre_danielle_sprites()
    guy_the_mage()

    # Apply RealCritical patches
    ac_more_enemies()
    fix_cave_chest_table()
    fix_menu()
    # gift_mode() # Already done by absynnonym. (unlock_gift_mode)
    killer_names() # Could be done with Iris. (Would also allow for moving item table if required later.)
    jelly_damage_display() # Should be done with Iris.  (When a more capable script parser is implemented.)
    bunny_girls()
    fix_shrine_tile_set()

    # Randomize the game
    # randomize_all_spells()
    # randomize_all_items() # Causes issues bc random bits are set (works in theory, crashes in practice.)
    # shuffle_items()
    # randomize_all_monsters() # Causes issues bc random bits are set (works in theory, crashes in practice.)
    # shuffle_monsters()
    # shuffle_chest_items()
    # randomize_chest_items()



if __name__ == "__main__":
    main()

read_file.close()
write_file.close()

# TODO: Implement the following:
# Create own rom extractor, which can and should extract data from the rom. > well on its way
# This **SHOULD** work for different versions of the rom.
# TODO: Add some form of caching to avoid cloning and for faster access.
