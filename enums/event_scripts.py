from enum import Enum


class EventClass(Enum):
    # See https://docs.google.com/document/d/e/2PACX-1vQ9Ag95-eO0IWKpVbh3f8WWRuTi6d7ukEI8Fs5bWyjzCOk9b4PjMUE1RZM7rIhEZlt8qFpCiukRShg4/pub
    # for reference of the marked letters.

    SETUP_MAP = 0   # X
    LOAD_MAP = 1    # A
    REFERENCED = 2  # B
    NPC = 3         # C
    TILE = 4        # D
    UNK_5 = 5       # E (undocumented)
    UNK_6 = 6       # D (undocumented)
    # 202 > ??
    NPC_SCRIPT = 7  # Custom identifier. Controls EventList Behavoir
