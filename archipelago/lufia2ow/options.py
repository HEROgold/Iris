"""Options (Iris-Dev#33). Only what changes routing or the item pool lives here; Iris's own patches (difficulty,
encounter scaling, fixes) are chosen when building the ROM and don't touch logic."""

from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, PerGameCommonOptions, Range, Toggle

from . import data


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
    the key lies in in vanilla (its own dungeon or town); with Open World there are no stages, so it is own_world.
    vanilla: where it lies in vanilla."""

    display_name = "Key Placement"


class ToolPlacement(Placement):
    """Where the Hook, Bomb, Fire arrow and Hammer can be placed. Maxim always starts with the Arrow.

    anywhere: any location in any world. own_world: any location in this world. own_stage: a location in the story stage
    the tool lies in in vanilla; with Open World there are no stages, so it is own_world. vanilla: where it lies in
    vanilla."""

    display_name = "Tool Placement"


class StoryRewards(Choice):
    """What the story rewards (items an NPC or a scene gives you, such as the Sundletan boss's Door key) hold.

    shuffled: any item. vanilla: their own item. Vanilla wins over Key and Tool Placement for these locations.
    Open World replaces the story scenes, so there it has no story rewards and this does nothing."""

    display_name = "Story Rewards"
    option_shuffled = 0
    option_vanilla = 1
    default = option_shuffled


class Goal(Choice):
    """What completes your game. Locations after it are left out.

    daos: beat the game: defeat Daos in the Shrine of Daos (the goal counts before the ending plays).
    shrine_of_daos_open: finish the three sealed towers, which opens the Shrine of Daos. chaed: see Chaed destroyed,
    after the Submarine Shrine. amon_divine_shrine: defeat Amon in the Divine Shrine. idura: defeat Idura in the Tower of
    Sacrifice. gades_ancient_tower: defeat Gades in the Ancient Tower.
    dragon_eggs: bring 8 Dragon eggs per wish to the Egg Dragon's shrine and make Egg Wishes wishes.
    With Open World only daos and dragon_eggs are allowed (the others are story events open world skips), and no
    locations are left out."""

    display_name = "Goal"
    option_daos = 0
    option_shrine_of_daos_open = 1
    option_chaed = 2
    option_amon_divine_shrine = 3
    option_idura = 4
    option_gades_ancient_tower = 5
    option_dragon_eggs = 6
    default = option_daos


class EggWishes(Range):
    """With the dragon_eggs goal: how many wishes to make. Each takes 8 Dragon eggs; the multiworld holds 8 per wish
    (one of them is Merix's, which stays where it is; Open World has no Merix egg, so all are in the pool). The Egg
    Dragon grants at most 4."""

    display_name = "Egg Wishes"
    range_start = 1
    range_end = 4
    default = 1


class FillerItems(Choice):
    """The items that don't open anything (consumables and equipment).

    vanilla: the ones the chests and story rewards held. randomized: random items from the whole game, see Useful Items."""

    display_name = "Filler Items"
    option_vanilla = 0
    option_randomized = 1
    default = option_vanilla


class UsefulItems(Range):
    """With randomized Filler Items: the percentage that is equipment (weapons, armour, rings, jewels, cursed copies
    included); the rest are consumables and other items. Dragon eggs always stay in the pool."""

    display_name = "Useful Items"
    range_start = 0
    range_end = 100
    default = 50


class ShipUpgrades(Choice):
    """How the Ship, the Submarine and the airship (the Engine) can come to you before the story gives them.

    progressive: three Progressive Ships: the Ship, then the Submarine, then the airship. separate: a Ship, a Submarine
    and an Engine, in any order (the Engine without the Submarine flies but can't dive). vanilla: only the story gives
    them. The story still gives them in every mode. With Open World there is no story to give them: vanilla is
    progressive there, and the Ship, Submarine and airship are what open the sea, the seafloor and the sky."""

    display_name = "Ship Upgrades"
    option_progressive = 0
    option_separate = 1
    option_vanilla = 2
    default = option_progressive


class Arrows(Choice):
    """progressive: two Progressive Arrows, the Arrow and then the Fire arrow. separate: an Arrow and a Fire arrow."""

    display_name = "Arrows"
    option_progressive = 0
    option_separate = 1
    default = option_progressive


class HintNpcs(Range):
    """How many townspeople tell you where one of your progression items is: in your world, or which player's world
    and where. Each picks a different item."""

    display_name = "Hint NPCs"
    range_start = 0
    range_end = len(data.HINT_FLAGS)
    default = 8


class HintUnlock(DefaultOnToggle):
    """Talking to a hint NPC also unlocks that hint on the server, as if you had used a hint."""

    display_name = "Hint Unlock"


class OpenWorld(Toggle):
    """Open world: the whole map is open from the start, and boss NPCs guard the dungeons (Iris's open world).

    You start in Elcid and can walk as far as Aleyn; the Ship opens the sea, the Submarine the seafloor and the
    airship the sky. Inside, the dungeons still need their keys and tools. Changes Goal (daos or dragon_eggs only),
    Key/Tool Placement (own_stage is own_world) and Ship Upgrades (vanilla is progressive).
    """

    display_name = "Open World"


class BossPlacement(Choice):
    """Open World only (does nothing without it): which boss stands at each of the 37 boss spots. Daos always waits
    in the Shrine of Daos.

    fixed: the bosses in story order. shuffled: every boss at least once, some twice, mostly near their story place
    (the spoiler log lists them)."""

    display_name = "Boss Placement"
    option_fixed = 0
    option_shuffled = 1
    default = option_fixed


class BossStrength(Choice):
    """Open World only (does nothing without it): how strong the bosses are. Logic doesn't take it into account.

    unchanged: their own stats. party_level: every boss battle scales to the party's average level when it starts.
    by_depth: each boss scales to the level of the story's boss at the spot it stands at, so a late boss placed early
    is weaker and an early one placed late stronger (Daos stays unchanged)."""

    display_name = "Boss Strength"
    option_unchanged = 0
    option_party_level = 1
    option_by_depth = 2
    default = option_unchanged


@dataclass
class L2OWOptions(PerGameCommonOptions):
    open_world: OpenWorld
    key_placement: KeyPlacement
    tool_placement: ToolPlacement
    story_rewards: StoryRewards
    goal: Goal
    egg_wishes: EggWishes
    filler_items: FillerItems
    useful_items: UsefulItems
    ship_upgrades: ShipUpgrades
    arrows: Arrows
    hint_npcs: HintNpcs
    hint_unlock: HintUnlock
    boss_placement: BossPlacement
    boss_strength: BossStrength
