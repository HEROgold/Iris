"""Set each character's "found/unlocked" flag wherever the story recruits them.

Companion to :mod:`patches.HEROgold.party_toggle`. The toggle gates joining on a per-character *found*
flag (``EventFlag.FOUND_*``, 242-248 -- see :attr:`PlayableCharacter.found_flag`). For that gate to track
normal progression, every event script that adds a party member (a ``2B`` "character joins" opcode) must
also *set* that character's found flag. This patch scans every map's event scripts and, right after each
``2B(idx)`` for a playable character (index 0-6), inserts a ``1A(found_flag)``. The flag is never cleared,
so a character who later leaves in the story stays "found" -- exactly the behaviour we want.

Inserting is safe with the in-place-only write path: we only *add* instructions, so every original line
label (and therefore every jump target) still exists and still resolves; a ``2B`` is two bytes, so
``line + 1`` is always a free label between it and the next instruction. The only hard constraint is the
original slot size -- a rewritten script must still fit ``len(script.raw)``. We compile-check each edited
script and, if it would overrun, **revert that script and skip it** (never corrupting the ROM).

Current reality (important): in-place growth is effectively **impossible** for the existing story-join
scripts, so this pass patches *zero* of them today and is retained as a safe, self-documenting no-op. Two
independent reasons: (1) the join scripts are packed to the byte (recompiling equals the original size, no
room for +2), and (2) dialogue-heavy scripts *inflate* on recompile because the text codec's ``0x0A``
``<REPEAT>`` back-references decode to literal bytes but ``encode_text`` re-compresses them less tightly.
Growing a script therefore requires **relocation**, and the only tracked free space (``EMPTY_BYTES`` at
``0x286a10``+) is unreachable via the 16-bit event-list offset (a script must sit within 64 KB of its map's
event-list block near ``0x3xxxx``; the event bank itself has ~156 free bytes total). Making this work needs
a **per-map event-container relocator** (move the whole ``PH`` block + tables + scripts to the far pool and
repoint the map record) -- see ``docs/event_script_write_path.md``. That is deliberately a
separate future spike (it can only be validated in an emulator).

Because the toggle checks membership *before* "found" and the LEAVE branch sets the found flag when you
remove an in-party character, the practical gap from this no-op is narrow: a character recruited in the
story, then removed *by the story*, whom you never toggled -- their toggle shows "not found" until they are
re-recruited or the relocator lands.
"""

from enums.flags import EventFlag
from logger import iris
from structures.event_script.compiler import compile_script
from structures.event_script.containers import MapEvent
from structures.event_script.instructions import Instruction
from structures.event_script.script import EventScript
from tables import MapEventObject


# ``2B`` operand values that are playable characters (Maxim=0 .. Lexis=6). The randomizer may reassign
# which character appears at a given story slot, so we cover all seven rather than skipping Maxim.
_CHARACTER_INDICES = frozenset(range(7))

_JOIN = 0x2B  # character joins the party
_SET_FLAG = 0x1A  # set event bit
_FOUND_BASE = int(EventFlag.FOUND_MAXIM)  # found flag == 242 + character index


def _found_flag(character_index: int) -> int:
    return _FOUND_BASE + character_index


# _inject outcomes.
_APPLIED = "applied"  # a fitting found-flag set was inserted; script marked dirty
_UNCHANGED = "unchanged"  # no playable join, or every join already sets its found flag
_TOO_BIG = "too_big"  # a join needs a found flag but the insertion would overrun the slot


def _inject(script: EventScript) -> str:
    """Insert ``1A(found_flag)`` after each playable ``2B`` in ``script``; revert if it won't fit.

    Returns :data:`_APPLIED` (and marks the script dirty), :data:`_UNCHANGED`, or :data:`_TOO_BIG`.
    """
    original = script.instructions
    rebuilt: list[Instruction] = []
    changed = False
    for position, instruction in enumerate(original):
        rebuilt.append(instruction)
        if instruction.opcode != _JOIN or not instruction.operands:
            continue
        character_index = instruction.operands[0]
        if character_index not in _CHARACTER_INDICES:
            continue
        found = _found_flag(character_index)
        following = original[position + 1] if position + 1 < len(original) else None
        if following is not None and following.opcode == _SET_FLAG and following.operands and following.operands[0] == found:
            continue  # already sets this found flag (e.g. a previous run)
        rebuilt.append(Instruction(instruction.line + 1, _SET_FLAG, [found]))
        changed = True

    if not changed:
        return _UNCHANGED

    script.instructions = rebuilt
    try:
        data = compile_script(script, ignore_pointers=True)
    except ValueError:
        script.instructions = original
        return _TOO_BIG
    if len(data) > len(script.raw):
        script.instructions = original
        return _TOO_BIG
    script.dirty = True
    return _APPLIED


def set_found_flags_on_story_joins() -> None:
    """Set every character's found flag wherever the story adds them to the party."""
    iris.info("Propagating 'found' flags to story party-join scripts.")
    patched = 0
    skipped = 0
    for index in range(MapEventObject.count):
        map_event = MapEvent.from_index(index)
        map_event.read()
        map_changed = False
        for event_list in map_event.event_lists:
            for script in event_list.events:
                outcome = _inject(script)
                if outcome == _APPLIED:
                    patched += 1
                    map_changed = True
                elif outcome == _TOO_BIG:
                    skipped += 1
                    iris.debug(
                        f"  script {script.pointer:#07x} (map {index:#04x}) has a party join but no room "
                        f"for its found flag ({len(script.raw)}B slot); skipped."
                    )
        if map_changed:
            map_event.write()
    iris.info(f"Found flags: {patched} join script(s) patched, {skipped} skipped for size (need relocator).")
    if skipped and not patched:
        iris.info(
            "Found-flag propagation is a no-op until the per-map event relocator lands "
            "(see docs/event_script_write_path.md). The toggle still self-marks 'found' "
            "when you remove an in-party character."
        )
