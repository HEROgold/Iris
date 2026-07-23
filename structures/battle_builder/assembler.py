"""Two-pass assembler: resolve a :class:`Node` tree's labels and write the bytes into a script.

Pass 1 records every :class:`Label`'s byte position; pass 2 emits the bytes, replacing each
:class:`Ref` with a 2-byte little-endian, record-relative value ``script.offset + position(label)`` --
exactly the jump encoding L2BASM uses (``monster.pointer + offset``) and the same scheme as
``structures/event_script/compiler.py``.
"""

from typing import TYPE_CHECKING

from structures.battle_builder.nodes import Label, Node, Ref, Token


if TYPE_CHECKING:
    from structures.battlescript import BattleScript


def _token_width(token: Token) -> int:
    if isinstance(token, Label):
        return 0
    if isinstance(token, Ref):
        return 2
    return 1


def _ends_in_end(tokens: list[Token]) -> bool:
    for token in reversed(tokens):
        if isinstance(token, Label):
            continue
        return token == 0x00
    return False


def _label_positions(tokens: list[Token]) -> dict[str, int]:
    """Pass 1: byte position of each label (Labels are zero-width; Refs are 2 bytes)."""
    positions: dict[str, int] = {}
    running = 0
    for token in tokens:
        if isinstance(token, Label):
            if token.name in positions:
                msg = f"Duplicate label: {token.name!r}"
                raise ValueError(msg)
            positions[token.name] = running
        running += _token_width(token)
    return positions


def assemble(script: "BattleScript", root: Node, *, max_size: int | None = None) -> bytes:
    """Emit ``root``'s bytecode for ``script``, resolving every label to a record-relative offset."""
    tokens = root.emit()
    if not _ends_in_end(tokens):
        tokens.append(0x00)  # guarantee a terminating END

    positions = _label_positions(tokens)
    out = bytearray()
    for token in tokens:
        if isinstance(token, Label):
            continue
        if isinstance(token, Ref):
            if token.name not in positions:
                msg = f"Undefined label: {token.name!r}"
                raise ValueError(msg)
            value = script.offset + positions[token.name]
            if not 0 <= value <= 0xFFFF:
                msg = f"Resolved jump out of range: {value:#x}"
                raise ValueError(msg)
            out.append(value & 0xFF)
            out.append(value >> 8)
        else:
            out.append(token & 0xFF)

    if max_size is not None and len(out) > max_size:
        msg = f"Assembled script is {len(out)} bytes, exceeds in-place footprint {max_size}."
        raise ValueError(msg)
    return bytes(out)


def apply(script: "BattleScript", root: Node, *, max_size: int | None = None) -> None:
    """Assemble ``root`` and write it into ``script`` in place, then re-read to round-trip verify.

    Writes the :class:`BattleScript` directly (never ``CapsuleMonster.write()``, which does not persist
    script bytecode and reroutes the reaction offset through the ``stats.mana_points`` hack).
    """
    script.bytecode = assemble(script, root, max_size=max_size)
    script.write()
    script.read()
