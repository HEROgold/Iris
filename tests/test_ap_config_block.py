"""Layout checks for the Archipelago config block reservation (docs/ap/config_block.md)."""

import constants
from constants import AP_CONFIG_REGION, RESERVED_REGIONS
from helpers.rom_expansion import assert_no_overlaps


def _option_fields() -> list[tuple[str, int, int]]:
    c = constants
    return [
        ("goal", c.AP_OPT_GOAL, 1),
        ("goal_param", c.AP_OPT_GOAL_PARAM, 1),
        ("mermaid_jade", c.AP_OPT_START_MERMAID_JADE, 1),
        ("engine", c.AP_OPT_START_ENGINE, 1),
        ("scaling_enabled", c.AP_OPT_SCALING_ENABLED, 1),
        ("scaling_low", c.AP_OPT_SCALING_LOW, 1),
        ("scaling_range", c.AP_OPT_SCALING_RANGE, 1),
        ("scenario_item_mode", c.AP_OPT_SCENARIO_ITEM_MODE, 1),
        ("blue_chests_enabled", c.AP_OPT_BLUE_CHESTS_ENABLED, 1),
        ("blue_chest_count", c.AP_OPT_BLUE_CHEST_COUNT, 2),
        ("death_link", c.AP_OPT_DEATH_LINK, 1),
        ("opt_reserved", c.AP_OPT_RESERVED, c.AP_OPTIONS_OFFSET + c.AP_OPTIONS_SIZE - c.AP_OPT_RESERVED),
    ]


def _fields() -> list[tuple[str, int, int]]:
    c = constants
    return [
        ("magic", c.AP_CONFIG_MAGIC_OFFSET, c.AP_CONFIG_MAGIC_SIZE),
        ("version", c.AP_CONFIG_VERSION_OFFSET, c.AP_CONFIG_VERSION_SIZE),
        ("auth", c.AP_CONFIG_AUTH_OFFSET, c.AP_CONFIG_AUTH_SIZE),
        *_option_fields(),
        ("hint_header", c.AP_HINT_HEADER_OFFSET, c.AP_HINT_HEADER_SIZE),
        ("hint_arena", c.AP_HINT_ARENA_OFFSET, c.AP_HINT_ARENA_END - c.AP_HINT_ARENA_OFFSET),
    ]


def test_region_is_in_expansion_and_bank_aligned() -> None:
    assert AP_CONFIG_REGION.start >= 0x300000
    assert AP_CONFIG_REGION.stop <= 0x400000
    assert AP_CONFIG_REGION.start & 0x7FFF == 0
    assert len(AP_CONFIG_REGION) == 0x8000


def test_fields_are_inside_region_and_disjoint() -> None:
    fields = sorted(_fields(), key=lambda f: f[1])
    for name, off, size in fields:
        assert off in AP_CONFIG_REGION, name
        assert off + size <= AP_CONFIG_REGION.stop, name
    for (an, ao, asz), (bn, bo, _) in zip(fields, fields[1:], strict=False):
        assert ao + asz <= bo, f"{an} overlaps {bn}"


def test_option_fields_fit_the_64_byte_option_area() -> None:
    c = constants
    assert c.AP_OPTIONS_SIZE == 64
    for name, off, size in _option_fields():
        assert c.AP_OPTIONS_OFFSET <= off, name
        assert off + size <= c.AP_OPTIONS_OFFSET + c.AP_OPTIONS_SIZE, name


def test_header_fields() -> None:
    assert constants.AP_CONFIG_MAGIC == b"IRISAP"
    assert len(constants.AP_CONFIG_MAGIC) == constants.AP_CONFIG_MAGIC_SIZE
    assert 0 < constants.AP_CONFIG_VERSION < 256


def test_no_overlap_with_other_reservations() -> None:
    assert AP_CONFIG_REGION in RESERVED_REGIONS
    assert_no_overlaps(RESERVED_REGIONS)
    for other in RESERVED_REGIONS:
        if other is not AP_CONFIG_REGION:
            assert other.stop <= AP_CONFIG_REGION.start or AP_CONFIG_REGION.stop <= other.start
