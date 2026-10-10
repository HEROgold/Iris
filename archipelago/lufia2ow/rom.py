"""Patch output: Iris's static base patch, then per-seed tokens (Iris-Dev#35)."""

import hashlib
import os
import pkgutil

import Utils
from settings import get_settings
from worlds.Files import APProcedurePatch, APTokenMixin, APTokenTypes

from . import data
from .items import GAME
from .locations import GRANT_BASE


US_MD5 = "6efc477d6203ed2b3b9133c1cd9e9c5d"
"""The headerless US ROM (No-Intro, 2.5MB): what the base patch is built against."""
AUTH_SIZE = data.CONFIG["AP_CONFIG_AUTH_SIZE"]
ITEM_HIGH_BIT = 0x40
"""misc1 bit 6: bit 8 of the chest's item index."""


class L2OWProcedurePatch(APProcedurePatch, APTokenMixin):
    hash = US_MD5
    game = GAME
    patch_file_ending = ".apl2ow"
    result_file_ending = ".sfc"
    procedure = [
        ("apply_bsdiff4", ["basepatch.bsdiff4"]),
        ("apply_tokens", ["tokens.bin"]),
    ]

    @classmethod
    def get_source_data(cls) -> bytes:
        return get_base_rom_bytes()

    def write_chest(self, chest_index: int, item_index: int) -> None:
        """Put ``item_index`` in a red chest: its low byte, and its bit 8 in misc1 (other misc1 bits unchanged)."""
        _, _, _, record, misc1, _ = data.CHESTS[chest_index]
        high = ITEM_HIGH_BIT if item_index & 0x100 else 0
        self.write_token(APTokenTypes.WRITE, record, bytes([(misc1 & ~ITEM_HIGH_BIT) | high]))
        self.write_token(APTokenTypes.WRITE, record + 2, bytes([item_index & 0xFF]))

    def write_grant(self, location: int, item_index: int) -> None:
        """Make a script grant give ``item_index``: opcode 0x20 gives items below 0x100, 0x21 gives 0x100 + its byte."""
        _, _, offset, _, _, _ = data.GRANTS[location - GRANT_BASE]
        opcode = 0x21 if item_index & 0x100 else 0x20
        self.write_token(APTokenTypes.WRITE, offset - 1, bytes([opcode, item_index & 0xFF]))

    def write_no_starting_arrow(self) -> None:
        """Maxim starts without the Arrow: empty the new-game tool slot and his starting tool (key_items.py)."""
        for offset, value in data.NO_STARTING_ARROW:
            self.write_token(APTokenTypes.WRITE, offset, value)

    def write_auth(self, auth: bytes) -> None:
        self.write_token(APTokenTypes.WRITE, data.CONFIG["AP_CONFIG_AUTH_OFFSET"], auth.ljust(AUTH_SIZE, b"\0"))


def base_patch() -> bytes:
    patch = pkgutil.get_data(__name__, "basepatch.bsdiff4")
    if patch is None:
        msg = "basepatch.bsdiff4 is missing from the world package."
        raise FileNotFoundError(msg)
    return patch


def get_base_rom_bytes() -> bytes:
    with open(get_base_rom_path(), "rb") as stream:
        rom = bytes(Utils.read_snes_rom(stream))
    if hashlib.md5(rom).hexdigest() != US_MD5:
        msg = "The ROM isn't the US release of Lufia II (No-Intro, 2.5MB). Get that version, then dump it."
        raise ValueError(msg)
    return rom


def get_base_rom_path() -> str:
    file_name = get_settings()["lufia2ow_options"]["rom_file"]
    if not os.path.exists(file_name):
        file_name = Utils.user_path(file_name)
    return file_name
