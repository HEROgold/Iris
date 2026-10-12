"""SNI client: authenticates against the config block, reports checks and the goal, delivers items (Iris-Dev#36, #20).

Chests are read from the opened-chest bits (confirmed in a real run); a script grant is reported once the event flag its
script sets is on, an open-world boss's rewards once its beaten flag is, and the goal once the goal option's flag (from
the slot data) is. Received items go into the SRAM list that the base patch's rx.asm hands out in the field. The server
also sends this world's own items: a character, capsule or maiden found in this world shows as the AP item, so it has to
come through the list; any other own item was already given by its chest or grant, so it is skipped. Talking to a hint NPC sets its flag; with Hint Unlock
on, the client then creates that hint on the server. Not here yet: death link. There is no "a save is loaded" flag;
``looks_uninitialised`` only rejects the fill pattern some emulators put in WRAM at power-on.
"""

import logging
from typing import TYPE_CHECKING, Any

from NetUtils import ClientStatus
from worlds.AutoSNIClient import SNIClient

from . import data
from .items import BASE_ID, CHARACTER_BASE, GAME
from .locations import BOSS_FLAGS, GRANT_FLAGS, ORB_FLAGS


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
RX_ADDRESS = 0xE00000 + 0x2800
"""SNI's address of SRAM $F0:2800: u16 received count, u16 processed count, then the u16 item list (rx.asm)."""
GOAL_FLAG = data.GOAL_FLAG
"""Defeat Daos: the goal flag until the server's slot data says otherwise."""
EVENT_VARIABLES = WRAM_START + 0x079E
"""Event-script variables, one byte each (the add-to-variable opcode at $80:A1EF does ADC $079E,X)."""


def is_set(flags: bytes, flag: int) -> bool:
    return bool(flags[flag >> 3] & (1 << (flag & 7)))


def opened_chests(bits: bytes) -> list[int]:
    """Chest indices whose "opened" bit is set (bit n & 7 of byte n >> 3)."""
    return [index for index in range(len(bits) * 8) if bits[index >> 3] & (1 << (index & 7))]


def flagged_locations(flags: bytes) -> list[int]:
    """Locations whose event flag is set: script grants, boss rewards (a boss's two rewards share its flag) and the
    open-world orb check."""
    return [location for location, flag in (GRANT_FLAGS | BOSS_FLAGS | ORB_FLAGS).items() if is_set(flags, flag)]


def given_in_game(item: Any, slot: int | None) -> bool:
    """Whether a received item came from this world's own chest or grant, which gave it already.

    Characters, capsules and maidens (ids from $0200) never sit in a chest: those always go through the list.
    Starting inventory and server-sent items have no location of this world (location <= 0).
    """
    return item.player == slot and item.location > 0 and item.item - BASE_ID < CHARACTER_BASE


def looks_uninitialised(bits: bytes) -> bool:
    """Every byte the same and not zero: power-on fill (0x55, 0xFF), not a save's chest bits."""
    return len(set(bits)) == 1 and bits[0] != 0


class L2OWSNIClient(SNIClient):
    game = GAME
    patch_suffix = ".apl2ow"

    def __init__(self) -> None:
        super().__init__()
        self.goal_flag: int | None = GOAL_FLAG
        self.goal_wishes = 0
        """With the dragon_eggs goal: the wishes to make, read from ``goal_wish_variable``."""
        self.goal_wish_variable = 0
        self.hint_unlock = False
        self.npc_hints: dict[int, tuple[int, int]] = {}
        """Hint NPC flag -> (player, location) to hint when the flag is set."""
        self.hinted: set[int] = set()
        """Hint NPC flags already sent this session."""

    def on_package(self, ctx: "SNIContext", cmd: str, args: dict[str, Any]) -> None:
        if cmd == "Connected":
            slot_data = args.get("slot_data", {})
            self.goal_flag = slot_data.get("goal_flag", GOAL_FLAG)
            self.goal_wishes = slot_data.get("goal_wishes", 0)
            self.goal_wish_variable = slot_data.get("goal_wish_variable", 0)
            self.hint_unlock = slot_data.get("hint_unlock", False)
            self.npc_hints = {int(flag): (spot[0], spot[1]) for flag, spot in slot_data.get("npc_hints", {}).items()}
            self.hinted = set()

    async def validate_rom(self, ctx: "SNIContext") -> bool:
        from SNIClient import snes_read

        magic = await snes_read(ctx, MAGIC_OFFSET, len(MAGIC))
        if magic != MAGIC:
            return False
        auth = await snes_read(ctx, AUTH_OFFSET, AUTH_SIZE)
        if auth is None:
            return False
        ctx.game = self.game
        ctx.items_handling = 0b111  # every item; our own are skipped unless special (``given_in_game``)
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
            checked += flagged_locations(flags)
        new = [loc for loc in checked if loc in ctx.server_locations and loc not in ctx.locations_checked]
        if new:
            ctx.locations_checked.update(new)
            await ctx.send_msgs([{"cmd": "LocationChecks", "locations": new}])

        await self._deliver(ctx)

        if flags is None or looks_uninitialised(flags):
            return
        await self._unlock_hints(ctx, flags)
        if not ctx.finished_game and await self._goal_reached(ctx, flags):
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            ctx.finished_game = True
            logger.info("Goal complete.")

    async def _goal_reached(self, ctx: "SNIContext", flags: bytes) -> bool:
        from SNIClient import snes_read

        if self.goal_wishes:
            wishes = await snes_read(ctx, EVENT_VARIABLES + self.goal_wish_variable, 1)
            return wishes is not None and wishes[0] >= self.goal_wishes
        return self.goal_flag is not None and is_set(flags, self.goal_flag)

    async def _unlock_hints(self, ctx: "SNIContext", flags: bytes) -> None:
        """A hint NPC talked to: create its hint on the server (CreateHints, for our own item)."""
        if not self.hint_unlock:
            return
        for flag, (player, location) in self.npc_hints.items():
            if flag in self.hinted or not is_set(flags, flag):
                continue
            self.hinted.add(flag)
            await ctx.send_msgs([{"cmd": "CreateHints", "player": player, "locations": [location]}])

    @staticmethod
    async def _deliver(ctx: "SNIContext") -> None:
        """Append the next received item to the SRAM list; the game hands it out and catches up one per frame.

        An item the game already gave (``given_in_game``) moves both counters on together, in one write once the game
        has caught up, so the game never sees it as pending.
        """
        from SNIClient import snes_buffered_write, snes_flush_writes, snes_read

        counters = await snes_read(ctx, RX_ADDRESS, 4)
        if counters is None:
            return
        received = int.from_bytes(counters[:2], "little")
        processed = int.from_bytes(counters[2:], "little")
        if received >= len(ctx.items_received):
            return
        item = ctx.items_received[received]
        index = item.item - BASE_ID
        skip = given_in_game(item, ctx.slot)
        if skip and processed != received:
            return  # the game is still handing out earlier items
        received += 1
        snes_buffered_write(ctx, RX_ADDRESS + 2 * (received + 1), index.to_bytes(2, "little"))
        counters = received.to_bytes(2, "little") * 2 if skip else received.to_bytes(2, "little")
        snes_buffered_write(ctx, RX_ADDRESS, counters)
        await snes_flush_writes(ctx)
        how = "Found" if skip else "Received"
        logger.info(f"{how} {ctx.item_names.lookup_in_game(item.item)} ({received}/{len(ctx.items_received)}).")
