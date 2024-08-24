from dataclasses import dataclass
from structures.validator import PositiveValidator
from helpers.files import write_file

@dataclass
class RpgStats:
    health_points: PositiveValidator[int] = PositiveValidator[int](0)
    mana_points: PositiveValidator[int] = PositiveValidator[int](0)
    attack: PositiveValidator[int] = PositiveValidator[int](0)
    defense: PositiveValidator[int] = PositiveValidator[int](0)
    agility: PositiveValidator[int] = PositiveValidator[int](0)
    intelligence: PositiveValidator[int] = PositiveValidator[int](0)
    guts: PositiveValidator[int] = PositiveValidator[int](0)
    magic_resistance: PositiveValidator[int] = PositiveValidator[int](0)
    level: PositiveValidator[int] = PositiveValidator[int](0)
    xp: PositiveValidator[int] = PositiveValidator[int](0)
    gold: PositiveValidator[int] = PositiveValidator[int](0)

    def __bytes__(self):
        return (
            (self.health_points.to_bytes()) +
            (self.mana_points.to_bytes()) +
            (self.attack.to_bytes()) +
            (self.defense.to_bytes()) +
            (self.agility.to_bytes()) +
            (self.intelligence.to_bytes()) +
            (self.guts.to_bytes()) +
            (self.magic_resistance.to_bytes()) +
            (self.level.to_bytes()) +
            (self.xp.to_bytes()) +
            (self.gold.to_bytes())
        )

    def write(self, pointer: int):
        write_file.seek(pointer)
        write_file.write(bytes(self))


@dataclass
class ScalableRpgStats:
    health_points: PositiveValidator[float] = PositiveValidator[float](0)
    mana_points: PositiveValidator[float] = PositiveValidator[float](0)
    attack: PositiveValidator[float] = PositiveValidator[float](0)
    defense: PositiveValidator[float] = PositiveValidator[float](0)
    agility: PositiveValidator[float] = PositiveValidator[float](0)
    intelligence: PositiveValidator[float] = PositiveValidator[float](0)
    guts: PositiveValidator[float] = PositiveValidator[float](0)
    magic_resistance: PositiveValidator[float] = PositiveValidator[float](0)
    level: PositiveValidator[float] = PositiveValidator[float](0)
    xp: PositiveValidator[float] = PositiveValidator[float](0)
    gold: PositiveValidator[float] = PositiveValidator[float](0)

    def to_int(self) -> RpgStats:
        return RpgStats(
            int(self.health_points),
            int(self.mana_points),
            int(self.attack),
            int(self.defense),
            int(self.agility),
            int(self.intelligence),
            int(self.guts),
            int(self.magic_resistance),
            int(self.level),
            int(self.xp),
            int(self.gold),
        )

    def __bytes__(self):
        stats = self.to_int()
        return (
            (stats.health_points.to_bytes()) +
            (stats.mana_points.to_bytes()) +
            (stats.attack.to_bytes()) +
            (stats.defense.to_bytes()) +
            (stats.agility.to_bytes()) +
            (stats.intelligence.to_bytes()) +
            (stats.guts.to_bytes()) +
            (stats.level.to_bytes()) +
            (stats.xp.to_bytes()) +
            (stats.gold.to_bytes())
        )

    def write(self, pointer: int):
        write_file.seek(pointer)
        write_file.write(bytes(self))
