"""Open world's region map against the linear one (Iris-Dev#43). Runs in an Archipelago checkout (WorldTestBase)."""

from BaseClasses import CollectionState
from Options import OptionError

from ..locations import BOSS_BASE, GRANT_BASE
from ..logic import OPEN_AREAS, STAGES
from ..options import Placement, ShipUpgrades
from . import L2OWTestBase


class OpenWorldBase(L2OWTestBase):
    options = {"open_world": True}

    def reach(self, region: str, *items: str) -> bool:
        """Whether ``region`` is reachable holding only ``items`` (a name may repeat for a count)."""
        state = CollectionState(self.multiworld)
        for name in items:
            state.collect(self.world.create_item(name), prevent_sweep=True)
        return state.can_reach_region(region, self.player)


class TestLinear(L2OWTestBase):
    options = {"open_world": False}

    def test_stage_regions(self) -> None:
        names = {region.name for region in self.multiworld.get_regions(self.player)}
        self.assertEqual(names, {"Menu"} | {stage.name for stage in STAGES})


class TestOpenWorldProgressive(OpenWorldBase):
    def test_area_regions(self) -> None:
        names = {region.name for region in self.multiworld.get_regions(self.player)}
        self.assertEqual(names, {"Menu"} | {area.name for area in OPEN_AREAS})

    def test_no_grant_locations(self) -> None:
        grants = [
            loc for loc in self.multiworld.get_locations(self.player) if GRANT_BASE <= (loc.address or 0) < BOSS_BASE
        ]
        self.assertEqual(grants, [])

    def test_travel(self) -> None:
        ship = "Progressive Ship"
        self.assertTrue(self.reach("Elcid to Aleyn"))
        self.assertFalse(self.reach("Sea"))
        self.assertTrue(self.reach("Sea", ship))
        self.assertFalse(self.reach("Seafloor", ship))
        self.assertTrue(self.reach("Seafloor", ship, ship))
        self.assertTrue(self.reach("Chaed and Dragon Mountain", ship, ship))
        self.assertFalse(self.reach("Sky", ship, ship))
        self.assertTrue(self.reach("Sky", ship, ship, ship))
        self.assertTrue(self.reach("Shrine of Daos", ship, ship, ship))

    def test_gratze_through_dankirk(self) -> None:
        self.assertFalse(self.reach("Gratze", "Progressive Ship"))
        self.assertTrue(self.reach("Gratze", "Progressive Ship", "Bomb", "Hook", "Dankirk key"))

    def test_pool_fits_locations(self) -> None:
        empty = [loc for loc in self.multiworld.get_locations(self.player) if loc.item is None]
        self.assertEqual(len(self.multiworld.itempool), len(empty))


class TestOpenWorldSeparate(OpenWorldBase):
    options = {"open_world": True, "ship_upgrades": "separate"}

    def test_travel(self) -> None:
        self.assertFalse(self.reach("Sea", "Submarine", "Engine"))
        self.assertTrue(self.reach("Sea", "Ship"))
        self.assertFalse(self.reach("Seafloor", "Ship", "Engine"))
        self.assertTrue(self.reach("Seafloor", "Ship", "Submarine"))
        self.assertTrue(self.reach("Chaed and Dragon Mountain", "Ship", "Engine"))
        self.assertTrue(self.reach("Sky", "Ship", "Engine"))
        self.assertFalse(self.reach("Shrine of Daos", "Ship", "Engine"))
        self.assertTrue(self.reach("Shrine of Daos", "Ship", "Engine", "Submarine"))


class TestOpenWorldVanillaShipsAndOwnStage(OpenWorldBase):
    options = {"open_world": True, "ship_upgrades": "vanilla", "key_placement": "own_stage", "tool_placement": "own_stage"}

    def test_options_mapped(self) -> None:
        self.assertEqual(self.world.options.ship_upgrades.value, ShipUpgrades.option_progressive)
        self.assertEqual(self.world.options.key_placement.value, Placement.option_own_world)
        self.assertEqual(self.world.options.tool_placement.value, Placement.option_own_world)
        self.assertIn("Hook", self.world.options.local_items.value)
        self.assertEqual(len(self.get_items_by_name("Progressive Ship")), 3)


class TestOpenWorldEggs(OpenWorldBase):
    options = {"open_world": True, "goal": "dragon_eggs", "egg_wishes": 2}

    def test_all_eggs_in_this_world(self) -> None:
        eggs = [item for item in self.multiworld.get_items() if item.name == "Dragon egg"]
        self.assertEqual(len(eggs), 16)  # no Merix egg in open world


class TestOpenWorldStoryGoal(L2OWTestBase):
    options = {"open_world": True, "goal": "chaed"}
    auto_construct = False

    def test_rejected(self) -> None:
        with self.assertRaises(OptionError):
            self.world_setup()
