from enums.patches import Patch


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


# --- Reserved space: ZoneData / event-script relocation freespace -------------------------------
# Dedicated arenas for the shared FreeSpaceAllocator instances (helpers.freespace) that back
# ZoneData.write_relocated and the event-script container relocator. 128KB each, bank-aligned, well
# clear of SCALE_ENCOUNTERS_REGION.
ZONE_DATA_FREESPACE = range(0x320000, 0x340000)
EVENT_SCRIPT_FREESPACE = range(0x340000, 0x360000)

# --- Reserved space: RealCritical fix_cave_chest_table --------------------------------------------
# 71-byte hook body at headerless 0x30D820 (SNES $E1:D820); the patched code at 0x19176 jumps to $E1:D84A.
CAVE_CHEST_FIX_REGION = range(0x30D820, 0x30D867)

RESERVED_REGIONS = [SCALE_ENCOUNTERS_REGION, ZONE_DATA_FREESPACE, EVENT_SCRIPT_FREESPACE, CAVE_CHEST_FIX_REGION]
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
