from enum import Enum, auto


class EventClass(Enum):
    # TODO: use the assigned byte values from the rom.
    SETUP_MAP = auto() # "X",
    MAP_LOAD = auto() # "A",
    REFERENCED = auto() # "B",
    NPC = auto() # "C",
    TILE = auto() # "D"
