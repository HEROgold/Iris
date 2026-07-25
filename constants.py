from enums.patches import Patch


PROJECT_NAME = "Iris"
VERSION = "0.1"
AUTHORS = [{"name":"HEROgold", "email":""}]
DESCRIPTION = "A Lufia II: Rise of the Sinistrals randomizer/patching toolkit."

POINTER_SIZE = 2


# --- Carved-out freespace: --scale-encounters (patches/HEROgold/scale_encounters) ---------------
# One LoROM bank-half at headerless 0x286a10 (SNES $D0:EA10) is reserved for the level-scaled
# encounter patch and therefore taken off the front of EMPTY_BYTES[0]. It holds Python-baked data
# (the level -> formation table and the roll constants) plus the asar hook body, which uses an
# explicit `org` rather than `freecode` so asar's freespace scanner can never hand the same bytes
# to another patch. Nothing else may allocate inside this range.
SCALE_ENCOUNTERS_REGION = range(0x286a10, 0x286e10)
SCALE_ENCOUNTERS_TABLE = 0x286a10
"""99 bytes: for each party level 1..99, the formation id that best matches it."""
SCALE_ENCOUNTERS_TABLE_SIZE = 99
SCALE_ENCOUNTERS_LOW = 0x286a73
"""1 byte, two's complement: the low end of the offset band added to the party average level."""
SCALE_ENCOUNTERS_RANGE = 0x286a74
"""1 byte: how many distinct offsets the band spans (high - low + 1)."""
SCALE_ENCOUNTERS_CODE = 0x286a75
"""Start of the asar-assembled hook body (SNES $D0:EA75)."""
SCALE_ENCOUNTERS_MAX_OFFSET = 98
"""Widest usable end of the offset band. The resulting target level is clamped to 1..99 anyway, so
a larger offset could never change the outcome -- rejecting it stops a typo doing nothing quietly."""
SCALE_ENCOUNTERS_MAX_BAND = 0xFF
"""The band size is baked as one byte, so it cannot span more than 255 distinct offsets."""


EMPTY_BYTES = [
    range(0x286e10, 0x30d80e),
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
