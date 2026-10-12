"""Lufia II: Rise of the Sinistrals, the overworld, as an Archipelago world built on Iris (Iris-Dev#2).

Routing follows the vanilla story (see ``logic``), or with Open World the travel map (``logic.OPEN_AREAS``): every progression item can land in any chest or flagged script grant
that it doesn't itself gate, in this world or another, within what the options allow. Items from other worlds arrive
through the base patch's RX (Iris-Dev#20); other worlds' items in this world's chests and grants show as the AP item.
"""

import base64
import os
import re
from collections.abc import Callable
from types import ModuleType
from typing import Any, ClassVar, TextIO

import settings
from BaseClasses import CollectionState, Item, ItemClassification, Location, MultiWorld, Region, Tutorial
from Fill import fill_restrictive
from Options import OptionError
from worlds.AutoWorld import WebWorld, World

from . import bosses, data, data_open_world, hints
from .client import L2OWSNIClient  # noqa: F401 - importing it registers the SNI client
from .items import (
    BASE_ID,
    CHARACTER_BASE,
    DRAGON_EGG,
    FIRE_ARROW,
    GAME,
    ITEM_CLASSIFICATION,
    ITEM_NAMES,
    KEYS,
    MAIDEN_BASE,
    MAIDENS,
    OPEN_WORLD_SPECIALS,
    RANDOM_FILLER,
    RANDOM_USEFUL,
    SPECIAL_ITEM_NAMES,
    TOOLS,
    L2OWItem,
    item_name_to_id,
)
from .locations import BOSS_REWARDS, LOCATIONS, BossReward, L2OWLocation, LocationInfo, grant_offsets, location_name_to_id
from .logic import (
    EGG_SHRINE_MAP,
    EGG_SHRINE_STAGE,
    EGG_WISH_VARIABLE,
    EGGS_PER_WISH,
    GOALS,
    GRANT_STAGE,
    MERIX_EGGS,
    NOTHING,
    OPEN_AREAS,
    OPEN_DAOS_EVENT,
    OPEN_GOALS,
    OPEN_MAP_RULES,
    STAGES,
    Requirement,
    Stage,
    area_of_map,
    stage_of_map,
    without,
)
from .options import (
    Arrows,
    BossPlacement,
    BossStrength,
    FillerItems,
    Goal,
    L2OWOptions,
    Placement,
    ShipUpgrades,
    StoryRewards,
)
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
    boss_rewards: list[BossReward]
    """Open world's boss NPC rewards (locations); empty in the linear game."""
    boss_offsets: dict[int, int]
    """Boss reward location id -> offset of its grant's item byte in the open-world base ROM."""
    boss_placement: list[bosses.Boss]
    """Open world: the boss at each spot of ``data_open_world.BOSS_SPOTS`` (Daos not included); empty in linear."""
    stages: list[Stage]
    """The stages up to and including the goal's; empty in open world, which has areas (``logic.OPEN_AREAS``)."""
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
        self.data = data_open_world if self.options.open_world else data
        self.grant_offsets = grant_offsets(self.data)
        self.boss_rewards = BOSS_REWARDS if self.options.open_world else []
        self.boss_offsets = {reward.code: reward.offset for reward in self.boss_rewards}
        self.boss_placement = []
        if self.options.open_world:
            self._open_world_options()
            self.boss_placement = (
                bosses.shuffled_placement(self.random)
                if self.options.boss_placement == BossPlacement.option_shuffled
                else bosses.fixed_placement()
            )
            self.stages = []
            self.location_infos = [
                info for info in LOCATIONS
                if info.grant is None or info.code in self.grant_offsets  # open world drops the story grants
            ]
        else:
            goal = GOALS[self.options.goal.current_key]
            last = next(index for index, stage in enumerate(STAGES) if stage.name == goal.stage)
            self.stages = STAGES[: last + 1]
            names = {stage.name for stage in self.stages}
            self.location_infos = [
                info for info in LOCATIONS
                if self._stage_of(info.map_index, info.grant).name in names
                and (info.grant is None or info.code in self.grant_offsets)
            ]
        self.counts = self._counts()
        for kind, placement in ((KEYS, self.options.key_placement), (TOOLS, self.options.tool_placement)):
            if placement == Placement.option_own_world:
                self.options.local_items.value |= {self._item_name(index) for index in kind}
        self.held = []
        self.held_stage = {}
        self.npc_hints = []

    def _open_world_options(self) -> None:
        """Open world has no stages and no story: own_stage placement is own_world, vanilla ship upgrades are
        progressive, and only the goals in ``OPEN_GOALS`` are allowed. Boss Placement and Boss Strength only act here;
        the linear game ignores them."""
        goal = self.options.goal.current_key
        if goal not in OPEN_GOALS:
            msg = f"{self.player_name}: goal {goal} needs the story; with Open World use one of {sorted(OPEN_GOALS)}."
            raise OptionError(msg)
        for option in (self.options.key_placement, self.options.tool_placement):
            if option == Placement.option_own_stage:
                option.value = Placement.option_own_world
        if self.options.ship_upgrades == ShipUpgrades.option_vanilla:
            self.options.ship_upgrades.value = ShipUpgrades.option_progressive

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
        if self.options.open_world:
            self._create_open_regions(menu)
            return
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

    def _create_open_regions(self, menu: Region) -> None:
        """One region per travel area, entered from the area before it; the maps keep their tool and key rules.

        Daos waits behind the Doom Island barrier, which the three maidens lift. A boss reward is in its map's area,
        under its map's rule.
        """
        regions: dict[str, Region] = {}
        for area in OPEN_AREAS:
            region = Region(area.name, self.player, self.multiworld)
            parent = menu if area.parent is None else regions[area.parent]
            parent.connect(region, f"To {area.name}", self._rule(area.entry))
            regions[area.name] = region
            self.multiworld.regions.append(region)
        if not self._egg_goal():
            daos = regions[OPEN_AREAS[-1].name]
            event = L2OWLocation(self.player, OPEN_DAOS_EVENT, None, daos)
            event.place_locked_item(self.create_event(OPEN_DAOS_EVENT))
            maidens, player = [SPECIAL_ITEM_NAMES[MAIDEN_BASE + n] for n in range(len(MAIDENS))], self.player
            event.access_rule = lambda state: state.has_all(maidens, player)
            daos.locations.append(event)
        for info in self.location_infos:
            area = area_of_map(info.map_index)
            if area is None:
                msg = f"Map {info.map_index:#04x} has no open-world area."
                raise ValueError(msg)
            location = L2OWLocation(self.player, info.name, info.code, regions[area.name])
            requirement = without(OPEN_MAP_RULES.get(info.map_index, NOTHING), ITEM_NAMES[info.vanilla_item])
            location.access_rule = self._rule(requirement)
            regions[area.name].locations.append(location)
        for reward in self.boss_rewards:
            area = area_of_map(reward.map_index)
            if area is None:
                msg = f"Boss map {reward.map_index:#04x} has no open-world area."
                raise ValueError(msg)
            location = L2OWLocation(self.player, reward.name, reward.code, regions[area.name])
            location.access_rule = self._rule(OPEN_MAP_RULES.get(reward.map_index, NOTHING))
            regions[area.name].locations.append(location)

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
        """Dragon eggs from the pool the wishes need; Merix's egg isn't in the pool (open world has no Merix egg)."""
        merix = 0 if self.options.open_world else MERIX_EGGS
        return EGGS_PER_WISH * self.options.egg_wishes.value - merix

    def create_event(self, name: str) -> Item:
        return L2OWItem(name, ItemClassification.progression, None, self.player)

    def create_items(self) -> None:
        """Lock what stays vanilla, hold back own_stage keys and tools for ``pre_fill``, and pool the rest.

        Boss rewards (open world) have no vanilla item: each pools a random filler item. Items without a vanilla
        location (ship upgrades, extra Dragon eggs, open world's characters, capsules and maidens) take the place of
        filler, so the pool stays the size of the locations.
        """
        pool: list[Item] = []
        for info in self.location_infos:
            item = self.create_item(self._item_name(info.vanilla_item))
            placement = self._placement(info)
            if placement == Placement.option_vanilla:
                self.get_location(info.name).place_locked_item(item)
            elif placement == Placement.option_own_stage:
                self._hold(item, self._stage_of(info.map_index, info.grant).name)
            else:
                pool.append(item)
        pool += [self._random_filler() for _ in self.boss_rewards]
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
        if self.options.open_world:
            extra += [(ITEM_NAMES[index], Placement.option_anywhere) for index in OPEN_WORLD_SPECIALS]
        return extra

    def _hold(self, item: Item, stage: str) -> None:
        self.held.append(item)
        self.held_stage[id(item)] = stage

    def _drop_filler(self, pool: list[Item]) -> None:
        """Remove one non-progression item (not a Dragon egg, a capsule or another special item) from ``pool``."""
        candidates = [
            item for item in pool
            if not item.advancement and item.code != BASE_ID + DRAGON_EGG and item.code - BASE_ID not in SPECIAL_ITEM_NAMES
        ]
        if not candidates:
            msg = f"{self.player_name}: no filler left to make room for the items without a location."
            raise OptionError(msg)
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
        if item.code == BASE_ID + DRAGON_EGG or item.code - BASE_ID in SPECIAL_ITEM_NAMES:
            return item
        return self._random_filler()

    def _random_filler(self) -> Item:
        """A random useful item (Useful Items percent of the time) or a random filler item."""
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
            shrine = EGG_SHRINE_STAGE
            if self.options.open_world:
                shrine = area_of_map(EGG_SHRINE_MAP).name  # type: ignore[union-attr] - the map has an area
            self.multiworld.completion_condition[player] = lambda state: (
                state.can_reach_region(shrine, player) and state.has("Dragon egg", player, eggs)
            )
            return
        goal = OPEN_DAOS_EVENT if self.options.open_world else self.stages[-1].event
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
            # A character, capsule or maiden can't sit in a chest or grant: it shows as the AP item and the server sends
            # it (the client hands on this world's own items only for those).
            own = item.player == self.player and item.code is not None and item.code - BASE_ID < CHARACTER_BASE
            index = item.code - BASE_ID if own else self.data.AP_ITEM_INDEX
            if location.address in self.boss_offsets:
                patch.write_grant(self.boss_offsets[location.address], index)
            elif location.address in self.grant_offsets:
                patch.write_grant(self.grant_offsets[location.address], index)
            else:
                patch.write_chest(location.address - BASE_ID, index)
        for n, (npc, _, _, texts) in enumerate(self.npc_hints):
            _, _, offset, size = self.data.HINT_NPCS[npc]
            patch.write_hint_npc(offset, hints.fitted(self.data.HINT_FLAGS[n], texts, size))
        if self.options.open_world:
            self._write_bosses(patch)
        patch.write_auth(self.auth)
        patch.write_file("tokens.bin", patch.get_token_binary())
        out_name = f"{self.multiworld.get_out_file_name_base(self.player)}{patch.patch_file_ending}"
        patch.write(os.path.join(output_directory, out_name))

    def _write_bosses(self, patch: L2OWProcedurePatch) -> None:
        """The shuffled bosses' sprite, music and formation at each spot (the base patch has the fixed ones), and the
        boss-scaling mode, with by_depth's level per formation from the placement in effect."""
        if self.options.boss_placement == BossPlacement.option_shuffled:
            for row, boss in zip(data_open_world.BOSS_NPCS[:-1], self.boss_placement, strict=True):  # Daos last, stays
                patch.write_boss(row, boss)
        strength = self.options.boss_strength.value
        levels = bosses.depth_levels(self.boss_placement) if strength == BossStrength.option_by_depth else None
        patch.write_boss_strength(strength, levels)

    def write_spoiler(self, spoiler_handle: TextIO) -> None:
        if not self.options.open_world:
            return
        spoiler_handle.write(f"\n\nBoss placement ({self.player_name}, {self.options.boss_placement.current_key}):\n")
        for (spot, _, _), boss in zip(data_open_world.BOSS_SPOTS, self.boss_placement, strict=True):
            spoiler_handle.write(f"    {spot}: {boss[0]}\n")
        spoiler_handle.write(f"    {data_open_world.FINAL_SPOT[0]}: {data_open_world.DAOS[0]}\n")

    def modify_multidata(self, multidata: dict[str, Any]) -> None:
        name = base64.b64encode(self.auth.ljust(AUTH_SIZE, b"\0")).decode()
        multidata["connect_names"][name] = multidata["connect_names"][self.player_name]
