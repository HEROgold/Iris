"""Export the plain data the Archipelago world needs, as a module that imports without a ROM (Iris-Dev#7).

``iris/lookups/`` reads the ROM at import, which the apworld can't do. This writes ``archipelago/lufia2ow/data.py``
(the linear base patch) and ``data_open_world.py`` (the open-world base patch, plus its boss NPCs): only literals, so
they import on Archipelago's Python with nothing else installed. Run from the repo root::

    python tools/export_ap_data.py --file <vanilla-rom>          # write both modules
    python tools/export_ap_data.py --file <vanilla-rom> --check  # exit 1 if a committed module is stale

Most of it comes from the vanilla ROM. What the base patch moves comes from the built base ROM instead: the hint slots
(``hint_npcs.make_hint_slots``) and the grants, whose scripts move with their map's event container.
"""

import argparse
import re
import sys
from dataclasses import replace
from pathlib import Path
from pprint import pformat


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from iris import constants
from iris.build import Options, build
from iris.enums.flags import GOAL_FLAG, EventFlag, Usability
from iris.enums.patches import Patch
from iris.helpers.files import open_rom, output_bytes, read_file
from iris.patches import open_world
from iris.patches.archipelago.overworld.ap_item import AP_ITEM_INDEX
from iris.patches.archipelago.overworld.hint_npcs import HINT_FLAGS, hint_slots
from iris.patches.archipelago.overworld.key_items import KEY_ITEM_NAMES
from iris.patches.open_world.bosses import (
    BOSS_BATTLE,
    BOSSES,
    DAOS,
    FINAL_SPOT,
    ITEM,
    LOAD_NPC,
    MUSIC,
    PLACEHOLDER_ITEM,
    SPOTS,
    Boss,
    _power,
    placed_bosses,
)
from iris.patches.open_world.leader import LEADERS, MAXIM
from iris.structures.chest import PointerChest
from iris.structures.chest_location import CHEST_MAP
from iris.structures.chest_names import CHEST_NAMES
from iris.structures.event_script import MapEvent
from iris.structures.event_script.event_patch import measure_event_patch, resolve_or_create
from iris.structures.event_script.dump import _signature
from iris.structures.item import Item
from iris.structures.key_doors import key_doors
from iris.structures.zone import Zone
from iris.structures.zone_data_pointers import zone_data_pointers
from iris.tables import ChestObject, ItemObject, select
from iris.structures.event_script.script import EventScript
from tools.build_ap_basepatch import OPEN_WORLD_OPTIONS, OPTIONS, vanilla_image
from tools.dump_item_grants import GRANT_OPS, SET_FLAG, collect


DATA_FILE = Path(__file__).resolve().parent.parent / "archipelago" / "lufia2ow" / "data.py"
OPEN_WORLD_DATA_FILE = DATA_FILE.with_name("data_open_world.py")
MODULES = ((DATA_FILE, OPTIONS), (OPEN_WORLD_DATA_FILE, OPEN_WORLD_OPTIONS))

TOOLS = range(423, 428)
"""Hook, Bomb, Arrow, Fire arrow, Hammer."""
SCENARIO_ITEMS = range(428, 462)
"""The scenario-item bitfield's ids (docs/ap/scenario_items.md); 454-458 are unused KEY26..KEY30."""
UNUSED_ITEM_SLOTS = range(454, 458)
CHEST_OPENED_BITS = 0x7E093B
"""WRAM bitfield of opened chests, indexed by chest number (docs/ap/chest_opened_bits.md)."""


def _classification(index: int, item: Item) -> str:
    if index in TOOLS or (index in SCENARIO_ITEMS and index not in UNUSED_ITEM_SLOTS and index != AP_ITEM_INDEX):
        return "progression"
    if Usability.EQUIPABLE in item.usability:
        return "useful"
    return "filler"


def _items() -> list[tuple[int, str, str]]:
    rows = []
    for index in range(ItemObject.count):
        item = Item.from_index(index)
        rows.append((index, item.name_pointer.name.strip(), _classification(index, item)))
    return rows


def _chests() -> list[tuple[int, int | None, str | None, int, int, int]]:
    """(chest index, map, guide name, record offset, vanilla misc1 byte, vanilla item) per red chest."""
    rows = []
    for index, pointer in enumerate(ChestObject.pointers):
        read_file.seek(pointer)
        misc1 = read_file.read(1)[0]
        item = PointerChest.from_index(index).item.index
        rows.append((index, CHEST_MAP.get(index), CHEST_NAMES.get(index), pointer, misc1, item))
    return rows


def _grants() -> list[tuple[int, str, int, int, int, tuple[int, ...]]]:
    """(map, event signature, offset of the item byte, item, count, flags the script sets) per script grant."""
    rows, mismatches = collect()
    if mismatches:
        msg = f"{mismatches} grant operands didn't read back from the ROM."
        raise ValueError(msg)
    return [(row["map"], row["sig"], row["addr"], row["item"], row["count"], tuple(row["flags"])) for row in rows]


def _map_names() -> dict[int, str]:
    """Map index -> the game's own map name; maps whose name doesn't decode to plain text are left out."""
    names = {}
    for index in range(len(zone_data_pointers)):
        name = Zone.from_index(index).clean_name.decode("ascii", errors="replace")
        if name and name.isprintable() and "�" not in name:
            names[index] = name
    return names


def _hint_npcs() -> list[tuple[int, str, int, int]]:
    """(map, signature, slot offset, slot size) of every talk script a hint can replace, as the build made them."""
    return [(npc.map_index, npc.signature, npc.pointer, npc.size) for npc in hint_slots()]


type Grant = tuple[int, str, int, int, int, tuple[int, ...]]
type HintSlot = tuple[int, str, int, int]
type BossRow = tuple[str, int, int, str, int, int, int, tuple[int, ...]]


def _script(map_index: int, signature: str) -> EventScript:
    map_event = MapEvent.from_index(map_index)
    map_event.read()
    return next(
        script for event_list in map_event.event_lists for script in event_list.events
        if _signature(map_index, script) == signature
    )


def _boss_npcs(rom: bytes) -> list[BossRow]:
    """(spot, map, flag, talk signature, sprite offset, bgm offset, formation offset, reward item offsets) per boss NPC.

    Each offset is that of a one-byte operand in ``rom``: the boss's sprite in the map's NPC-load script, the boss
    music and the boss formation in the talk script, and the item of each reward grant (its count byte follows).
    """
    rows = []
    for npc in placed_bosses():
        map_event = MapEvent.from_index(npc.spot.map_index)
        map_event.read()
        load = map_event.npc_script
        sprite = next(
            load.pointer + ins.line + 2 for ins in load.instructions
            if ins.opcode == LOAD_NPC and list(ins.operands) == [npc.npc_slot, npc.boss.sprite]
        )
        talk = _script(npc.spot.map_index, npc.signature)
        operand = {
            opcode: [talk.pointer + ins.line + 1 for ins in talk.instructions if ins.opcode == opcode]
            for opcode in (MUSIC, BOSS_BATTLE, ITEM)
        }
        rewards = tuple(operand[ITEM])
        row = (npc.spot.name, npc.spot.map_index, npc.flag, npc.signature, sprite,
               operand[MUSIC][0], operand[BOSS_BATTLE][0], rewards)
        expected = [(sprite, npc.boss.sprite), (row[5], npc.boss.bgm), (row[6], npc.boss.formation)]
        expected += [(offset, PLACEHOLDER_ITEM) for offset in rewards]
        if len(rewards) != npc.spot.rewards or any(rom[offset] != value for offset, value in expected):
            msg = f"The {npc.spot.name} boss NPC's operands don't read back from the base ROM."
            raise ValueError(msg)
        rows.append(row)
    return rows


def _boss(boss: Boss) -> tuple[str, int, int, int, int]:
    """(name, sprite, formation, bgm, power): power is the highest vanilla level among the formation's monsters."""
    return boss.name, boss.sprite, boss.formation, boss.bgm, _power(boss)


def _moved(grants: list[Grant], *, open_world: bool) -> list[Grant]:
    """``grants`` (from the vanilla ROM) with the offsets of their item bytes in the active session.

    A grant is the n-th grant instruction of its script; the script is found again by its signature, which moving its
    container doesn't change. Open world replaces some story scripts with ones that grant nothing (13 scripts, 14
    grants); those grants are left out. It adds no grant of its own besides the boss rewards (``BOSS_NPCS``).
    """
    out = []
    order: dict[tuple[int, str], int] = {}
    for map_index, signature, _, item, count, flags in grants:
        n = order.get((map_index, signature), 0)
        order[map_index, signature] = n + 1
        script = _script(map_index, signature)
        script_grants = [ins for ins in script.instructions if ins.opcode in GRANT_OPS]
        if open_world and not script_grants:
            continue
        instruction = script_grants[n]
        if GRANT_OPS[instruction.opcode] + int(instruction.operands[0]) != item:
            msg = f"Grant {n} of {signature} gives {instruction.operands[0]} in the base ROM, not item {item}."
            raise ValueError(msg)
        out.append((map_index, signature, script.pointer + instruction.line + 1, item, count, flags))
    return out


def _from_base_rom(
    vanilla: bytes, grants: list[Grant], options: Options
) -> tuple[list[Grant], list[HintSlot], list[BossRow]]:
    """Where ``grants`` and the hint slots are in the base ROM Iris builds: the base patch moves event containers.

    Read from the build's own session, where every moved script was parsed again from its new bytes. Parsing the built
    ROM afresh would not do: a script's end is found from the next known pointer, and a moved neighbour no longer
    marks it, so a parse runs on into the neighbour's old bytes and finds its grants there too.
    """
    rom = build(vanilla, options)
    return _moved(grants, open_world=options.open_world), _hint_npcs(), _boss_npcs(rom)


type Runs = tuple[tuple[int, str], ...]
CHECKSUM = range(0x7FDC, 0x7FE0)
"""The header's checksum and complement: every variant changes them, and the game doesn't read them."""
ORB_CHECK = "orb_check"
ORB_SCRIPT = "44-D-01"
"""The orb's tile script, in event-patch letters (``orb_check.txt``)."""
LEADER_SCRIPT_OPCODES = {0x33: 1, 0x86: 0, 0x8C: 0}
"""``leader.CHARACTER_OPERAND``: an extra's script with one of these naming Maxim changes with the leader too."""
_SCRIPT_LINE = re.compile(r"\s*[0-9A-F]{4}\.\s*([0-9A-F]{2})\(([^)]*)\)")


def _runs(base: bytes, variant: bytes) -> Runs:
    """The bytes ``variant`` changes in ``base``, as (offset, hex) runs of consecutive changed bytes."""
    runs: list[list[int]] = []
    for offset, (old, new) in enumerate(zip(base, variant, strict=True)):
        if old == new or offset in CHECKSUM:
            continue
        if runs and runs[-1][1] == offset:
            runs[-1][1] = offset + 1
        else:
            runs.append([offset, offset + 1])
    return tuple((start, variant[start:stop].hex()) for start, stop in runs)


def apply_runs(rom: bytes, *runs: Runs) -> bytes:
    """``rom`` with every run of ``runs`` written over it, in order (what the world's tokens do)."""
    out = bytearray(rom)
    for group in runs:
        for offset, data in group:
            chunk = bytes.fromhex(data)
            out[offset : offset + len(chunk)] = chunk
    return bytes(out)


def _moves_maxim(extra: str) -> bool:
    """True if ``extra``'s scripts move character 0, which the leader replaces (``leader._replace_leader_in_events``)."""
    path = open_world.OPEN_WORLD / f"{extra}.txt"
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _SCRIPT_LINE.match(line)
        if match and int(match[1], 16) in LEADER_SCRIPT_OPCODES:
            operands = match[2].split("-")
            if int(operands[LEADER_SCRIPT_OPCODES[int(match[1], 16)]], 16) == MAXIM:
                return True
    return False


def _orb_check() -> tuple[int, int, int, int]:
    """(map, offset of the item byte, item, flag) of the orb check's grant, in the active (orb_check) session."""
    script = resolve_or_create(ORB_SCRIPT)
    grant = next(ins for ins in script.instructions if ins.opcode in GRANT_OPS)
    flag = next(int(ins.operands[0]) for ins in script.instructions if ins.opcode == SET_FLAG)
    item = GRANT_OPS[grant.opcode] + int(grant.operands[0])
    return int(ORB_SCRIPT[:2], 16), script.pointer + grant.line + 1, item, flag


def _variants(vanilla: bytes, grants: list[Grant], options: Options, base: tuple) -> dict[str, object]:
    """Every open-world extra and leader as runs over the base ROM, and what they move (Iris-Dev#43).

    The base keeps room for each (``apply_open_world(reserve=True)``), so each is a small diff in place. Grants and
    hint slots must stay where they are; a boss NPC whose sprite moves gets its row for that extra.
    """
    base_grants, base_hints, base_bosses, base_rom = base
    extra_runs: dict[str, Runs] = {}
    boss_rows: dict[str, dict[int, BossRow]] = {}
    orb = None
    replaced: dict[str, tuple[str, ...]] = {}
    for extra in open_world.EXTRAS:
        rom = build(vanilla, replace(options, open_world_extras=(extra,)))
        extra_runs[extra] = _runs(base_rom, rom)
        scripts = _replaced_scripts(extra)
        if scripts:
            replaced[extra] = scripts
        kept = [grant for grant in grants if grant[1] not in scripts]
        if _moved(kept, open_world=True) != [g for g in base_grants if g[1] not in scripts] or _hint_npcs() != base_hints:
            msg = f"Open-world extra {extra} moves a grant or a hint slot; the base needs room for it."
            raise ValueError(msg)
        rows = {n: row for n, (row, old) in enumerate(zip(_boss_npcs(rom), base_bosses, strict=True)) if row != old}
        if rows:
            boss_rows[extra] = rows
        if extra == ORB_CHECK:
            orb = _orb_check()
    leader_runs: dict[str, Runs] = {}
    for name, leader in LEADERS.items():
        rom = build(vanilla, replace(options, leader=leader))
        leader_runs[name] = _runs(base_rom, rom)
        if (_moved(grants, open_world=True), _hint_npcs(), _boss_npcs(rom)) != (base_grants, base_hints, base_bosses):
            msg = f"Leader {name} moves a grant, a hint slot or a boss NPC; the base needs room for it."
            raise ValueError(msg)
    pairs: dict[tuple[str, str], Runs] = {}
    for extra in filter(_moves_maxim, open_world.EXTRAS):
        for name, leader in LEADERS.items():
            rom = build(vanilla, replace(options, open_world_extras=(extra,), leader=leader))
            runs = _runs(apply_runs(base_rom, extra_runs[extra], leader_runs[name]), rom)
            if runs:
                pairs[name, extra] = runs
    return {
        "extras": extra_runs, "leaders": leader_runs, "pairs": pairs, "boss_rows": boss_rows, "orb": orb,
        "replaced": replaced,
    }


def _replaced_scripts(extra: str) -> tuple[str, ...]:
    """The signatures (Iris's letters) of the existing scripts ``extra`` replaces, in the active session."""
    path = open_world.OPEN_WORLD / f"{extra}.txt"
    if not path.exists():
        return ()
    sizes, _ = measure_event_patch(path.read_text(encoding="utf-8"))
    out = []
    for signature in sizes:
        script = resolve_or_create(signature)
        if script.index >= 0:
            out.append(_signature(int(signature[:2], 16), script))
    return tuple(sorted(out))


def render(vanilla: bytes, options: Options = OPTIONS) -> str:
    """The module's text, from the vanilla US ROM ``vanilla`` and the base ROM Iris builds from it with ``options``."""
    select(Patch.VANILLA)
    open_rom(vanilla)
    vanilla_grants = _grants()
    grants, hint_npcs, boss_npcs = _from_base_rom(vanilla, vanilla_grants, options)
    variants = (
        _variants(vanilla, vanilla_grants, options, (grants, hint_npcs, boss_npcs, output_bytes()))
        if options.open_world else None
    )
    select(Patch.VANILLA)
    open_rom(vanilla)
    ap_constants = {name: getattr(constants, name) for name in dir(constants) if name.startswith("AP_")}
    sections = [
        '"""Lufia II data for the Archipelago world. AUTO-GENERATED by tools/export_ap_data.py from the vanilla US ROM;\n'
        'regenerate it instead of editing. Offsets are headerless ROM offsets."""\n',
        "# (item index, name, classification)",
        f"ITEMS = {pformat(_items(), width=120)}\n",
        f"TOOLS = {tuple(TOOLS)!r}",
        f"SCENARIO_ITEMS = {tuple(i for i in SCENARIO_ITEMS if i not in UNUSED_ITEM_SLOTS and i != AP_ITEM_INDEX)!r}",
        f"AP_ITEM_INDEX = {AP_ITEM_INDEX}",
        "# Free scenario slots the base patch names (key_items.py): Ship, Submarine and the two progressive tokens.",
        f"KEY_ITEMS = {KEY_ITEM_NAMES!r}",
        "# Red chests: (chest index, map, guide name, record offset, vanilla misc1 byte, vanilla item).",
        "# A chest's item is 9 bits: the low byte at record offset + 2, the high bit in misc1 bit 6.",
        "# Chest n is opened when bit n & 7 of CHEST_OPENED_BITS + (n >> 3) is set (docs/ap/chest_opened_bits.md).",
        f"CHEST_OPENED_BITS = {CHEST_OPENED_BITS:#08x}",
        f"CHESTS = {pformat(_chests(), width=120)}\n",
        "# Event-script grants: (map, event signature, offset of the item byte, item, count, flags the script sets).",
        "# Opcode 0x21 grants item 0x100 + the byte, opcode 0x20 the byte itself.",
        f"GRANTS = {pformat(grants, width=120)}\n",
        "# Locked doors: (map, map object, key item). A door opens when the party holds the key.",
        f"KEY_DOORS = {pformat([(d.map_index, d.map_object, d.item) for d in key_doors()], width=120)}\n",
        f"MAP_NAMES = {pformat(_map_names(), width=120)}\n",
        "# Talk scripts that only show text, which a hint can overwrite: (map, signature, offset, size). The base patch",
        "# moved each into a slot of at least hint_npcs.HINT_SLOT_SIZE bytes. Hint NPC n sets HINT_FLAGS[n] when talked to.",
        f"HINT_NPCS = {pformat(hint_npcs, width=120)}",
        f"HINT_FLAGS = {HINT_FLAGS!r}\n",
        f"EVENT_FLAGS = {pformat({flag.name: int(flag) for flag in EventFlag}, width=120, sort_dicts=False)}",
        f"GOAL_FLAG = {int(GOAL_FLAG)}\n",
        "# The config block (docs/ap/config_block.md).",
        f"CONFIG = {pformat(ap_constants, width=120)}",
    ]
    if options.open_world:
        sections += [
            "",
            "# Open world, fixed boss placement. Boss spots in story order: (name, map, rewards); FINAL_SPOT is Daos's.",
            f"BOSS_SPOTS = {pformat([(spot.name, spot.map_index, spot.rewards) for spot in SPOTS], width=120)}",
            f"FINAL_SPOT = {(FINAL_SPOT.name, FINAL_SPOT.map_index, FINAL_SPOT.rewards)!r}\n",
            "# Bosses in story order: (name, sprite, formation, bgm, power). DAOS always guards FINAL_SPOT. Power is the",
            "# highest vanilla level among the formation's monsters (bosses._power), what scale_to_depth compares.",
            f"BOSSES = {pformat([_boss(boss) for boss in BOSSES], width=120)}",
            f"DAOS = {_boss(DAOS)!r}\n",
            "# Boss NPCs as the base patch places them, Daos last: (spot, map, flag set when beaten, talk signature,",
            "# offset of the sprite byte in the map's NPC-load script, offsets of the bgm and formation bytes in the talk",
            "# script, offsets of each reward grant's item byte). A reward is opcode 0x20 [item, 1] giving",
            "# PLACEHOLDER_ITEM in the base patch; these grants are not in GRANTS.",
            f"PLACEHOLDER_ITEM = {PLACEHOLDER_ITEM:#04x}",
            f"BOSS_NPCS = {pformat(boss_npcs, width=120)}",
        ]
    if variants is not None:
        sections += [
            "",
            "# Per-seed open-world variants (Iris-Dev#43). The base patch keeps room for each, so each is a list of",
            "# (offset, hex bytes) runs that turn the base ROM into Iris's build with it, the checksum left out. Write the",
            "# chosen extras in EXTRAS order, then the leader, then LEADER_EXTRA_DIFFS[leader, extra] for each chosen",
            "# extra, before every other token. The extras of a group in EXCLUSIVE_EXTRAS can't be chosen together.",
            f"EXTRAS = {tuple(open_world.EXTRAS)!r}",
            f"EXCLUSIVE_EXTRAS = {tuple(tuple(sorted(group)) for group in open_world.EXCLUSIVE)!r}",
            f"EXTRA_DIFFS = {pformat(variants['extras'], width=120, sort_dicts=False)}",
            "# Leaders by character index; Maxim (0) is the base patch's.",
            f"LEADERS = {LEADERS!r}",
            f"LEADER_DIFFS = {pformat(variants['leaders'], width=120, sort_dicts=False)}",
            "# The leader's change inside an extra's own scripts (where the extra moves Maxim).",
            f"LEADER_EXTRA_DIFFS = {pformat(variants['pairs'], width=120, sort_dicts=False)}",
            "# BOSS_NPCS rows an extra moves (its NPC-load script grows in front of the boss): extra -> {row: new row}.",
            f"EXTRA_BOSS_NPCS = {pformat(variants['boss_rows'], width=120, sort_dicts=False)}",
            "# Scripts an extra replaces: GRANTS rows in them don't hold with that extra (9F-B-50, the egg wishes).",
            f"EXTRA_REPLACED_SCRIPTS = {pformat(variants['replaced'], width=120, sort_dicts=False)}",
            "# orb_check's grant, a location: (map, offset of the item byte, vanilla item, flag set once taken).",
            f"ORB_CHECK = {variants['orb']!r}",
        ]
    return "\n".join(sections) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", type=Path, required=True, help="The vanilla US ROM (headered or not).")
    parser.add_argument("--check", action="store_true", help="Fail if the committed module is stale.")
    args = parser.parse_args()
    vanilla = vanilla_image(args.file)
    stale = 0
    for data_file, options in MODULES:
        text = render(vanilla, options)
        if args.check:
            current = data_file.exists() and data_file.read_text(encoding="utf-8") == text
            state = "current" if current else "stale: rerun tools/export_ap_data.py and commit it"
            print(f"{data_file.name} is {state}.")
            stale += not current
        else:
            data_file.write_text(text, encoding="utf-8", newline="\n")
            print(f"Wrote {data_file}.")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
