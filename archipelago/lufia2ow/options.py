"""Options. The goal is fixed (defeat Daos) until Iris-Dev#33 adds the rest."""

from dataclasses import dataclass

from Options import PerGameCommonOptions


@dataclass
class L2OWOptions(PerGameCommonOptions):
    pass
