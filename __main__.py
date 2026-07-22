from args import args
from helpers.files import read_file, write_file
from logger import iris
from patcher import (
    apply_absynnonym_patch,
    apply_game_genie_codes,
    apply_patch,
    set_spawn_location,
    start_engine,
)
from patches.genie_codes import (
    AIRSHIP_ANYWHERE,
    ALWAYS_DROP_33,
    CAPSULE_ALWAYS_LOVE_FOOD,
    ELCID_REPORT,
    MASTER_ONE_SHOT,
    NO_SCENARIO_ITEMS,
    UNLOCK_WARP,
)
from patches.HEROgold import (
    arty_to_artea,
    ax_to_axe,
    fix_boltfish,
    gorem_to_golem,
    guy_the_mage,
    # maxim_starts_with_warp,
    party_toggle_in_elcid,
    set_rom_name,
    swap_pierre_danielle_sprites,
    unlock_all_warp_destinations,
)
from patches.RealCritical import (
    ac_more_enemies,
    fix_cave_chest_table,
    fix_menu,
    jelly_damage_display,
    killer_names,
)
from patches.RealCritical.sprites import bunny_girls, fix_shrine_tile_set
from structures.zone import Zone
from tests.read_write import read_write_all


def main() -> None:

    if args.debug:
        iris.setLevel("DEBUG")

    if args.no_patch:
        read_write_all()
        # Cleanup after testing.
        write_file.close()
        # new_file.unlink()
        return

    set_rom_name(b"Lufia II (Iris patch)") # For identification purposes.

    party_toggle_in_elcid()  # event-script demo: Elcid townspeople toggle party join/leave

    apply_patch(args.selected_patch) # TODO: test with others besides Vanilla.
    if args.fix_softlocks:
        fix_boltfish()

    if args.debug:
        # apply_game_genie_codes(DEBUG_MODE)
        apply_game_genie_codes(*MASTER_ONE_SHOT)
        apply_game_genie_codes(NO_SCENARIO_ITEMS)
        apply_game_genie_codes(*AIRSHIP_ANYWHERE)
        apply_game_genie_codes(ALWAYS_DROP_33)
        apply_game_genie_codes(CAPSULE_ALWAYS_LOVE_FOOD)
        apply_game_genie_codes(ELCID_REPORT)
        # Unlock all warp locations.
        # Doesn't apply to ROM. Why? Because some are applied to running memory.
        # These also don't contain a `-` between the 2 parts of the code
        # Like flags for warp unlocks
        apply_game_genie_codes(*UNLOCK_WARP)
        apply_game_genie_codes("7E0C4324") # Maxim starts with warp. (slot 1)

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
    if args.custom_spawn_city:
        set_spawn_location(Zone.from_name("Elcid"), entrance_cutscene=0x02) # TODO: Investigate and fix (event) script loading.
        # set_spawn_location(Zone.from_name(args.spawn_location))
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
    # Dev/debug patches (not intended for release):
    # maxim_starts_with_warp()  # dev fix: Maxim begins every game knowing Warp (field teleport)
    unlock_all_warp_destinations()  # dev fix: every Warp destination available from a fresh save

    # Apply RealCritical patches
    fix_menu()
    killer_names() # Could be done with Iris. (Would also allow for moving item table if required later.)
    # gift_mode() # Already done by absynnonym. (unlock_gift_mode)
    ac_more_enemies()
    fix_cave_chest_table()
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

    # Chest randomizers -- two independent options (see docs/chest_system.md). Enable either:
    # from patches.HEROgold.chest_randomizer import randomize_chest_contents, randomize_chest_locations
    # randomize_chest_contents()    # randomize WHAT each chest holds
    # randomize_chest_locations()   # shuffle WHERE chests sit, within each map



if __name__ == "__main__":
    main()

read_file.close()
write_file.close()

# TODO: Implement the following:
# Create own rom extractor, which can and should extract data from the rom. > well on its way
# This **SHOULD** work for different versions of the rom.
# TODO: Add some form of caching to avoid cloning and for faster access.
