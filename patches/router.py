"""
Refer to https://github.com/dkolke/lufia2r-webtracker/blob/main/data/locations.json
Also look at what we've got at the Archipelago implementation.
"""

from enum import Enum

from structures.item import Item
from structures.zone import Zone
from tables.zones import ZoneObject


class KeyItems(Enum):
    HOOK            = 423
    BOMB            = 424
    ARROW           = 425
    FIRE_ARROW      = 426
    HAMMER          = 427
    TREASURE_SWORD  = 428
    DOOR_KEY        = 429
    SHRINE_KEY      = 430
    SKY_KEY         = 431
    LAKE_KEY        = 432
    RUBY_KEY        = 433
    WIND_KEY        = 434
    CLOUD_KEY       = 435
    LIGHT_KEY       = 436
    SWORD_KEY       = 437
    TREE_KEY        = 438
    FLOWER_KEY      = 439
    MAGMA_KEY       = 440
    HEART_KEY       = 441
    GHOST_KEY       = 442
    TRIAL_KEY       = 443
    DANKIRK_KEY     = 444
    BASEMENT_KEY    = 445
    NARCYSUS_KEY    = 446
    TRUTH_KEY       = 447
    MERMAID_JADE    = 448 # Submarine
    ENGINE          = 449 # Air ship
    ANCIENT_KEY     = 450
    PRETTY_FLOWER   = 451
    GLASS_ANGEL     = 452
    VIP_CARD        = 453
    KEY26           = 454
    KEY27           = 455
    KEY28           = 456
    KEY29           = 457
    KEY30           = 458
    CROWN           = 459
    RUBY_APPLE      = 460
    PURIFIA         = 461
    TAG_RING1       = 462
    TAG_RING2       = 463
    RAN_RAN_STEP    = 464
    TAG_CANDY       = 465
    LAST            = 466
    CLAIRE          = -1     # Not items, but event flags.
    LISA            = -2     # Not items, but event flags.
    MARIE           = -3     # Not items, but event flags.

# TODO: update to strict requirements, so you will need all the items in the list to unlock the zone.
# TODO: Allow for multiple requirement sets to unlock a zone. (lets say you can unlock a zone with either A or B)
unlocks = {
    "Alunze Basement": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HAMMER,
        ],
    },
    "Alunze Northwest Cave": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HAMMER,
        ],
    },
    "Ancient Tower": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HOOK,
            KeyItems.ANCIENT_KEY,
            KeyItems.HAMMER,
        ],
    },
    "Bridge Cave": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HOOK,
            KeyItems.HAMMER,
        ],
    },
    "Capsule Monster Cave": {
        "requirements": [
            KeyItems.MERMAID_JADE,
        ],
    },
    "Dankirk North Cave": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HOOK,
            KeyItems.DANKIRK_KEY,
        ],
    },
    "Divine Shrine": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HOOK,
            KeyItems.HEART_KEY,
        ],
    },
    "Doom Island": {
        "requirements": [
            KeyItems.CLAIRE,
            KeyItems.LISA,
            KeyItems.MARIE,
        ],
    },
    "Dragon Mountain": {
        "requirements": [
            KeyItems.MAGMA_KEY,
            KeyItems.HOOK,
            KeyItems.HAMMER,
            KeyItems.FIRE_ARROW,
            KeyItems.ENGINE,
            KeyItems.MERMAID_JADE,
        ],
    },
    "Flower Capsule": {
        "requirements": [
            KeyItems.HAMMER,
            KeyItems.HOOK,
        ],
    },
    "Flower Mountain": {
        "requirements": [
            KeyItems.HAMMER,
            KeyItems.FLOWER_KEY,
        ],
    },
    "Gordovan West Tower": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HOOK,
            KeyItems.WIND_KEY,
        ],
    },
    "Gratze Castle": {
        "requirements": [
            KeyItems.DANKIRK_KEY,
            KeyItems.BASEMENT_KEY,
            KeyItems.ARROW,
            KeyItems.FIRE_ARROW,
            KeyItems.HOOK,
            KeyItems.ENGINE,
            KeyItems.MERMAID_JADE,
        ],
    },
    "Kamirno": {
        "requirements": [
            KeyItems.ENGINE,
        ],
    },
    "Karlloon North Shrine": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HOOK,
        ],
    },
    "Lake Cave": {
        "requirements": [
            KeyItems.LAKE_KEY,
            KeyItems.ARROW,
            KeyItems.HOOK,
        ],
    },
    "North Dungeon Capsule": {
        "requirements": [
            KeyItems.HOOK,
        ],
    },
    "North Dungeon": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HOOK,
        ],
    },
    "North Lighthouse": {
        "requirements": [
            KeyItems.LIGHT_KEY,
        ],
    },
    "Northeast Tower": {
        "requirements": [
            KeyItems.HOOK,
            KeyItems.HAMMER,
            KeyItems.TRIAL_KEY,
        ],
    },
    "Phantom Tree Mountain": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HOOK,
            KeyItems.FIRE_ARROW,
            KeyItems.TREE_KEY,
        ],
    },
    "Ruby Cave Capsule": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HAMMER,
        ],
    },
    "Ruby Cave": {
        "requirements": [
            KeyItems.RUBY_KEY,
        ],
    },
    "Shrine Of Vengeance": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.HAMMER,
            KeyItems.MERMAID_JADE,
            KeyItems.GHOST_KEY,
        ],
    },
    "Shuman": {
        "requirements": [
            KeyItems.ENGINE,
        ],
    },
    "Skill Cave": {
        "requirements": [
            KeyItems.ARROW,
            KeyItems.FIRE_ARROW,
            KeyItems.HOOK,
        ],
    },
    "Strahda": {
        "requirements": [
            KeyItems.ENGINE,
        ],
    },
    "Submarine Cave": {
        "requirements": [
            KeyItems.MERMAID_JADE,
        ],
    },
    "Tanbel Southeast Tower": {
        "requirements": [
            KeyItems.SKY_KEY,
        ],
    },
    "Tower of Sacrifice": {
        "requirements": [
            KeyItems.BOMB,
            KeyItems.NARCYSUS_KEY,
            KeyItems.HOOK,
            KeyItems.HAMMER,
        ],
    },
    "Tower of Truth": {
        "requirements": [
            KeyItems.TRUTH_KEY,
            KeyItems.HOOK,
            KeyItems.HAMMER,
            KeyItems.BOMB,
        ],
    },
    "Treasure Sword Shrine": {
        "requirements": [
            KeyItems.SWORD_KEY,
            KeyItems.BOMB,
        ],
    },
}

def as_key_item(item: Item) -> KeyItems:
    return KeyItems(item.index)

def get_requirements(zone: Zone) -> list[KeyItems]:
    return unlocks[zone.clean_name.decode()].get("requirements", [])

def get_reachable_zones(items: list[KeyItems]) -> list[Zone]:
    reachable_zones = []
    for zone in range(ZoneObject.count):
        zone = Zone.from_index(zone)
        requirements = get_requirements(zone)
        if all(item in items for item in requirements):
            reachable_zones.append(zone)
    return reachable_zones

