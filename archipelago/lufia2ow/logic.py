"""Routing: the vanilla story as a chain of stages, with the items each map and each story event needs (Iris-Dev#32).

The game isn't open: NPCs, ships and story scenes let you through in story order. So each stage is one region, entered
from the previous one once that stage's closing story event happened, and every location in it can still need items:

- **Keys** come from the ROM's door table (``data.KEY_DOORS``): a location on a door's map, or on a map behind it, needs
  that key. The key's own vanilla chest never does (in vanilla it sits in front of its door).
- **Tools** come from the dungeon requirements of RndmMeme's Lufia 2 tracker, split per map where the tool itself lies
  inside the dungeon (the Bomb in Alunze Castle B2, the Hook in Gordovan West Tower 4F, ...).
- **Story items** (Crown, Ruby apple, Treasure sword, ...) are needed by the story event that takes them.

When a rule isn't certain it asks for more, never less: extra requirements narrow where items can go, but can't make a
seed unbeatable. Maxim starts with the Arrow (no chest or script gives it), so no rule needs it.
"""

from dataclasses import dataclass, field

Requirement = tuple[tuple[str, ...], ...]
"""Alternatives: the location is reachable when any one tuple of items is held."""

NOTHING: Requirement = ((),)
BOMB_OR_HAMMER: Requirement = (("Bomb",), ("Hammer",))


def all_of(*items: str) -> Requirement:
    return (items,)


def both(first: Requirement, second: Requirement) -> Requirement:
    """Every combination of one alternative from each."""
    return tuple(tuple(dict.fromkeys(a + b)) for a in first for b in second)


@dataclass(frozen=True)
class Stage:
    name: str
    maps: frozenset[int]
    event: str
    """The story event that closes the stage and lets the next one open."""
    clear: Requirement = NOTHING
    """What reaching ``event`` needs, on top of being in the stage."""
    entry: Requirement = NOTHING
    """What entering the stage needs, on top of the previous stage's event."""
    map_rules: dict[int, Requirement] = field(default_factory=dict)


def maps(*indices: int | range) -> frozenset[int]:
    out: set[int] = set()
    for index in indices:
        out.update(index if isinstance(index, range) else (index,))
    return frozenset(out)


STAGES: list[Stage] = [
    Stage("Elcid", maps(range(0x02, 0x06)), "Elcid: heard the bad news"),
    Stage(
        "Cave to Sundletan", maps(0x06, 0x07), "Cave to Sundletan: met Iris",
    ),
    Stage(
        "Sundletan and Lake Cave", maps(0x08, 0x09, range(0x0A, 0x0D)), "Lake Cave: saved Tia",
        entry=all_of("Door key"),  # the Cave to Sundletan B1 door
        clear=all_of("Lake key"),
        map_rules={0x0C: all_of("Lake key")},
    ),
    Stage(
        "Alunze", maps(range(0x0D, 0x1C)), "Alunze Northwest Cave: defeated the Regal Goblin",
        clear=both(all_of("Crown"), BOMB_OR_HAMMER),
        map_rules={
            0x12: BOMB_OR_HAMMER, 0x13: BOMB_OR_HAMMER, 0x14: BOMB_OR_HAMMER,  # Alunze Castle B3-B5 (Bomb is on B2)
            **dict.fromkeys(range(0x18, 0x1C), BOMB_OR_HAMMER),  # Alunze Northwest Cave
        },
    ),
    Stage(
        "Tanbel", maps(range(0x1C, 0x25)), "Tanbel Southeast Tower: defeated Camu",
        entry=all_of("Shrine key"),  # the North Shrine door for Hilda
        clear=all_of("Sky key"),
        map_rules={0x24: all_of("Sky key")},
    ),
    Stage(
        "Clamento and Ruby Cave", maps(0x25, 0x26, range(0x27, 0x2B)), "Clamento: delivered the Ruby apple",
        clear=all_of("Ruby key", "Ruby apple"),
        map_rules={0x2A: all_of("Ruby key")},
    ),
    Stage(
        "Parcelyte and the Treasure Sword Shrine", maps(range(0x2B, 0x35)), "Parcelyte: returned the Treasure sword",
        clear=all_of("Sword key", "Bomb", "Treas. sword"),
        map_rules={
            **dict.fromkeys(range(0x30, 0x34), all_of("Sword key", "Bomb")),
            0x34: all_of("Bomb"),
        },
    ),
    Stage(
        "Gordovan", maps(range(0x35, 0x3E)), "Gordovan West Tower: passed Gades",
        clear=all_of("Bomb", "Hook", "Wind key"),
        map_rules={
            0x38: all_of("Bomb", "Wind key"),
            0x39: all_of("Bomb"), 0x3A: all_of("Bomb"), 0x3B: all_of("Bomb"),
            0x3C: all_of("Bomb", "Hook", "Wind key"), 0x3D: all_of("Bomb", "Hook", "Wind key"),
        },
    ),
    Stage(
        "Merix and Cave Bridge", maps(0x3E, 0x3F, range(0x40, 0x45)), "Merix: bridge repaired",
        clear=both(BOMB_OR_HAMMER, all_of("Hook")),
        map_rules=dict.fromkeys(range(0x40, 0x45), both(BOMB_OR_HAMMER, all_of("Hook"))),
    ),
    Stage(
        "Bound and the North Dungeon", maps(range(0x45, 0x4C)), "Bound: Dekar and Guy joined",
        clear=all_of("Bomb", "Hook"),
        map_rules=dict.fromkeys(range(0x47, 0x4B), all_of("Bomb", "Hook")),
    ),
    Stage(
        "Ancient Tower", maps(range(0x4C, 0x56)), "Ancient Tower: defeated Gades",
        clear=both(BOMB_OR_HAMMER, all_of("Hook", "Cloud key")),
        map_rules={
            **dict.fromkeys(range(0x4C, 0x51), both(BOMB_OR_HAMMER, all_of("Hook"))),
            **dict.fromkeys(range(0x51, 0x56), both(BOMB_OR_HAMMER, all_of("Hook", "Cloud key"))),
        },
    ),
    Stage(
        "Aleyn and the North Lighthouse", maps(range(0x56, 0x60)), "North Lighthouse: saved Jeros",
        clear=all_of("Light key"),
        map_rules={0x58: all_of("Light key"), 0x5C: all_of("Light key"), 0x5D: all_of("Light key")},
    ),
    Stage(
        "Phantom Tree Mountain", maps(range(0x60, 0x68)), "Aleyn: brought Jyad home",
        clear=all_of("Bomb", "Hook", "Fire arrow", "Tree key"),
        map_rules={
            **dict.fromkeys(range(0x60, 0x63), all_of("Bomb", "Hook")),
            **dict.fromkeys(range(0x63, 0x67), all_of("Bomb", "Hook", "Fire arrow")),
            0x67: all_of("Bomb", "Hook", "Fire arrow", "Tree key"),
        },
    ),
    Stage(
        "Gruberik, Narcysus and the Tower of Sacrifice", maps(range(0x68, 0x73)), "Tower of Sacrifice: defeated Idura",
        clear=all_of("Bomb", "Hook", "Narcysus key"),
        map_rules={
            0x6D: all_of("Bomb", "Hook"), 0x6E: all_of("Bomb", "Hook"),
            **dict.fromkeys(range(0x6F, 0x73), all_of("Bomb", "Hook", "Narcysus key")),
        },
    ),
    Stage(
        "Karlloon", maps(range(0x73, 0x79)), "Karlloon: finished the shrine",
        clear=all_of("Bomb", "Hook"),
        map_rules=dict.fromkeys(range(0x75, 0x79), all_of("Bomb", "Hook")),
    ),
    Stage(
        "Treadool and Flower Mountain", maps(range(0x79, 0x85)), "Treadool: delivered the Pretty flower",
        clear=all_of("Hammer", "Flower key", "Pretty flwr."),
        map_rules={
            0x7E: all_of("Hammer", "Flower key"),  # the Pretty flower grant is given at the summit
            0x80: all_of("Hammer"),
            **dict.fromkeys(range(0x81, 0x85), all_of("Hammer", "Flower key")),
        },
    ),
    Stage(
        "Forfeit, Dankirk and Auralio", maps(range(0x85, 0x91)), "Dankirk: returned the real Ruby Icon",
        clear=all_of("Bomb", "Hook", "Dankirk key", "Glass angel", "VIP card"),
        map_rules={
            **dict.fromkeys(range(0x8C, 0x90), all_of("Bomb", "Hook")),
            0x90: all_of("Bomb", "Hook", "Dankirk key"),
        },
    ),
    Stage(
        "Ferim and the Northeast Tower", maps(range(0x91, 0x99)), "Ferim: rescued the King",
        clear=all_of("Hook", "Hammer", "Trial key"),
        map_rules={
            **dict.fromkeys(range(0x94, 0x98), all_of("Hook", "Hammer")),
            0x98: all_of("Hook", "Hammer", "Trial key"),
        },
    ),
    Stage(
        "Agurio to the Divine Shrine", maps(range(0x99, 0xAC)), "Portravia: got the Submarine",
        clear=all_of("Hook", "Hammer", "Heart key"),
        map_rules={
            0xA8: all_of("Hook", "Hammer"), 0xA9: all_of("Hook", "Hammer"), 0xAB: all_of("Hook", "Hammer"),
            0xAA: all_of("Hook", "Hammer", "Heart key"),
        },
    ),
    Stage(
        "Barnan and the Shrine of Vengeance", maps(range(0xAC, 0xB5)), "Shrine of Vengeance: defeated the ghost",
        clear=all_of("Bomb", "Hammer", "Ghost key"),
        map_rules={
            **dict.fromkeys(range(0xAF, 0xB0), all_of("Bomb", "Hammer")),
            **dict.fromkeys(range(0xB0, 0xB3), all_of("Bomb", "Hammer", "Ghost key")),
            0xB3: all_of("Bomb", "Hammer"), 0xB4: all_of("Bomb", "Hammer"),
        },
    ),
    Stage(
        "Durale and the Tower of Truth", maps(range(0xB5, 0xBE)), "Tower of Truth: finished",
        clear=both(BOMB_OR_HAMMER, all_of("Hook", "Truth key")),
        map_rules={
            **dict.fromkeys(range(0xB8, 0xBD), both(BOMB_OR_HAMMER, all_of("Hook"))),
            0xBD: both(BOMB_OR_HAMMER, all_of("Hook", "Truth key")),
        },
    ),
    Stage(
        "Chaed and Dragon Mountain", maps(0xBE, 0xBF, range(0xC0, 0xC8)), "Chaed: got the Mermaid jade",
        clear=all_of("Hook", "Hammer", "Fire arrow", "Magma key"),
        map_rules={
            **dict.fromkeys(range(0xC0, 0xC3), all_of("Hook", "Hammer", "Fire arrow")),
            **dict.fromkeys(range(0xC3, 0xC8), all_of("Hook", "Hammer", "Fire arrow", "Magma key")),
            # Chaed gives the Mermaid jade once Dragon Mountain is done.
            0xBF: all_of("Hook", "Hammer", "Fire arrow", "Magma key"),
        },
    ),
    Stage(
        "Preamarl and the Submarine Shrine", maps(range(0xC8, 0xD1)), "Chaed: destroyed",
        entry=all_of("Mermaid jade"),
    ),
    Stage(
        "Gratze", maps(range(0xD1, 0xD8)), "Gratze: got the Engine",
        clear=all_of("Basement key"),
        map_rules={0xD2: all_of("Basement key")},
    ),
    # The airship: Gratze's Engine (a script grant without a flag, so it stays vanilla) goes into it at Kirmo.
    Stage("Narvick and the sealed towers", maps(range(0xD8, 0xE7)), "Kamirno Tower: the Shrine of Daos opens"),
    Stage("Shrine of Daos", maps(range(0xE7, 0xEC)), "Defeat Daos"),
]

GRANT_STAGE = {"26-B-18": "Forfeit, Dankirk and Auralio"}
"""Grants given in a town on a later visit than the town's own stage."""

EXCLUDED_MAPS = frozenset((0xEF, 0xF0, 0xF1))
"""The Ancient Cave: its chests sit 99 floors down."""
EXCLUDED_GRANTS = frozenset(("9F-B-50",))
"""The Dragon Egg shrine's wishes need eight Dragon eggs and give one of 26 items."""


def stage_of_map(map_index: int) -> Stage | None:
    return next((stage for stage in STAGES if map_index in stage.maps), None)
