"""Party join/leave toggle, built entirely with the ``structures.event_script`` subsystem.

Repurposes the seven townsperson NPCs Elcid already has (map ``0x03``, NPC slots ``0x50``-``0x58``)
into the seven playable characters. Talking to one:

- if that character is **in** the party (membership flag set) -> they **leave** (``2C`` + clear flag)
- otherwise                                                    -> they **join**  (``2B`` + set flag)

Membership uses the vanilla convention ``flag == character_index + 1`` (proved in the base game, e.g.
``6A(07 ...)`` gating Lexis dialogue), exposed as :attr:`PlayableCharacter.party_flag`. Each NPC's
overworld sprite is swapped to the character sprite via the existing ``0x68`` loads in the map-load (X)
script (:meth:`Zone.set_npc_sprite`).

Why Elcid and not the tutorial cave: the event-script write path is **in-place only** (it does not
relocate or add scripts), and NPC *placement* (positions/actor slots) is map data, not event-script
data. So we cannot add new standing NPCs to a room -- we reuse a room that already has them. Every
replacement script (32 bytes) is shorter than the original talk script, so it fits its slot; the write
path enforces this and raises if a script would overrun (see :meth:`EventScript.write`), so this patch
no longer needs to hand-check lengths or diff the ROM.

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
    flag = character.party_flag
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
