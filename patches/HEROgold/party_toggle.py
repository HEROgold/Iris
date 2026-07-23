"""Party join/leave toggle, built entirely with the ``structures.event_script`` subsystem.

Repurposes the seven townsperson NPCs Elcid already has (map ``0x03``, NPC slots ``0x50``-``0x58``)
into the seven playable characters. Talking to one shows dialogue and:

- if that character is **in** the party -> they **leave** ("X leaves the party.")
- else if they've been **found** (recruited in the story) -> they **join** ("X joins the party!")
- else -> nothing happens ("You haven't found X yet.")

Membership uses :attr:`PlayableCharacter.party_flag` (flags 1..7; note Tia/Dekar are *not* ``index + 1``).
"Found" uses :attr:`PlayableCharacter.found_flag` (new flags 242..248); the story scripts that recruit a
character set it too -- see ``patches.HEROgold.found_flags``. Each NPC's overworld sprite is swapped to the
character sprite via the existing ``0x68`` loads in the map-load (X) script (:meth:`Zone.set_npc_sprite`).

Why Elcid and not the tutorial cave: the event-script write path is **in-place only** (it does not
relocate or add scripts), and NPC *placement* (positions/actor slots) is map data, not event-script
data. So we cannot add new standing NPCs to a room -- we reuse a room that already has them. Each
replacement script (toggle logic + three short dialogue lines) still fits comfortably inside its original
talk-script slot (the smallest Elcid slot is 142 B); the write path enforces this and raises if a script
would overrun (see :meth:`EventScript.write`), so this patch no longer needs to hand-check lengths.

Softlock safety: removing the party's last member (or the field leader when the party would empty)
leaves no controllable character. The leave branch is therefore gated on an "any other member present?"
check, so the party can never drop to zero -- and because that check reads the live membership flags, it
works regardless of who the (randomizable) leader is. See :func:`_toggle`.

A hard 4-member *upper* cap is not enforced here: it would need a counter variable that is
guaranteed-free and initialised to the real starting party size, which isn't safe to inject in place
without risking save state. The active-party size is left to the game's own limit.
"""

from logger import iris
from structures.character import PlayableCharacter
from structures.event_script.codec import decode_text, encode_text
from structures.event_script.instructions import Address, Instruction, Operand
from structures.zone import Zone


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


# The seven playable characters are tracked by membership flags 1..7. The set is fixed (all seven flags);
# which flag belongs to which character is *not* simply index + 1 (Tia/Dekar are swapped) -- see
# ``PlayableCharacter.party_flag``. For the "any *other* member present?" guard we only need the set.
_MEMBER_FLAGS = tuple(range(1, 8))

# Symbolic line-number labels for the toggle's jump targets. Line numbers are labels only -- the compiler
# recomputes real byte offsets and snaps each ``Address`` to its target line -- so sequential integers are
# fine and we avoid the brittle byte-offset arithmetic the old fixed-length toggle needed.
_LEAVE = 3
_NOT_IN_PARTY = 7
_NOT_FOUND = 11


def _speech(line: int, message: str) -> Instruction:
    """Build a ``0x08`` ("the NPC you're talking to speaks") instruction from a Python string.

    Mirrors the dump importer (``dump.py``): round-trip ``message`` through the text codec to obtain the
    ``list[TextChunk]`` operand. ``message`` must end with ``<END EVENT>`` so the box closes and the
    script terminates (``0x00``).
    """
    raw = encode_text(message, compress=True)
    chunks, _ = decode_text(0x08, raw, b"", b"")
    return Instruction(line, 0x08, [chunks])


def _toggle(character: PlayableCharacter) -> list[Instruction]:
    """A three-way join/leave/"not found" toggle with dialogue that refuses to remove the last member.

    Membership is checked first, so anyone currently in the party (including whoever the randomizer starts
    you as) always reaches the LEAVE branch; the "found" flag is consulted only when the character is *not*
    in the party. The LEAVE branch also *sets* the found flag: being in the party proves the character was
    met, so recording it on the way out makes re-adding work regardless of who the starter is.

    Removing the last party member softlocks the game, so LEAVE is gated on an ``0x14`` "any *other* member
    present?" check -- leader-agnostic, since it reads the live membership flags.

    ``6A(party_flag -> NOT_IN_PARTY)``            not in party -> go check "found"
    ``14(OR of other flags -> LEAVE)``            in party: leave only if another member is present
    ``00``                                        otherwise (last member): stay
    ``LEAVE: 2C; 1B(party_flag); 1A(found); 08``  leave, clear membership, mark found, "X leaves the party."
    ``NOT_IN_PARTY: 6A(found -> NOT_FOUND)``       not yet discovered -> "not found" message
    ``2B; 1A(party_flag); 08``                    JOIN: join, set membership, "X joins the party!"
    ``NOT_FOUND: 08``                             "You haven't found X yet."
    """
    flag = character.party_flag
    found = character.found_flag
    name = character.name
    others = [f for f in _MEMBER_FLAGS if f != flag]

    # 0x14 chain: (other0 set) OR (other1 set) OR ... -> branch-if-true to LEAVE.
    # 0x00 = first flag, 0x40 = OR flag, 0x20 = branch-if-true, 0xFF = end of chain.
    chain: list[Operand] = [0x00, others[0]]
    for other in others[1:]:
        chain += [0x40, other]
    chain += [0x20, Address(_LEAVE), 0xFF]

    return [
        Instruction(0, 0x6A, [flag, Address(_NOT_IN_PARTY)]),  # in party? no -> NOT_IN_PARTY
        Instruction(1, 0x14, chain),                           # in party: leave only if another remains
        Instruction(2, 0x00, []),                              # last member: stay
        # LEAVE:
        Instruction(_LEAVE, 0x2C, [character.index]),          # leave party
        Instruction(4, 0x1B, [flag]),                          # clear membership flag
        Instruction(5, 0x1A, [found]),                         # mark found (randomized-starter safe)
        _speech(6, f"{name} leaves the party.<END EVENT>"),
        # NOT_IN_PARTY:
        Instruction(_NOT_IN_PARTY, 0x6A, [found, Address(_NOT_FOUND)]),  # found? no -> NOT_FOUND
        Instruction(8, 0x2B, [character.index]),               # JOIN: join party
        Instruction(9, 0x1A, [flag]),                          # set membership flag
        _speech(10, f"{name} joins the party!<END EVENT>"),
        # NOT_FOUND:
        _speech(_NOT_FOUND, f"You haven't found {name} yet.<END EVENT>"),
    ]


def party_toggle_in_elcid() -> None:
    """Turn Elcid's townspeople into join/leave toggles for the seven playable characters.

    Callsite order no longer matters: the write path only persists the scripts this patch marks dirty
    and leaves the rest of the ROM untouched, so it neither depends on running before Zone generation
    nor clobbers other patches.
    """
    iris.info("Building party join/leave toggle in Elcid (map 0x03).")
    zone = Zone.from_name("Elcid")

    for slot, index in _SLOT_TO_CHARACTER.items():
        character = PlayableCharacter.from_index(index)
        zone.set_npc_sprite(slot, character.overworld_sprite)  # swap overworld sprite (0x68 load)
        script = zone.referenced_script(slot)                  # talk script index == NPC slot
        script.instructions = _toggle(character)
        script.dirty = True
        iris.info(f"  slot {slot:#04x} {character.name} -> join/leave toggle.")

    zone.write_events()
    iris.info("Party toggle applied.")
