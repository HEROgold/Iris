"""SNI client: authenticates against the config block, reports opened chests, script grants and the goal (Iris-Dev#36).

Chests are read from the opened-chest bits (confirmed in a real run); a script grant is reported once the event flag its
script sets is on. Not here yet: receiving items (needs the ROM's RX buffer, Iris-Dev#20), death link. There is no
"a save is loaded" flag; ``looks_uninitialised`` only rejects the fill pattern some emulators put in WRAM at power-on.
"""

import logging
from typing import TYPE_CHECKING

from NetUtils import ClientStatus
from worlds.AutoSNIClient import SNIClient

from . import data
from .items import BASE_ID, GAME
from .locations import GRANT_FLAGS

if TYPE_CHECKING:
    from SNIClient import SNIContext

logger = logging.getLogger("Client")

WRAM_START = 0xF50000
"""SNI's address of $7E:0000."""
MAGIC = data.CONFIG["AP_CONFIG_MAGIC"]
MAGIC_OFFSET = data.CONFIG["AP_CONFIG_MAGIC_OFFSET"]
AUTH_OFFSET = data.CONFIG["AP_CONFIG_AUTH_OFFSET"]
AUTH_SIZE = data.CONFIG["AP_CONFIG_AUTH_SIZE"]
CHEST_BITS = WRAM_START + (data.CHEST_OPENED_BITS & 0xFFFF)
CHEST_BYTES = max(data.CHESTS)[0] // 8 + 1
EVENT_FLAGS = WRAM_START + 0x077E
EVENT_FLAG_BYTES = 32
GOAL_FLAG = data.GOAL_FLAG


def is_set(flags: bytes, flag: int) -> bool:
    return bool(flags[flag >> 3] & (1 << (flag & 7)))


def opened_chests(bits: bytes) -> list[int]:
    """Chest indices whose "opened" bit is set (bit n & 7 of byte n >> 3)."""
    return [index for index in range(len(bits) * 8) if bits[index >> 3] & (1 << (index & 7))]


def looks_uninitialised(bits: bytes) -> bool:
    """Every byte the same and not zero: power-on fill (0x55, 0xFF), not a save's chest bits."""
    return len(set(bits)) == 1 and bits[0] != 0


class L2OWSNIClient(SNIClient):
    game = GAME
    patch_suffix = ".apl2ow"

    async def validate_rom(self, ctx: "SNIContext") -> bool:
        from SNIClient import snes_read

        magic = await snes_read(ctx, MAGIC_OFFSET, len(MAGIC))
        if magic != MAGIC:
            return False
        auth = await snes_read(ctx, AUTH_OFFSET, AUTH_SIZE)
        if auth is None:
            return False
        ctx.game = self.game
        ctx.items_handling = 0b000  # every item of this world sits in its own chests
        ctx.rom = auth
        return True

    async def game_watcher(self, ctx: "SNIContext") -> None:
        from SNIClient import snes_read

        if await snes_read(ctx, AUTH_OFFSET, AUTH_SIZE) != ctx.rom:
            ctx.rom = None
            return
        if ctx.server is None or ctx.slot is None:
            return

        checked: list[int] = []
        bits = await snes_read(ctx, CHEST_BITS, CHEST_BYTES)
        if bits is not None and not looks_uninitialised(bits):
            checked += [BASE_ID + index for index in opened_chests(bits)]
        flags = await snes_read(ctx, EVENT_FLAGS, EVENT_FLAG_BYTES)
        if flags is not None and not looks_uninitialised(flags):
            checked += [location for location, flag in GRANT_FLAGS.items() if is_set(flags, flag)]
        new = [loc for loc in checked if loc in ctx.server_locations and loc not in ctx.locations_checked]
        if new:
            ctx.locations_checked.update(new)
            await ctx.send_msgs([{"cmd": "LocationChecks", "locations": new}])

        if not ctx.finished_game and flags is not None and not looks_uninitialised(flags):
            if is_set(flags, GOAL_FLAG):
                await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                ctx.finished_game = True
                logger.info("Daos is defeated: goal complete.")
