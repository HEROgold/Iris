import argparse
from textwrap import dedent
from time import time

from config import PROJECT_NAME, VERSION, SUGGESTED_PATCH
from enums.patches import Patch
from logger import iris


CANNOT_PATCH_TOGETHER = dedent("""
    Cannot be used with other patches. Spekkio and Kureji are explicitly incompatible.
    The most right selected patch will be applied:
    Vanilla > Fixxxer > Frue > Spekkio OR Kureji
""")
ALL_CITIES = ", ".join([
    "Overworld","Seafloor","Arek Daos Shrine","Elcid","Secret Skills Cave","Sundletan Cave",
    "Sundletan","Lake Cave","Alunze South Shrine","Foomy Woods","Alunze Castle","Alunze",
    "Alunze North Shrine","Alunze Cave","Tanbel","Tanbel Tower","Clamento","Ruby Cave",
    "Parcelyte Shrine","Parcelyte","Parcelyte Castle","Treasure Sword Shrine","Gordovan Shrine","Gordovan",
    "Gordovan Tower","Merix","Cave Bridge","Bound","North Dungeon","Ancient Tower",
    "Aleyn Shrine","Lighthouse","Aleyn","Phantom Tree Mountain","Gruberik","Narcysus",
    "Tower of Sacrifice","Karlloon","Karlloon Shrine","Treadool Shrine","Treadool","Lexis Shaia Laboratory",
    "Flower Mountain","Forfeit Island","Dankirk","Auralio","Dankirk Dungeon","Ferim",
    "Ferim Tower","Agurio Shrine","Agurio","Treble","Pico Forest","Dragon Egg Shrine",
    "Portravia","Mountain of No Return","Eserikto","Divine Shrine","Barnan","Shrine of Vengeance",
    "Durale","Tower of Truth","Chaed","Dragon Mountain","Preamarl","Submarine Shrine",
    "Gratze Castle","Narvick","Shuman Tower","Strahda Tower","Kamirno Tower","Daos Shrine",
    "Darbi Shrine","Zeppy Cave","Ancient Cave",
])

class Args(argparse.Namespace):
    debug: bool
    seed: int
    file: str
    character: bool
    item: bool
    spell: bool
    monster: bool
    movement: bool
    capsule: bool
    shop: bool
    treasure: bool
    world: bool
    vanilla: bool
    randomness: float
    # Difficulty patches
    selected_patch: Patch = Patch.VANILLA
    no_patch: bool
    fixxxer: bool   # TODO: Remove, and use Frue.
    frue: bool
    spekkio: bool
    kureji: bool
    # Game Genie Codes
    game_genie_codes: list[str]
    # Event patches
    max_world_clock: bool
    open_world_base: bool
    skip_tutorial: bool
    treadool_warp: bool
    # Specific rom patches
    aggressive_movement: bool
    passive_movement: bool
    easy_mode: bool
    equip_everyone: bool
    equip_anywhere: bool
    capsule_feeding_bonus: bool
    clear_initial_spells: bool
    eat_dragon_eggs: bool
    no_boat_encounters: bool
    secondary_tool: bool
    custom_spawn_city: bool  # start in portravia
    spawn_location: str = "portravia"  # start in portravia
    unlock_gift_mode: bool
    start_engine: bool
    # Fixing patches
    ancient_cave_music: bool
    capsule_master_select: bool
    capsule_tag: bool
    ancient_cave_items: bool
    no_maxim_boat: bool
    no_maxim_warp: bool
    no_submarine: bool
    spell_target_limit: bool
    zero_capsule_command: bool
    zero_gold_command: bool
    fix_softlocks: bool



parser = argparse.ArgumentParser(prog=PROJECT_NAME, description="Randomize Lufia II: Rise of the Sinistrals.")
parser.add_argument("-v", "--version", action="version", version=f"{PROJECT_NAME}, {VERSION}")
parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode.")
parser.add_argument("-s", "--seed", type=int, default=int(time()), help="Seed for the randomizer.")
parser.add_argument("-f", "--file", type=str, help="File to randomize.", required=True)
parser.add_argument("-gg", "--game_genie_codes", action="append", nargs="+", default=[""], help="Game Genie code to activate (on the ROM), Multiple uses supported.")
# Randomization flags
parser.add_argument("--character", action="store_true", help="Randomize characters.", default=False)
parser.add_argument("--item", action="store_true", help="Randomize items and item.", default=False)
parser.add_argument("--spell", action="store_true", help="Randomize learnable spells.", default=False)
parser.add_argument("--monster", action="store_true", help="Randomize monsters.", default=False)
parser.add_argument("--movement", action="store_true", help="Randomize monster movements.", default=False)
parser.add_argument("--capsule", action="store_true", help="Randomize capsule monsters.", default=False)
parser.add_argument("--shop", action="store_true", help="Randomize shops.", default=False)
parser.add_argument("--treasure", action="store_true", help="Randomize treasure chests.", default=False)
parser.add_argument("--world", action="store_true", help="Create an open-world seed.", default=False)
parser.add_argument("--vanilla", action="store_true", help="Randomize nothing. (dummy flag to create vanilla seeds). Takes precedence over all other flags.")
parser.add_argument("--randomness", type=float, choices=range(0, 1), default=0.5, help="Set the randomness of the seed. Default is 0.5.")
parser.add_argument("--no-patch", action="store_true", help="Do not apply any patches. (Needs to be explicitly set). Default patch is Frue.")
parser.add_argument("--fixxxer", action="store_true", help="Apply the Fixxxer Lufia patch.\n" + CANNOT_PATCH_TOGETHER)
parser.add_argument("--frue", action="store_true", help="Apply the Frue Lufia patch.\n" + CANNOT_PATCH_TOGETHER)
parser.add_argument("--spekkio", action="store_true", help="Apply the Spekkio Lufia patch.\n" + CANNOT_PATCH_TOGETHER)
parser.add_argument("--kureji", action="store_true", help="Apply the Kureji Lufia patch.\n" + CANNOT_PATCH_TOGETHER)
# Event patches
parser.add_argument("--max_world_clock", action="store_true")  # TODO: Implement and set default to True
parser.add_argument("--open_world_base", action="store_true")  # TODO: Implement and set default to True
parser.add_argument("--skip_tutorial", action="store_true")  # TODO: Implement and set default to True
parser.add_argument("--treadool_warp", action="store_true")  # TODO: Implement and set default to True
# Patch flags
parser.add_argument("--aggressive-movement", action="store_true", help="Set all monsters to be aggressive.")
parser.add_argument("--passive-movement", action="store_true", help="Set all monsters to be passive.")
parser.add_argument("--easy-mode", action="store_true", help="Makes all monsters weak.")
parser.add_argument("--equip-everyone", action="store_true", help="Any character can equip every item.")
parser.add_argument("--equip-anywhere", action="store_true", help="Any item can be equipped in any slot.")
parser.add_argument("--custom_spawn_city", action="store_true")
parser.add_argument("--spawn_location", action="store", default="portravia", help="Set the starting location. Default is Portravia. Available locations:\n" + ALL_CITIES)
parser.add_argument("--capsule_feeding_bonus", action="store_true")
parser.add_argument("--clear_initial_spells", action="store_true")
parser.add_argument("--eat_dragon_eggs", action="store_true")
parser.add_argument("--no_boat_encounters", action="store_true")
parser.add_argument("--secondary_tool", action="store_true")
parser.add_argument("--unlock_gift_mode", action="store_true")
parser.add_argument("--start_engine", action="store_true")
# Fix patches
parser.add_argument("--ancient_cave_music", action="store_true") # TODO: seems to not work?
parser.add_argument("--capsule_master_select", action="store_true")
parser.add_argument("--capsule_tag", action="store_true")
parser.add_argument("--ancient_cave_items", action="store_true")
parser.add_argument("--no_maxim_boat", action="store_true")
parser.add_argument("--no_maxim_warp", action="store_true")
parser.add_argument("--no_submarine", action="store_true")
parser.add_argument("--spell_target_limit", action="store_true")
parser.add_argument("--zero_capsule_command", action="store_true")
parser.add_argument("--zero_gold_command", action="store_true")
parser.add_argument("--fix-softlocks", action="store_true")


args: Args = parser.parse_args(namespace=Args())


assert not args.max_world_clock,"EventPatch not implemented."
assert not args.open_world_base,"EventPatch not implemented."
assert not args.skip_tutorial,"EventPatch not implemented."
assert not args.treadool_warp,"EventPatch not implemented."
assert not args.capsule_feeding_bonus, "Patch not implemented."
assert not args.clear_initial_spells, "Patch not implemented."
assert not args.eat_dragon_eggs, "Patch not implemented."
assert not args.no_boat_encounters, "Patch not implemented."
assert not args.secondary_tool, "Patch not implemented."
assert not args.custom_spawn_city, "Custom starting location not implemented."
assert args.spawn_location == "portravia", "Custom starting location not implemented."
assert not args.unlock_gift_mode, "Patch not implemented."
assert not args.start_engine, "Patch not implemented."
assert not args.ancient_cave_music, "Fix not implemented."  # Won't be implemented.
assert not args.capsule_master_select, "Fix not implemented."
assert not args.capsule_tag, "Fix not implemented."
assert not args.ancient_cave_items, "Fix not implemented."
assert not args.no_maxim_boat, "Fix not implemented."
assert not args.no_maxim_warp, "Fix not implemented."
assert not args.no_submarine, "Fix not implemented."
assert not args.spell_target_limit, "Fix not implemented."
assert not args.zero_capsule_command, "Fix not implemented."
assert not args.zero_gold_command, "Fix not implemented."


if args.spekkio and args.kureji:
    raise ValueError("You cannot apply both the Spekkio and Kureji patches at the same time.")

if args.kureji:
    args.selected_patch = Patch.KUREJI
elif args.spekkio:
    args.selected_patch = Patch.SPEKKIO
elif args.frue:
    args.selected_patch = Patch.FRUE
elif args.fixxxer:
    args.selected_patch = Patch.FIXXXER
elif args.no_patch or args.vanilla:
    args.selected_patch = Patch.VANILLA
else:
    args.selected_patch = SUGGESTED_PATCH

iris.info(f"Selected patch is {args.selected_patch.name}")

if args.aggressive_movement and args.passive_movement:
    raise ValueError("You cannot set both aggressive and passive movement at the same time.")


if args.debug:
    args.max_world_clock = True
    args.open_world_base = True
    args.skip_tutorial = True
    args.treadool_warp = True
    args.capsule_feeding_bonus = True
    args.clear_initial_spells = True
    args.eat_dragon_eggs = True
    args.no_boat_encounters = True
    args.secondary_tool = True
    args.unlock_gift_mode = True
    args.custom_spawn_city = True
    args.start_engine = True
    args.ancient_cave_music = True
    args.capsule_master_select = True
    args.capsule_tag = True
    args.ancient_cave_items = True
    args.no_maxim_boat = True
    args.no_maxim_warp = True
    args.no_submarine = True
    args.spell_target_limit = True
    args.zero_capsule_command = True
    args.zero_gold_command = True
