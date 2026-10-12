from iris.enums.patches import Patch


PROJECT_NAME = "Iris"
VERSION = "0.1"
AUTHORS = [{"name":"HEROgold", "email":""}]
DESCRIPTION = "A Lufia II: Rise of the Sinistrals randomizer/patching toolkit."

POINTER_SIZE = 2


# --- Reserved ROM-expansion space (see helpers.rom_expansion) -----------------------------------
# The base cart is a full 3MB (0x300000) with only ~1.2KB of blank space in the entire file
# (verified: a full-file scan for runs of 0x00/0xFF >= 1KB finds exactly one, 0x0f8d3e-0x0f9220 --
# see docs/encounter_scaling.md). `EMPTY_BYTES` below does NOT describe this ROM (its first range
# starts at 0x286a10, which holds real game data) and must never be used as an allocation source.
#
# The only bytes provably safe to write into are ones that don't exist yet: LoROM can address up to
# 4MB, so expanding the ROM file to that ceiling yields a clean, genuinely blank megabyte at
# 0x300000-0x3FFFFF. Every dedicated-space reservation below lives in that expansion area, is
# appended to RESERVED_REGIONS so `helpers.rom_expansion.assert_no_overlaps` can catch a colliding
# reservation, and is written only via an explicit seek+write (or `org` in asm) -- never `freecode`,
# whose freespace scanner has never heard of these reservations.
EXPANDED_ROM_SIZE = 0x400000
"""The full 4MB a LoROM map can address; every region below is carved out of the megabyte this
gains over the unexpanded 3MB cart."""

# --- Reserved space: --scale-encounters (patches/HEROgold/scale_encounters) ---------------------
# 1KB at headerless 0x310000 (SNES $E2:8000) holds the level -> formation table, the roll constants
# and the asar hook body.
SCALE_ENCOUNTERS_REGION = range(0x310000, 0x310400)
SCALE_ENCOUNTERS_ROM_SIZE = EXPANDED_ROM_SIZE
"""Kept as its own name since scale_encounters.py already imports it; same value as EXPANDED_ROM_SIZE."""
SCALE_ENCOUNTERS_TABLE = 0x310000
"""99 bytes: for each party level 1..99, the formation id that best matches it."""
SCALE_ENCOUNTERS_TABLE_SIZE = 99
SCALE_ENCOUNTERS_LOW = 0x310063
"""1 byte, two's complement: the low end of the offset band added to the party average level."""
SCALE_ENCOUNTERS_RANGE = 0x310064
"""1 byte: how many distinct offsets the band spans (high - low + 1)."""
SCALE_ENCOUNTERS_CODE = 0x310065
"""Start of the asar-assembled hook body (SNES $E2:8065)."""
SCALE_ENCOUNTERS_MAX_OFFSET = 98
"""Widest usable end of the offset band. The resulting target level is clamped to 1..99 anyway, so
a larger offset could never change the outcome -- rejecting it stops a typo doing nothing quietly."""
SCALE_ENCOUNTERS_MAX_BAND = 0xFF
"""The band size is baked as one byte, so it cannot span more than 255 distinct offsets."""


# --- Reserved space: ZoneData relocation freespace ----------------------------------------------
# The arena for the shared ZoneData FreeSpaceAllocator (helpers.freespace): 128KB, bank-aligned, well clear of
# SCALE_ENCOUNTERS_REGION. structures.zone.move_all_zone_data moves every map's ZoneData (111KB) here. Event containers
# have no arena out here: they must stay in banks $80-$BF (HER-232) and grow into the space ZoneData leaves behind.
ZONE_DATA_FREESPACE = range(0x320000, 0x340000)

# --- Reserved space: asar patch code --------------------------------------------------------------
# Code an asar patch adds (not just hooks over vanilla code) goes here with `org !code` (patcher.apply_asm_patch's
# code_region), never `freecode`: asar's freespace finder takes the first run of $00 it sees, and in vanilla those runs
# are blank tiles. Bank $9F from $8000 is DMA'd raw into VRAM, so code at $9F:84FF / $9F:8D3E showed up as garbled item
# icons and battle tiles. One slot per patch in bank $E8 (headerless 0x340000); each patch's `warnpc !code_end` keeps it
# inside its slot.
RX_CODE_REGION = range(0x340000, 0x340800)
"""rx.asm with rx_specials.asm and key_items.asm (about 0.75KB)."""
NEW_GAME_CODE_REGION = range(0x340800, 0x340C00)
"""new_game.asm, including its start-item table."""
START_CAPSULE_CODE_REGION = range(0x340C00, 0x340E00)
"""start_capsule.asm."""
SCALE_BOSSES_CODE_REGION = range(0x340E00, 0x341800)
"""open_world/scale_bosses.asm (about 0.6KB)."""

# --- Reserved space: RealCritical fix_cave_chest_table --------------------------------------------
# 71-byte hook body at headerless 0x30D820 (SNES $E1:D820); the patched code at 0x19176 jumps to $E1:D84A.
CAVE_CHEST_FIX_REGION = range(0x30D820, 0x30D867)

# --- Reserved space: Archipelago config block (docs/ap/config_block.md) --------------------------
# One bank-aligned 32KB bank at headerless 0x360000 (SNES $EC:8000). Read by the Archipelago SNI
# client and by our asm; filled per seed by Archipelago tokens (offset + bytes) over a static base
# patch, so every field has a fixed offset. Bump AP_CONFIG_VERSION whenever the layout changes.
AP_CONFIG_REGION = range(0x360000, 0x368000)
AP_CONFIG_VERSION = 2
"""Layout version stored in the byte at AP_CONFIG_VERSION_OFFSET."""
AP_CONFIG_MAGIC = b"IRISAP"
AP_CONFIG_MAGIC_OFFSET = 0x360000
AP_CONFIG_MAGIC_SIZE = 6
AP_CONFIG_VERSION_OFFSET = 0x360006
"""1 byte: the layout version (AP_CONFIG_VERSION)."""
AP_CONFIG_VERSION_SIZE = 1
AP_CONFIG_AUTH_OFFSET = 0x360008
"""32 bytes: the seed/slot name the client authenticates with, zero-padded ASCII/UTF-8."""
AP_CONFIG_AUTH_SIZE = 32

AP_OPTIONS_OFFSET = 0x360040
AP_OPTIONS_SIZE = 64
"""Fixed 64-byte option area; unused bytes at the end are reserved (zero)."""
AP_OPT_GOAL = 0x360040
"""1 byte: goal id."""
AP_OPT_GOAL_PARAM = 0x360041
"""1 byte: goal parameter, e.g. Iris treasures required."""
AP_OPT_START_MERMAID_JADE = 0x360042
"""1 byte (0/1): start with Mermaid Jade."""
AP_OPT_START_ENGINE = 0x360043
"""1 byte (0/1): start with the Engine."""
AP_OPT_SCALING_ENABLED = 0x360044
"""1 byte (0/1): encounter scaling enabled."""
AP_OPT_SCALING_LOW = 0x360045
"""1 byte, two's complement: scaling band low end (same semantics as SCALE_ENCOUNTERS_LOW)."""
AP_OPT_SCALING_RANGE = 0x360046
"""1 byte: scaling band size (same semantics as SCALE_ENCOUNTERS_RANGE)."""
AP_OPT_SCENARIO_ITEM_MODE = 0x360047
"""1 byte: scenario-item removal mode."""
AP_OPT_BLUE_CHESTS_ENABLED = 0x360048
"""1 byte (0/1): Ancient Cave blue chests are checks."""
AP_OPT_BLUE_CHEST_COUNT = 0x360049
"""2 bytes, little-endian: number of blue chest checks N."""
AP_OPT_DEATH_LINK = 0x36004B
"""1 byte (0/1): death link."""
AP_OPT_BOSS_STRENGTH = 0x36004C
"""1 byte: how scripted (boss) battles scale (open world, scale_bosses.asm): 0 not, 1 to the party's average level,
2 to AP_OPT_BOSS_LEVELS."""
AP_OPT_BOSS_LEVELS = 0x36004D
"""39 bytes: per boss formation, the level its monsters are scaled to in mode 2 (0 = unchanged)."""
AP_OPT_BOSS_LEVELS_SIZE = 39
AP_OPT_RESERVED = 0x360074
"""Reserved option bytes up to the end of the 64-byte option area."""

AP_HINT_HEADER_OFFSET = 0x360080
AP_HINT_HEADER_SIZE = 16
"""Hint table header: u16 hint count, u16 arena bytes used, 12 reserved bytes."""
AP_HINT_ARENA_OFFSET = 0x360090
AP_HINT_ARENA_END = 0x368000
"""Reserved hint text arena: AP_HINT_ARENA_OFFSET up to the end of AP_CONFIG_REGION."""

RESERVED_REGIONS = [
    SCALE_ENCOUNTERS_REGION,
    ZONE_DATA_FREESPACE,
    CAVE_CHEST_FIX_REGION,
    AP_CONFIG_REGION,
    RX_CODE_REGION,
    NEW_GAME_CODE_REGION,
    START_CAPSULE_CODE_REGION,
    SCALE_BOSSES_CODE_REGION,
]
"""Every fixed ROM-expansion reservation, checked for overlaps by helpers.rom_expansion.assert_no_overlaps."""


# NOTE: does NOT describe this ROM -- see the reserved-space block above. EMPTY_BYTES[0] starts at
# 0x286a10, which holds real game data (structures.zone/ZoneData.write_relocated and
# structures.event_script.allocator.FreeSpaceAllocator still draw from this and are corrupting
# consumers pending migration to helpers.freespace; see docs/encounter_scaling.md).
EMPTY_BYTES = [
    range(0x286a10, 0x30d80e),
    range(0x30d87b, 0x3e4038),
    range(0x3e700d, 0x3e7ffc),
    range(0x3ec8d6, 0x3ee0ff),
    range(0x3eed0b, 0x3fffff),
]


ASCII_ART = r"""
_________ _______ _________ _______
\__   __/(  ____ )\__   __/(  ____ \
   ) (   | (    )|   ) (   | (    \/
   | |   | (____)|   | |   | (_____
   | |   |     __)   | |   (_____  )
   | |   | (\ (      | |         ) |
___) (___| ) \ \_____) (___/\____) |
\_______/|/   \__/\_______/\_______)
"""

ASCII_ART_COLORIZED = """
\033[32m_________ \033[0m\033[33m_______ \033[0m\033[37m_________\033[0m \033[31m_______ \033[0m
\033[32m\\__   __/\033[0m\033[33m(  ____ )\033[0m\033[37m\\__   __/\033[0m\033[31m(  ____ \\\033[0m
   \033[32m) (   \033[0m\033[33m| (    )|\033[0m\033[37m   ) (   \033[0m\033[31m| (    \\/ \033[0m
   \033[32m| |   \033[0m\033[33m| (____)|\033[0m\033[37m   | |   \033[0m\033[31m| (_____ \033[0m
   \033[32m| |   \033[0m\033[33m|     __)\033[0m\033[37m   | |   \033[0m\033[31m(_____  )\033[0m
   \033[32m| |   \033[0m\033[33m| (\\ (   \033[0m\033[37m   | |     \033[0m\033[31m    ) |\033[0m
\033[32m___) (___\033[0m\033[33m| ) \\ \\__\033[0m\033[37m___) (___\033[0m\033[31m/\\____) |\033[0m
\033[32m\\_______/\033[0m\033[33m|/   \\__/\033[0m\033[37m\\_______/\033[0m\033[31m\\_______)\033[0m
"""

SUGGESTED_PATCH = Patch.FRUE
