"""Every red chest has a unique, non-empty human-readable location name."""

from iris.structures.chest_location import ChestLocation
from iris.structures.chest_names import CHEST_NAMES


def test_every_chest_has_a_name() -> None:
    indices = {location.chest_index for location in ChestLocation.all()}
    assert len(indices) == 171
    assert set(CHEST_NAMES) == indices


def test_names_are_non_empty() -> None:
    assert all(name.strip() for name in CHEST_NAMES.values())


def test_names_are_unique() -> None:
    assert len(set(CHEST_NAMES.values())) == len(CHEST_NAMES)
