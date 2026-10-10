"""Lufia II: Rise of the Sinistrals, the overworld, as an Archipelago world built on Iris (Iris-Dev#2).

Routing follows the vanilla story (see ``logic``): every progression item can land in any chest or flagged script grant
that it doesn't itself gate, in this world or another. Items from other worlds arrive through the base patch's RX
(Iris-Dev#20); other worlds' items in this world's chests and grants show as the AP item.
"""

import base64
import os
from collections.abc import Callable
from typing import Any, ClassVar

import settings
from BaseClasses import CollectionState, Item, ItemClassification, MultiWorld, Region, Tutorial
from worlds.AutoWorld import WebWorld, World

from . import data
from .client import L2OWSNIClient  # noqa: F401 - importing it registers the SNI client
from .items import BASE_ID, GAME, ITEM_CLASSIFICATION, ITEM_NAMES, L2OWItem, item_name_to_id
from .locations import LOCATIONS, L2OWLocation, location_name_to_id
from .logic import GRANT_STAGE, STAGES, Requirement, Stage, stage_of_map
from .options import L2OWOptions
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

    @classmethod
    def stage_assert_generate(cls, multiworld: MultiWorld) -> None:
        rom_file = get_base_rom_path()
        if not os.path.exists(rom_file):
            msg = f"Could not find the base ROM for {cls.game}: {rom_file}"
            raise FileNotFoundError(msg)

    def generate_early(self) -> None:
        self.auth = f"IRIS{self.player}_{self.multiworld.seed}".encode()[:AUTH_SIZE]

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)
        regions: dict[str, Region] = {}
        previous, previous_event = menu, None
        for stage in STAGES:
            region = Region(stage.name, self.player, self.multiworld)
            previous.connect(region, f"To {stage.name}", self._entry_rule(stage, previous_event))
            event = L2OWLocation(self.player, stage.event, None, region)
            event.place_locked_item(self.create_event(stage.event))
            event.access_rule = self._rule(stage.clear)
            region.locations.append(event)
            regions[stage.name] = region
            self.multiworld.regions.append(region)
            previous, previous_event = region, stage.event
        for info in LOCATIONS:
            stage = self._stage_of(info.map_index, info.grant)
            location = L2OWLocation(self.player, info.name, info.code, regions[stage.name])
            location.access_rule = self._rule(stage.map_rules.get(info.map_index, ((),)))
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
        for info in LOCATIONS:
            self.multiworld.itempool.append(self.create_item(ITEM_NAMES[info.vanilla_item]))

    def set_rules(self) -> None:
        goal = STAGES[-1].event
        self.multiworld.completion_condition[self.player] = lambda state: state.has(goal, self.player)

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
