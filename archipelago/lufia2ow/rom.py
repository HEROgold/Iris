"""Patch output: Iris's static base patch, then per-seed tokens (Iris-Dev#35)."""

import hashlib
import os
import pkgutil

import Utils
from settings import get_settings
from worlds.Files import APProcedurePatch, APTokenMixin, APTokenTypes

from . import data
from .items import GAME


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

    def write_grant(self, offset: int, item_index: int) -> None:
        """Make the script grant whose item byte is at ``offset`` (``locations.grant_offsets``) give ``item_index``.

        Opcode 0x20 gives items below 0x100, 0x21 gives 0x100 + its byte.
        """
        opcode = 0x21 if item_index & 0x100 else 0x20
        self.write_token(APTokenTypes.WRITE, offset - 1, bytes([opcode, item_index & 0xFF]))

    def write_hint_npc(self, offset: int, script: bytes) -> None:
        """Overwrite a hint NPC's talk script: its slot in the base ROM, which hints.py fills to the slot's size."""
        self.write_token(APTokenTypes.WRITE, offset, script)

    def write_boss(self, row: tuple, boss: tuple) -> None:
        """Put ``boss`` (a ``data_open_world.BOSSES`` row) at the spot of ``row`` (a ``BOSS_NPCS`` row): its sprite in
        the map's NPC-load script, its music and its formation in the talk script."""
        _, _, _, _, sprite_offset, bgm_offset, formation_offset, _ = row
        _, sprite, formation, bgm, _ = boss
        self.write_token(APTokenTypes.WRITE, sprite_offset, bytes([sprite]))
        self.write_token(APTokenTypes.WRITE, bgm_offset, bytes([bgm]))
        self.write_token(APTokenTypes.WRITE, formation_offset, bytes([formation]))

    def write_boss_strength(self, mode: int, levels: bytes | None = None) -> None:
        """The boss-scaling mode (0 unchanged, 1 party level, 2 per formation) and, for mode 2, the level per formation
        byte (0 = unchanged). The config block is the same in both base patches."""
        self.write_token(APTokenTypes.WRITE, data.CONFIG["AP_OPT_BOSS_STRENGTH"], bytes([mode]))
        if levels is not None:
            self.write_token(APTokenTypes.WRITE, data.CONFIG["AP_OPT_BOSS_LEVELS"], levels)

    def write_auth(self, auth: bytes) -> None:
        self.write_token(APTokenTypes.WRITE, data.CONFIG["AP_CONFIG_AUTH_OFFSET"], auth.ljust(AUTH_SIZE, b"\0"))


BASE_PATCHES = {False: "basepatch.bsdiff4", True: "basepatch_open_world.bsdiff4"}
"""Base patch file per open_world: the linear game, or open world (data_open_world.py describes its ROM)."""


def base_patch(open_world: bool = False) -> bytes:
    """The base patch's bytes; the patch file always stores it as ``basepatch.bsdiff4``, which ``procedure`` applies."""
    name = BASE_PATCHES[open_world]
    patch = pkgutil.get_data(__name__, name)
    if patch is None:
        msg = f"{name} is missing from the world package."
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
