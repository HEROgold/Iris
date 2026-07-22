"""Party join/leave toggle, built entirely with the ``structures.event_script`` subsystem.

Repurposes the seven townsperson NPCs Elcid already has (map ``0x03``, NPC slots ``0x50``-``0x58``)
into the seven playable characters. Talking to one:

- if that character is **in** the party (membership flag set) -> they **leave** (``2C`` + clear flag)
- otherwise                                                    -> they **join**  (``2B`` + set flag)

Membership uses the vanilla convention ``flag == character_index + 1`` (proved in the base game, e.g.
``6A(07 ...)`` gating Lexis dialogue). Each NPC's overworld sprite is swapped to the character sprite
via the existing ``0x68`` loads in the map-load (X) script.

Why Elcid and not the tutorial cave: the event-script write path is **in-place only** (it does not
relocate or add scripts), and NPC *placement* (positions/actor slots) is map data, not event-script
data. So we cannot add new standing NPCs to a room -- we reuse a room that already has them. Every
replacement script (32 bytes) is shorter than the original talk script, so the write stays inside the
original byte range and never disturbs a neighbouring script.

Softlock safety: removing the party's last member (or the field leader when the party would empty)
leaves no controllable character. The leave branch is therefore gated on an "any other member present?"
check, so the party can never drop to zero -- and because that check reads the live membership flags, it
works regardless of who the (randomizable) leader is. See :func:`_toggle`.

A hard 4-member *upper* cap is not enforced here: it would need a counter variable that is
guaranteed-free and initialised to the real starting party size, which isn't safe to inject in place
without risking save state. The active-party size is left to the game's own limit.
"""

from enums.event_scripts import EventClass
from helpers.files import write_file
from logger import iris
from structures.character import PlayableCharacter
from structures.event_script import MapEvent
from structures.event_script.compiler import compile_script
from structures.event_script.instructions import Address, Instruction, Operand


ELCID = 0x03

# Elcid (map 0x03) NPC slot -> playable-character index. The overworld sprite index equals the
# character index, and the party-membership flag equals the character index + 1.
_SLOT_TO_CHARACTER: dict[int, int] = {
    0x50: 0,  # Maxim
    0x51: 1,  # Selan
    0x52: 2,  # Guy
    0x53: 3,  # Artea
    0x56: 4,  # Tia
    0x57: 5,  # Dekar
    0x58: 6,  # Lexis
}


# The seven playable characters are tracked by membership flags 1..7 (flag == character index + 1).
_MEMBER_FLAGS = tuple(range(1, 8))


def _toggle(character: PlayableCharacter) -> list[Instruction]:
    """A 32-byte join/leave toggle that refuses to remove the party's last member.

    Removing the last party member (or the field leader when the party would empty) softlocks the
    game. Rather than assume who the leader is -- this is a randomizer, so it may not be Maxim -- the
    leave branch is gated on an ``0x14`` "any other member present?" check: a character may only leave
    while at least one *other* membership flag is set. The party can therefore never drop to zero,
    whoever the leader is.

    ``6A(flag -> JOIN)``                       if this character is not in the party, jump to JOIN
    ``14(OR of the other six flags -> LEAVE)`` in party: leave only if another member is present
    ``00``                                     otherwise (this is the last member): stay, do nothing
    ``LEAVE: 2C(character); 1B(flag); 00``     leave the party and clear the membership flag
    ``JOIN:  2B(character); 1A(flag); 00``     join the party and set the membership flag
    """
    flag = character.index + 1
    others = [f for f in _MEMBER_FLAGS if f != flag]

    # 0x14 chain: (other0 set) OR (other1 set) OR ... -> branch-if-true to LEAVE (line 0x16).
    # 0x00 = first flag, 0x40 = OR flag, 0x20 = branch-if-true, 0xFF = end of chain.
    chain: list[Operand] = [0x00, others[0]]
    for other in others[1:]:
        chain += [0x40, other]
    chain += [0x20, Address(0x0016), 0xFF]

    return [
        Instruction(0x0000, 0x6A, [flag, Address(0x001B)]),  # not in party -> JOIN
        Instruction(0x0004, 0x14, chain),                    # in party: leave only if another remains
        Instruction(0x0015, 0x00, []),                       # last member: stay
        Instruction(0x0016, 0x2C, [character.index]),        # LEAVE: leave party
        Instruction(0x0018, 0x1B, [flag]),                   # clear membership flag
        Instruction(0x001A, 0x00, []),                       # end
        Instruction(0x001B, 0x2B, [character.index]),        # JOIN: join party
        Instruction(0x001D, 0x1A, [flag]),                   # set membership flag
        Instruction(0x001F, 0x00, []),                       # end
    ]


def party_toggle_in_elcid() -> None:
    """Turn Elcid's townspeople into join/leave toggles for the seven playable characters."""
    # FIXME:
    # Required to be ran before Zone's are generated?
    # Identify that's the real cause, and fix it.
    # (Should always be able to edit scripts of a zone, using read() and write() to properly place it's code.)
    # We should avoid using compile_script here, and instead make it such that
    # Zone.by_name("Elcid") returns the Zone object
    # We should then edit that zone object, such that the MapEvent, MapEvent.event_lists, and MapEvent.event_lists.events are all properly updated
    # and automatically written to the correct location in the ROM when MapEvent.write() is called.
    # When that's properly set up and linked
    # the sanity check is also not needed.
    #
    # Preferably, we even have helpers that help us easily objectify characters,
    # and how we can interact/edit them and their relative script.
    iris.info("Building party join/leave toggle in Elcid (map 0x03).")
    event = MapEvent.from_index(ELCID)
    characters: dict[Operand, PlayableCharacter] = {slot: PlayableCharacter.from_index(index) for slot, index in _SLOT_TO_CHARACTER.items()}

    # 1) Swap NPC sprites in the map-load (X) script. Same length -> safe in place.
    npc_script = event.npc_script
    npc_length = len(npc_script.raw)
    for instruction in npc_script.instructions:
        if instruction.opcode == 0x68 and instruction.operands[0] in characters:
            instruction.operands[1] = characters[instruction.operands[0]].index  # sprite index == character index
    npc_script.dirty = True
    assert len(compile_script(npc_script, script_pointer=npc_script.pointer)) == npc_length, (
        "map-load script changed length; refusing to overrun the following script"
    )

    # 2) Replace each townspeople talk script with the toggle. Must stay <= original length.
    talk_list = next(el for el in event.event_lists if el.event_class is EventClass.REFERENCED)
    for script in talk_list.events:
        if script.index not in characters:
            continue
        character = characters[script.index]
        original_length = len(script.raw)
        script.instructions = _toggle(character)
        script.dirty = True
        emitted = compile_script(script, script_pointer=script.pointer)
        assert len(emitted) <= original_length, (
            f"toggle for {character.name} ({len(emitted)}B) exceeds original script ({original_length}B)"
        )
        iris.info(f"  slot {script.index:#04x} {character.name} -> {len(emitted)}B toggle (from {original_length}B).")

    # 3) Sanity-check that *our* write is confined to the edited scripts, then persist the map.
    # Snapshot the working ROM immediately before/after our write so earlier patches don't count.
    write_file.seek(0)
    before = write_file.read()
    event.write()
    write_file.flush()
    write_file.seek(0)
    after = write_file.read()

    allowed = set(range(npc_script.pointer, npc_script.pointer + npc_length))
    for script in talk_list.events:
        if script.index in characters:
            allowed.update(range(script.pointer, script.pointer + len(script.raw)))
    stray = [i for i in range(len(before)) if before[i] != after[i] and i not in allowed]
    assert not stray, f"patch touched bytes outside the edited scripts: {[hex(i) for i in stray[:8]]}"
    iris.info("Party toggle applied; all changes confined to the edited scripts.")
