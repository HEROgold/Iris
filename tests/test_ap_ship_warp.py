"""A Ship or Submarine item follows Warp to the destination's dock before the Auralio water gate opens (Iris-Dev#51).

Warp arrival ($86:9BCA) puts the ship at the destination's dock, but while flag 149 is clear it moves a dock below $D6
(the towns before Treadool) to $D6, Treadool's. key_items.asm hooks that flag test: with either item held it keeps the
dock. Static checks on the committed base patches (``tools/build_ap_basepatch.py --check`` keeps them current);
``tests/emulator/ship_warp.lua`` checks it in the game.
"""

import pytest
from iris.constants import RX_CODE_REGION
from iris.helpers import files
from iris.helpers.addresses import address_from_lorom
from iris.patches.archipelago.overworld.key_items import SHIP, SUBMARINE


bsdiff4 = pytest.importorskip("bsdiff4")

from tools.build_ap_basepatch import PATCHES, vanilla_image


JML, NOP, BNE = 0x5C, 0xEA, 0xD0
HOOK = 0x869C2B
"""Vanilla ``LDA #$95 : JSL $80BE1A``: flag 149, the Auralio water gate."""
VANILLA_GATE = bytes.fromhex("a995221abe80d03c")
"""The hooked bytes and the ``BNE $9C6F`` after them (gate open: keep the dock)."""
CLAMP = 0x869C31
"""``BNE $9C6F``, then the clamp to dock $D6."""
KEEP_DOCK = 0x869C6F
FIRST_KEY_ITEM = 428
SCENARIO_BITS = 0x7E091E


def _at(rom: bytes, snes: int, size: int) -> bytes:
    offset = address_from_lorom(snes)
    return rom[offset : offset + size]


def _jml(target: int) -> bytes:
    return bytes([JML]) + target.to_bytes(3, "little")


@pytest.fixture(scope="module")
def roms() -> list[tuple[bytes, bytes]]:
    """(vanilla, base ROM) for the linear and the open-world base patch."""
    vanilla = vanilla_image(files.original_file)
    return [(vanilla, bsdiff4.patch(vanilla, patch_file.read_bytes())) for patch_file, _ in PATCHES]


def test_vanilla_gate_is_where_the_hook_goes(roms: list[tuple[bytes, bytes]]) -> None:
    for vanilla, _ in roms:
        assert _at(vanilla, HOOK, len(VANILLA_GATE)) == VANILLA_GATE


def test_hook_keeps_the_dock_for_item_ships(roms: list[tuple[bytes, bytes]]) -> None:
    ship_byte = SCENARIO_BITS + ((SHIP - FIRST_KEY_ITEM) >> 3)
    assert ship_byte == SCENARIO_BITS + ((SUBMARINE - FIRST_KEY_ITEM) >> 3)
    mask = (1 << ((SHIP - FIRST_KEY_ITEM) & 7)) | (1 << ((SUBMARINE - FIRST_KEY_ITEM) & 7))
    for _, rom in roms:
        hook = _at(rom, HOOK, len(VANILLA_GATE))
        assert hook[0] == JML
        assert hook[4:] == bytes([NOP, NOP, BNE, VANILLA_GATE[-1]]), "the BNE after the flag test stays"
        target = int.from_bytes(hook[1:4], "little")
        assert address_from_lorom(target) in RX_CODE_REGION
        expected = (
            bytes([0xAF])
            + ship_byte.to_bytes(3, "little")  # LDA.l $7E0921
            + bytes([0x29, mask])  # AND #Ship|Submarine
            + bytes([BNE, 0x0A])  # held: keep the dock
            + VANILLA_GATE[:6]  # else the vanilla flag test...
            + _jml(CLAMP)  # ...and its BNE
            + _jml(KEEP_DOCK)
        )
        assert _at(rom, target, len(expected)) == expected, f"${target:06X}"
