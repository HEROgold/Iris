"""Lufia II: Rise of the Sinistrals, the overworld, as an Archipelago world built on Iris (Iris-Dev#2).

Routing follows the vanilla story (see ``logic``): every progression item can land in any chest or flagged script grant
that it doesn't itself gate, in this world or another, within what the options allow. Items from other worlds arrive
through the base patch's RX (Iris-Dev#20); other worlds' items in this world's chests and grants show as the AP item.
"""

import base64
import os
from collections.abc import Callable
from typing import Any, ClassVar

import settings
from BaseClasses import CollectionState, Item, ItemClassification, Location, MultiWorld, Region, Tutorial
from Fill import fill_restrictive
from worlds.AutoWorld import WebWorld, World

from . import data
from .client import L2OWSNIClient  # noqa: F401 - importing it registers the SNI client
from .items import (
    BASE_ID,
    DRAGON_EGG,
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
from .locations import LOCATIONS, L2OWLocation, LocationInfo, location_name_to_id
from .logic import GOALS, GRANT_STAGE, STAGES, Requirement, Stage, stage_of_map, without
from .options import FillerItems, L2OWOptions, Placement, StoryRewards
from .rom import AUTH_SIZE, US_MD5, L2OWProcedurePatch, base_patch, get_base_rom_path


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
    stages: list[Stage]
    """The stages up to and including the goal's."""
    location_infos: list[LocationInfo]
    """The locations in ``stages``."""
    item_stage: dict[str, str]
    """own_stage key or tool -> the stage it has to stay in (its vanilla location's)."""
    held: list[Item]
    """The own_stage keys and tools, kept out of the pool and placed first, in ``pre_fill``."""

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
        self.location_infos = [info for info in LOCATIONS if self._stage_of(info.map_index, info.grant).name in names]
        self.item_stage = {
            ITEM_NAMES[info.vanilla_item]: self._stage_of(info.map_index, info.grant).name
            for info in self.location_infos
            if self._placement(info) == Placement.option_own_stage
        }
        for kind, placement in ((KEYS, self.options.key_placement), (TOOLS, self.options.tool_placement)):
            if placement == Placement.option_own_world:
                self.options.local_items.value |= {ITEM_NAMES[index] for index in kind}
        self.held = []

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

    def _rule(self, requirement: Requirement) -> Callable[[CollectionState], bool]:
        player = self.player
        return lambda state: any(state.has_all(items, player) for items in requirement)

    def _entry_rule(self, stage: Stage, previous_event: str | None) -> Callable[[CollectionState], bool]:
        entry = self._rule(stage.entry)
        if previous_event is None:
            return entry
        player = self.player
        return lambda state: state.has(previous_event, player) and entry(state)

    def create_item(self, name: str) -> Item:
        code = item_name_to_id[name]
        return L2OWItem(name, ITEM_CLASSIFICATION[code - BASE_ID], code, self.player)

    def create_event(self, name: str) -> Item:
        return L2OWItem(name, ItemClassification.progression, None, self.player)

    def create_items(self) -> None:
        """Lock what stays vanilla, hold back own_stage keys and tools for ``pre_fill``, and pool the rest."""
        for info in self.location_infos:
            item = self.create_item(ITEM_NAMES[info.vanilla_item])
            placement = self._placement(info)
            if placement == Placement.option_vanilla:
                self.get_location(info.name).place_locked_item(item)
            elif placement == Placement.option_own_stage:
                self.held.append(item)
            else:
                self.multiworld.itempool.append(self._filler_swap(item))

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
        stages = set(self.item_stage.values())
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
        player, others = self.player, {name for name, own in self.item_stage.items() if own != stage}
        return lambda item: not (item.player == player and item.name in others)

    def set_rules(self) -> None:
        goal = self.stages[-1].event
        self.multiworld.completion_condition[self.player] = lambda state: state.has(goal, self.player)

    def fill_slot_data(self) -> dict[str, Any]:
        goal = self.options.goal.current_key
        return {"goal": goal, "goal_flag": GOALS[goal].flag}

    def get_filler_item_name(self) -> str:
        return "Potion"

    def generate_output(self, output_directory: str) -> None:
        patch = L2OWProcedurePatch(player=self.player, player_name=self.player_name)
        patch.write_file("basepatch.bsdiff4", base_patch())
        grants = {info.code for info in LOCATIONS if info.grant is not None}
        for location in self.get_locations():
            if location.address is None or location.item is None:
                continue
            item = location.item
            own = item.player == self.player and item.code is not None
            index = item.code - BASE_ID if own else data.AP_ITEM_INDEX
            if location.address in grants:
                patch.write_grant(location.address, index)
            else:
                patch.write_chest(location.address - BASE_ID, index)
        patch.write_auth(self.auth)
        patch.write_file("tokens.bin", patch.get_token_binary())
        out_name = f"{self.multiworld.get_out_file_name_base(self.player)}{patch.patch_file_ending}"
        patch.write(os.path.join(output_directory, out_name))

    def modify_multidata(self, multidata: dict[str, Any]) -> None:
        name = base64.b64encode(self.auth.ljust(AUTH_SIZE, b"\0")).decode()
        multidata["connect_names"][name] = multidata["connect_names"][self.player_name]
