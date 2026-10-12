"""Another character leads instead of Maxim (terrorwave's open-world starting character).

- New game: the first scene (Maxim brings Tia his jellies, ``04-B-01``) needs Maxim in the party, so the leader joins
  and Maxim leaves at its end, where the game hands over control, unless the leader is in the party already.
- Overworld: the overworld sprites and palettes point at the leader's town sprite (terrorwave's
  ``OverSpriteObject.become_character``).
- Events: wherever a script moves character 0 (``33``, ``86``, ``8C``), it moves the leader, except the cutscenes
  where Maxim appears as himself (terrorwave's ``set_new_leader_for_events``).
- Artea and Lexis get EveTheFeesh's town sprites from terrorwave (``new_artea.bin``, ``new_lexis.bin``), which have
  the frames a field leader needs.

Dialogue still calls the hero ``$MAXIM$``.
"""

from pathlib import Path

from iris.helpers.addresses import address_to_lorom
from iris.helpers.files import on_new_session, write_file
from iris.logger import iris
from iris.rom_space.pool import pool
from iris.structures.character import party_flag_of
from iris.structures.event_script.containers import MapEvent
from iris.structures.event_script.event_patch import resolve_or_create
from iris.structures.event_script.instructions import Address, Instruction
from iris.structures.event_script.script import EventScript
from iris.structures.sprites import OverPallette, OverSprite, TownSprite
from iris.tables import MapEventObject, OverPaletteObject, OverSpriteObject


MAXIM = 0
LEADERS = {"selan": 1, "guy": 2, "artea": 3, "tia": 4, "dekar": 5, "lexis": 6}
TOWN_SPRITES = (0x27F1F6, 0x27F1FB, 0x27F200, 0x27F205, 0x27F214, 0x27F20A, 0x27F20F)
"""Each character's town-sprite record (palette index, 3-byte sprite pointer), by character index."""
NEW_SPRITES = {3: "new_artea.bin", 6: "new_lexis.bin"}
SPRITE_SIZE = 0x1800
OPENING = "04-B-01"
EXEMPT = frozenset(("02-B-01", "02-B-02", "03-B-02", "04-B-01", "04-B-02", "1C-B-03", "2C-B-04", "45-B-02", "7A-B-01", "A6-B-03"))
"""Scripts where character 0 stays Maxim (terrorwave's EXEMPT_EVENTS, in its letters), plus Elcid's new-game entrance
``03-B-02``: terrorwave starts in Portravia, Iris in Elcid, where Maxim walks before the opening."""
END = 0x00
CHARACTER_OPERAND = {0x33: 1, 0x86: 0, 0x8C: 0}
"""Opcode -> the operand that names a character: walk a route, move with an animation, ..."""
JOIN, LEAVE, SET_FLAG, CLEAR_FLAG, BRANCH_ON_FLAG = 0x2B, 0x2C, 0x1A, 0x1B, 0x15


_imported: dict[int, int] = {}
"""Character -> where :func:`reserve_leader_room` put its new town sprite in this session."""


@on_new_session
def _reset() -> None:
    _imported.clear()


def reserve_leader_room() -> None:
    """Room for any leader, so :func:`set_leader` afterwards only changes bytes in place (the Archipelago open-world
    base, whose leader is a per-seed diff, Iris-Dev#43). The new Artea and Lexis sprites go in (unused until one of
    them leads), and the opening gets its party swap with Maxim as the leader, which the game skips: Maxim is in the
    party by then."""
    for character in NEW_SPRITES:
        _imported[character] = _write_sprite(character)
    _swap_new_game_party(MAXIM)


def set_leader(leader: int) -> None:
    """Make character ``leader`` (1-6) lead from the new game on."""
    if leader not in LEADERS.values():
        msg = f"Leader must be a character index 1-6 (not Maxim), got {leader}."
        raise ValueError(msg)
    iris.info(f"Starting leader: character {leader}.")
    if leader in NEW_SPRITES:
        _import_town_sprite(leader)
    _become_character(leader)
    _replace_leader_in_events(leader)
    _swap_new_game_party(leader)


def _write_sprite(character: int) -> int:
    data = (Path(__file__).parent / NEW_SPRITES[character]).read_bytes()
    assert len(data) == SPRITE_SIZE
    at = pool().alloc(SPRITE_SIZE)
    write_file.seek(at)
    write_file.write(data)
    return at


def _import_town_sprite(character: int) -> None:
    at = _imported[character] if character in _imported else _write_sprite(character)
    sprite = TownSprite.from_pointer(TOWN_SPRITES[character])
    sprite.sprite_pointer = address_to_lorom(at)
    sprite.write()


def _become_character(character: int) -> None:
    maxim = TownSprite.from_pointer(TOWN_SPRITES[MAXIM])
    other = TownSprite.from_pointer(TOWN_SPRITES[character])
    offset = other.sprite_pointer - maxim.sprite_pointer
    for index in range(OverSpriteObject.count):
        over = OverSprite.from_index(index)
        over.sprite_index += offset
        over.write()
    for index in range(OverPaletteObject.count):
        palette = OverPallette.from_index(index)
        palette.pallette_index = other.sprite_index * 2  # TownSprite.sprite_index is its palette index
        palette.write()


def _signature(map_index: int, letter: str, index: int) -> str:
    return f"{map_index:02X}-{letter}-{index:02X}"


def _replace_leader_in_events(leader: int) -> None:
    letters = "ABCDEF"
    for map_index in range(MapEventObject.count):
        map_event = MapEvent.from_index(map_index)
        changed = False
        for event_list in map_event.event_lists:
            for script in event_list.events:
                if script.index >= 0 and _signature(map_index, letters[script.event_class.value], script.index) in EXEMPT:
                    continue
                for instruction in script.instructions:
                    operand = CHARACTER_OPERAND.get(instruction.opcode)
                    if operand is not None and instruction.operands[operand] == MAXIM:
                        instruction.operands[operand] = leader
                        script.dirty = changed = True
        if changed:
            map_event.write()


def _swap_new_game_party(leader: int) -> None:
    """At the end of the first scene, before its END (after it sets Maxim's party flag): the leader joins, Maxim leaves.

    If the swap is there already (:func:`reserve_leader_room`), only its character and flags change.
    """
    script = resolve_or_create(OPENING)
    swap = _existing_swap(script)
    if swap is not None:
        branch, join, set_flag = swap
        branch.operands[0] = set_flag.operands[0] = party_flag_of(leader)
        join.operands[0] = leader
        script.dirty = True
        MapEvent.from_index(int(OPENING[:2], 16)).write()
        return
    # Room for new lines: every line and local jump target times 0x10 (lines are labels; the compiler lays out bytes).
    for instruction in script.instructions:
        instruction.line *= 0x10
        instruction.operands = [
            Address(op.offset * 0x10) if isinstance(op, Address) and op.is_local else op for op in instruction.operands
        ]
    last = script.instructions[-1]
    if last.opcode != END:
        msg = f"{OPENING} doesn't end with END any more; the party swap has no place to go."
        raise ValueError(msg)
    at = last.line - 0x0F
    swap = [
        Instruction(at, BRANCH_ON_FLAG, [party_flag_of(leader), Address(last.line)]),
        Instruction(at + 4, JOIN, [leader]),
        Instruction(at + 6, SET_FLAG, [party_flag_of(leader)]),
        Instruction(at + 8, LEAVE, [MAXIM]),
        Instruction(at + 10, CLEAR_FLAG, [party_flag_of(MAXIM)]),
    ]
    index = script.instructions.index(last)
    script.instructions[index:index] = swap
    script.dirty = True
    MapEvent.from_index(int(OPENING[:2], 16)).write()


SWAP_OPCODES = (BRANCH_ON_FLAG, JOIN, SET_FLAG, LEAVE, CLEAR_FLAG, END)


def _existing_swap(script: EventScript) -> tuple[Instruction, Instruction, Instruction] | None:
    """The branch, join and set-flag instructions of a party swap that ends ``script``, if it has one."""
    tail = script.instructions[-len(SWAP_OPCODES) :]
    if tuple(instruction.opcode for instruction in tail) != SWAP_OPCODES:
        return None
    return tail[0], tail[1], tail[2]
