"""Options (Iris-Dev#33). Only what changes routing or the item pool lives here; Iris's own patches (difficulty,
encounter scaling, fixes) are chosen when building the ROM and don't touch logic."""

from dataclasses import dataclass

from Options import Choice, PerGameCommonOptions, Range


class Placement(Choice):
    """anywhere: any location in any world. own_world: any location in this world. own_stage: a location in the story
    stage the item lies in in vanilla. vanilla: where it lies in vanilla."""

    option_anywhere = 0
    option_own_world = 1
    option_own_stage = 2
    option_vanilla = 3
    default = option_anywhere


class KeyPlacement(Placement):
    """Where the dungeon keys can be placed.

    anywhere: any location in any world. own_world: any location in this world. own_stage: a location in the story stage
    the key lies in in vanilla (its own dungeon or town). vanilla: where it lies in vanilla."""

    display_name = "Key Placement"


class ToolPlacement(Placement):
    """Where the Hook, Bomb, Fire arrow and Hammer can be placed. Maxim always starts with the Arrow.

    anywhere: any location in any world. own_world: any location in this world. own_stage: a location in the story stage
    the tool lies in in vanilla. vanilla: where it lies in vanilla."""

    display_name = "Tool Placement"


class StoryRewards(Choice):
    """What the story rewards (items an NPC or a scene gives you, such as the Sundletan boss's Door key) hold.

    shuffled: any item. vanilla: their own item. Vanilla wins over Key and Tool Placement for these locations."""

    display_name = "Story Rewards"
    option_shuffled = 0
    option_vanilla = 1
    default = option_shuffled


class Goal(Choice):
    """The story event that completes your game. Locations after it are left out.

    daos: defeat Daos. shrine_of_daos_open: finish the three sealed towers. chaed: see Chaed destroyed, after the
    Submarine Shrine. amon_divine_shrine: defeat Amon in the Divine Shrine. idura: defeat Idura in the Tower of Sacrifice.
    gades_ancient_tower: defeat Gades in the Ancient Tower."""

    display_name = "Goal"
    option_daos = 0
    option_shrine_of_daos_open = 1
    option_chaed = 2
    option_amon_divine_shrine = 3
    option_idura = 4
    option_gades_ancient_tower = 5
    default = option_daos


class FillerItems(Choice):
    """The items that don't open anything (consumables and equipment).

    vanilla: the ones the chests and story rewards held. randomized: random items from the whole game, see Useful Items."""

    display_name = "Filler Items"
    option_vanilla = 0
    option_randomized = 1
    default = option_vanilla


class UsefulItems(Range):
    """With randomized Filler Items: the percentage that is equipment (weapons, armour, rings, jewels); the rest are
    consumables. Dragon eggs always stay in the pool."""

    display_name = "Useful Items"
    range_start = 0
    range_end = 100
    default = 50


@dataclass
class L2OWOptions(PerGameCommonOptions):
    key_placement: KeyPlacement
    tool_placement: ToolPlacement
    story_rewards: StoryRewards
    goal: Goal
    filler_items: FillerItems
    useful_items: UsefulItems
