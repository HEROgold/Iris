class CompatibilityError(Exception):
    pass


class AlreadyScaledError(Exception):
    pass

class NotScaledError(Exception):
    pass


class SpellNotFound(Exception):
    pass


class FileEntryReadException(Exception):
    pass


class EventFreeSpaceError(Exception):
    pass


class ScriptAssemblyError(ValueError):
    """A script can't be assembled: undefined or duplicate label, operand out of range, or too large."""


class ScriptDecodeError(ValueError):
    """Bytes can't be decoded as an operand (for example, the data ends mid-operand)."""
