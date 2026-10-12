"""Open world's Leader, Cave Bridge Orb, Escapable Dungeons and Extra NPCs options and their tokens (Iris-Dev#43)."""

import tempfile
from unittest import mock

from .. import data, data_open_world
from ..items import BASE_ID, CHARACTER_BASE, CHARACTERS, ITEM_NAMES
from ..locations import BOSS_BASE, GRANT_BASE, ORB_CHECK, ORB_FLAGS, location_name_to_id
from ..logic import EXCLUDED_GRANTS
from ..rom import L2OWProcedurePatch
from . import L2OWTestBase


ALL_NPCS = ["secondary_tool_tip", "capsule_tips", "tanbel_inn", "egg_key_trader", "egg_wishes"]


def runs(*groups: tuple[tuple[int, str], ...]) -> list[tuple[int, bytes]]:
    return [(offset, bytes.fromhex(hex_bytes)) for group in groups for offset, hex_bytes in group]


class VariantTest(L2OWTestBase):
    def writes(self) -> list[tuple[int, bytes]]:
        """Every WRITE token generate_output makes for this player, in order."""
        written: list[tuple[int, bytes]] = []
        original = L2OWProcedurePatch.write_token

        def record(patch: L2OWProcedurePatch, kind: object, offset: int, value: bytes) -> None:
            written.append((offset, bytes(value)))
            original(patch, kind, offset, value)

        with mock.patch.object(L2OWProcedurePatch, "write_token", record), tempfile.TemporaryDirectory() as directory:
            self.world.generate_output(directory)
        return written

    def pool_names(self) -> list[str]:
        return [item.name for item in self.multiworld.itempool if item.player == self.player]

    def test_pool_fits_locations(self) -> None:
        empty = [loc for loc in self.multiworld.get_locations(self.player) if loc.item is None]
        self.assertEqual(len(self.multiworld.itempool), len(empty))


class TestDefaults(VariantTest):
    options = {"open_world": True}

    def test_no_variant_tokens(self) -> None:
        self.assertEqual((self.world.extras, self.world.leader), ((), "maxim"))
        variant_offsets = {offset for group in data_open_world.EXTRA_DIFFS.values() for offset, _ in group}
        variant_offsets |= {offset for group in data_open_world.LEADER_DIFFS.values() for offset, _ in group}
        self.assertFalse(variant_offsets & {offset for offset, _ in self.writes()})

    def test_maxim_not_in_pool(self) -> None:
        names = self.pool_names()
        self.assertNotIn("Maxim", names)
        self.assertTrue(all(name in names for name in CHARACTERS[1:]))

    def test_no_orb_location(self) -> None:
        self.assertNotIn(ORB_CHECK.name, {loc.name for loc in self.multiworld.get_locations(self.player)})


class TestLinearIgnoresThem(VariantTest):
    options = {"leader": "guy", "cave_bridge_orb": "orb_check", "escapable_dungeons": True, "extra_npcs": ALL_NPCS}

    def test_nothing_changes(self) -> None:
        self.assertEqual((self.world.extras, self.world.leader), ((), "maxim"))
        self.assertNotIn(ORB_CHECK.name, {loc.name for loc in self.multiworld.get_locations(self.player)})
        self.assertNotIn("Maxim", self.pool_names())


class LeaderChecks:
    """Mixed into one TestCase per leader (not a TestCase itself, so it doesn't run alone)."""

    leader: str

    def test_leader_tokens_come_first(self) -> None:
        expected = runs(data_open_world.LEADER_DIFFS[self.leader])
        self.assertEqual(self.writes()[: len(expected)], expected)

    def test_pool_has_maxim_not_the_leader(self) -> None:
        names = self.pool_names()
        self.assertIn("Maxim", names)
        self.assertNotIn(ITEM_NAMES[CHARACTER_BASE + data_open_world.LEADERS[self.leader]], names)
        self.assertEqual(sum(name in CHARACTERS for name in names), len(CHARACTERS) - 1)


def _leader_test(name: str) -> type[VariantTest]:
    attributes = {"options": {"open_world": True, "leader": name}, "leader": name}
    return type(f"TestLeader{name.title()}", (LeaderChecks, VariantTest), attributes)


TestLeaderSelan, TestLeaderGuy, TestLeaderArtea, TestLeaderTia, TestLeaderDekar, TestLeaderLexis = (
    _leader_test(name) for name in data_open_world.LEADERS
)


class TestEverything(VariantTest):
    options = {
        "open_world": True, "leader": "lexis", "cave_bridge_orb": "orb_check", "escapable_dungeons": True,
        "extra_npcs": ALL_NPCS,
    }

    def test_extras(self) -> None:
        self.assertEqual(self.world.extras, tuple(e for e in data_open_world.EXTRAS if e != "npc_cave_bridge_orb_guard"))

    def test_tokens_in_order(self) -> None:
        extras = self.world.extras
        expected = runs(
            *(data_open_world.EXTRA_DIFFS[extra] for extra in extras),
            data_open_world.LEADER_DIFFS["lexis"],
            *(data_open_world.LEADER_EXTRA_DIFFS[("lexis", extra)] for extra in extras
              if ("lexis", extra) in data_open_world.LEADER_EXTRA_DIFFS),
        )
        self.assertTrue(any(key[1] in extras for key in data_open_world.LEADER_EXTRA_DIFFS))
        self.assertEqual(self.writes()[: len(expected)], expected)

    def test_orb_location(self) -> None:
        location = self.multiworld.get_location(ORB_CHECK.name, self.player)
        self.assertEqual(location.address, ORB_CHECK.code)
        self.assertEqual(location_name_to_id[ORB_CHECK.name], ORB_CHECK.code)
        self.assertEqual(ORB_FLAGS[ORB_CHECK.code], 0x30)
        self.assertEqual(self.world.grant_offsets[ORB_CHECK.code], data_open_world.ORB_CHECK[1])

    def test_orb_grant_token(self) -> None:
        """The orb's grant gets the item placed there, after the variants that put the grant in."""
        location = self.multiworld.get_location(ORB_CHECK.name, self.player)
        location.item = self.world.create_item("Potion")
        offset = data_open_world.ORB_CHECK[1]
        writes = self.writes()
        self.assertIn((offset - 1, bytes([0x20, location.item.code - BASE_ID])), writes)
        orb_runs = runs(data_open_world.EXTRA_DIFFS["orb_check"])
        self.assertLess(writes.index(orb_runs[-1]), writes.index((offset - 1, bytes([0x20, location.item.code - BASE_ID]))))

    def test_used_offsets_outside_the_variants(self) -> None:
        """The tokens written after the variants (grants, hints, boss rewards) don't land in a variant's bytes."""
        changed = set()
        for extra in self.world.extras:
            changed |= {o + n for o, h in data_open_world.EXTRA_DIFFS[extra] for n in range(len(h) // 2)}
        changed |= {o + n for o, h in data_open_world.LEADER_DIFFS["lexis"] for n in range(len(h) // 2)}
        used = set(self.world.grant_offsets.values()) | set(self.world.boss_offsets.values())
        used.discard(data_open_world.ORB_CHECK[1])  # orb_check's own grant: its item is written on purpose
        used |= {offset + n for _, _, offset, size in data_open_world.HINT_NPCS for n in range(size)}
        self.assertFalse(used & changed)


class TestGuard(VariantTest):
    options = {"open_world": True, "cave_bridge_orb": "guard"}

    def test_guard_only(self) -> None:
        self.assertEqual(self.world.extras, ("npc_cave_bridge_orb_guard",))
        self.assertNotIn(ORB_CHECK.name, {loc.name for loc in self.multiworld.get_locations(self.player)})


class TestToolTipMovesTheSkillCaveBoss(VariantTest):
    options = {"open_world": True, "extra_npcs": ["secondary_tool_tip"], "boss_placement": "shuffled"}

    def test_boss_row_and_rewards(self) -> None:
        moved = data_open_world.EXTRA_BOSS_NPCS["npc_secondary_tool_tip"]
        self.assertTrue(moved)
        writes = dict(self.writes())
        for row, npc in moved.items():
            self.assertEqual(self.world.boss_rows[row], npc)
            self.assertIn(npc[4], writes)  # the shuffled boss's sprite goes where the boss is with the tip on
            for n, offset in enumerate(npc[7]):
                self.assertEqual(self.world.boss_offsets[BOSS_BASE + 2 * row + n], offset)


class TestEggWishesDropsItsGrants(VariantTest):
    options = {"open_world": True, "extra_npcs": ["egg_wishes"]}

    def test_no_wish_grant(self) -> None:
        replaced = data_open_world.EXTRA_REPLACED_SCRIPTS["npc_egg_wishes"]
        self.assertIn("9F-B-50", replaced)
        self.assertIn("9F-B-50", EXCLUDED_GRANTS)  # not locations anyway
        for code in self.world.grant_offsets:
            if code >= GRANT_BASE and code - GRANT_BASE < len(data.GRANTS):
                self.assertNotIn(data.GRANTS[code - GRANT_BASE][1], replaced)


class TestEggGoalDropsTheTrader(VariantTest):
    options = {"open_world": True, "goal": "dragon_eggs", "extra_npcs": ["egg_key_trader", "tanbel_inn"]}

    def test_trader_left_out(self) -> None:
        self.assertEqual(self.world.extras, ("npc_tanbel_inn",))
