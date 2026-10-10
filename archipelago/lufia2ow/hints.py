"""Hint NPCs: their new talk script, written over the old one in place (data.HINT_NPCS, Iris hint_npcs.py).

Script: ``1A(flag)``, then text boxes ``08 <text> 01`` with the last ending in ``00`` (END EVENT); the rest of the old
script's slot is zero. Text is plain ASCII (the game's font for 0x20-0x7E); line breaks are 0x03. A box holds three
lines of up to 24 characters (vanilla boxes are 26 wide and up to four lines).
"""

import re


SET_FLAG, TEXT, NEWLINE, END_MESSAGE, END_EVENT = 0x1A, 0x08, 0x03, 0x01, 0x00
LINE_WIDTH = 24
BOX_LINES = 3
_UNSAFE = re.compile(r"[^A-Za-z0-9 .,!?'\-:()&/]")
"""Characters outside the set vanilla text uses; replaced with a space."""


def clean(text: str) -> str:
    return re.sub(r" +", " ", _UNSAFE.sub(" ", text)).strip()


def _lines(text: str) -> list[str]:
    """Greedy word wrap; a word longer than a line is cut."""
    lines: list[str] = []
    for word in text.split(" "):
        rest = word
        while len(rest) > LINE_WIDTH:
            lines.append(rest[:LINE_WIDTH])
            rest = rest[LINE_WIDTH:]
        if lines and len(lines[-1]) + 1 + len(rest) <= LINE_WIDTH:
            lines[-1] += " " + rest
        else:
            lines.append(rest)
    return lines


def script(flag: int, text: str) -> bytes:
    """The talk script: set ``flag``, then ``text`` in boxes."""
    lines = _lines(clean(text))
    boxes = [lines[i : i + BOX_LINES] for i in range(0, len(lines), BOX_LINES)]
    out = bytearray([SET_FLAG, flag])
    for number, box in enumerate(boxes):
        out.append(TEXT)
        out += bytes([NEWLINE]).join(line.encode("ascii") for line in box)
        out.append(END_EVENT if number == len(boxes) - 1 else END_MESSAGE)
    return bytes(out)


def fitted(flag: int, texts: list[str], size: int) -> bytes:
    """The first of ``texts`` (longest to shortest) whose script fits ``size`` bytes, zero-padded to it."""
    for text in texts:
        data = script(flag, text)
        if len(data) <= size:
            return data.ljust(size, b"\0")
    data = script(flag, texts[-1])[: size - 1] + bytes([END_EVENT])
    return data.ljust(size, b"\0")
