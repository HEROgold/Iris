"""Lufia II: Rise of the Sinistrals, the overworld, as an Archipelago world built on Iris (Iris-Dev#2).

Until the region graph (Iris-Dev#32) exists there is no logic: every progression item stays in its vanilla chest and
the rest of the chests' contents are shuffled. Until the ROM can receive items (Iris-Dev#20), this world's items stay
in this world; other worlds' items in its chests show as the AP item.
"""

import base64
import os
from typing import Any, ClassVar

import settings
from BaseClasses import Item, ItemClassification, MultiWorld, Region, Tutorial
from worlds.AutoWorld import WebWorld, World

from . import data
from .client import L2OWSNIClient  # noqa: F401 - importing it registers the SNI client
from .items import BASE_ID, GAME, ITEM_CLASSIFICATION, ITEM_NAMES, L2OWItem, item_name_to_id
from .locations import CHESTS, VICTORY, L2OWLocation, location_name_to_id
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
    """Lufia II's overworld campaign: the chests of every dungeon and town hold the multiworld's items."""

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
        self.options.local_items.value |= set(item_name_to_id)

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        world = Region("Lufia II", self.player, self.multiworld)
        menu.connect(world)
        for index, chest in CHESTS.items():
            world.locations.append(L2OWLocation(self.player, chest[2], BASE_ID + index, world))
        victory = L2OWLocation(self.player, VICTORY, None, world)
        victory.place_locked_item(self.create_event("Victory"))
        world.locations.append(victory)
        self.multiworld.regions += [menu, world]

    def create_item(self, name: str) -> Item:
        code = item_name_to_id[name]
        return L2OWItem(name, ITEM_CLASSIFICATION[code - BASE_ID], code, self.player)

    def create_event(self, name: str) -> Item:
        return L2OWItem(name, ItemClassification.progression, None, self.player)

    def create_items(self) -> None:
        for chest in CHESTS.values():
            item = self.create_item(ITEM_NAMES[chest[5]])
            if item.advancement:
                self.get_location(chest[2]).place_locked_item(item)
            else:
                self.multiworld.itempool.append(item)

    def set_rules(self) -> None:
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def get_filler_item_name(self) -> str:
        return "Potion"

    def generate_output(self, output_directory: str) -> None:
        patch = L2OWProcedurePatch(player=self.player, player_name=self.player_name)
        patch.write_file("basepatch.bsdiff4", base_patch())
        for location in self.get_locations():
            if location.address is None or location.item is None:
                continue
            item = location.item
            own = item.player == self.player and item.code is not None
            patch.write_chest(location.address - BASE_ID, item.code - BASE_ID if own else data.AP_ITEM_INDEX)
        patch.write_auth(self.auth)
        patch.write_file("tokens.bin", patch.get_token_binary())
        out_name = f"{self.multiworld.get_out_file_name_base(self.player)}{patch.patch_file_ending}"
        patch.write(os.path.join(output_directory, out_name))

    def modify_multidata(self, multidata: dict[str, Any]) -> None:
        name = base64.b64encode(self.auth.ljust(AUTH_SIZE, b"\0")).decode()
        multidata["connect_names"][name] = multidata["connect_names"][self.player_name]
