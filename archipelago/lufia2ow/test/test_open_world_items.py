"""Open world's characters, capsules and maidens as items, and the boss NPC rewards as locations (Iris-Dev#43)."""

import tempfile
from collections import namedtuple
from unittest import mock

from BaseClasses import CollectionState, ItemClassification

from .. import data_open_world
from ..client import flagged_locations, given_in_game
from ..items import BASE_ID, CAPSULE_BASE, CHARACTER_BASE, MAIDENS, MAXIM, OPEN_WORLD_SPECIALS, SPECIAL_ITEM_NAMES
from ..locations import BOSS_BASE, BOSS_FLAGS, BOSS_REWARDS
from ..logic import OPEN_DAOS_EVENT, area_of_map
from ..rom import L2OWProcedurePatch
from . import L2OWTestBase


NetworkItem = namedtuple("NetworkItem", "item location player flags")


class TestBossRewardData(L2OWTestBase):
    options = {"open_world": True}

    def test_fifty_rewards(self) -> None:
        spots = data_open_world.BOSS_NPCS[:-1]  # Daos last, no reward
        self.assertEqual(len(BOSS_REWARDS), 48)  # 26 spots give one, the 11 big dungeons two
        self.assertEqual(len(BOSS_REWARDS), sum(len(row[7]) for row in spots))
        self.assertEqual(data_open_world.BOSS_NPCS[-1][7], ())
        self.assertEqual(len({reward.name for reward in BOSS_REWARDS}), 48)
        self.assertEqual(min(reward.code for reward in BOSS_REWARDS), BOSS_BASE)
        self.assertIn("Skill Cave Boss", {reward.name for reward in BOSS_REWARDS})
        self.assertIn("Tanbel Tower Boss 2", {reward.name for reward in BOSS_REWARDS})

    def test_two_rewards_one_flag(self) -> None:
        spot, _, flag, *_ = next(row for row in data_open_world.BOSS_NPCS if len(row[7]) == 2)
        title = spot.replace("_", " ").title()
        codes = {reward.code for reward in BOSS_REWARDS if reward.name.startswith(f"{title} Boss")}
        self.assertEqual(len(codes), 2)
        flags = bytearray(32)
        flags[flag >> 3] |= 1 << (flag & 7)
        self.assertEqual(set(flagged_locations(bytes(flags))) & set(BOSS_FLAGS), codes)
        self.assertEqual(flagged_locations(bytes(32)), [])


class TestOpenWorldItemsAndRewards(L2OWTestBase):
    options = {"open_world": True}

    def test_reward_locations_in_their_areas(self) -> None:
        for reward in BOSS_REWARDS:
            location = self.multiworld.get_location(reward.name, self.player)
            self.assertEqual(location.address, reward.code)
            self.assertEqual(location.parent_region.name, area_of_map(reward.map_index).name)

    def test_specials_in_pool(self) -> None:
        names = [item.name for item in self.multiworld.itempool]
        for index in OPEN_WORLD_SPECIALS:
            self.assertEqual(names.count(SPECIAL_ITEM_NAMES[index]), 1, SPECIAL_ITEM_NAMES[index])
        self.assertNotIn(SPECIAL_ITEM_NAMES[MAXIM], names)
        self.assertEqual(len(OPEN_WORLD_SPECIALS), 16)
        for item in self.multiworld.itempool:
            index = item.code - BASE_ID
            if index in SPECIAL_ITEM_NAMES:
                capsule = CAPSULE_BASE <= index < CAPSULE_BASE + 0x10
                expected = ItemClassification.useful if capsule else ItemClassification.progression
                self.assertEqual(item.classification, expected, item.name)

    def test_pool_fits_locations(self) -> None:
        empty = [loc for loc in self.multiworld.get_locations(self.player) if loc.item is None]
        self.assertEqual(len(self.multiworld.itempool), len(empty))

    def test_daos_needs_the_maidens(self) -> None:
        daos = self.multiworld.get_location(OPEN_DAOS_EVENT, self.player)
        state = CollectionState(self.multiworld)
        for name in ("Progressive Ship",) * 3:
            state.collect(self.world.create_item(name), prevent_sweep=True)
        self.assertTrue(daos.parent_region.can_reach(state))
        for maiden in MAIDENS:
            self.assertFalse(daos.can_reach(state))
            state.collect(self.world.create_item(maiden), prevent_sweep=True)
        self.assertTrue(daos.can_reach(state))

    def test_tokens_write_boss_rewards(self) -> None:
        """Each reward's grant gets its item: an own game item as itself, a character (or another world's item) as the
        AP item."""
        rewards = [self.multiworld.get_location(reward.name, self.player) for reward in BOSS_REWARDS]
        potion, selan = self.world.create_item("Potion"), self.world.create_item("Selan")
        rewards[0].item, rewards[1].item = potion, selan
        written: list[tuple[int, int]] = []
        with mock.patch.object(L2OWProcedurePatch, "write_grant", lambda _, offset, index: written.append((offset, index))):
            with tempfile.TemporaryDirectory() as directory:
                self.world.generate_output(directory)
        offsets = {reward.code: reward.offset for reward in BOSS_REWARDS}
        self.assertIn((offsets[rewards[0].address], potion.code - BASE_ID), written)
        self.assertIn((offsets[rewards[1].address], data_open_world.AP_ITEM_INDEX), written)


class TestClientDelivery(L2OWTestBase):
    options = {"open_world": True}

    def test_given_in_game(self) -> None:
        slot, potion, selan = 1, BASE_ID + 2, BASE_ID + CHARACTER_BASE + 1
        self.assertTrue(given_in_game(NetworkItem(potion, BASE_ID + 5, slot, 0), slot))  # own chest gave it
        self.assertFalse(given_in_game(NetworkItem(selan, BOSS_BASE, slot, 0), slot))  # specials always come
        self.assertFalse(given_in_game(NetworkItem(potion, BASE_ID + 5, 2, 0), slot))  # another world's location
        self.assertFalse(given_in_game(NetworkItem(potion, -2, slot, 0), slot))  # starting inventory
