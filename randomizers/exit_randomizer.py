"""Exit/Entrance Randomizer for Lufia II.

This module provides tools to randomize map connections (exits/entrances) in Lufia II.
Based on insights from the event_dump.py export functionality and Archipelago entrance
randomization patterns.

Example usage:
    >>> from structures.zone import Zone
    >>> from randomizers import ExitRandomizer
    >>>
    >>> # Load zones
    >>> elcid = Zone.from_name("Elcid")
    >>> alunze = Zone.from_name("Alunze Kingdom")
    >>>
    >>> # Create randomizer
    >>> randomizer = ExitRandomizer()
    >>>
    >>> # Shuffle all world exits randomly
    >>> randomizer.shuffle_world_exits()
    >>>
    >>> # Or create specific connections
    >>> randomizer.connect_exits(elcid, 0, alunze, 1)
    >>>
    >>> # Write changes to ROM
    >>> randomizer.write_all()

Architecture:
- ExitRandomizer: Main class for managing exit randomization
- ExitConnection: Represents a connection between two map exits
- ExitValidationError: Raised when invalid exit connections are detected
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from logger import iris


if TYPE_CHECKING:
    from structures.zone import Exit, Zone


class ExitValidationError(Exception):
    """Raised when exit connection validation fails."""


@dataclass
class ExitConnection:
    """Represents a connection between two map exits.

    Attributes:
        source_zone: The zone containing the exit
        source_exit_index: Index of the exit in the source zone
        dest_zone: The destination zone
        dest_exit_index: Index of the entrance in destination zone
        original_dest_map: Original destination map (for restoration)
        original_dest_x: Original destination X coordinate
        original_dest_y: Original destination Y coordinate
    """
    source_zone: Zone
    source_exit_index: int
    dest_zone: Zone
    dest_exit_index: int
    original_dest_map: int
    original_dest_x: int
    original_dest_y: int

    @property
    def source_exit(self) -> Exit:
        """Get the source exit object."""
        return self.source_zone.exits[self.source_exit_index]

    @property
    def dest_entrance(self) -> Exit | None:
        """Get the destination entrance object if available."""
        if self.dest_exit_index < len(self.dest_zone.exits):
            return self.dest_zone.exits[self.dest_exit_index]
        return None

    def validate(self) -> bool:
        """Validate that this connection is valid.

        Returns:
            True if valid, False otherwise
        """
        # Check that exit exists in source zone
        if self.source_exit_index >= len(self.source_zone.exits):
            return False

        # Check that destination zone has exits
        if not self.dest_zone.exits:
            return False

        # Additional validation can be added here:
        # - Check for one-way vs two-way connections
        # - Verify destination has appropriate entrance
        # - Check for logic requirements

        return True

    def apply(self) -> None:
        """Apply this connection by modifying the source exit."""
        exit_obj = self.source_exit
        exit_obj.destination_map = self.dest_zone.index

        # If we have a specific destination entrance, use its coordinates
        if self.dest_entrance:
            exit_obj.destination_x = self.dest_entrance.boundary.west
            exit_obj.destination_y = self.dest_entrance.boundary.north
        else:
            # Use zone's default entry point (could be improved)
            exit_obj.destination_x = 16
            exit_obj.destination_y = 16

    def restore(self) -> None:
        """Restore the original connection."""
        exit_obj = self.source_exit
        exit_obj.destination_map = self.original_dest_map
        exit_obj.destination_x = self.original_dest_x
        exit_obj.destination_y = self.original_dest_y


class ExitRandomizer:
    """Main class for randomizing map exits/entrances in Lufia II.

    This randomizer handles:
    - Shuffling exits within logical groups (towns, dungeons, etc.)
    - Creating custom exit connections
    - Validating exit connections
    - Writing changes back to ROM

    Design inspired by:
    - Archipelago's entrance_rando.py generic entrance randomization
    - The Wind Waker's entrance randomizer
    - ALttP's entrance shuffle

    Attributes:
        connections: List of exit connections to apply
        zone_cache: Cache of loaded zones
        original_connections: Backup of original connections for restoration
    """

    def __init__(self, seed: int | None = None) -> None:
        """Initialize the exit randomizer.

        Args:
            seed: Random seed for reproducible randomization. If None, uses random.
        """
        self.connections: list[ExitConnection] = []
        self.zone_cache: dict[int, Zone] = {}
        self.original_connections: list[ExitConnection] = []
        self._rng = random.Random(seed) if seed is not None else random.Random()
        iris.info(f"Initialized ExitRandomizer with seed: {seed}")

    def _get_zone(self, zone_index: int) -> Zone:
        """Get a zone from cache or load it.

        Args:
            zone_index: Zone index to load

        Returns:
            Zone object
        """
        if zone_index not in self.zone_cache:
            from structures.zone import Zone
            self.zone_cache[zone_index] = Zone.from_index(zone_index)
        return self.zone_cache[zone_index]

    def _backup_original_connections(self) -> None:
        """Backup all original exit connections for restoration."""
        from tables import MapEventObject

        self.original_connections.clear()

        for map_idx in range(MapEventObject.count):
            zone = self._get_zone(map_idx)
            if not zone.exits:
                continue

            for exit_idx, exit_obj in enumerate(zone.exits):
                connection = ExitConnection(
                    source_zone=zone,
                    source_exit_index=exit_idx,
                    dest_zone=self._get_zone(exit_obj.destination_map),
                    dest_exit_index=0,  # Default
                    original_dest_map=exit_obj.destination_map,
                    original_dest_x=exit_obj.destination_x,
                    original_dest_y=exit_obj.destination_y,
                )
                self.original_connections.append(connection)

    def connect_exits(
        self,
        source_zone: Zone,
        source_exit_index: int,
        dest_zone: Zone,
        dest_entrance_index: int = 0,
    ) -> ExitConnection:
        """Create a custom exit connection.

        Args:
            source_zone: Zone containing the exit to modify
            source_exit_index: Index of the exit in source zone's exit list
            dest_zone: Destination zone
            dest_entrance_index: Index of entrance in destination zone

        Returns:
            ExitConnection object representing the new connection

        Raises:
            ExitValidationError: If the connection is invalid
        """
        # Get original values for restoration
        source_exit = source_zone.exits[source_exit_index]

        connection = ExitConnection(
            source_zone=source_zone,
            source_exit_index=source_exit_index,
            dest_zone=dest_zone,
            dest_exit_index=dest_entrance_index,
            original_dest_map=source_exit.destination_map,
            original_dest_x=source_exit.destination_x,
            original_dest_y=source_exit.destination_y,
        )

        if not connection.validate():
            msg = (
                f"Invalid connection: {source_zone.name}[{source_exit_index}] "
                f"-> {dest_zone.name}[{dest_entrance_index}]"
            )
            raise ExitValidationError(
                msg,
            )

        self.connections.append(connection)
        iris.debug(f"Created connection: {source_zone.name} exit {source_exit_index} -> {dest_zone.name}")

        return connection

    def shuffle_world_exits(
        self,
        exclude_zones: list[int] | None = None,
        groups: dict[str, list[int]] | None = None,
    ) -> None:
        """Shuffle all world map exits randomly.

        This performs a full shuffle of exits, optionally respecting logical
        groupings (e.g., keeping town exits connected to towns).

        Args:
            exclude_zones: List of zone indices to exclude from shuffling
            groups: Optional grouping of zones. If provided, shuffles within groups.
                   Format: {"group_name": [zone_index, ...]}

        Example:
            >>> randomizer.shuffle_world_exits(
            ...     exclude_zones=[0x00, 0x01],  # Exclude starting zones
            ...     groups={
            ...         "towns": [0x04, 0x05, 0x08],
            ...         "dungeons": [0x20, 0x21, 0x22],
            ...     }
            ... )
        """
        from tables import MapEventObject

        iris.info("Shuffling world exits...")
        exclude_zones = exclude_zones or []

        # Backup original connections
        self._backup_original_connections()

        # Collect all exits
        all_exits: list[tuple[Zone, int]] = []

        for map_idx in range(MapEventObject.count):
            if map_idx in exclude_zones:
                continue

            zone = self._get_zone(map_idx)
            if not zone.exits:
                continue

            for exit_idx in range(len(zone.exits)):
                all_exits.append((zone, exit_idx))

        if not all_exits:
            iris.warning("No exits found to shuffle")
            return

        # Collect all destinations (zones with exits)
        all_destinations = [zone for zone in self.zone_cache.values() if zone.exits]

        if not all_destinations:
            iris.warning("No destination zones found")
            return

        # Shuffle destinations
        shuffled_destinations = all_destinations.copy()
        self._rng.shuffle(shuffled_destinations)

        # Create connections
        for (source_zone, exit_idx), dest_zone in zip(all_exits, shuffled_destinations, strict=False):
            try:
                # Pick a random entrance in the destination
                dest_entrance_idx = self._rng.randint(0, len(dest_zone.exits) - 1) if dest_zone.exits else 0

                self.connect_exits(source_zone, exit_idx, dest_zone, dest_entrance_idx)
            except ExitValidationError as e:
                iris.warning(f"Skipped invalid connection: {e}")

        iris.info(f"Shuffled {len(self.connections)} exits")

    def shuffle_zone_group(
        self,
        zone_indices: list[int],
        coupled: bool = True,
    ) -> None:
        """Shuffle exits within a specific group of zones.

        This is useful for shuffling dungeons, town areas, or other logical groups
        while keeping them isolated from the rest of the world.

        Args:
            zone_indices: List of zone indices to shuffle among themselves
            coupled: If True, ensures two-way connections (A->B and B->A)

        Example:
            >>> # Shuffle all dungeon exits among themselves
            >>> randomizer.shuffle_zone_group([0x20, 0x21, 0x22, 0x23])
        """
        zones = [self._get_zone(idx) for idx in zone_indices]

        # Collect exits from these zones
        exits: list[tuple[Zone, int]] = []
        for zone in zones:
            for exit_idx in range(len(zone.exits)):
                exits.append((zone, exit_idx))

        if not exits:
            iris.warning(f"No exits found in zone group: {zone_indices}")
            return

        # Create shuffled pairing
        shuffled_exits = exits.copy()
        self._rng.shuffle(shuffled_exits)

        for (source_zone, source_idx), (dest_zone, dest_idx) in zip(exits, shuffled_exits, strict=False):
            try:
                self.connect_exits(source_zone, source_idx, dest_zone, dest_idx)

                # If coupled, create reverse connection
                if coupled:
                    self.connect_exits(dest_zone, dest_idx, source_zone, source_idx)
            except ExitValidationError as e:
                iris.warning(f"Skipped invalid connection: {e}")

        iris.info(f"Shuffled {len(exits)} exits within zone group")

    def apply_all(self) -> None:
        """Apply all pending exit connections without writing to ROM."""
        for connection in self.connections:
            connection.apply()
        iris.info(f"Applied {len(self.connections)} exit connections")

    def restore_all(self) -> None:
        """Restore all original exit connections."""
        for connection in self.original_connections:
            connection.restore()
        self.connections.clear()
        iris.info("Restored all original exit connections")

    def write_all(self) -> None:
        """Write all exit connections to ROM.

        This applies the connections and writes the modified Exit data back to ROM.
        """
        self.apply_all()

        # Write each zone's modified exits
        written_zones = 0
        for zone in self.zone_cache.values():
            if zone.exits:
                zone.write()
                written_zones += 1

        iris.info(f"Wrote {written_zones} zones with modified exits to ROM")

    def export_connections(self) -> str:
        """Export all connections as human-readable text.

        Returns:
            String representation of all connections
        """
        lines = ["# Exit Randomizer Connections", ""]

        for i, conn in enumerate(self.connections, 1):
            source = f"{conn.source_zone.name} exit {conn.source_exit_index}"
            dest = f"{conn.dest_zone.name}"
            original = f"{self._get_zone(conn.original_dest_map).name}"

            lines.append(f"{i}. {source} -> {dest} (originally -> {original})")

        return "\n".join(lines)

    @classmethod
    def from_export(cls, export_text: str) -> Self:
        """Create a randomizer from exported connection text.

        This allows loading and reusing previous randomization configurations.

        Args:
            export_text: Text exported by export_connections()

        Returns:
            New ExitRandomizer with the loaded connections
        """
        randomizer = cls()

        # Parse export text and recreate connections
        # This is a simplified implementation - would need full parsing logic

        iris.warning("from_export not fully implemented yet")
        return randomizer
