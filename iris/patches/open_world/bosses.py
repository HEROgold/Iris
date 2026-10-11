"""Boss NPCs (terrorwave's open world): a boss stands at each of 38 spots; beating it gives one or two items.

The spots and bosses are terrorwave's ``open_boss_locations.txt`` and ``open_bosses.txt``; a spot gives two items
where terrorwave's requirements list a ``name1`` and ``name2`` (the 11 big dungeons). Daos always guards Daos' Shrine,
and beating him sets DAOS_DEFEATED, the Archipelago goal flag.

Each other boss NPC is a new NPC on the spot's map:

- its position record (1x1, misc 05);
- in the map's NPC-load script: the boss's sprite until its flag is set, then the "beaten" sprite;
- a talk script: the boss battle (``53``), then on a win its flag, the boss vanishing and the items, each a ``9E``
  text box plus a ``20`` grant. The Archipelago world writes its own items into the grants, so the text names none.

Each boss gets a flag no script reads or writes after open world (terrorwave takes them from the story flags
0x20-0x6F, which the end-of-story world no longer uses).
"""

import random
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from iris.enums.flags import EventFlag
from iris.helpers.files import on_new_session
from iris.logger import iris
from iris.structures.event_script.codec import decode_text, encode_text
from iris.structures.event_script.containers import MapEvent
from iris.structures.event_script.event_patch import resolve_or_create
from iris.structures.event_script.instructions import Address, Instruction
from iris.structures.event_script.script import EventScript
from iris.structures.map_meta import MapMeta
from iris.structures.zone import NPC, Boundary, Zone
from iris.tables import MapEventObject


@dataclass(frozen=True)
class BossSpot:
    name: str
    map_index: int
    x: int
    y: int
    battle_bg: int
    map_bgm: int
    rewards: int


@dataclass(frozen=True)
class Boss:
    name: str
    sprite: int
    formation: int
    bgm: int


@dataclass(frozen=True)
class BossNpc:
    """A placed boss NPC, for the data export."""

    spot: BossSpot
    boss: Boss
    flag: int
    npc_slot: int
    signature: str
    """The talk script, in Iris's dump letters (``MAP-B-SLOT``)."""


SPOTS = (
    BossSpot("skill_cave", 0x05, 0x31, 0x05, 0x0C, 0x17, 1),
    BossSpot("foomy_woods", 0x0E, 0x0F, 0x12, 0x04, 0x14, 1),
    BossSpot("darbi_shrine", 0xED, 0x0F, 0x09, 0x04, 0x14, 1),
    BossSpot("zeppy_cave", 0xEF, 0x0A, 0x07, 0x0F, 0x14, 1),
    BossSpot("sundletan_cave", 0x07, 0x21, 0x10, 0x0C, 0x17, 1),
    BossSpot("catfish_cave", 0x0C, 0x09, 0x0F, 0x0F, 0x17, 1),
    BossSpot("alunze_basement", 0x14, 0x0A, 0x1C, 0x09, 0x08, 1),
    BossSpot("alunze_cave", 0x1B, 0x3F, 0x06, 0x09, 0x17, 1),
    BossSpot("tanbel_tower", 0x24, 0x11, 0x08, 0x0A, 0x3A, 2),
    BossSpot("ruby_cave", 0x2A, 0x18, 0x0D, 0x14, 0x17, 1),
    BossSpot("ruby_capsule", 0x27, 0x15, 0x19, 0x12, 0x17, 1),
    BossSpot("tsword_shrine", 0x33, 0x08, 0x11, 0x05, 0x2F, 2),
    BossSpot("gordovan_tower", 0x3D, 0x0F, 0x15, 0x0A, 0x05, 2),
    BossSpot("cave_bridge", 0x43, 0x08, 0x13, 0x0B, 0x17, 1),
    BossSpot("north_dungeon", 0x4A, 0x1B, 0x0A, 0x09, 0x08, 1),
    BossSpot("north_capsule", 0x49, 0x2C, 0x0C, 0x09, 0x08, 1),
    BossSpot("ancient_tower", 0x52, 0x0A, 0x26, 0x0A, 0x05, 2),
    BossSpot("lighthouse", 0x5D, 0x0A, 0x07, 0x0A, 0x05, 2),
    BossSpot("phantom_mountain", 0x67, 0x08, 0x1B, 0x01, 0x13, 1),
    BossSpot("sacrifice_tower", 0x72, 0x0E, 0x08, 0x0A, 0x05, 2),
    BossSpot("sacrifice_capsule", 0x70, 0x14, 0x16, 0x0A, 0x05, 1),
    BossSpot("karlloon_shrine", 0x78, 0x0E, 0x1E, 0x05, 0x2F, 2),
    BossSpot("lexis_lab", 0x7D, 0x03, 0x08, 0x16, 0x1F, 1),
    BossSpot("flower_mountain", 0x7E, 0x34, 0x26, 0x07, 0x13, 1),
    BossSpot("flower_capsule", 0x7E, 0x12, 0x0D, 0x07, 0x13, 1),
    BossSpot("dankirk_dungeon", 0x90, 0x34, 0x23, 0x09, 0x08, 1),
    BossSpot("northeast_tower", 0x98, 0x0A, 0x10, 0x0A, 0x05, 2),
    BossSpot("no_return_mountain", 0xA5, 0x1D, 0x0C, 0x01, 0x13, 1),
    BossSpot("divine_shrine", 0xAA, 0x1A, 0x19, 0x05, 0x2F, 2),
    BossSpot("vengeance_shrine", 0xB2, 0x07, 0x12, 0x05, 0x3A, 2),
    BossSpot("truth_tower", 0xBD, 0x10, 0x15, 0x0A, 0x05, 2),
    BossSpot("dragon_mountain", 0xC7, 0x1D, 0x1B, 0x12, 0x13, 1),
    BossSpot("underwater_shrine", 0xCC, 0x09, 0x0B, 0x0F, 0x20, 1),
    BossSpot("gratze_basement", 0xD5, 0x1D, 0x07, 0x09, 0x08, 1),
    BossSpot("shuman", 0xDC, 0x10, 0x0C, 0x02, 0x09, 1),
    BossSpot("stradha", 0xE0, 0x0A, 0x0F, 0x02, 0x09, 1),
    BossSpot("kamirno", 0xE4, 0x10, 0x0C, 0x02, 0x09, 1),
)
"""In terrorwave's order, which roughly follows the story: the fixed placement and the shuffle use it as depth."""
FINAL_SPOT = BossSpot("daos_shrine", 0xE9, 0x10, 0x17, 0x08, 0x0A, 0)

BOSSES = (
    Boss("lizardman", 0x9E, 0x01, 0x19),
    Boss("catfish", 0xC5, 0x02, 0x19),
    Boss("regal_goblin", 0x9D, 0x05, 0x19),
    Boss("followers", 0x76, 0x06, 0x19),
    Boss("camu", 0x75, 0x07, 0x19),
    Boss("tarantula", 0xC6, 0x08, 0x19),
    Boss("pierre1", 0x77, 0x09, 0x19),
    Boss("daniele1", 0x78, 0x0A, 0x19),
    Boss("gades1", 0x7A, 0x0B, 0x1B),
    Boss("mummies", 0xA8, 0x0C, 0x19),
    Boss("trolls", 0xA9, 0x0D, 0x19),
    Boss("gades2", 0x7A, 0x0E, 0x1B),
    Boss("idura1", 0x74, 0x0F, 0x19),
    Boss("lions", 0xB7, 0x12, 0x19),
    Boss("idura2", 0x74, 0x13, 0x19),
    Boss("idura3", 0x74, 0x14, 0x19),
    Boss("flower", 0x96, 0x15, 0x19),
    Boss("soldiers1", 0x18, 0x16, 0x19),
    Boss("gargoyles", 0xC4, 0x17, 0x19),
    Boss("venge_ghost", 0xD0, 0x18, 0x19),
    Boss("white_dragons", 0xC0, 0x19, 0x19),
    Boss("fire_dragon", 0xC0, 0x1A, 0x19),
    Boss("ghost_ship", 0xC8, 0x1B, 0x19),
    Boss("soldiers2", 0x18, 0x1C, 0x19),
    Boss("soldiers3", 0x18, 0x1D, 0x19),
    Boss("tank", 0xC7, 0x1E, 0x19),
    Boss("gades3", 0x7A, 0x1F, 0x1B),
    Boss("amon1", 0x79, 0x20, 0x1B),
    Boss("gades4", 0x7A, 0x21, 0x1B),
    Boss("amon2", 0x79, 0x22, 0x1B),
    Boss("erim", 0x7C, 0x23, 0x1B),
)
"""Story order, which also stands in for strength (terrorwave ranks by its monster stats; Iris has no port of that)."""
DAOS = Boss("daos", 0x7B, 0x24, 0x1B)

FLAG_RANGE = range(0x20, 0x70)
NOT_BOSS_FLAGS = frozenset((0x5F, 0x62, 0x30))
"""terrorwave's banned 0x5F and 0x62, and 0x30, the orb check's."""
BEATEN_SPRITE = 0x48
NPC_MISC = 0x05
FIRST_TALK_SLOT = 0x4F
MAX_NPC_INDEX = 0x20
SHUFFLE_SPREAD = 0.25
"""How far a shuffled boss may move from its story position, as a share of all spots (a rough port of terrorwave's
random_degree: early spots still tend to get early bosses)."""

# Opcodes
END, SET_FLAG, CLEAR_FLAG, JUMP, BRANCH_ON_FLAG, BRANCH_ON_NOT_FLAG, LOAD_NPC = 0x00, 0x1A, 0x1B, 0x1C, 0x15, 0x6A, 0x68
ITEM, ITEM_HIGH, TEXT_WINDOW, MUSIC, BATTLE_BG, BOSS_BATTLE = 0x20, 0x21, 0x9E, 0x4B, 0x74, 0x53
BATTLE_WON = 0xFF
"""The flag a boss battle leaves set when the party won (terrorwave's ``6A(FF-...)``)."""
REWARD_TEXT = "<POSITION 02>You found a treasure!<END MESSAGE>"
PLACEHOLDER_ITEM = 0x09
"""Miracle: what a reward gives until the Archipelago world writes its own item."""


def fixed_placement() -> dict[BossSpot, Boss]:
    """Each spot gets the boss at the same place in story order."""
    return {spot: BOSSES[index * len(BOSSES) // len(SPOTS)] for index, spot in enumerate(SPOTS)}


def shuffled_placement(seed: int) -> dict[BossSpot, Boss]:
    """Bosses drawn in story order (repeats fill the spots past the 31 bosses), each moved a random distance, sorted."""
    rng = random.Random(f"open-world-bosses-{seed}")
    pool = list(BOSSES) + rng.sample(BOSSES, len(SPOTS) - len(BOSSES))
    pool.sort(key=BOSSES.index)
    spread = SHUFFLE_SPREAD * len(SPOTS)
    order = sorted(range(len(pool)), key=lambda i: i + rng.uniform(-spread, spread))
    return {spot: pool[i] for spot, i in zip(SPOTS, order, strict=True)}


_placed: list[BossNpc] = []


@on_new_session
def _reset_placed() -> None:
    _placed.clear()


def placed_bosses() -> list[BossNpc]:
    """The boss NPCs :func:`place_bosses` put in the active session, for the data export."""
    return list(_placed)


def place_bosses(placement: dict[BossSpot, Boss]) -> list[BossNpc]:
    """Put a boss NPC at every spot in ``placement`` and Daos at his shrine; return them, Daos last."""
    flags = _free_flags()
    _placed.extend(_place(spot, boss, next(flags)) for spot, boss in placement.items())
    _placed.append(_place(FINAL_SPOT, DAOS, int(EventFlag.DAOS_DEFEATED)))
    iris.info(f"Placed {len(_placed)} boss NPCs.")
    return placed_bosses()


def _free_flags() -> Iterator[int]:
    used = set(NOT_BOSS_FLAGS)
    for index in range(MapEventObject.count):
        for event_list in MapEvent.from_index(index).event_lists:
            for script in event_list.events:
                used |= _flags_of(script.instructions)
    free = [flag for flag in FLAG_RANGE if flag not in used]
    if len(free) < len(SPOTS):
        msg = f"Only {len(free)} free flags in {FLAG_RANGE} for {len(SPOTS)} boss NPCs."
        raise ValueError(msg)
    return iter(free)


def _flags_of(instructions: Iterable[Instruction]) -> set[int]:
    flags: set[int] = set()
    for instruction in instructions:
        if instruction.opcode in (SET_FLAG, CLEAR_FLAG, BRANCH_ON_FLAG, BRANCH_ON_NOT_FLAG):
            flags.add(int(instruction.operands[0]))
        elif instruction.opcode == 0x14:  # condition chain: a flag follows codes 00/01/40/41/80/81
            operands = list(instruction.operands)
            for i, code in enumerate(operands[:-1]):
                if isinstance(code, int) and code in (0x00, 0x01, 0x40, 0x41, 0x80, 0x81):
                    flags.add(int(operands[i + 1]))
    return flags


def _place(spot: BossSpot, boss: Boss, flag: int) -> BossNpc:
    zone = Zone.from_index(spot.map_index)
    npc_index = max((npc.index for npc in zone.data.npc_positions), default=0) + 1
    if npc_index > MAX_NPC_INDEX:
        msg = f"Map {spot.map_index:#04x} has no free NPC index for the {spot.name} boss."
        raise ValueError(msg)
    position = NPC(npc_index, spot.x, spot.y, Boundary(spot.x, spot.y, spot.x + 1, spot.y + 1), NPC_MISC)
    zone.data.set_npcs([*zone.data.npc_positions, position])
    slot = FIRST_TALK_SLOT + npc_index
    final = spot is FINAL_SPOT
    _prefix_npc_load(zone.event.npc_script, flag, slot, boss.sprite, final=final)
    talk = resolve_or_create(f"{spot.map_index:02X}-C-{slot:02X}")
    talk.instructions = _talk(spot, boss, flag, slot, final=final)
    talk.dirty = True
    MapMeta.from_index(spot.map_index).write()
    zone.write_events()
    return BossNpc(spot, boss, flag, slot, f"{spot.map_index:02X}-B-{slot:02X}")


def _prefix_npc_load(script: EventScript, flag: int, slot: int, sprite: int, *, final: bool) -> None:
    """The boss's sprite until ``flag`` is set; then the beaten sprite (nothing for Daos, who vanishes)."""
    shift = 0x1000
    for instruction in script.instructions:
        instruction.line += shift
        instruction.operands = [
            Address(op.offset + shift) if isinstance(op, Address) and op.is_local else op for op in instruction.operands
        ]
    old = script.instructions[0].line
    prefix = [
        Instruction(0x000, BRANCH_ON_FLAG, [flag, Address(0x100 if not final else old)]),
        Instruction(0x010, LOAD_NPC, [slot, sprite]),
        Instruction(0x020, JUMP, [Address(old)]),
    ]
    if not final:
        prefix.append(Instruction(0x100, LOAD_NPC, [slot, BEATEN_SPRITE]))
    script.instructions = prefix + script.instructions
    script.dirty = True


def _talk(spot: BossSpot, boss: Boss, flag: int, slot: int, *, final: bool) -> list[Instruction]:
    """terrorwave's template_boss_npc: the battle, then on a win the flag, the vanishing boss and the rewards."""
    lines = [
        (BRANCH_ON_FLAG, [flag, Address(0x7FFF)]),  # beaten already: nothing happens
        (MUSIC, [boss.bgm]),
        (BATTLE_BG, [spot.battle_bg]),
        (BOSS_BATTLE, [boss.formation]),
        (BRANCH_ON_NOT_FLAG, [BATTLE_WON, Address(0x80)]),
        (0xA5, []),  # lost: game over
        (END, []),
    ]
    script = [Instruction(i * 0x10, opcode, operands) for i, (opcode, operands) in enumerate(lines)]
    won = [
        (SET_FLAG, [flag]),
        (0x70, []),
        (0xA4, []),
        (0x76, []),
        (0xA3, [slot, 0x85]),
        (0x37, [0x30]),
    ]
    if final:
        won.append((0x2E, [slot]))  # Daos vanishes
    else:
        won += [(0x34, [slot, BEATEN_SPRITE]), (0xA3, [slot, 0x86]), (0x37, [0x30])]
        for _ in range(spot.rewards):
            won += [(TEXT_WINDOW, [_text(REWARD_TEXT)]), (ITEM, [PLACEHOLDER_ITEM, 1])]
    won.append((MUSIC, [spot.map_bgm]))
    script += [Instruction(0x80 + i * 0x10, opcode, operands) for i, (opcode, operands) in enumerate(won)]
    script.append(Instruction(0x7FFF, END, []))
    return script


def _text(text: str) -> list:
    chunks, _ = decode_text(TEXT_WINDOW, encode_text(text), b"", b"")
    return chunks

