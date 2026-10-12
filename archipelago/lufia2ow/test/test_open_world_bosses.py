"""Open world's Boss Placement and Boss Strength options and their tokens (Iris-Dev#43)."""

import random
import tempfile
from collections import Counter
from unittest import TestCase, mock

from .. import bosses, data_open_world
from ..rom import L2OWProcedurePatch
from . import L2OWTestBase


STRENGTH = data_open_world.CONFIG["AP_OPT_BOSS_STRENGTH"]
LEVELS = data_open_world.CONFIG["AP_OPT_BOSS_LEVELS"]
LEVELS_SIZE = data_open_world.CONFIG["AP_OPT_BOSS_LEVELS_SIZE"]
SPOT_ROWS = data_open_world.BOSS_NPCS[:-1]  # Daos last


class TokenTest(L2OWTestBase):
    def tokens(self) -> dict[int, bytes]:
        """offset -> bytes of every WRITE token generate_output makes for this player."""
        written: dict[int, bytes] = {}
        original = L2OWProcedurePatch.write_token

        def record(patch: L2OWProcedurePatch, kind: object, offset: int, value: bytes) -> None:
            written[offset] = bytes(value)
            original(patch, kind, offset, value)

        with mock.patch.object(L2OWProcedurePatch, "write_token", record), tempfile.TemporaryDirectory() as directory:
            self.world.generate_output(directory)
        return written

    def placement_bytes(self, tokens: dict[int, bytes]) -> list[tuple[int, int, int] | None]:
        """(sprite, formation, bgm) written at each spot, or None where nothing was written."""
        out = []
        for row in SPOT_ROWS:
            sprite, bgm, formation = row[4], row[5], row[6]
            if sprite in tokens or bgm in tokens or formation in tokens:
                out.append((tokens[sprite][0], tokens[formation][0], tokens[bgm][0]))
            else:
                out.append(None)
        return out


class TestDefaults(TokenTest):
    options = {"open_world": True}

    def test_unchanged_fixed(self) -> None:
        tokens = self.tokens()
        self.assertEqual(tokens[STRENGTH], b"\0")
        self.assertNotIn(LEVELS, tokens)
        self.assertEqual(self.placement_bytes(tokens), [None] * len(SPOT_ROWS))  # the base patch has the fixed bosses
        self.assertEqual(self.world.boss_placement, bosses.fixed_placement())


class TestPartyLevel(TokenTest):
    options = {"open_world": True, "boss_strength": "party_level"}

    def test_mode_byte(self) -> None:
        tokens = self.tokens()
        self.assertEqual(tokens[STRENGTH], b"\x01")
        self.assertNotIn(LEVELS, tokens)


class TestByDepthFixed(TokenTest):
    options = {"open_world": True, "boss_strength": "by_depth"}

    def test_each_formation_gets_its_own_power(self) -> None:
        tokens = self.tokens()
        self.assertEqual(tokens[STRENGTH], b"\x02")
        levels = tokens[LEVELS]
        self.assertEqual(len(levels), LEVELS_SIZE)
        for _, _, formation, _, power in data_open_world.BOSSES:
            self.assertEqual(levels[formation], power)
        placed = {boss[2] for boss in data_open_world.BOSSES}
        self.assertTrue(all(level == 0 for formation, level in enumerate(levels) if formation not in placed))
        self.assertEqual(levels[data_open_world.DAOS[2]], 0)


class TestShuffledByDepth(TokenTest):
    options = {"open_world": True, "boss_placement": "shuffled", "boss_strength": "by_depth"}

    def test_placement_tokens(self) -> None:
        tokens = self.tokens()
        placement = self.world.boss_placement
        self.assertEqual(self.placement_bytes(tokens), [(boss[1], boss[2], boss[3]) for boss in placement])
        daos = data_open_world.BOSS_NPCS[-1]
        self.assertTrue(all(offset not in tokens for offset in daos[4:7]))

    def test_levels_follow_the_spots(self) -> None:
        levels = self.tokens()[LEVELS]
        story = bosses.fixed_placement()
        for boss in set(self.world.boss_placement):
            powers = [story[spot][4] for spot, placed in enumerate(self.world.boss_placement) if placed == boss]
            self.assertEqual(levels[boss[2]], max(1, min(99, round(sum(powers) / len(powers)))))

    def test_spoiler_lists_the_bosses(self) -> None:
        lines: list[str] = []

        class Handle:
            def write(self, text: str) -> None:
                lines.append(text)

        self.world.write_spoiler(Handle())  # type: ignore[arg-type]
        text = "".join(lines)
        self.assertIn("Boss placement", text)
        self.assertIn(f"{data_open_world.FINAL_SPOT[0]}: daos", text)
        for (spot, _, _), boss in zip(data_open_world.BOSS_SPOTS, self.world.boss_placement, strict=True):
            self.assertIn(f"{spot}: {boss[0]}", text)


class TestLinearIgnoresBossOptions(TokenTest):
    options = {"boss_placement": "shuffled", "boss_strength": "by_depth"}

    def test_no_boss_tokens(self) -> None:
        tokens = self.tokens()
        self.assertNotIn(STRENGTH, tokens)
        self.assertNotIn(LEVELS, tokens)
        self.assertEqual(self.world.boss_placement, [])


class TestShuffledPlacement(TestCase):
    def test_every_boss_present_with_repeats(self) -> None:
        for seed in range(50):
            placement = bosses.shuffled_placement(random.Random(seed))
            self.assertEqual(len(placement), len(data_open_world.BOSS_SPOTS))
            counts = Counter(placement)
            self.assertEqual(set(counts), set(data_open_world.BOSSES))
            self.assertEqual(sum(count - 1 for count in counts.values()), len(placement) - len(data_open_world.BOSSES))
            self.assertNotIn(data_open_world.DAOS, counts)

    def test_fixed_matches_story_order(self) -> None:
        placement = bosses.fixed_placement()
        self.assertEqual(placement[0], data_open_world.BOSSES[0])
        self.assertEqual(placement[-1], data_open_world.BOSSES[-1])
        self.assertEqual(set(placement), set(data_open_world.BOSSES))
