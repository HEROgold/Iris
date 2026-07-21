"""``ZoneEventManager`` -- the thin coordinator that ``Zone`` consumes.

It owns no game logic of its own so ``Zone`` stays unaware of the package internals.
"""

import logging
from typing import TYPE_CHECKING

from logger import iris
from structures.event_script.containers import MapEvent
from structures.event_script.dump import dump_map
from structures.event_script.script import EventScript


if TYPE_CHECKING:
    from structures.zone import Zone


log = logging.getLogger(f"{iris.name}.ZoneEventManager")


class ZoneEventManager:
    """Loads/serialises the event scripts for a Zone's map. Backed by ``structures.event_script``."""

    def load_zone_events(self, zone: "Zone") -> None:
        """Parse the map's events and attach them to the zone (idempotent per zone)."""
        zone.event = MapEvent.from_index(zone.index)

    def get_npc_script(self, zone: "Zone") -> EventScript:
        """Return the NPC-load (``EventClass.NPC_SCRIPT``) script for the zone's map."""
        return zone.event.npc_script

    def export_zone_events(self, zone: "Zone") -> str:
        """Dump the zone's map events to the round-trippable text format."""
        return dump_map(zone.event)
