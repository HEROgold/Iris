class EventInstObject:
    reference_pointer = 2
    address = 0x4A14
    count = 205


class IPAttackObject:
    effect = 2
    animation = 1
    target_cursor = 1
    target_mode = 1
    ip_cost = 1
    pointers = [
        0x21060,
        0x21074,
        0x21084,
        0x21097,
        0x210A1,
        0x210AC,
        0x210BE,
        0x210D1,
        0x210E5,
        0x210F8,
        0x21109,
        0x2111C,
        0x2112E,
        0x21140,
        0x21153,
        0x21165,
        0x21177,
        0x2118B,
        0x2119D,
        0x211B0,
        0x211C2,
        0x211D4,
        0x211E4,
        0x211F6,
        0x21207,
        0x2121B,
        0x2122B,
        0x2123F,
        0x21252,
        0x21264,
        0x21276,
        0x21288,
        0x2129A,
        0x212AD,
        0x212BF,
        0x212D0,
        0x212E4,
        0x212F8,
        0x2130C,
        0x2131B,
        0x21330,
        0x2133F,
        0x21350,
        0x2135F,
        0x2136E,
        0x21380,
        0x2138E,
        0x2139C,
        0x213AF,
        0x213C2,
        0x213D4,
        0x213E3,
        0x213F2,
        0x21403,
        0x2140F,
        0x21421,
        0x21431,
        0x21444,
        0x21456,
        0x21469,
        0x21476,
        0x21487,
        0x2149B,
        0x214AB,
        0x214BA,
        0x214C9,
        0x214D8,
        0x214E3,
        0x214F3,
        0x21500,
        0x21512,
        0x21523,
        0x2152E,
        0x2153C,
        0x2154B,
        0x2155A,
        0x21567,
        0x21574,
        0x21583,
        0x21592,
        0x2159F,
        0x215AD,
        0x215B9,
        0x215C7,
        0x215D2,
        0x215DE,
        0x215EC,
        0x215FA,
        0x21608,
        0x21615,
        0x21624,
        0x21633,
        0x21643,
        0x21657,
        0x21665,
        0x21679,
        0x21685,
        0x21696,
        0x216A6,
        0x216B4,
        0x216C8,
        0x216D6,
        0x216E4,
        0x216F0,
        0x216FE,
        0x2170F,
        0x2171B,
        0x2172E,
        0x21740,
        0x2174D,
        0x21758,
        0x21765,
        0x21773,
        0x2177E,
        0x2178F,
        0x217A1,
        0x217B2,
        0x217C3,
        0x217D5,
        0x217E7,
        0x217FB,
        0x2180E,
        0x21820,
        0x21833,
        0x21847,
        0x21857,
        0x2186B,
        0x21879,
        0x21885,
        0x21890,
        0x2189F,
        0x218B0,
        0x218C4,
        0x218D5,
        0x218E5,
        0x218F6,
        0x21909,
        0x2191B,
        0x2192F,
        0x21941,
        0x21951,
        0x21963,
        0x21976,
        0x21988,
        0x21999,
        0x219AC,
        0x219BF,
        0x219D1,
        0x219E4,
        0x219F4,
        0x21A04,
        0x21A17,
        0x21A29,
        0x21A3B,
        0x21A4C,
        0x21A5E,
        0x21A70,
        0x21A80,
        0x21A93,
        0x21AA4,
        0x21AB7,
        0x21AC9,
        0x21AD5,
        0x21AE7,
        0x21AF4,
        0x21B05,
        0x21B17,
        0x21B2A,
    ]


class CharLevelObject:
    level = 1
    pointers = [
        0x2B2B6,
        0x2B2D3,
        0x2B2F7,
        0x2B314,
        0x2B339,
        0x2B359,
        0x2B376,
    ]


class CharExpObject:
    xp = 3
    pointers = [
        0x2B2BB,
        0x2B2DF,
        0x2B2FC,
        0x2B321,
        0x2B341,
        0x2B35E,
        0x2B383,
    ]


class InitialEquipObject:
    weapon = 2
    armor = 2
    shield = 2
    helmet = 2
    ring = 2
    jewel = 2
    pointers = [
        0x2B2BE,
        0x2B2E2,
        0x2B2FF,
        0x2B324,
        0x2B344,
        0x2B361,
        0x2B386,
    ]


class OverPaletteObject:
    palette_index = 1
    unknown = 12
    address = 0x36CA6
    count = 3


class OverSpriteObject:
    unknown = 3
    sprite_pointer = 3
    address = 0x37086
    count = 6


class MapEventObject:
    eventlist_lowbytes = 2
    eventlist_highbyte = 1
    npc_lowbytes = 2
    npc_highbyte = 1
    map_name_pointer = 2
    address = 0x38010
    count = 242


class RoamingNPCObject:
    map_npc_event_index = 1
    sprite_index = 1
    map_index = 1
    map_npc_index = 1
    address = 0x3AE4E
    count = 34


class ChestObject:
    misc1: bytes = b"u00 u01 u02 u03 u04 u05 item_high_bit u07"
    misc2 = 1
    item_low_byte = 1
    pointers = [
        0x8BABB,
        0x8BABE,
        0x8BAC1,
        0x8BAC5,
        0x8BAC8,
        0x8BACB,
        0x8BACE,
        0x8BAD5,
        0x8BAD8,
        0x8BADB,
        0x8BADE,
        0x8BAE2,
        0x8BAEA,
        0x8BAED,
        0x8BAF0,
        0x8BAF4,
        0x8BAF7,
        0x8BAFB,
        0x8BAFE,
        0x8BB01,
        0x8BB04,
        0x8BB0C,
        0x8BB0F,
        0x8BB12,
        0x8BB16,
        0x8BB19,
        0x8BB1C,
        0x8BB20,
        0x8BB23,
        0x8BB26,
        0x8BB29,
        0x8BB2C,
        0x8BB2F,
        0x8BB33,
        0x8BB36,
        0x8BB3F,
        0x8BB44,
        0x8BB48,
        0x8BB4B,
        0x8BB4E,
        0x8BB56,
        0x8BB59,
        0x8BB5C,
        0x8BB60,
        0x8BB68,
        0x8BB6D,
        0x8BB70,
        0x8BB75,
        0x8BB79,
        0x8BB7C,
        0x8BB7F,
        0x8BB82,
        0x8BB85,
        0x8BB8C,
        0x8BB90,
        0x8BB93,
        0x8BB98,
        0x8BB9B,
        0x8BB9E,
        0x8BBA3,
        0x8BBA6,
        0x8BBAD,
        0x8BBB1,
        0x8BBB9,
        0x8BBBD,
        0x8BBC0,
        0x8BBC4,
        0x8BBC7,
        0x8BBCF,
        0x8BBD2,
        0x8BBD5,
        0x8BBD9,
        0x8BBDC,
        0x8BBDF,
        0x8BBE7,
        0x8BBEE,
        0x8BBF1,
        0x8BBF4,
        0x8BBF9,
        0x8BBFD,
        0x8BC00,
        0x8BC03,
        0x8BC0B,
        0x8BC10,
        0x8BC15,
        0x8BC21,
        0x8BC26,
        0x8BC30,
        0x8BC34,
        0x8BC38,
        0x8BC41,
        0x8BC45,
        0x8BC4A,
        0x8BC4D,
        0x8BC50,
        0x8BC54,
        0x8BC57,
        0x8BC5B,
        0x8BC68,
        0x8BC6B,
        0x8BC6F,
        0x8BC72,
        0x8BC75,
        0x8BC78,
        0x8BC7C,
        0x8BC84,
        0x8BC89,
        0x8BC8D,
        0x8BC90,
        0x8BCA1,
        0x8BCA7,
        0x8BCAB,
        0x8BCAF,
        0x8BCB2,
        0x8BCB6,
        0x8BCBE,
        0x8BCC2,
        0x8BCC5,
        0x8BCC9,
        0x8BCCD,
        0x8BCD1,
        0x8BCD4,
        0x8BCD7,
        0x8BCDF,
        0x8BCE4,
        0x8BCE7,
        0x8BCEA,
        0x8BCEE,
        0x8BCF5,
        0x8BCF9,
        0x8BCFC,
        0x8BCFF,
        0x8BD02,
        0x8BD05,
        0x8BD08,
        0x8BD0B,
        0x8BD0F,
        0x8BD12,
        0x8BD15,
        0x8BD18,
        0x8BD1B,
        0x8BD1F,
        0x8BD22,
        0x8BD25,
        0x8BD28,
        0x8BD2B,
        0x8BD2E,
        0x8BD35,
        0x8BD44,
        0x8BD48,
        0x8BD54,
        0x8BD57,
        0x8BD5A,
        0x8BD65,
        0x8BD6A,
        0x8BD6D,
        0x8BD70,
        0x8BD73,
        0x8BD76,
        0x8BD7A,
        0x8BD7D,
        0x8BD81,
        0x8BD84,
        0x8BD88,
        0x8BD8B,
        0x8BD8E,
        0x8BD96,
        0x8BD99,
        0x8BD9D,
        0x8BDA0,
        0x8BDA3,
    ]


class CapsuleLevelObject:
    level = 1
    address = 0x764C4
    count = 7


class WordObject:
    word_pointer = 2
    address = 0x76A00
    count = 640


class AncientChest2Object:
    item_index = 2
    address = 0x8FFDC
    count = 9


class BlueChestObject:
    item_index = 2
    address = 0xA6EA0
    count = 41


class AncientChest1Object:
    item_index = 2
    address = 0xA713D
    count = 31


class SpellObject:
    name_text = 8   # String
    unk1 = 1
    element = 1
    characters: bytes = b"maxim selan guy artea tia dekar lexis u37"
    unk4 = 1
    mp_cost = 1
    zero = 2
    price = 2
    pointers = [
        0xAFAAB,
        0xAFACD,
        0xAFAEF,
        0xAFB11,
        0xAFB33,
        0xAFB55,
        0xAFB77,
        0xAFB99,
        0xAFBBB,
        0xAFBDD,
        0xAFBFF,
        0xAFC21,
        0xAFC43,
        0xAFC5C,
        0xAFC75,
        0xAFC8E,
        0xAFCA7,
        0xAFCC0,
        0xAFCD9,
        0xAFCF8,
        0xAFD15,
        0xAFD32,
        0xAFD4B,
        0xAFD64,
        0xAFD7D,
        0xAFD96,
        0xAFDB2,
        0xAFDCE,
        0xAFDEA,
        0xAFE03,
        0xAFE22,
        0xAFE41,
        0xAFE5B,
        0xAFE75,
        0xAFE8E,
        0xAFEA7,
        0xAFEC0,
        0xAFED6,
        0xAFEEC,
        0xAFF02,
    ]


class MonsterObject:
    name_text = 13  # String
    level = 1
    unknown = 1
    battle_sprite = 1
    palette = 1
    hp = 2
    mp = 2
    attack = 2
    defense = 2
    agility = 1
    intelligence = 1
    guts = 1
    magic_resistance = 1
    xp = 2
    gold = 2
    misc = 1
    address = 0xB05C0
    count = 224
    grouped = ["224", "point1", "b05c0", "2"]


class ItemObject:
    usability: bytes = (
        b"consumable equipable u02 cursed fruit unsellable usable_menu usable_battle"
    )
    unknown: bytes = b"u10 u11 u12 u13 u14 ban_ancient_cave u16 u17"
    targetting = 1
    icon = 1
    sprite = 1
    price = 2
    item_type: bytes = b"weapon armor shield helmet ring jewel u66 u67"
    equipability: bytes = b"maxim selan guy artea tia dekar lexis u77"
    misc1: bytes = b"menu_effect battle_effect weapon_effect armor_effect increase_atp increase_dfp increase_str increase_agl"
    misc2: bytes = (
        b"increase_int increase_gut increase_mgr u93 u94 battle_animation u96 ip_effect"
    )
    zero = 2
    address = 0xB4F69
    count = 467
    grouped = ["467", "point1", "b4f69", "2"]


class CharGrowthObject:
    hp = 1
    mp = 1
    str = 1
    agl = 1
    int = 1
    gut = 1
    mgr = 1
    unk = 1
    pointers = [
        0xBB62C,
        0xBB634,
        0xBB63C,
        0xBB644,
        0xBB64C,
        0xBB654,
        0xBB65C,
        0xBB664,
        0xBB66C,
        0xBB674,
        0xBB67C,
        0xBB684,
        0xBB68C,
        0xBB69C,
        0xBB6A4,
        0xBB6AC,
        0xBB6B4,
        0xBB6BC,
        0xBB6C4,
        0xBB6CC,
        0xBB6D4,
        0xBB6DC,
        0xBB6E4,
        0xBB6EC,
        0xBB6F4,
        0xBB6FC,
        0xBB70C,
        0xBB714,
        0xBB71C,
        0xBB724,
        0xBB72C,
        0xBB734,
        0xBB73C,
        0xBB744,
        0xBB74C,
        0xBB754,
        0xBB75C,
        0xBB764,
        0xBB76C,
        0xBB77C,
        0xBB784,
        0xBB78C,
        0xBB794,
        0xBB79C,
        0xBB7A4,
        0xBB7AC,
        0xBB7B4,
        0xBB7BC,
        0xBB7C4,
        0xBB7CC,
        0xBB7D4,
        0xBB7DC,
        0xBB7EC,
        0xBB7F4,
        0xBB7FC,
        0xBB804,
        0xBB80C,
        0xBB814,
        0xBB81C,
        0xBB824,
        0xBB82C,
        0xBB834,
        0xBB83C,
        0xBB844,
        0xBB84C,
        0xBB85C,
        0xBB864,
        0xBB86C,
        0xBB874,
        0xBB87C,
        0xBB884,
        0xBB88C,
        0xBB894,
        0xBB89C,
        0xBB8A4,
        0xBB8AC,
        0xBB8B4,
        0xBB8BC,
        0xBB8CC,
        0xBB8D4,
        0xBB8DC,
        0xBB8E4,
        0xBB8EC,
        0xBB8F4,
        0xBB8FC,
        0xBB904,
        0xBB90C,
        0xBB914,
        0xBB91C,
        0xBB924,
        0xBB92C,
    ]


class CharacterObject:
    hp = 2
    mp = 2
    str = 2
    agl = 2
    int = 2
    gut = 2
    mgr = 2
    address = 0xBB93C
    count = 7


class MapFormationsObject:
    reference_pointer = 2
    address = 0xBB9AC
    count = 248


class FormationObject:
    monster_indexes = 8 # List
    address = 0xBBE93
    count = 192


class BossFormationObject:
    reference_pointer = 2
    address = 0xBC53D
    count = 39


class SpriteMetaObject:
    width = 1
    height_misc = 1
    address = 0xBCA64
    count = 134


class CapPaletteObject:
    color0 = 2
    color1 = 2
    color2 = 2
    color3 = 2
    color4 = 2
    color5 = 2
    color6 = 2
    color7 = 2
    color8 = 2
    color9 = 2
    colorA = 2
    colorB = 2
    colorC = 2
    colorD = 2
    colorE = 2
    colorF = 2
    address = 0xBD258
    count = 35


class CapsuleObject:
    name_text = 12  # String
    zero = 1
    capsule_class = 1
    alignment = 1
    start_skills = 3    # List
    upgrade_skills = 3  # List
    hp = 1
    attack = 1
    defense = 1
    strength = 1
    agility = 1
    intelligence = 1
    guts = 1
    magic_resistance = 1
    hp_factor = 1
    strength_factor = 1
    agility_factor = 1
    intelligence_factor = 1
    guts_factor = 1
    magic_resistance_factor = 1
    address = 0xBDCB8
    count = 35
    grouped = ["35", "point1", "bdcb8", "2"]


class ShopObject:
    reference_pointer = 2
    address = 0xBEE9F
    count = 63


class CapAttackObject:
    unknown = 1
    animation = 1
    address = 0xBF63B
    count = 84
    grouped = ["84", "point1", "bf63b", "2"]


class ItemNameObject:
    name_text= 12   # String
    address = 0xF47E8
    count = 467


class CapSpritePTRObject:
    sprite_pointer = 3
    address = 0x1384BC
    count = 35


class TownSpriteObject:
    unknown = 1
    palette_index = 1
    sprite_pointer = 3
    pointers = [
        0x27F1F6,
        0x27F1FB,
        0x27F200,
        0x27F205,
        0x27F214,
        0x27F20A,
        0x27F20F,
    ]


class MonsterMoveObject:
    movement = 1
    address = 0x27F6B5
    count = 112


class MapMetaObject:
    reference_pointer = 3
    address = 0x27FCBC
    count = 242


addresses = {
    "capsule_end": 0xBEEAD,
    "rng1": 0x63,
    "rng2": 0x2F4,
    "starting_tool": 0x2B2CA,
    "credits": 0x89AFF,
    "credits_pointer1": 0x73449,
    "credits_pointer2": 0x73496,
    "credits_pointer3": 0x7349D,
    "credits_pointer4": 0x734B3,
    "credits_pointer5": 0x73503,
    "credits_pointer6": 0x73511,
    "sprites": [
        "Maxim",
        "Selan",
        "Guy",
        "Arty",
        "Tia",
        "Dekar",
        "Lex",
        "Maxim2",
        "Maxim3",
        "Maxim4",
        "Red Boy",
        "Green Girl",
        "Blue Man",
        "Yellow Woman",
        "Yellow Middle Man",
        "Green Middle Woman",
        "Bald Old Man",
        "Gray Old Woman",
        "King",
        "Queen",
        "Prince",
        "Princess",
        "Knight",
        "Maid",
        "Armored Knight",
        "Red Man",
        "Sailor",
        "Bandana Sailor",
        "Brown Woman",
        "Maxim Lifting",
        "Maxim Pushing",
        "Maxim Falling",
        "Selan Lifting",
        "Selan Pushing",
        "Selan Falling",
        "Guy Lifting",
        "Guy Pushing",
        "Guy Falling",
        "Chest",
        "Arty Pushing",
        "Chest",
        "Dekar Lifting",
        "Dekar Pushing",
        "Dekar Falling",
        "Chest",
        "Chest",
        "Chest",
        "Tia Lifting",
        "Tia Pushing",
        "Tia Falling",
        "Priest",
        "Maxim5",
        "Elf Man",
        "Elf Woman",
        "Elf Boy",
        "Elf Girl",
        "Erim",
        "Berty",
        "Bart",
        "Blonde Woman",
        "Apron Dude",
        "Ribbon Girl",
        "Kerchief Boy",
        "Basket Woman",
        "Lab Assistant",
        "Pale Mermaid",
        "Blue Mermaid",
        "Merman",
        "Toga Maiden",
        "Green Dress Girl",
        "Fallen Man",
        "Phantom Fish",
        "Crown",
        "Big Boat",
        "Sword",
        "Bomb",
        "Caped Sinister Man",
        "Shadow",
        "Big Shadow",
        "Wedding Attire Maxim",
        "Wedding Attire Selan",
        "Unconscious Woman",
        "Fallen Tia",
        "Fallen Guy",
        "Fallen Arty",
        "Fallen Blue Dude",
        "Fallen Hilda",
        "Shocked Dekar",
        "Formal Blue Dude",
        "Dazed Stars",
        "Crying Ribbon Girl South",
        "Crying Ribbon Girl East",
        "Bald Cleric",
        "Fallen Twintails Girl",
        "Fallen Bald Old Man",
        "Swaddled Baby",
        "Ruby Angel",
        "Old Woman South",
        "Propeller",
        "Engine",
        "Bird",
        "Snake",
        "Blue Flower (NPC)",
        "Confetti",
        "Fallen Maxim",
        "Fallen Selan",
        "Jaw?",
        "Tail?",
        "Ruby Apple",
        "Iris",
        "Gray Lab Assistant",
        "Red Lab Assistant",
        "Nothing",
        "Little Boat",
        "Submarine",
        "Airship",
        "Idura",
        "Camu",
        "Follower",
        "Blue Clown",
        "Red Clown",
        "Amon",
        "Gades",
        "Daos",
        "Erim (Large)",
        "Broken Ruby Apple",
        "Blue Diamond",
        "Green Lump",
        "Octopus",
        "Snail",
        "Ninja",
        "Lizard",
        "Bull",
        "Horse",
        "Beetle",
        "Crab",
        "Eyeball",
        "Spider",
        "Dog",
        "Scorpion",
        "Mushroom",
        "Chickenhead",
        "Tree",
        "Bat",
        "Sword",
        "Will-o-Wisp",
        "Fly",
        "Butterfly",
        "Jelly",
        "Core",
        "Orange Flower",
        "Blue Flower",
        "Hornet",
        "Dullahan",
        "Flytrap",
        "Bugbear",
        "Medusa",
        "Goblin",
        "Lizardman",
        "Vampire",
        "Skeleton",
        "Iron Golem",
        "Wood Golem",
        "Mud Golem",
        "Mimic",
        "Hobgoblin",
        "Kobold",
        "Zombie",
        "Mummy",
        "Troll",
        "Minotaur",
        "Necromancer",
        "Imp",
        "Lich",
        "Lamia",
        "Pumpkin Head",
        "Samurai",
        "Fairy Thing",
        "Shade",
        "Snake (Enemy)",
        "Eagle",
        "Flaming Skull",
        "Stegosaurus",
        "Lion",
        "Tartona",
        "Cyclops",
        "Skeleton Chariot",
        "Giant Squid",
        "Giant Plant",
        "Fiend",
        "Frog",
        "Hydra",
        "Dragon",
        "Dragonian",
        "Whale",
        "Wyvern",
        "Gargoyle",
        "Catfish",
        "Giant Spider",
        "Monster Tank",
        "Ghost Ship",
        "Jelze",
        "Flash",
        "Gusto",
        "Zeppy",
        "Darbi",
        "Sully",
        "Blaze",
        "Big Phantom",
        "Another Ship",
        "Quetzalcotl",
        "T-Rex",
        "Tengu",
        "Red Dullahan",
        "Blue Lizard",
        "Red Beetle",
        "Blue Crab",
        "Green Spider",
        "Orange Spider",
        "Blue Mushroom",
        "Red Butterfly",
        "Blue Jelly",
        "Green Jelly",
        "Yellow Flower",
        "Purple Flytrap",
        "Ghoul",
        "Gold Golem",
        "Magma Golem",
        "Sand Golem",
        "Nuborg",
        "Green Clay Golem",
        "Red Lich",
        "Blue Eagle",
        "Red Snake",
        "Blue Snake",
        "Green Tartona",
        "Red Giant Plant",
        "Yellow Tengu",
        "Blue Dragonian",
        "Green Dragonian",
        "Blue Chest",
        "Sword",
        "Shield",
        "Helm",
        "Armor",
        "Ring",
        "Gemstone",
        "Rod",
        "Vase",
        "Circlet",
        "Glider",
        "GAME CRASH",
        "Glitched Graphics",
        "GAME CRASH",
        "Invisible (Wide)",
        "Invisible",
    ],
}
