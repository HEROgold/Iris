"""Dialogue text codec: decode a raw text stream into chunks/strings and encode it back.

The event-text scheme is a dictionary + back-reference compression, **not** the generic 9-bit LZW in
``helpers/lempel_ziv.py`` (do not use that here). Words come from the :class:`Word` table; the
``0x0A`` ``<REPEAT>`` code is an LZ-style back-reference into a sliding window.
"""

import logging
import re
from collections import defaultdict

from logger import iris
from structures.event_script.instructions import TextChunk
from structures.event_script.opcodes import EXIT_TEXT_MODE, VALID_ASCII_CHARACTERS
from structures.word import Word
from tables import WordObject


log = logging.getLogger(f"{iris.name}.EventScript.Codec")


# Text-mode metadata (mirrors terrorwave ``MapEventObject``).
TEXT_TERMINATORS = set(EXIT_TEXT_MODE)  # {0x00, 0x01, 0x0B}
TEXT_PARAMETERS = {0x04: 1, 0x05: 1, 0x06: 1, 0x0A: 2}
CHARACTER_MAP = {
    0x00: "<END EVENT>",
    0x01: "<END MESSAGE>",
    0x03: "\n",
    0x04: "<PAUSE>",
    0x09: "$MAXIM$",
    0x0A: "<REPEAT>",
    0x0B: "<CHOICE>",
    0x0C: "?\n",
    0x0D: "!\n",
    0x0E: ",\n",
    0x0F: ".\n",
}
REVERSE_CHARACTER_MAP = {v: k for k, v in CHARACTER_MAP.items()}
TAG_MATCHER = re.compile("<([^>]*) ([^> ]*)>")

# The window preceding a script that ``<REPEAT>`` can point back into.
PRE_DATA_SIZE = 0x1000

# Word dictionary page bases (see 03_text_codec.md).
WORD_PAGE_05 = 0x000
WORD_PAGE_06 = 0x100
WORD_PAGE_HIGH = 0x200


def _hexify(data: bytes) -> str:
    return "-".join(f"{b:02X}" for b in data)


def _word(index: int) -> str:
    return Word.from_index(index).word


def decode_text(
    opcode: int,
    data: bytes,
    full_data: bytes,
    pre_data: bytes,
) -> tuple[list[TextChunk], bytes]:
    """Decode a text stream beginning after ``opcode`` in ``data``.

    ``full_data`` is the entire script byte string (needed to size the ``<REPEAT>`` window) and
    ``pre_data`` is the ``0x1000`` bytes preceding the script. Returns the decoded chunks and the
    remaining (unconsumed) bytes.
    """
    chunks: list[TextChunk] = []
    if opcode == 0x13:
        chunks.append(TextChunk("NPC", data[:1]))
        data = data[1:]
    elif opcode in {0x6D, 0x6E}:
        chunks.append(TextChunk("POSITION", data[:2]))
        data = data[2:]
    elif opcode == 0x9E:
        chunks.append(TextChunk("POSITION", data[:1]))
        data = data[1:]
    chunks.append(TextChunk(None, b""))

    while True:
        if not data:
            break
        textcode, data = data[0], data[1:]

        if textcode in TEXT_TERMINATORS:
            chunks.append(TextChunk(textcode, b""))
            break
        if textcode == 0x0A:
            size = TEXT_PARAMETERS[textcode]
            params, data = data[:size], data[size:]
            value = int.from_bytes(params, "little")
            length = (value >> 12) + 2
            pointer = (value & 0x0FFF) + 2
            consumed = full_data[: len(full_data) - len(data)]
            buffer = pre_data + consumed
            index = len(buffer) - pointer
            repeat = buffer[index : index + length] if index >= 0 else b""
            chunks.append(TextChunk(None, repeat))
        elif textcode in TEXT_PARAMETERS:
            size = TEXT_PARAMETERS[textcode]
            params, data = data[:size], data[size:]
            chunks.append(TextChunk(textcode, params))
        else:
            if chunks[-1].tag is not None:
                chunks.append(TextChunk(None, b""))
            chunks[-1].data += bytes([textcode])

    chunks = [c for c in chunks if c.data or c.tag is not None]
    return chunks, data


def render_text(chunks: list[TextChunk]) -> str:
    """Render decoded chunks into the dump's human-readable text form."""
    out = ""
    for chunk in chunks:
        tag, data = chunk.tag, chunk.data
        if tag in {0x05, 0x06}:
            index = data[0] + (WORD_PAGE_06 if tag == 0x06 else WORD_PAGE_05)
            out += _word(index)
        elif isinstance(tag, int) and tag in TEXT_TERMINATORS:
            out += CHARACTER_MAP.get(tag, "<END MESSAGE>")
        elif tag == "NPC":
            out += f"<VOICE {_hexify(data)}>"
        elif tag == "POSITION":
            out += f"<POSITION {_hexify(data)}>"
        elif tag is None:
            for c in data:
                if c in CHARACTER_MAP:
                    out += CHARACTER_MAP[c]
                elif c & 0x80:
                    try:
                        out += _word((c & 0x7F) + WORD_PAGE_HIGH)
                    except (KeyError, IndexError, ValueError):
                        out += f"<{c:02X}>"
                elif chr(c) in VALID_ASCII_CHARACTERS:
                    out += chr(c)
                else:
                    out += f"<{c:02X}>"
        elif tag in CHARACTER_MAP:
            sub = CHARACTER_MAP[tag]
            if data:
                sub = f"{sub.rstrip('>')} {_hexify(data)}>"
            out += sub
        else:
            msg = f"Unhandled text tag {tag!r}."
            raise ValueError(msg)
    return out


class _WordCompressor:
    """Lazily-built reverse dictionary for greedy longest-word-first text compression."""

    def __init__(self) -> None:
        self._by_length: dict[int, dict[str, list[tuple[str, int]]]] | None = None

    def _build(self) -> dict[int, dict[str, list[tuple[str, int]]]]:
        by_length: dict[int, dict[str, list[tuple[str, int]]]] = defaultdict(lambda: defaultdict(list))
        for index in range(WordObject.count):
            word = _word(index)
            if not word:
                continue
            by_length[len(word)][word[0]].append((word, index))
        for length in by_length:
            for first in by_length[length]:
                by_length[length][first].sort()
        return by_length

    @property
    def by_length(self) -> dict[int, dict[str, list[tuple[str, int]]]]:
        if self._by_length is None:
            self._by_length = self._build()
        return self._by_length

    @staticmethod
    def _encode_index(index: int) -> str:
        if index >= WORD_PAGE_HIGH:
            return "\x01" + chr(0x80 | (index - WORD_PAGE_HIGH))
        if index >= WORD_PAGE_06:
            return "\x01\x06" + chr(index - WORD_PAGE_06)
        return "\x01\x05" + chr(index)

    def compress(self, message: str) -> list[str]:
        """Return ``message`` split into a list of literal runs and ``\\x01``-prefixed word tokens.

        The split ``marker`` must be a non-byte sentinel: word-index bytes can be ``0x00``, so using
        a real byte here would slice a token apart.
        """
        marker = "￿"
        uncompressed = message
        raw = message
        target = len(uncompressed)
        for length in sorted(self.by_length, reverse=True):
            if length > target:
                continue
            head = raw[: (target - length) + 1]
            for first in sorted(set(head)):
                if first not in self.by_length[length]:
                    continue
                for word, index in self.by_length[length][first]:
                    if word in uncompressed:
                        replacement = marker + self._encode_index(index) + marker
                        message = message.replace(word, replacement)
                        uncompressed = uncompressed.replace(word, marker)
                        raw = uncompressed.replace(marker, "")
                        target = len(raw)
                        if length > target:
                            break
        return [m for m in message.split(marker) if m]


_compressor = _WordCompressor()


def _split_once(part: str, reverse_keys: list[str], *, compress: bool) -> list[str | int] | None:
    """Split one literal ``part`` at the first control code, ``<TAG X-Y>``, or compressible word.

    Returns the replacement fragments, or ``None`` if ``part`` cannot be reduced further.
    """
    if len(part) == 2 and part[0] in "\x05\x06":
        return None
    for key in reverse_keys:
        if key in part:
            left, right = part.split(key, 1)
            return [left, REVERSE_CHARACTER_MAP[key], right]
    match = TAG_MATCHER.search(part)
    if match:
        key = match.group(0)
        values: list[str | int] = [int(v, 0x10) for v in match.group(2).split("-")]
        label = f"<{match.group(1)}>"
        if label in REVERSE_CHARACTER_MAP:
            values.insert(0, REVERSE_CHARACTER_MAP[label])
        left, right = part.split(key, 1)
        return [left, *values, right]
    if not compress:
        return None
    compressed = _compressor.compress(part)
    if len(compressed) == 1 and compressed[0] == part:
        return None
    expanded: list[str | int] = []
    for token in compressed:
        if token.startswith("\x01"):
            expanded.extend(ord(c) for c in token[1:])
        else:
            expanded.append(token)
    return expanded


def encode_text(message: str, *, compress: bool = True) -> bytes:
    """Turn a rendered text string back into the raw byte stream (including its terminator).

    Mirrors terrorwave's ``reverse_prettify_text``: split out control codes and ``<TAG X-Y>`` first,
    then (optionally) apply dictionary compression to the remaining literal runs.
    """
    reverse_keys = sorted(REVERSE_CHARACTER_MAP, key=lambda k: (-len(k), k))
    parts: list[str | int] = [message]
    changed = True
    while changed:
        changed = False
        for i, part in list(enumerate(parts)):
            if not isinstance(part, str) or not part:
                continue
            replacement = _split_once(part, reverse_keys, compress=compress)
            if replacement is None:
                continue
            parts = parts[:i] + replacement + parts[i + 1 :]
            changed = True
            break

    flat: list[int] = []
    for part in parts:
        if isinstance(part, int):
            flat.append(part)
        elif part:
            flat.extend(ord(c) for c in part)
    return bytes(flat)
