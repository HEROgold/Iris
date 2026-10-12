"""L2BASM: the battle/AI script language. See scripting.l2basm.opcodes, parser, records, edit and helpers."""

from iris.scripting.l2basm.opcodes import L2BASM
from iris.scripting.l2basm.parser import ParsedRecord, parse_record


__all__ = ["L2BASM", "ParsedRecord", "parse_record"]
