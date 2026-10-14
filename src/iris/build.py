"""Build a ROM in memory from a source ROM and typed options, with no command line and no disk write (Iris-Dev#5).

The CLI (``__main__``), the Archipelago world and the check-ROM scripts all build through :func:`build`. Each call opens
its own ROM session, which drops every cache of the previous one, so builds in one process don't share state.
"""

import random
from dataclasses import KW_ONLY, dataclass, fields
from pathlib import Path
from typing import Self

from iris.args import Args
from iris.constants import SUGGESTED_PATCH
from iris.enums.patches import Patch
from iris.helpers.files import open_rom, output_bytes
from iris.patcher import (
    apply_absynnonym_patch,
    apply_game_genie_codes,
    set_spawn_location,
)
from iris.patches.genie_codes import (
    AIRSHIP_ANYWHERE,
    CAPSULE_ALWAYS_LOVE_FOOD,
    DEBUG_MODE,
    ELCID_REPORT,
    MASTER_ONE_SHOT,
    NO_SCENARIO_ITEMS,
)
from iris.patches.HEROgold import (
    apply_new_game_hook,
    arty_to_artea,
    ax_to_axe,
    everyone_learns_reset,
    fix_boltfish,
    foomy_s_firebird_valor,
    gorem_to_golem,
    guy_the_mage,
    max_out_party,
    party_toggle_in_elcid,
    scale_encounters,
    set_found_flags_on_story_joins,
    set_rom_name,
    swap_pierre_danielle_sprites,
)
from iris.patches.HEROgold.new_game import INTRO_SPAWN_ENTRANCE
from iris.patches.HEROgold.scale_encounters import (
    AP_DEFAULT_BAND,
    install_ap_encounter_scaling,
    write_ap_scaling_defaults,
)
from iris.patches.HEROgold.start_capsule import start_capsule
from iris.patches.RealCritical import (
    ac_more_enemies,
    fix_cave_chest_table,
    fix_menu,
    jelly_damage_display,
    killer_names,
)
from iris.patches.archipelago.overworld.basepatch import apply_overworld_basepatch
from iris.patches.archipelago.overworld.grant_flags import set_flags_on_grants
from iris.patches.archipelago.overworld.grant_text import name_placed_items
from iris.patches.archipelago.overworld.hand_ins import gate_airship_on_engine, gate_hand_ins_on_items
from iris.patches.archipelago.overworld.hint_npcs import hint_npc_candidates
from iris.patches.open_world import apply_open_world
from iris.patches.open_world.bosses import (
    fixed_placement,
    place_bosses,
    BOSS_SCALING_NONE,
    BOSS_SCALING_PARTY,
    install_boss_scaling,
    scale_to_depth,
    shuffled_placement,
)
from iris.patches.open_world.leader import LEADERS, set_leader
from iris.patches.RealCritical.sprites import bunny_girls, fix_shrine_tile_set
from iris.structures.item import Item
from iris.structures.monster import Monster
from iris.structures.shop import Shop
from iris.structures.zone import Zone, move_all_zone_data
from iris.tables import select
from tests.read_write import read_write_all


# Absynnonym patches, in the order they're applied: (option, patch name).
_RANDOMIZER_PATCHES = (
    ("capsule_feeding_bonus", "capsule_feeding_bonus"),
    ("clear_initial_spells", "clear_initial_spells"),
    ("eat_dragon_eggs", "eat_dragon_eggs"),
    ("no_boat_encounters", "no_boat_encounters"),
    ("secondary_tool", "secondary_tool"),
    ("unlock_gift_mode", "unlock_gift_mode"),
)
_FIX_PATCHES = (
    ("capsule_master_select", "capsule_master_select"),
    ("capsule_tag", "capsule_tag"),
    ("ancient_cave_items", "fix_ac_items"),
    ("no_maxim_boat", "maximless_boat_fix"),
    ("no_maxim_warp", "maximless_warp_animation_fix"),
    ("no_submarine", "no_submarine"),
    ("spell_target_limit", "spell_target_limit"),
    ("zero_capsule_command", "zero_capsule_command"),
    ("zero_gold_command", "zero_gold_command"),
)


@dataclass(frozen=True)
class Options:
    """What a build does. Field names match :class:`args.Args`, so :meth:`from_args` copies them over."""

    seed: int
    _: KW_ONLY
    selected_patch: Patch = SUGGESTED_PATCH
    debug: bool = False
    no_patch: bool = False
    debug_party: bool = False
    easy_mode: bool = False
    fix_softlocks: bool = False
    foomy_firebird: bool = False
    skip_tutorial: bool = False
    skip_intro: bool = False
    """Debug runs: a new game starts in Elcid past the intro scenes, with their flags set. Implies ``skip_tutorial``."""
    game_genie_codes: tuple[str, ...] = ()
    scale_encounters: tuple[int, int] | None = None
    start_capsule: int | None = None
    start_capsule_name: str | None = None
    start_items: tuple[tuple[int, int], ...] = ()
    """``(item index, quantity)`` pairs in the inventory at new game."""
    custom_spawn_city: bool = False
    start_mermaid_jade: bool = False
    """Start with the Mermaid jade and the submarine at Elcid's dock (Iris-Dev#24)."""
    start_engine: bool = False
    """Start with the Engine and the airship at Elcid's dock. It can also dive: vanilla has no airship-only ship."""
    capsule_feeding_bonus: bool = False
    clear_initial_spells: bool = False
    eat_dragon_eggs: bool = False
    no_boat_encounters: bool = False
    secondary_tool: bool = False
    unlock_gift_mode: bool = False
    capsule_master_select: bool = False
    capsule_tag: bool = False
    ancient_cave_items: bool = False
    no_maxim_boat: bool = False
    no_maxim_warp: bool = False
    no_submarine: bool = False
    spell_target_limit: bool = False
    zero_capsule_command: bool = False
    zero_gold_command: bool = False
    unlock_warps: bool = True
    """Dev fix: every Warp destination is open from the start. Off for Archipelago, whose logic tracks travel."""
    open_world: bool = False
    """terrorwave's open world: the story at its end, every area open (Iris-Dev#43)."""
    open_world_extras: tuple[str, ...] = ()
    """Optional open-world patches, by name (``patches.open_world.EXTRAS``). Each needs ``open_world``."""
    leader: int | None = None
    boss_placement: str = "shuffled"
    boss_strength: str = "unchanged"
    """Open world: ``"unchanged"``, ``"depth"`` (each boss as strong as the story's boss for its spot) or ``"party"``."""
    """Open world: which boss stands at which boss-NPC spot, ``"shuffled"`` (per seed) or ``"fixed"`` (story order)."""
    """Open world: the character index (1-6) who leads instead of Maxim."""
    archipelago: bool = False
    """Add the overworld Archipelago base patch (config block, AP item); see tools/build_ap_basepatch.py."""

    @classmethod
    def from_args(cls, args: Args) -> Self:
        """The options of a parsed command line (see :func:`args.parse_args`)."""
        values = {field.name: getattr(args, field.name) for field in fields(cls) if hasattr(args, field.name)}
        values["game_genie_codes"] = tuple(values["game_genie_codes"])
        values["open_world_extras"] = tuple(values["open_world_extras"])
        if args.leader is not None:
            name = random.Random(args.seed).choice(sorted(LEADERS)) if args.leader == "random" else args.leader
            values["leader"] = LEADERS[name]
        if values["scale_encounters"] is not None:
            low, high = values["scale_encounters"]
            values["scale_encounters"] = (low, high)
        return cls(**values)


def build(source: Path | bytes, options: Options) -> bytes:
    """Build the ROM ``options`` describe from ``source`` and return it. It stays the active session until the next build."""
    select(options.selected_patch)
    Shop.verify_pointers = options.debug or options.no_patch  # an unrandomized ROM keeps every shop's next pointer
    Monster.easy_mode = options.easy_mode
    # One read of the ROM, with the base patch (FRUE, Spekkio, Kureji) applied before any structure reads it.
    open_rom(source, base=options.selected_patch)

    if options.no_patch:
        read_write_all()
        return output_bytes()

    set_rom_name(b"Lufia II (Iris patch)") # For identification purposes.
    if (options.open_world_extras or options.leader is not None) and not options.open_world:
        msg = "Open-world extras and --leader need open world."
        raise ValueError(msg)
    if options.archipelago or options.open_world:
        move_all_zone_data()  # event containers need to grow (hint slots, open world), before anything reads ZoneData
    if options.open_world:
        apply_open_world(options.open_world_extras, reserve=options.archipelago)  # replaces whole scripts, so before any patch edits one
        if options.leader is not None:
            set_leader(options.leader)
        placement = shuffled_placement(options.seed) if options.boss_placement == "shuffled" else fixed_placement()
        place_bosses(placement)
        if options.boss_strength == "depth":
            scale_to_depth(placement)
        elif options.boss_strength == "party":
            install_boss_scaling(BOSS_SCALING_PARTY)
        elif options.archipelago:
            install_boss_scaling(BOSS_SCALING_NONE)  # the world's tokens set the mode and levels per seed
    if options.archipelago:
        hint_npcs = hint_npc_candidates()  # before any patch changes a script
        if not options.open_world:
            gate_hand_ins_on_items()  # the hand-ins test the item, not the grant's flag (Iris-Dev#49)
            gate_airship_on_engine()  # Lexis's lab builds the airship from a held Engine (Iris-Dev#86)
        set_flags_on_grants()  # grants that set no flag get one, so the client can report them (Iris-Dev#22)
        if not options.open_world:
            name_placed_items()  # each grant's "Gets ..." message is a slot the world writes the item's name in (Iris-Dev#52)

    party_toggle_in_elcid(require_found=not options.debug_party)  # event-script demo: Elcid townspeople toggle party join/leave
    set_found_flags_on_story_joins()  # story joins also set each character's "found/unlocked" flag

    everyone_learns_reset()  # the party toggle can remove Maxim, who alone learned Reset in vanilla
    if options.fix_softlocks:
        fix_boltfish()
    if options.foomy_firebird:
        foomy_s_firebird_valor()

    if options.debug:
        _apply_debug_codes()
    apply_game_genie_codes(*options.game_genie_codes)

    # TODO: treadool_warp is an event patch too (patches/absynnonym); apply it with event_patch.apply_event_patch_file.

    _apply_randomizer_patches(options)

    # TODO: Implement a route finder, which will place required items (arrow, hook, scenario items.)

    # Apply custom patches
    ax_to_axe()
    arty_to_artea()
    gorem_to_golem()
    swap_pierre_danielle_sprites()
    guy_the_mage()
    # Dev/debug patches (not intended for release):
    # maxim_starts_with_warp()  # dev fix: Maxim begins every game knowing Warp (field teleport)
    _apply_new_game(options)

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

    # Chest randomizers -- two independent options (see docs/guides/chests.md). Enable either:
    # from patches.HEROgold.chest_randomizer import randomize_chest_contents, randomize_chest_locations
    # randomize_chest_contents()    # randomize WHAT each chest holds
    # randomize_chest_locations()   # shuffle WHERE chests sit, within each map

    if options.archipelago:
        apply_overworld_basepatch(hint_npcs)
        # Encounter scaling is off until the world's tokens switch it on (Iris-Dev#25); a CLI band switches it on here.
        band = options.scale_encounters or AP_DEFAULT_BAND
        write_ap_scaling_defaults(*band, enabled=options.scale_encounters is not None)
    return output_bytes()


def _apply_debug_codes() -> None:
    apply_game_genie_codes(DEBUG_MODE)
    apply_game_genie_codes(*MASTER_ONE_SHOT)
    apply_game_genie_codes(NO_SCENARIO_ITEMS)
    apply_game_genie_codes(*AIRSHIP_ANYWHERE)
    # ALWAYS_DROP_33 is left out: it turns `CMP $09FB` at $81:FB55 into `BRA $FB52`, which loops forever
    # inside the item-drop roll, so the game freezes when a defeated enemy rolls for its drop.
    apply_game_genie_codes(CAPSULE_ALWAYS_LOVE_FOOD)
    apply_game_genie_codes(ELCID_REPORT)
    # UNLOCK_WARP and "7E0C4324" (Maxim knows Warp) are Pro Action Replay RAM codes. They can't be baked
    # into the ROM; decoding them as Game Genie codes wrote 0x3F into random ROM bytes, so
    # apply_game_genie_codes now rejects them. Warps are unlocked by apply_new_game_hook().


def _apply_randomizer_patches(options: Options) -> None:
    for option, patch in _RANDOMIZER_PATCHES:
        if getattr(options, option):
            apply_absynnonym_patch(patch)
    if options.skip_intro:
        # Elcid entrance 3 instead of 2, so the opening scene in Tia's shop never loads; the hook sets its flags.
        set_spawn_location(Zone.from_name("Elcid"), entrance_cutscene=INTRO_SPAWN_ENTRANCE)
    elif options.custom_spawn_city:
        set_spawn_location(Zone.from_name("Elcid"), entrance_cutscene=0x02) # TODO: Investigate and fix (event) script loading.
        # set_spawn_location(Zone.from_name(options.spawn_location))
    for option, patch in _FIX_PATCHES:
        if getattr(options, option):
            apply_absynnonym_patch(patch)


def _apply_new_game(options: Options) -> None:
    # One asar hook at the new-game handoff: every Warp destination unlocked (dev fix, unless unlock_warps is off),
    # --skip-tutorial, --skip-intro and the start items. The tutorial sits between the intro scenes, so --skip-intro skips it too.
    start_items = [(Item.from_index(index), quantity) for index, quantity in options.start_items]
    apply_new_game_hook(
        unlock_warps=options.unlock_warps,
        skip_tutorial=options.skip_tutorial or options.skip_intro,
        skip_intro=options.skip_intro,
        start_items=start_items,
        clear_ap_rx=options.archipelago,
        start_mermaid_jade=options.start_mermaid_jade,
        start_engine=options.start_engine,
        ap_start_vehicles=options.archipelago,
    )
    if options.debug_party:
        max_out_party()
    if options.start_capsule is not None:
        start_capsule(options.start_capsule, options.start_capsule_name)
    # Runs with the other asm patches so asar assembles after every structure write.
    if options.archipelago:
        install_ap_encounter_scaling()  # the config block switches it per seed (Iris-Dev#25)
    elif options.scale_encounters:
        scale_encounters(*options.scale_encounters, seed=options.seed)
