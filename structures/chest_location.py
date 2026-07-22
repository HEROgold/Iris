"""Chest -> map-location mapping.

This module ports terrorwave's hand-reverse-engineered chest->map table (its ``tables/chest_maps.txt``)
and joins it to Iris's chest content records (``ChestObject.pointers``) and map objects. Today it
resolves a chest to the **map** (and, 1:1, the **zone**) it belongs to.

CHEST COORDINATES (discovered): each map's ``ZoneData`` object data is 21 offset-delimited sections
(see ``structures.zone.ZoneData``); only exits/tiles/npcs/waypoints were decoded. Empirically,
**section 18 is the per-map chest-placement table**: 4-byte records ``[local_chest_index, x, y, misc]``
terminated by ``0xFF``, and its record count matches this module's chest-count-per-map on ~all maps.
``local_chest_index`` (0,1,2,... per map) + the map's first global chest index gives the global chest
index used here. So a chest's ``(x, y)`` IS in the ROM and this mapping can be extended to expose/write
it (via ``ZoneData``) to support physical placement randomization -- that wiring is not built yet.

The ``vanilla_item`` label is the item a chest holds in an unmodified ROM -- documentation only; it is
not re-read from the ROM, so it stays constant even after the contents are randomized.
"""

from typing import TYPE_CHECKING, Self

from tables import ChestObject


if TYPE_CHECKING:
    from structures.chest import PointerChest
    from structures.zone import Chest, Zone


# chest_index  map_index  vanilla_item  (ported verbatim from terrorwave tables/chest_maps.txt)
_CHEST_MAP_DATA = """
00 06 Escape
01 06 Antidote
02 06 Life potion
03 07 Power potion
04 07 Dragon egg
05 07 Magic jar
06 07 Hide armor
07 0B Power potion
08 0B Insect crush
09 0B Speedy ring
0A 0B Miracle
0B 0C Lake key
0C 11 Bomb
0D 11 Headband
0E 11 Water jewel
0F 12 Escape
10 12 Coat
11 13 Secret fruit
12 13 Dragon egg
13 13 Miracle
14 13 Light knife
15 18 Hi-Potion
16 18 Eron hat
17 18 Tuff buckler
18 19 Horse rock
19 19 Brave
1A 19 Miracle
1B 1A Jet helm
1C 1A Hi-Potion
1D 1A Hi-Magic
1E 1A Power brace
1F 1A Light armor
20 1A Witch ring
21 1B Shrine key
22 1B Miracle
23 21 Sky key
24 23 Jute helmet
25 24 Fire dagger
26 24 Camu armor
27 24 Pearl brace
28 29 Flame fruit
29 29 Aqua whip
2A 29 Fury helmet
2B 2A Ruby key
2C 2F Holy wings
2D 31 Bat rock
2E 31 Mind ring
2F 33 Treas. sword
30 34 Sword key
31 34 Anger brace
32 34 Cold rapier
33 34 Undead ring
34 34 Round shield
35 38 Eagle rock
36 39 Speed potion
37 39 Muscle ring
38 3B Wind key
39 3B Hook
3A 3B Miracle
3B 3D Scimitar
3C 3D Block shield
3D 41 Regain
3E 42 Hi-Magic
3F 47 Thunder ring
40 48 Deadly sword
41 48 Thunder ax
42 49 Life potion
43 49 Dragon egg
44 4E Protect ring
45 4E Pumkin jewel
46 4E Muscle ring
47 4F Cloud key
48 4F Miracle
49 4F Fayza shield
4A 54 Magic bikini
4B 58 Mystery ring
4C 58 Dragon egg
4D 58 Big shield
4E 5A Cancer rock
4F 5B Light key
50 5B Bee rock
51 5B Fire ring
52 60 Tree key
53 62 Fire arrow
54 64 Water ring
55 6D Narcysus key
56 6F Ice ring
57 76 Dekar blade
58 77 Lion fang
59 78 Fury ring
5A 7E Flower key
5B 7F Hammer
5C 81 Dragon egg
5D 81 Flying ax
5E 81 Power ring
5F 82 Life potion
60 82 Snake rock
61 83 Burn sword
62 8D Hi-Magic
63 8D Earth fruit
64 8E Fury ribbon
65 8E Dragon egg
66 8E Figgoru
67 8E Flame jewel
68 8F Dankirk key
69 94 Trial key
6A 96 Stun gun
6B 97 Mysto jewel
6C 97 Samu jewel
6D A5 Aqua sword
6E A8 Revive armor
6F A9 Heart key
70 AA Dragon egg
71 AA Holy whip
72 AB Rocket ring
73 B0 Heal armor
74 B1 Evil jewel
75 B1 Bright armor
76 B2 Cursed bow
77 B3 Ghost key
78 B4 Power robe
79 B4 Freeze sword
7A B4 Boom sword
7B B9 Super sword
7C BB Song rock
7D BB Ghost ring
7E BB Ghostclothes
7F BC Truth key
80 C0 Magma key
81 C1 Gorgon rock
82 C1 Hipower ring
83 C1 S-witch ring
84 C1 Hidora rock
85 C1 S-myst ring
86 C1 S-power ring
87 C1 Miracle
88 C2 Sonic ring
89 C2 Lizard blow
8A C2 Legend helm
8B C2 Mega shield
8C C2 Holy robe
8D C3 Magic scale
8E C3 S-pro ring
8F C3 Miracle
90 C3 S-mind ring
91 C3 Angry ring
92 C3 Kraken rock
93 C7 Miracle
94 D3 Miracle
95 D4 Basement key
96 DD S-thun ring
97 DD S-water ring
98 DD S-ice ring
99 E5 S-fire ring
9A E7 Miracle
9B E7 Miracle
9C E7 Miracle
9D E7 Miracle
9E E7 Miracle
9F E8 Miracle
A0 E8 Miracle
A1 E9 Miracle
A2 E9 Miracle
A3 EA Miracle
A4 EA Miracle
A5 EA Miracle
A6 EF Secret fruit
A7 EF Secret fruit
A8 F0 Light jewel
A9 F0 Dragon ring
AA F0 Brill helm
"""

CHEST_MAP: dict[int, int] = {}
_VANILLA_ITEM: dict[int, str] = {}
for _line in _CHEST_MAP_DATA.strip().splitlines():
    _chest, _map, _item = _line.split(maxsplit=2)
    CHEST_MAP[int(_chest, 16)] = int(_map, 16)
    _VANILLA_ITEM[int(_chest, 16)] = _item


class ChestLocation:
    """The map a chest belongs to (the finest location resolvable without the map tile layer)."""

    def __init__(self, chest_index: int, map_index: int) -> None:
        self.chest_index = chest_index
        self.map_index = map_index

    def __repr__(self) -> str:
        return f"<ChestLocation chest={self.chest_index:#04x} map={self.map_index:#04x} ({self.vanilla_item})>"

    @classmethod
    def from_index(cls, chest_index: int) -> Self:
        """Build the location for a chest by its chest index."""
        if chest_index not in CHEST_MAP:
            msg = f"Chest {chest_index:#04x} has no known map (not in the chest->map table)."
            raise KeyError(msg)
        return cls(chest_index, CHEST_MAP[chest_index])

    @classmethod
    def all(cls) -> list[Self]:
        """Every mapped chest, ordered by chest index."""
        return [cls(chest, mapped) for chest, mapped in sorted(CHEST_MAP.items())]

    @property
    def content_pointer(self) -> int:
        """ROM offset of this chest's content record (in ``ChestObject.pointers``)."""
        return ChestObject.pointers[self.chest_index]

    @property
    def vanilla_item(self) -> str:
        """The item this chest holds in an unmodified ROM (documentation label)."""
        return _VANILLA_ITEM[self.chest_index]

    @property
    def map_name(self) -> str:
        """Human-readable name of the map this chest is on."""
        from structures.event_script import MapEvent  # noqa: PLC0415  (avoid import cycle at load)

        return MapEvent.from_index(self.map_index).clean_map_name.decode("latin-1")

    @property
    def zone(self) -> "Zone":
        """The Zone (map) object this chest sits on."""
        from structures.zone import Zone  # noqa: PLC0415  (avoid import cycle at load)

        return Zone.from_index(self.map_index)

    @property
    def chest(self) -> "PointerChest":
        """The content object (item) for this chest."""
        from structures.chest import PointerChest  # noqa: PLC0415  (avoid import cycle at load)

        return PointerChest.from_index(self.chest_index)

    @property
    def placement(self) -> "Chest | None":
        """This chest's physical placement (x, y, slot, type) from the map's ZoneData section 18.

        The content<->placement link is positional/heuristic: chests on a map are ordered by global chest
        index (as ``chests_by_map`` yields them), and that order is matched against the section-18 records in
        order -- the same assumption ``randomize_chest_locations`` makes (docs/chest_system.md "Open questions"
        #1). Returns None when the map's parsed chest count doesn't match the mapping (a few maps don't line up).
        """
        placements = self.zone.data.chests
        on_map = chests_by_map().get(self.map_index, [])
        if len(placements) != len(on_map):
            return None
        local_order = [location.chest_index for location in on_map].index(self.chest_index)
        return placements[local_order]

    @property
    def x(self) -> int | None:
        """Map tile X of this chest, or None if placement is unavailable."""
        placement = self.placement
        return placement.x if placement is not None else None

    @property
    def y(self) -> int | None:
        """Map tile Y of this chest, or None if placement is unavailable."""
        placement = self.placement
        return placement.y if placement is not None else None


def chests_by_map() -> dict[int, list[ChestLocation]]:
    """Group every mapped chest by the map it sits on."""
    grouped: dict[int, list[ChestLocation]] = {}
    for location in ChestLocation.all():
        grouped.setdefault(location.map_index, []).append(location)
    return grouped


def dump_chest_locations() -> str:
    """Render the chest->map mapping as readable text (chest index, content pointer, vanilla item)."""
    lines: list[str] = []
    for map_index, locations in sorted(chests_by_map().items()):
        lines.append(f"# MAP {map_index:#04x} {locations[0].map_name}")
        lines.extend(
            f"  CHEST {location.chest_index:#04x} @ {location.content_pointer:#07x}  ({location.vanilla_item})"
            for location in locations
        )
    return "\n".join(lines)
