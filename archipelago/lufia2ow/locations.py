"""Locations: the 171 red chests, named from guides (Iris structures/chest_names.py). id = BASE_ID + chest index.

Script grants (Iris-Dev#22) and Ancient Cave blue chests (#21) come later.
"""

from BaseClasses import Location

from . import data
from .items import BASE_ID, GAME

CHESTS = {chest[0]: chest for chest in data.CHESTS}
location_name_to_id = {name: BASE_ID + index for index, _, name, *_ in data.CHESTS}
VICTORY = "Defeat Daos"


class L2OWLocation(Location):
    game = GAME
