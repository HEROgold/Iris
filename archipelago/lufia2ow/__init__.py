"""Lufia II: Rise of the Sinistrals, the overworld, as an Archipelago world built on Iris (Iris-Dev#2).

Routing follows the vanilla story (see ``logic``): every progression item can land in any chest or flagged script grant
that it doesn't itself gate, in this world or another, within what the options allow. Items from other worlds arrive
through the base patch's RX (Iris-Dev#20); other worlds' items in this world's chests and grants show as the AP item.
"""

import base64
import os
import re
from collections.abc import Callable
from types import ModuleType
from typing import Any, ClassVar

import settings
from BaseClasses import CollectionState, Item, ItemClassification, Location, MultiWorld, Region, Tutorial
from Fill import fill_restrictive
from worlds.AutoWorld import WebWorld, World

from . import data, data_open_world, hints
from .client import L2OWSNIClient  # noqa: F401 - importing it registers the SNI client
from .items import (
    BASE_ID,
    DRAGON_EGG,
    FIRE_ARROW,
    GAME,
    ITEM_CLASSIFICATION,
    ITEM_NAMES,
    KEYS,
    RANDOM_FILLER,
    RANDOM_USEFUL,
    TOOLS,
    L2OWItem,
    item_name_to_id,
)
from .locations import LOCATIONS, L2OWLocation, LocationInfo, grant_offsets, location_name_to_id
from .logic import (
    EGG_SHRINE_STAGE,
    EGG_WISH_VARIABLE,
    EGGS_PER_WISH,
    GOALS,
    GRANT_STAGE,
    MERIX_EGGS,
    STAGES,
    Requirement,
    Stage,
    stage_of_map,
    without,
)
from .options import Arrows, FillerItems, Goal, L2OWOptions, Placement, ShipUpgrades, StoryRewards
from .rom import AUTH_SIZE, US_MD5, L2OWProcedurePatch, base_patch, get_base_rom_path


Resolved = tuple[tuple[tuple[str, int], ...], ...]
"""A requirement in items and counts: alternatives of (item, count) pairs."""


class L2OWSettings(settings.Group):
    class RomFile(settings.SNESRomPath):
        """File name of the US Lufia II ROM"""

        description = "Lufia II ROM File"
        copy_to = "Lufia II - Rise of the Sinistrals (USA).sfc"
        md5s = [US_MD5]

    rom_file: RomFile = RomFile(RomFile.copy_to)


class L2OWWeb(WebWorld):
    tutorials = [
        Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up Lufia II Overworld for Archipelago.",
            "English",
            "setup_en.md",
            "setup/en",
            ["HEROgold"],
        ),
    ]


class L2OWWorld(World):
    """Lufia II's overworld campaign: the chests and story rewards of every dungeon and town hold the multiworld's items."""

    game = GAME
    web = L2OWWeb()
    settings: ClassVar[L2OWSettings]
    settings_key = "lufia2ow_options"
    options_dataclass = L2OWOptions
    options: L2OWOptions
    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id
    auth: bytes
    data: ModuleType
    """``data`` or ``data_open_world``: the ROM data of this player's base patch (players can mix them)."""
    grant_offsets: dict[int, int]
    """Grant location id -> offset of its item byte in this player's base ROM."""
    stages: list[Stage]
    """The stages up to and including the goal's."""
    location_infos: list[LocationInfo]
    """The locations in ``stages``."""
    counts: dict[str, tuple[str, int] | None]
    """A requirement's name -> the item and count that give it under the options; None when it is always held."""
    held: list[Item]
    """The own_stage keys and tools, kept out of the pool and placed first, in ``pre_fill``."""
    held_stage: dict[int, str]
    """id() of a held item -> the stage it has to stay in."""
    npc_hints: list[tuple[int, int, int, list[str]]]
    """(row in data.HINT_NPCS, location's player, location id, texts from longest to shortest), chosen in post_fill."""

    @classmethod
    def stage_assert_generate(cls, multiworld: MultiWorld) -> None:
        rom_file = get_base_rom_path()
        if not os.path.exists(rom_file):
            msg = f"Could not find the base ROM for {cls.game}: {rom_file}"
            raise FileNotFoundError(msg)

    def generate_early(self) -> None:
        self.auth = f"IRIS{self.player}_{self.multiworld.seed}".encode()[:AUTH_SIZE]
        goal = GOALS[self.options.goal.current_key]
        last = next(index for index, stage in enumerate(STAGES) if stage.name == goal.stage)
        self.stages = STAGES[: last + 1]
        names = {stage.name for stage in self.stages}
        self.data = data_open_world if self.options.open_world else data
        self.grant_offsets = grant_offsets(self.data)
        self.location_infos = [
            info for info in LOCATIONS
            if self._stage_of(info.map_index, info.grant).name in names
            and (info.grant is None or info.code in self.grant_offsets)  # open world drops some story grants
        ]
        self.counts = self._counts()
        for kind, placement in ((KEYS, self.options.key_placement), (TOOLS, self.options.tool_placement)):
            if placement == Placement.option_own_world:
                self.options.local_items.value |= {self._item_name(index) for index in kind}
        self.held = []
        self.held_stage = {}
        self.npc_hints = []

    def _counts(self) -> dict[str, tuple[str, int] | None]:
        # Maxim always starts with the Arrow: the game assumes at least one tool, and an empty tool list leaves the
        # opening scene on a black screen (its text box looks up the wrong map object).
        if self.options.arrows == Arrows.option_progressive:
            arrows = {"Arrow": None, "Fire arrow": ("Progressive Arrow", 1)}
        else:
            arrows = {"Arrow": None, "Fire arrow": ("Fire arrow", 1)}
        if self.options.ship_upgrades == ShipUpgrades.option_progressive:
            ships = {"Ship": ("Progressive Ship", 1), "Submarine": ("Progressive Ship", 2), "Airship": ("Progressive Ship", 3)}
        elif self.options.ship_upgrades == ShipUpgrades.option_separate:
            ships = {"Ship": ("Ship", 1), "Submarine": ("Submarine", 1), "Airship": ("Engine", 1)}
        else:
            ships = dict.fromkeys(("Ship", "Submarine", "Airship"))  # the story gives them
        return arrows | ships

    def _item_name(self, index: int) -> str:
        """The pool item that stands for game item ``index``: the Fire arrow is a Progressive Arrow when those are on."""
        if index == FIRE_ARROW and self.options.arrows == Arrows.option_progressive:
            return "Progressive Arrow"
        return ITEM_NAMES[index]

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)
        regions: dict[str, Region] = {}
        previous, previous_event = menu, None
        for stage in self.stages:
            region = Region(stage.name, self.player, self.multiworld)
            previous.connect(region, f"To {stage.name}", self._entry_rule(stage, previous_event))
            event = L2OWLocation(self.player, stage.event, None, region)
            event.place_locked_item(self.create_event(stage.event))
            event.access_rule = self._rule(stage.clear)
            region.locations.append(event)
            regions[stage.name] = region
            self.multiworld.regions.append(region)
            previous, previous_event = region, stage.event
        for info in self.location_infos:
            stage = self._stage_of(info.map_index, info.grant)
            location = L2OWLocation(self.player, info.name, info.code, regions[stage.name])
            # A key's own vanilla chest sits in front of its door, even when the door is on the same map.
            requirement = without(stage.map_rules.get(info.map_index, ((),)), ITEM_NAMES[info.vanilla_item])
            location.access_rule = self._rule(requirement)
            location.item_rule = self._stage_item_rule(stage.name)
            regions[stage.name].locations.append(location)

    @staticmethod
    def _stage_of(map_index: int, grant: str | None) -> Stage:
        if grant in GRANT_STAGE:
            return next(stage for stage in STAGES if stage.name == GRANT_STAGE[grant])
        stage = stage_of_map(map_index)
        if stage is None:
            msg = f"Map {map_index:#04x} has no stage."
            raise ValueError(msg)
        return stage

    def _resolve(self, requirement: Requirement) -> Resolved:
        """Names to (item, count) pairs; names that are always held drop out."""
        out = []
        for alternative in requirement:
            pairs = (self.counts.get(name, (name, 1)) for name in alternative)
            out.append(tuple(pair for pair in pairs if pair is not None))
        return tuple(out)

    def _rule(self, requirement: Requirement) -> Callable[[CollectionState], bool]:
        player, alternatives = self.player, self._resolve(requirement)
        return lambda state: any(all(state.has(item, player, count) for item, count in alt) for alt in alternatives)

    def _entry_rule(self, stage: Stage, previous_event: str | None) -> Callable[[CollectionState], bool]:
        entry = self._rule(stage.entry)
        if previous_event is None:
            return entry
        player = self.player
        return lambda state: state.has(previous_event, player) and entry(state)

    def create_item(self, name: str) -> Item:
        code = item_name_to_id[name]
        classification = ITEM_CLASSIFICATION[code - BASE_ID]
        if code == BASE_ID + DRAGON_EGG and self._egg_goal():
            classification = ItemClassification.progression
        return L2OWItem(name, classification, code, self.player)

    def _egg_goal(self) -> bool:
        return self.options.goal == Goal.option_dragon_eggs

    def _eggs_needed(self) -> int:
        """Dragon eggs from the pool the wishes need; Merix's egg isn't in the pool."""
        return EGGS_PER_WISH * self.options.egg_wishes.value - MERIX_EGGS

    def create_event(self, name: str) -> Item:
        return L2OWItem(name, ItemClassification.progression, None, self.player)

    def create_items(self) -> None:
        """Lock what stays vanilla, hold back own_stage keys and tools for ``pre_fill``, and pool the rest.

        Items without a vanilla location (ship upgrades, extra Dragon eggs) take the place of filler, so the pool stays
        the size of the locations.
        """
        pool: list[Item] = []
        for info in self.location_infos:
            item = self.create_item(self._item_name(info.vanilla_item))
            stage = self._stage_of(info.map_index, info.grant).name
            placement = self._placement(info)
            if placement == Placement.option_vanilla:
                self.get_location(info.name).place_locked_item(item)
            elif placement == Placement.option_own_stage:
                self._hold(item, stage)
            else:
                pool.append(item)
        for name, placement in self._extra_items():
            item = self.create_item(name)
            if placement == Placement.option_vanilla:
                self.multiworld.push_precollected(item)
                continue
            self._drop_filler(pool)
            if placement == Placement.option_own_stage:
                self._hold(item, self._first_stage_with_locations())
            else:
                pool.append(item)
        self.multiworld.itempool += [self._filler_swap(item) for item in pool]

    def _extra_items(self) -> list[tuple[str, int]]:
        """(item, placement) of the items that have no vanilla location."""
        extra: list[tuple[str, int]] = []
        if self.options.ship_upgrades == ShipUpgrades.option_progressive:
            extra += [("Progressive Ship", Placement.option_anywhere)] * 3
        elif self.options.ship_upgrades == ShipUpgrades.option_separate:
            extra += [(name, Placement.option_anywhere) for name in ("Ship", "Submarine", "Engine")]
        if self._egg_goal():
            in_pool = sum(info.vanilla_item == DRAGON_EGG for info in self.location_infos)
            extra += [("Dragon egg", Placement.option_anywhere)] * max(0, self._eggs_needed() - in_pool)
        return extra

    def _hold(self, item: Item, stage: str) -> None:
        self.held.append(item)
        self.held_stage[id(item)] = stage

    def _drop_filler(self, pool: list[Item]) -> None:
        """Remove one non-progression item (not a Dragon egg) from ``pool`` to make room."""
        candidates = [item for item in pool if not item.advancement and item.code != BASE_ID + DRAGON_EGG]
        pool.remove(self.random.choice(candidates))

    def _first_stage_with_locations(self) -> str:
        return self._stage_of(self.location_infos[0].map_index, self.location_infos[0].grant).name

    def _placement(self, info: LocationInfo) -> int:
        """How the vanilla item of ``info`` is placed. Vanilla story rewards win over the key and tool options."""
        if info.grant is not None and self.options.story_rewards == StoryRewards.option_vanilla:
            return Placement.option_vanilla
        if info.vanilla_item in KEYS:
            return self.options.key_placement.value
        if info.vanilla_item in TOOLS:
            return self.options.tool_placement.value
        return Placement.option_anywhere

    def _filler_swap(self, item: Item) -> Item:
        """With randomized Filler Items, a non-progression item becomes a random one; Dragon eggs stay."""
        if self.options.filler_items == FillerItems.option_vanilla or item.advancement:
            return item
        if item.code == BASE_ID + DRAGON_EGG:
            return item
        pool = RANDOM_USEFUL if self.random.randrange(100) < self.options.useful_items.value else RANDOM_FILLER
        return self.create_item(ITEM_NAMES[self.random.choice(pool)])

    def get_pre_fill_items(self) -> list[Item]:
        return list(self.held)

    def pre_fill(self) -> None:
        """Place the own_stage keys and tools before anything else, while their stages still have room.

        One fill for all of them, from a state holding the whole item pool, so one can sit behind another; the item
        rules keep each in its own stage.
        """
        if not self.held:
            return
        state = CollectionState(self.multiworld)
        for item in self.multiworld.itempool:
            state.collect(item, prevent_sweep=True)
        stages = set(self.held_stage.values())
        locations: list[Location] = [
            location
            for location in self.get_locations()
            if location.address is not None and location.item is None and location.parent_region.name in stages
        ]
        held, self.held = self.held, []
        self.random.shuffle(locations)
        fill_restrictive(
            self.multiworld, state, locations, held, single_player_placement=True, lock=True,
            name=f"{self.player_name} own-stage keys and tools",
        )

    def _stage_item_rule(self, stage: str) -> Callable[[Item], bool]:
        """Keep the own_stage keys and tools of other stages out of a location in ``stage``."""
        held_stage = self.held_stage
        return lambda item: held_stage.get(id(item), stage) == stage

    def set_rules(self) -> None:
        player = self.player
        if self._egg_goal():
            eggs = self._eggs_needed()
            self.multiworld.completion_condition[player] = lambda state: (
                state.can_reach_region(EGG_SHRINE_STAGE, player) and state.has("Dragon egg", player, eggs)
            )
            return
        goal = self.stages[-1].event
        self.multiworld.completion_condition[player] = lambda state: state.has(goal, player)

    def post_fill(self) -> None:
        """Pick the hint NPCs and what each one tells: a different progression item of this world each."""
        count = min(self.options.hint_npcs.value, len(self.data.HINT_FLAGS), len(self.data.HINT_NPCS))
        spots = [
            location for location in self.multiworld.get_locations()
            if location.item is not None and location.address is not None and location.item.player == self.player
            and location.item.advancement and location.item.code is not None
        ]
        spots.sort(key=lambda location: (location.player, location.address))
        chosen = self.random.sample(spots, min(count, len(spots)))
        npcs = self.random.sample(range(len(self.data.HINT_NPCS)), len(chosen))
        self.npc_hints = [
            (npc, location.player, location.address, self._hint_texts(location))
            for npc, location in zip(npcs, chosen, strict=True)
        ]

    def _hint_texts(self, location: Location) -> list[str]:
        item = location.item.name if location.item else "?"
        if location.player == self.player:
            spot = re.sub(r" \[map [^]]*\]", "", location.name)  # drop the duplicate-name marker
            spot = re.sub(r" \([^)]*\)$", "", spot)  # and the vanilla item, which would mislead
            spot = re.sub(r": .* reward$", ", a reward", spot)
            place = spot.split(", ", 1)[0]
            return [f"Your {item} is here, in {spot}.", f"{item}: {spot}.", f"{item}: {place}.", f"{item} is here."]
        owner = self.multiworld.get_player_name(location.player)
        game = self.multiworld.game[location.player]
        return [
            f"Your {item} is in {owner}'s world ({game}): {location.name}.",
            f"Your {item} is with {owner}: {location.name}.",
            f"Your {item} is in {owner}'s world.",
            f"{item}: {owner}.",
        ]

    def fill_slot_data(self) -> dict[str, Any]:
        goal = self.options.goal.current_key
        return {
            "goal": goal,
            "goal_flag": GOALS[goal].flag,
            "goal_wishes": self.options.egg_wishes.value if self._egg_goal() else 0,
            "goal_wish_variable": EGG_WISH_VARIABLE,
            "hint_unlock": bool(self.options.hint_unlock),
            "npc_hints": {self.data.HINT_FLAGS[n]: [player, address] for n, (_, player, address, _) in enumerate(self.npc_hints)},
        }

    def get_filler_item_name(self) -> str:
        return "Potion"

    def generate_output(self, output_directory: str) -> None:
        patch = L2OWProcedurePatch(player=self.player, player_name=self.player_name)
        patch.write_file("basepatch.bsdiff4", base_patch(bool(self.options.open_world)))
        for location in self.get_locations():
            if location.address is None or location.item is None:
                continue
            item = location.item
            own = item.player == self.player and item.code is not None
            index = item.code - BASE_ID if own else self.data.AP_ITEM_INDEX
            if location.address in self.grant_offsets:
                patch.write_grant(self.grant_offsets[location.address], index)
            else:
                patch.write_chest(location.address - BASE_ID, index)
        for n, (npc, _, _, texts) in enumerate(self.npc_hints):
            _, _, offset, size = self.data.HINT_NPCS[npc]
            patch.write_hint_npc(offset, hints.fitted(self.data.HINT_FLAGS[n], texts, size))
        patch.write_auth(self.auth)
        patch.write_file("tokens.bin", patch.get_token_binary())
        out_name = f"{self.multiworld.get_out_file_name_base(self.player)}{patch.patch_file_ending}"
        patch.write(os.path.join(output_directory, out_name))

    def modify_multidata(self, multidata: dict[str, Any]) -> None:
        name = base64.b64encode(self.auth.ljust(AUTH_SIZE, b"\0")).decode()
        multidata["connect_names"][name] = multidata["connect_names"][self.player_name]
