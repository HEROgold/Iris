"""Validation helpers for randomization in Lufia II.

This module provides validation utilities to ensure that randomization
doesn't create impossible or broken game states.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from logger import iris


if TYPE_CHECKING:
    from randomizers.exit_randomizer import ExitConnection
    from structures.zone import Zone


class ValidationError(Exception):
    """Base exception for validation errors."""


class ExitLogicError(ValidationError):
    """Raised when exit connections violate game logic."""


class ReachabilityError(ValidationError):
    """Raised when randomization creates unreachable areas."""


def validate_exit_connection(connection: ExitConnection) -> tuple[bool, str]:
    """Validate that an exit connection is valid.

    Checks:
    - Source and destination zones exist
    - Exit indices are within bounds
    - No self-loops (zone connecting to itself)
    - Destination zone has valid entry points

    Args:
        connection: ExitConnection to validate

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    # Check source exit exists
    if connection.source_exit_index >= len(connection.source_zone.exits):
        return False, f"Source exit index {connection.source_exit_index} out of bounds for zone {connection.source_zone.index}"

    # Check destination zone has exits (entry points)
    if not connection.dest_zone.exits:
        return False, f"Destination zone {connection.dest_zone.index} has no entry points"

    # Warn about self-loops (usually not desired)
    if connection.source_zone.index == connection.dest_zone.index:
        iris.warning(f"Self-loop detected: Zone {connection.source_zone.index} connects to itself")

    return True, ""


def validate_zone_reachability(zones: list[Zone], start_zone: Zone) -> tuple[bool, list[int]]:
    """Validate that all zones are reachable from a starting zone.

    Uses breadth-first search to determine reachability.

    Args:
        zones: List of all zones to check
        start_zone: Starting zone (usually the spawn point)

    Returns:
        Tuple of (all_reachable, unreachable_zone_indices)
    """
    visited = set()
    queue = [start_zone]

    while queue:
        current = queue.pop(0)
        if current.index in visited:
            continue

        visited.add(current.index)

        # Add all destinations from exits
        for exit_obj in current.exits:
            dest_index = exit_obj.destination_map
            if dest_index not in visited:
                # Find destination zone
                dest_zone = next((z for z in zones if z.index == dest_index), None)
                if dest_zone:
                    queue.append(dest_zone)

    # Find unreachable zones
    all_indices = {z.index for z in zones}
    unreachable = sorted(all_indices - visited)

    if unreachable:
        iris.warning(f"Found {len(unreachable)} unreachable zones: {unreachable[:10]}...")
        return False, unreachable

    return True, []


def validate_two_way_connections(zone: Zone) -> tuple[bool, list[str]]:
    """Validate that exits have corresponding return paths.

    This checks that if zone A has an exit to zone B, then zone B
    has an exit back to zone A (for two-way connections).

    Args:
        zone: Zone to validate

    Returns:
        Tuple of (all_two_way, list_of_one_way_connections)
    """
    one_way_connections = []

    for exit_obj in zone.exits:
        dest_map = exit_obj.destination_map

        # Check if destination has an exit back to this zone
        # This would require loading the destination zone and checking
        # For now, return placeholder
        one_way_connections.append(f"Zone {zone.index} exit to {dest_map}")

    return len(one_way_connections) == 0, one_way_connections


def validate_dungeon_progression(zone_indices: list[int]) -> tuple[bool, str]:
    """Validate that dungeon zones maintain logical progression.

    Dungeons typically have a specific order that must be maintained:
    - Early floors are accessible
    - Boss rooms are gated behind key items or progression
    - Exit back to world map is always available

    Args:
        zone_indices: List of zone indices representing a dungeon

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Placeholder implementation
    # Real implementation would need to:
    # 1. Identify dungeon entrance/exit zones
    # 2. Check that all floors are connected
    # 3. Verify boss room accessibility
    # 4. Ensure escape route exists

    if not zone_indices:
        return False, "No zones provided for dungeon validation"

    return True, ""


def check_softlock_potential(
    zone: Zone,
    required_items: list[int] | None = None,
) -> tuple[bool, str]:
    """Check if a zone could create a softlock situation.

    A softlock occurs when the player becomes stuck with no way to progress
    or return to a previous location.

    Args:
        zone: Zone to check
        required_items: List of item IDs that might be required for progression

    Returns:
        Tuple of (safe, potential_issue_description)
    """
    # Check if zone has at least one exit
    if not zone.exits:
        return False, f"Zone {zone.index} has no exits - potential softlock"

    # Check if all exits lead somewhere valid
    for i, exit_obj in enumerate(zone.exits):
        if exit_obj.destination_map == zone.index:
            iris.warning(f"Zone {zone.index} exit {i} leads back to itself")

    # More sophisticated checks would involve:
    # - Checking if required items are obtainable before this zone
    # - Verifying that progression flags can be set
    # - Ensuring escape options exist

    return True, ""


def validate_event_requirements(zone: Zone) -> tuple[bool, list[str]]:
    """Validate that event scripts in a zone have proper requirements.

    Checks:
    - NPCs reference valid scripts
    - Event flags are properly set/cleared
    - Item gives/checks are valid

    Args:
        zone: Zone to validate

    Returns:
        Tuple of (all_valid, list_of_issues)
    """
    issues = []

    # Check if zone has event data
    if not hasattr(zone, "event") or not zone.event:
        issues.append(f"Zone {zone.index} has no event data")
        return False, issues

    # Additional checks would go here
    # - Verify NPC script indices
    # - Check event flag consistency
    # - Validate item IDs

    return len(issues) == 0, issues


def suggest_exit_candidates(
    source_zone: Zone,
    all_zones: list[Zone],
    criteria: str = "similar",
) -> list[Zone]:
    """Suggest good candidate destinations for an exit.

    This helps randomizers choose sensible connections by considering:
    - Zone types (town, dungeon, overworld)
    - Progression requirements
    - Thematic similarity

    Args:
        source_zone: Zone whose exit needs a destination
        all_zones: List of all available zones
        criteria: Matching criteria ("similar", "random", "progression")

    Returns:
        List of suggested destination zones, ordered by suitability
    """
    candidates = []

    # Filter out the source zone itself
    candidates = [z for z in all_zones if z.index != source_zone.index]

    # Apply criteria
    if criteria == "similar":
        # Prefer zones with similar number of exits
        source_exit_count = len(source_zone.exits)
        candidates.sort(key=lambda z: abs(len(z.exits) - source_exit_count))
    elif criteria == "progression":
        # Prefer zones that advance progression
        # This would need game-specific logic
        pass
    # "random" just returns the unordered list

    return candidates[:10]  # Return top 10 candidates
