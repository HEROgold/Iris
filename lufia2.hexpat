// =====================================================================================================
//  Lufia II - Rise of the Sinistrals (US) : ImHex pattern and ROM knowledge bank
// =====================================================================================================
//
//  This file is the single place that records what every known byte range of the vanilla US ROM is:
//  game data tables, scripts, text, graphics, sound, free space, and 65816 code (subroutines, jump
//  tables, hook sites). When you learn something new about the ROM, add it here.
//
//  Load it in ImHex on the vanilla US ROM (headerless, "Lufia II - Rise of the Sinistrals (U) [!].smc",
//  3 MiB). Or run it from the command line:
//
//      imhex --pl format -I "<ImHex>/includes" -i <rom> -p src/lufia2.hexpat -f json -o out.json
//
//  ADDRESSES
//  ---------
//  * Every offset in this file is a HEADERLESS file offset (Iris strips the 512-byte copier header).
//    The info/*.txt docs and the Reli/RealCitizen docs use HEADERED offsets: subtract 0x200.
//  * The ROM is LoROM. Each 32 KiB bank of the file maps to SNES $8000-$FFFF of bank $80 + n:
//        file  = (bank & 0x7F) * 0x8000 + (addr & 0x7FFF)
//        SNES  = (0x80 | file >> 15) : (0x8000 | (file & 0x7FFF))
//    e.g. $85:B483 = 0x2B483, $97:DCB8 = 0xBDCB8. `lorom_to_file()` below does this.
//  * The game is 2.5 MiB (0x000000-0x27FFFF). In the 3 MiB file, 0x280000-0x2FFFFF is a MIRROR of
//    0x200000-0x27FFFF, not zeros. Iris treats that mirror as free space and grows patched ROMs to
//    4 MiB (0x300000-0x3FFFFF, SNES $E0-$FF); see section 9.
//  * Banks $80-$BF can reach WRAM with 16-bit addresses; $C0+ cannot. Event scripts must therefore stay
//    below 0x200000 (the interpreter sets DBR to the script bank). Long-addressed data (monsters,
//    items, $42 subroutines, ZoneData, ...) works anywhere.
//
//  LAYOUT OF THIS FILE
//  -------------------
//    1. Conventions: type aliases, colours, helper functions
//    2. Name enums (items, monsters, spells, maps, capsules, IPs, words, characters, event flags)
//    3. Small value enums and bitfields
//    4. L2BASM: the battle/AI/effect bytecode (monsters, items, spells, IPs, capsules, $42 subroutines)
//    5. L2SASM: the event/map script bytecode
//    6. Game data, bank by bank (typed and cross-linked)
//    7. Code and data map: every documented subroutine and region, grouped per bank (bank_80, ...)
//    8. Patch hook sites: where Iris and the Archipelago base patch hook vanilla code
//    9. Expansion area and Iris-owned addresses (only present in patched ROMs)
//   10. RAM map (comments only: RAM cannot be placed on the ROM file)
//
//  SOURCES (and how much to trust them)
//  ------------------------------------
//    [iris]   Verified against the ROM by Iris code or an emulator check (src/, docs/, skills).
//    [reli]   info/Reli + RealCitizen/L2_SMC_FileStruct.txt, L2_SMC_80/85_in-depth.txt (2004-2019).
//             Mostly right; "?" in a comment means the doc itself was unsure.
//    [info]   info/L2_*.txt data-format docs (headered offsets; the $42 doc has copy-paste errors).
//    [ap]     src/patches/archipelago/ancient_cave/basepatch.asm (hook comments).
//    [tw]     terrorwave's Lufia II randomizer (ported into Iris).
//
//  Known corrections to older notes, all checked against the vanilla ROM:
//    * The IP-effect script table is at 0xAF1EF (not 0xAF3EF, which is the headered offset).
//    * 0xB05C0 (monsters), 0xB4F69 (items), 0xBDCB8 (capsules) are self-relative u16 pointer tables
//      to variable-length records, not arrays of fixed records.
//    * The character templates at 0x2B2B0 have a variable-length 0xFF-terminated spell list.
//    * The chest table 0x8B8B5 is a per-map pointer table to 0xFF-terminated 3-byte records.
//    * L2BASM opcode 0x11 (RAND) takes 1 operand byte; 0x46 takes 3 (condition + u16 jump, not 1 as
//      older notes said); 0x3D and 0x4C take 1 each (RAN-RAN step's weapon script).
// =====================================================================================================

#pragma pattern_limit 8000000
#pragma array_limit 8000000
#pragma loop_limit 8000000

import std.mem;
import std.io;
import std.string;


// =====================================================================================================
//  1. CONVENTIONS
// =====================================================================================================

// Region kinds. The colour tells you what a range is at a glance in the hex view.
using Code       = u8 [[color("9E9E9E")]];   // 65816 machine code
using Data       = u8 [[color("4FC3F7")]];   // data whose layout is not modelled yet
using Text       = u8 [[color("81C784")]];   // text (ASCII-ish, with control codes / dictionary refs)
using Gfx        = u8 [[color("BA68C8")]];   // graphics (tiles, sprites; often compressed)
using Spc        = u8 [[color("FFB74D")]];   // SPC700 sound program / samples / music
using Compressed = u8 [[color("F06292")]];   // compressed blob of a known kind
using Free       = u8 [[color("37474F")]];   // free space (unused by the vanilla game)
using Unknown    = u8 [[color("FFF176")]];   // documented range whose meaning is unknown

// LoROM SNES address (24-bit, as stored in long pointers / LDA long operands) -> file offset.
fn lorom_to_file(u32 v) {
    return ((v >> 16) & 0x7F) * 0x8000 + (v & 0x7FFF);
};

// File offset -> LoROM SNES address.
fn file_to_lorom(u32 off) {
    return ((0x80 | (off >> 15)) << 16) | 0x8000 | (off & 0x7FFF);
};

// REFERENCES. A field that refers to another place in the ROM is a small sealed struct whose value
// reads "-> 0x0B0780  $96:8780" (file offset, SNES address): Ctrl+G that offset in ImHex. Whatever it
// points at is placed next to it as a named child (click that row to jump there); code and jump
// destinations only get the "->" value, so no byte is described twice.
fn fmt_dest(u32 target) {
    u32 s = file_to_lorom(target);
    return std::format("-> 0x{:06X}  ${:02X}:{:04X}", target, s >> 16, s & 0xFFFF);
};
fn fmt_ref(ref auto r) { return fmt_dest(r.target); };

// 16-bit offset from `base` (a table, a record start, a jump origin, ...).
struct Ref16<auto base> {
    u16 value;
    u32 target = base + value;
} [[format("fmt_ref"), sealed]];

// 24-bit offset from `base`.
struct Ref24<auto base> {
    u24 value;
    u32 target = base + value;
} [[format("fmt_ref"), sealed]];

// 16-bit address inside SNES bank `bank` ($8000-$FFFF).
struct BankRef<auto bank> {
    u16 value;
    u32 target = (bank & 0x7F) * 0x8000 + (value & 0x7FFF);
} [[format("fmt_ref"), sealed]];

// 24-bit LoROM address ($BB:AAAA).
struct LoRomRef {
    u24 value;
    u32 target = lorom_to_file(value);
} [[format("fmt_ref"), sealed]];

// End of a variable-length record that lives behind a u16 pointer table: the smallest target that is
// greater than `cur`, else `limit`. `base + ptr[j]` is the target of entry j (base is the table address
// for self-relative tables, or the bank base for bank-relative ones).
fn next_target(u32 table, u32 count, u32 base, u32 cur, u32 limit) {
    u32 best = limit;
    u32 j = 0;
    while (j < count) {
        u32 p = base + std::mem::read_unsigned(table + j * 2, 2);
        if (p > cur && p < best) { best = p; }
        j = j + 1;
    }
    return best;
};

fn peek8(u32 at) { return std::mem::read_unsigned(at, 1); };

// True when entry `index` of a table of `width`-byte values (`stride` bytes apart) is the first entry
// holding its value. Tables where several entries share a target only draw the target under the
// first entry, so no byte is described twice; the others show the raw offset.
fn first_with_value(u32 table, u32 stride, u32 width, u32 index) {
    u64 v = std::mem::read_unsigned(table + index * stride, width);
    u32 j = 0;
    while (j < index) {
        if (std::mem::read_unsigned(table + j * stride, width) == v) { return false; }
        j = j + 1;
    }
    return true;
};

// A 0x00-terminated ASCII string (names, menu text).
struct CString {
    char text[while(std::mem::read_unsigned($, 1) != 0x00)];
    u8 terminator;
} [[format("fmt_cstring"), color("81C784"), sealed]];

fn fmt_cstring(ref CString s) { return s.text; };


// =====================================================================================================
//  2. NAME ENUMS  (generated from src/lookups/*.py and src/enums/flags.py; value = table index)
// =====================================================================================================

// Item, MonsterId, Spell, Zone, MapEvents, Capsule, IPAttack, Word, Player: copied from structs.hexpat
enum Item : u16 {
    NO_EQUIP = 0,
    CHARRED_NEWT = 1,
    POTION = 2,
    HI_POTION = 3,
    EX_POTION = 4,
    MAGIC_JAR = 5,
    HI_MAGIC = 6,
    EX_MAGIC = 7,
    REGAIN = 8,
    MIRACLE = 9,
    ANTIDOTE = 10,
    AWAKE = 11,
    SHRIEK = 12,
    MYSTERY_PIN = 13,
    POWER_GOURD = 14,
    MIND_GOURD = 15,
    MAGIC_GUARD = 16,
    LIFE_POTION = 17,
    SPELL_POTION = 18,
    POWER_POTION = 19,
    SPEED_POTION = 20,
    MIND_POTION = 21,
    BRAVE = 22,
    PEAR_CIDER = 23,
    SOUR_CIDER = 24,
    LIME_CIDER = 25,
    PLUM_CIDER = 26,
    APPLE_CIDER = 27,
    SLEEP_BALL = 28,
    CONFUSE_BALL = 29,
    FREEZE_BALL = 30,
    SMOKE_BALL = 31,
    ICE_BALL = 32,
    FIRE_BALL = 33,
    TERROR_BALL = 34,
    EAR_PICK = 35,
    BOOMERANG = 36,
    BIG_BOOMER = 37,
    EX_BOOMER = 38,
    DRAGON_TOOTH = 39,
    GREEN_TEA = 40,
    ESCAPE = 41,
    WARP = 42,
    DRAGON_EGG = 43,
    CURSELIFTER = 44,
    PROVIDENCE = 45,
    SECRET_FRUIT = 46,
    HOLY_FRUIT = 47,
    BREEZE_FRUIT = 48,
    CHARM_FRUIT = 49,
    DARK_FRUIT = 50,
    EARTH_FRUIT = 51,
    FLAME_FRUIT = 52,
    MAGIC_FRUIT = 53,
    DUAL_BLADE = 54,
    FRYPAN = 55,
    KNIFE = 56,
    SMALL_KNIFE = 57,
    RAPIER = 58,
    BATTLE_KNIFE = 59,
    DAGGER = 60,
    INSECT_CRUSH = 61,
    LONG_KNIFE = 62,
    SHORT_SWORD = 63,
    LIGHT_KNIFE = 64,
    KUKRI = 65,
    GLADIUS = 66,
    COLD_RAPIER = 67,
    SCIMITAR = 68,
    DEADLY_SWORD = 69,
    DEADLY_SWORD_70 = 70,
    SUHRCUSTOM11 = 71,
    BRONZE_SWORD = 72,
    FIRE_DAGGER = 73,
    WAR_RAPIER = 74,
    LONG_SWORD = 75,
    BESERK_BLADE = 76,
    BESERK_BLADE_77 = 77,
    MULTI_SWORD = 78,
    ROCKBREAKER = 79,
    BROADSWORD = 80,
    ESTOK = 81,
    SILVO_RAPIER = 82,
    BURN_SWORD = 83,
    DEKAR_BLADE = 84,
    CRAZY_BLADE = 85,
    DEADLY_SWORD_86 = 86,
    DEADLY_SWORD_87 = 87,
    LUCK_RAPIER = 88,
    LUCK_RAPIER_89 = 89,
    AQUA_SWORD = 90,
    RED_SABER = 91,
    LUCKY_BLADE = 92,
    LUCKY_BLADE_93 = 93,
    MIST_RAPIER = 94,
    BOOM_SWORD = 95,
    FREEZE_SWORD = 96,
    SILVER_SWORD = 97,
    FLYING_BLOW = 98,
    SUPER_SWORD = 99,
    BUSTER_SWORD = 100,
    RUNE_RAPIER = 101,
    OLD_SWORD = 102,
    LIZARD_BLOW = 103,
    ZIRCO_SWORD = 104,
    SIZZLE_SWORD = 105,
    BLAZE_SWORD = 106,
    MYTH_BLADE = 107,
    GADES_BLADE = 108,
    SKY_SWORD = 109,
    SNOW_SWORD = 110,
    FRY_SWORD = 111,
    EGG_SWORD = 112,
    FRANSHISKA = 113,
    THUNDER_AX = 114,
    HAND_AX = 115,
    BRONZE_AX = 116,
    FLYING_AX = 117,
    RAINY_AX = 118,
    GREAT_AX = 119,
    ZIRCO_AX = 120,
    MEGA_AX = 121,
    MACE = 122,
    ROD = 123,
    STAFF = 124,
    DEADLY_ROD = 125,
    DEADLY_ROD_126 = 126,
    SLEEP_ROD = 127,
    LONG_STAFF = 128,
    HOLY_STAFF = 129,
    MORNING_STAR = 130,
    POUNDER_ROD = 131,
    CRYSTAL_WAND = 132,
    SILVER_ROD = 133,
    ZIRCO_ROD = 134,
    ZIRCO_FLAIL = 135,
    SPARK_STAFF = 136,
    WHIP = 137,
    WIRE = 138,
    CHAIN = 139,
    AQUA_WHIP = 140,
    CUTTER_WHIP = 141,
    ROYAL_WHIP = 142,
    HOLY_WHIP = 143,
    ZIRCO_WHIP = 144,
    AIR_WHIP = 145,
    FATAL_PICK = 146,
    FATAL_PICK_147 = 147,
    SPEAR = 148,
    TRIDENT = 149,
    HALBERD = 150,
    HEAVY_LANCE = 151,
    WATER_SPEAR = 152,
    DRAGON_SPEAR = 153,
    VICE_PLIERS = 154,
    COMA_HIT = 155,
    FIGGORU = 156,
    SUPERDRIVER = 157,
    STUN_GUN = 158,
    BATTLEDRIVER = 159,
    LAUNCHER = 160,
    FREEZE_BOW = 161,
    CURSED_BOW = 162,
    ARTY_S_BOW = 163,
    APRON = 164,
    DRESS = 165,
    CLOTH = 166,
    LAB_COAT = 167,
    HIDE_ARMOR = 168,
    FROCK = 169,
    ROBE = 170,
    CLOTH_ARMOR = 171,
    COAT = 172,
    TOUGH_HIDE = 173,
    LIGHT_DRESS = 174,
    LIGHT_ARMOR = 175,
    CAMU_ARMOR = 176,
    BAGGY = 177,
    TIGHT_DRESS = 178,
    CHAINMAIL = 179,
    HOLY_WINGS = 180,
    IRONMAIL = 181,
    TOGA = 182,
    CHAIN_ARMOR = 183,
    THICK_CLOTH = 184,
    STONE_PLATE = 185,
    LONG_ROBE = 186,
    PLATED_CLOTH = 187,
    IRON_PLATE = 188,
    METAL_MAIL = 189,
    SILK_TOGA = 190,
    SILVER_ARMOR = 191,
    LIGHT_JACKET = 192,
    METAL_COAT = 193,
    SILVER_MAIL = 194,
    POWER_JACKET = 195,
    QUILTED_SILK = 196,
    METAL_ARMOR = 197,
    POWER_CAPE = 198,
    MAGIC_BIKINI = 199,
    SILVER_ROBE = 200,
    EVENING_GOWN = 201,
    PLATE_ARMOR = 202,
    PLATI_PLATE = 203,
    SILK_ROBE = 204,
    REVIVE_ARMOR = 205,
    CRYSTAL_MAIL = 206,
    CRYSTAL_ROBE = 207,
    HEAL_ARMOR = 208,
    METAL_JACKET = 209,
    DEADLY_ARMOR = 210,
    DEADLY_ARMOR_211 = 211,
    ERON_DRESS = 212,
    BRIGHT_ARMOR = 213,
    BRIGHT_CLOTH = 214,
    POWER_ROBE = 215,
    MAGIC_SCALE = 216,
    HOLY_ROBE = 217,
    GHOSTCLOTHES = 218,
    ROYAL_DRESS = 219,
    FULL_MAIL = 220,
    OLD_ARMOR = 221,
    ZIRCON_PLATE = 222,
    ZIRCON_ARMOR = 223,
    MIRAK_PLATE = 224,
    RUSE_ARMOR = 225,
    PEARL_ARMOR = 226,
    CHOP_BOARD = 227,
    SMALL_SHIELD = 228,
    HIDE_SHIELD = 229,
    BUCKLER = 230,
    MINI_SHIELD = 231,
    WOOD_SHIELD = 232,
    BRACELET = 233,
    POWER_BRACE = 234,
    KITE_SHIELD = 235,
    TOUGH_GLOVES = 236,
    BRONE_SHIELD = 237,
    ANGER_BRACE = 238,
    BLOCK_SHIELD = 239,
    TECTO_GLOVES = 240,
    ROUND_SHIELD = 241,
    PEARL_BRACE = 242,
    FAYZA_SHIELD = 243,
    BIG_SHIELD = 244,
    TALL_SHIELD = 245,
    SILVO_SHIELD = 246,
    SPIKE_SHIELD = 247,
    SLASH_SHIELD = 248,
    MAGE_SHIELD = 249,
    TUFF_BUCKLER = 250,
    TECT_BUCKLER = 251,
    GOLD_GLOVES = 252,
    GOLD_SHIELD = 253,
    PLATI_GLOVES = 254,
    PLATI_SHIELD = 255,
    GAUNTLET = 256,
    RUNE_GLOVES = 257,
    HOLY_SHIELD = 258,
    ZIRCO_GLOVES = 259,
    ZIRCO_SHIELD = 260,
    OLD_SHIELD = 261,
    FLAME_SHIELD = 262,
    WATER_GAUNT = 263,
    BOLT_SHIELD = 264,
    CRYST_SHIELD = 265,
    MEGA_SHIELD = 266,
    DARK_MIRROR = 267,
    DARK_MIRROR_268 = 268,
    APRON_SHIELD = 269,
    PEARL_SHIELD = 270,
    POT = 271,
    BERET = 272,
    CAP = 273,
    CLOTH_HELMET = 274,
    HAIRBAND = 275,
    HEADBAND = 276,
    HIDE_HELMET = 277,
    JET_HELM = 278,
    RED_BERET = 279,
    GLASS_CAP = 280,
    WOOD_HELMET = 281,
    BLUE_BERET = 282,
    BRONE_HELMET = 283,
    STONE_HELMET = 284,
    CLOCHE = 285,
    FURY_HELMET = 286,
    IRON_HELMET = 287,
    TIGHT_HELMET = 288,
    TURBAN = 289,
    PLATE_CAP = 290,
    ROOMY_HELMET = 291,
    TIGHT_TURBAN = 292,
    GLASS_CLOCHE = 293,
    PLATE_HELMET = 294,
    ROCK_HELMET = 295,
    JUTE_HELMET = 296,
    SHADE_HAT = 297,
    METAL_CLOCHE = 298,
    SILVERHELMET = 299,
    FURY_RIBBON = 300,
    SILVER_HAT = 301,
    ERON_HAT = 302,
    CIRCLET = 303,
    GOLDEN_HELM = 304,
    GOLD_BAND = 305,
    PLATI_BAND = 306,
    PLATI_HELM = 307,
    CRYSTO_BERET = 308,
    CRYSTO_HELM = 309,
    HOLY_CAP = 310,
    SAFETY_HAT = 311,
    ZIRCO_BAND = 312,
    ZIRCO_HELMET = 313,
    OLD_HELMET = 314,
    AGONY_HELM = 315,
    BOOM_TURBAN = 316,
    AQUA_HELM = 317,
    ICE_HAIRBAND = 318,
    LEGEND_HELM = 319,
    HAIRPIN = 320,
    BRILL_HELM = 321,
    PEARL_HELMET = 322,
    EAR_JEWEL = 323,
    GLASS_BRACE = 324,
    GLASS_RING = 325,
    EARRING = 326,
    SPEEDY_RING = 327,
    POWER_RING = 328,
    MUSCLE_RING = 329,
    PROTECT_RING = 330,
    MIND_RING = 331,
    WITCH_RING = 332,
    FIRE_RING = 333,
    WATER_RING = 334,
    ICE_RING = 335,
    THUNDER_RING = 336,
    FURY_RING = 337,
    MYSTERY_RING = 338,
    SONIC_RING = 339,
    HIPOWER_RING = 340,
    TRICK_RING = 341,
    FAKE_RING = 342,
    S_FIRE_RING = 343,
    S_WATER_RING = 344,
    S_ICE_RING = 345,
    S_THUN_RING = 346,
    S_POWER_RING = 347,
    S_MIND_RING = 348,
    S_PRO_RING = 349,
    S_WITCH_RING = 350,
    UNDEAD_RING = 351,
    ROCKET_RING = 352,
    GHOST_RING = 353,
    ANGRY_RING = 354,
    S_MYST_RING = 355,
    DIA_RING = 356,
    SEA_RING = 357,
    DRAGON_RING = 358,
    ENGAGE_RING = 359,
    EGG_RING = 360,
    HORSE_ROCK = 361,
    EAGLE_ROCK = 362,
    LION_FANG = 363,
    BEE_ROCK = 364,
    SNAKE_ROCK = 365,
    CANCER_ROCK = 366,
    PUMKIN_JEWEL = 367,
    UNI_JEWEL = 368,
    MYSTO_JEWEL = 369,
    SAMU_JEWEL = 370,
    BAT_ROCK = 371,
    HIDORA_ROCK = 372,
    FLAME_JEWEL = 373,
    WATER_JEWEL = 374,
    THUNDO_JEWEL = 375,
    EARTH_JEWEL = 376,
    TWIST_JEWEL = 377,
    GLOOM_JEWEL = 378,
    TIDAL_JEWEL = 379,
    MAGMA_ROCK = 380,
    EVIL_JEWEL = 381,
    EVIL_JEWEL_382 = 382,
    GORGON_ROCK = 383,
    SONG_ROCK = 384,
    KRAKEN_ROCK = 385,
    CATFISH_JWL = 386,
    CAMU_JEWEL = 387,
    SPIDO_JEWEL = 388,
    GORGAN_ROCK = 389,
    LIGHT_JEWEL = 390,
    BLACK_EYE = 391,
    SILVER_EYE = 392,
    GOLD_EYE = 393,
    ITEM_1_COIN = 394,
    ITEM_10_COIN_SET = 395,
    ITEM_50_COIN_SET = 396,
    ITEM_100_COIN_SET = 397,
    FLAME_CHARM = 398,
    ZAP_CHARM = 399,
    MAGIC_LAMP = 400,
    STATUE = 401,
    RAGE_KNIFE = 402,
    FORTUNE_WHIP = 403,
    DRAGON_BLADE = 404,
    BUNNY_RING = 405,
    BUNNY_EARS = 406,
    BUNNYLADY = 407,
    BUNNY_SWORD = 408,
    BUNNYSUIT = 409,
    SEETHRU_CAPE = 410,
    SEETHRU_SILK = 411,
    IRIS_SWORD = 412,
    IRIS_SHIELD = 413,
    IRIS_HELMET = 414,
    IRIS_ARMOR = 415,
    IRIS_RING = 416,
    IRIS_JEWEL = 417,
    IRIS_STAFF = 418,
    IRIS_POT = 419,
    IRIS_TIARA = 420,
    POWER_JELLY = 421,
    JEWEL_SONAR = 422,
    HOOK = 423,
    BOMB = 424,
    ARROW = 425,
    FIRE_ARROW = 426,
    HAMMER = 427,
    TREAS_SWORD = 428,
    DOOR_KEY = 429,
    SHRINE_KEY = 430,
    SKY_KEY = 431,
    LAKE_KEY = 432,
    RUBY_KEY = 433,
    WIND_KEY = 434,
    CLOUD_KEY = 435,
    LIGHT_KEY = 436,
    SWORD_KEY = 437,
    TREE_KEY = 438,
    FLOWER_KEY = 439,
    MAGMA_KEY = 440,
    HEART_KEY = 441,
    GHOST_KEY = 442,
    TRIAL_KEY = 443,
    DANKIRK_KEY = 444,
    BASEMENT_KEY = 445,
    NARCYSUS_KEY = 446,
    TRUTH_KEY = 447,
    MERMAID_JADE = 448,
    ENGINE = 449,
    ANCIENT_KEY = 450,
    PRETTY_FLWR = 451,
    GLASS_ANGEL = 452,
    VIP_CARD = 453,
    KEY26 = 454,
    KEY27 = 455,
    KEY28 = 456,
    KEY29 = 457,
    KEY30 = 458,
    CROWN = 459,
    RUBY_APPLE = 460,
    PURIFIA = 461,
    TAG_RING = 462,
    TAG_RING_463 = 463,
    RAN_RAN_STEP = 464,
    TAG_CANDY = 465,
    LAST = 466,
};

enum MonsterId : u8 {
    GOBLIN = 0,
    ARMOR_GOBLIN = 1,
    REGAL_GOBLIN = 2,
    GOBLIN_MAGE = 3,
    TROLL = 4,
    ORK = 5,
    FIGHTER_ORK = 6,
    ORK_MAGE = 7,
    LIZARDMAN = 8,
    SKULL_LIZARD = 9,
    ARMOUR_DAIT = 10,
    DRAGONIAN = 11,
    CYCLOPS = 12,
    MEGA_CYCLOPS = 13,
    FLAME_GENIE = 14,
    WELL_GENIE = 15,
    WIND_GENIE = 16,
    EARTH_GENIE = 17,
    COBALT = 18,
    MERMAN = 19,
    AQUALOI = 20,
    IMP = 21,
    FIEND = 22,
    ARCHFIEND = 23,
    HOUND = 24,
    DOBEN = 25,
    WINGER = 26,
    SERFACO = 27,
    PUG = 28,
    SALAMANDER = 29,
    BRINZ_LIZARD = 30,
    SEAHORSE = 31,
    SEIREIN = 32,
    EARTH_VIPER = 33,
    GNOME = 34,
    WISPY = 35,
    THUNDERBEAST = 36,
    LUNAR_BEAR = 37,
    SHADOWFLY = 38,
    SHADOW = 39,
    LION = 40,
    SPHINX = 41,
    MAD_HORSE = 42,
    ARMOR_HORSE = 43,
    BUFFALO = 44,
    BRUSE = 45,
    BAT = 46,
    BIG_BAT = 47,
    RED_BAT = 48,
    EAGLE = 49,
    HAWK = 50,
    CROW = 51,
    BABY_FROG = 52,
    KING_FROG = 53,
    LIZARD = 54,
    NEWT = 55,
    NEEDLE_LIZARD = 56,
    POISON_LIZARD = 57,
    MEDUSA = 58,
    RAMIA = 59,
    BASILISK = 60,
    COKATORIS = 61,
    SCORPION = 62,
    ANTARES = 63,
    SMALL_CRAB = 64,
    BIG_CRAB = 65,
    RED_LOBSTER = 66,
    SPIDER = 67,
    WEB_SPIDER = 68,
    BEETLE = 69,
    POISON_BEETLE = 70,
    MOSQUITO = 71,
    CORIDRAS = 72,
    SPINNER = 73,
    TARTONA = 74,
    ARMOUR_NAIL = 75,
    MOTH = 76,
    MEGA_MOTH = 77,
    BIG_BEE = 78,
    DARK_FLY = 79,
    STINGER = 80,
    ARMOR_BEE = 81,
    SENTOPEZ = 82,
    CANCER = 83,
    GARBOST = 84,
    BOLT_FISH = 85,
    MORAY = 86,
    SHE_VIPER = 87,
    ANGLER_FISH = 88,
    UNICORN = 89,
    EVIL_SHELL = 90,
    DRILL_SHELL = 91,
    SNELL = 92,
    AMMONITE = 93,
    EVIL_FISH = 94,
    SQUID = 95,
    KRAKEN = 96,
    KILLER_WHALE = 97,
    WHITE_WHALE = 98,
    GRIANOS = 99,
    BEHEMOTH = 100,
    PERCH = 101,
    CURRENT = 102,
    VAMPIRE_ROSE = 103,
    DESERT_ROSE = 104,
    VENUS_FLY = 105,
    MORAY_VINE = 106,
    TORRENT = 107,
    MAD_ENT = 108,
    CROW_KELP = 109,
    RED_PLANT = 110,
    LA_FLESHIA = 111,
    WHEEL_EEL = 112,
    SKELETON = 113,
    GHOUL = 114,
    ZOMBIE = 115,
    SPECTER = 116,
    DARK_SPIRIT = 117,
    SNATCHER = 118,
    JURAHAN = 119,
    DEMISE = 120,
    LEECH = 121,
    NECROMANCER = 122,
    HADE_CHARIOT = 123,
    HADES = 124,
    DARK_SKULL = 125,
    HADES_SKULL = 126,
    MUMMY = 127,
    VAMPIRE = 128,
    NOSFERATO = 129,
    GHOST_SHIP = 130,
    DEADLY_SWORD = 131,
    DEADLY_ARMOR = 132,
    T_REX = 133,
    BROKION = 134,
    PUMPKIN_HEAD = 135,
    MAD_HEAD = 136,
    SNOW_GAS = 137,
    GREAT_COCA = 138,
    GARGOYLE = 139,
    ROGUE_SHAPE = 140,
    BONE_GOREM = 141,
    NUBORG = 142,
    WOOD_GOREM = 143,
    MAD_GOREM = 144,
    GREEN_CLAY = 145,
    SAND_GOREM = 146,
    MAGMA_GOREM = 147,
    IRON_GOREM = 148,
    GOLD_GOREM = 149,
    HIDORA = 150,
    SEA_HIDORA = 151,
    HIGH_HIDORA = 152,
    KING_HIDORA = 153,
    ORKY = 154,
    WAIBAN = 155,
    WHITE_DRAGON = 156,
    RED_DRAGON = 157,
    BLUE_DRAGON = 158,
    GREEN_DRAGON = 159,
    BLACK_DRAGON = 160,
    COPPER_DRAGON = 161,
    SILVER_DRAGON = 162,
    GOLD_DRAGON = 163,
    RED_JELLY = 164,
    BLUE_JELLY = 165,
    BILI_JELLY = 166,
    RED_CORE = 167,
    BLUE_CORE = 168,
    GREEN_CORE = 169,
    NO_CORE = 170,
    MIMIC = 171,
    BLUE_MIMIC = 172,
    ICE_ROGE = 173,
    MUSHROOM = 174,
    BIG_MUSHR_M = 175,
    MINATAURUS = 176,
    GORGON = 177,
    NINJA = 178,
    ASASHIN = 179,
    SAMURAI = 180,
    DARK_WARRIOR = 181,
    OCHI_WARRIOR = 182,
    SLY_FOX = 183,
    TENGU = 184,
    WARM_EYE = 185,
    WIZARD = 186,
    DARK_SUM_NER = 187,
    BIG_CATFISH = 188,
    FOLLOWER = 189,
    TARANTULA = 190,
    PIERRE = 191,
    DANIELE = 192,
    VENGE_GHOST = 193,
    FIRE_DRAGON = 194,
    TANK = 195,
    IDURA = 196,
    CAMU = 197,
    GADES = 198,
    AMON = 199,
    ERIM = 200,
    DAOS = 201,
    LIZARD_MAN = 202,
    GOBLIN_203 = 203,
    SKELETON_204 = 204,
    REGAL_GOBLIN_205 = 205,
    GOBLIN_206 = 206,
    GOBLIN_MAGE_207 = 207,
    SLAVE = 208,
    FOLLOWER_209 = 209,
    GROUPIE = 210,
    EGG_DRAGON = 211,
    MUMMY_212 = 212,
    TROLL_213 = 213,
    GADES_214 = 214,
    IDURA_215 = 215,
    LION_216 = 216,
    ROGUE_FLOWER = 217,
    GARGOYLE_218 = 218,
    GHOST_SHIP_219 = 219,
    IDURA_220 = 220,
    SOLDIER = 221,
    GADES_222 = 222,
    MASTER = 223,
};

enum Spell : u8 {
    FLASH = 0,
    BOLT = 1,
    THUNDER = 2,
    SPARK = 3,
    FIREBALL = 4,
    FIREBIRD = 5,
    DROPLET = 6,
    VORTEX = 7,
    DRAGON = 8,
    GALE = 9,
    BLIZZARD = 10,
    ICE_VALK = 11,
    PERISH = 12,
    DESTROY = 13,
    DROWSY = 14,
    COMA = 15,
    DREAD = 16,
    DEFLECT = 17,
    ABSORB = 18,
    FAKE = 19,
    TRICK = 20,
    CONFUSE = 21,
    BRAVERY = 22,
    COURAGE = 23,
    MIRROR = 24,
    STRONG = 25,
    STRONGER = 26,
    CHAMPION = 27,
    POISON = 28,
    RALLY = 29,
    VALOR = 30,
    FRY = 31,
    ZAP = 32,
    SHIELD = 33,
    WAKEN = 34,
    RELEASE = 35,
    WARP = 36,
    ESCAPE = 37,
    RESET = 38,
    LIGHT = 39,
};

enum Zone : u8 {
    WORLD_MAP = 0,
    MAP_OF_SEAFLOOR = 1,
    AREK_DAOS_SHRINE = 2,
    ELCID = 3,
    ZONE_4 = 4,
    SECRET_SKILLS_CAVE = 5,
    TO_SUNDLETAN_B1 = 6,
    ZONE_2 = 7,
    ZONE_8 = 8,
    ZONE_9 = 9,
    LAKE_B1 = 10,
    B2 = 11,
    B3 = 12,
    ALUNZE_KINGDOM = 13,
    FOOMY_WOODS = 14,
    CASTLE = 15,
    ZONE_16 = 16,
    B2_17 = 17,
    B3_18 = 18,
    B4 = 19,
    B5 = 20,
    ZONE_21 = 21,
    ZONE_22 = 22,
    NORTH = 23,
    WEST_B1 = 24,
    B2_25 = 25,
    B3_26 = 26,
    B4_27 = 27,
    TANBEL = 28,
    ZONE_29 = 29,
    ZONE_30 = 30,
    SOUTHEAST_TOWER_1F = 31,
    ZONE_2F = 32,
    ZONE_3F = 33,
    ZONE_4F = 34,
    ZONE_5F = 35,
    ZONE_6F = 36,
    CLAMENTO = 37,
    ZONE_38 = 38,
    RUBY_B1 = 39,
    B2_40 = 40,
    B3_41 = 41,
    B4_42 = 42,
    SMALLPARCELYTE = 43,
    ZONE_44 = 44,
    ZONE_45 = 45,
    ZONE_46 = 46,
    ZONE_47 = 47,
    TREASURE_SWORD_1F = 48,
    ZONE_2F_49 = 49,
    ZONE_3F_50 = 50,
    ZONE_4F_51 = 51,
    B1 = 52,
    GORDOVAN = 53,
    ZONE_54 = 54,
    ZONE_55 = 55,
    WE = 56,
    WE2F = 57,
    WE3F = 58,
    WE4F = 59,
    WE5F = 60,
    WE6F = 61,
    MERIX_VILLAGE = 62,
    ZONE_63 = 63,
    BRIDGE_B1 = 64,
    ZONE_2_65 = 65,
    ZONE_3 = 66,
    ZONE_4_67 = 67,
    ZONE_5 = 68,
    BOUND = 69,
    ZONE_70 = 70,
    DUNGEO = 71,
    N_B2 = 72,
    N_B3 = 73,
    N_B4 = 74,
    ZONE_75 = 75,
    ANCIEN = 76,
    ZONE_2F_77 = 77,
    ZONE_3F_78 = 78,
    ZONE_4F_79 = 79,
    ZONE_5F_80 = 80,
    ZONE_6F_81 = 81,
    ZONE_7F = 82,
    ZONE_6F_83 = 83,
    ZONE_5F_84 = 84,
    ZONE_4F_85 = 85,
    ALEYN = 86,
    ZONE_87 = 87,
    LIGHTHOUSE_1F = 88,
    ZONE_2F_89 = 89,
    ZONE_3F_90 = 90,
    ZONE_4F_91 = 91,
    ZONE_5F_92 = 92,
    ZONE_6F_93 = 93,
    PORN = 94,
    PORN_95 = 95,
    PHANTOM_TREE_MOUNTAIN = 96,
    ZONE_97 = 97,
    ZONE_98 = 98,
    ZONE_99 = 99,
    ZONE_100 = 100,
    ZONE_101 = 101,
    ZONE_102 = 102,
    ZONE_103 = 103,
    GRUBERIK = 104,
    ZONE_105 = 105,
    NARCYSUS = 106,
    ZONE_107 = 107,
    ZONE_108 = 108,
    ACRIFIC = 109,
    E_2F = 110,
    E_3F = 111,
    E_4F = 112,
    E_5F = 113,
    E_6F = 114,
    KARLLOON = 115,
    ZONE_116 = 116,
    ZONE_1F = 117,
    ZONE_2F_118 = 118,
    ZONE_3F_119 = 119,
    B1_120 = 120,
    DOOL = 121,
    ZONE_122 = 122,
    ZONE_123 = 123,
    ZONE_124 = 124,
    LEXIAIA_LABORATORY = 125,
    FL = 126,
    FL_127 = 127,
    FL_128 = 128,
    FL_129 = 129,
    FL_130 = 130,
    FL_131 = 131,
    FL_132 = 132,
    FORFEIT_ISLAND = 133,
    ZONE_134 = 134,
    MARKAO = 135,
    DANKIRK = 136,
    ZONE_137 = 137,
    AURALIO = 138,
    ZONE_139 = 139,
    B1_140 = 140,
    B2_141 = 141,
    B3_142 = 142,
    B4_143 = 143,
    B5_144 = 144,
    FERIM = 145,
    ZONE_146 = 146,
    ZONE_147 = 147,
    ZONE_148 = 148,
    ZONE_2F_149 = 149,
    ZONE_3F_150 = 150,
    ZONE_4F_151 = 151,
    ZONE_5F_152 = 152,
    AGURIO = 153,
    ZONE_154 = 154,
    TREBLE = 155,
    ZONE_156 = 156,
    PICO_FOREST = 157,
    ZONE_158 = 158,
    DRAGON_EGG = 159,
    PORTRAVIA = 160,
    ZONE_161 = 161,
    KIRMO = 162,
    NO_RETURN = 163,
    ZONE_164 = 164,
    ZONE_165 = 165,
    ESTO = 166,
    ESTO_167 = 167,
    DIVINE_1F = 168,
    ZONE_2F_169 = 169,
    ZONE_3F_170 = 170,
    B1_171 = 171,
    BARNAN = 172,
    ZONE_173 = 173,
    STH_SUBMA = 174,
    VENGEANC = 175,
    ZONE_176 = 176,
    ZONE_177 = 177,
    ZONE_178 = 178,
    ZONE_179 = 179,
    E_B2 = 180,
    DE = 181,
    DE_182 = 182,
    ZONE_183 = 183,
    OF_TRUTH_1F = 184,
    ZONE_2F_185 = 185,
    ZONE_3F_186 = 186,
    ZONE_4F_187 = 187,
    ZONE_5F_188 = 188,
    ZONE_6F_189 = 189,
    CHAED = 190,
    ZONE_191 = 191,
    ZONE_192 = 192,
    ZONE_193 = 193,
    ZONE_194 = 194,
    ZONE_195 = 195,
    ZONE_196 = 196,
    ZONE_197 = 197,
    ZONE_198 = 198,
    ZONE_199 = 199,
    N = 200,
    NPREAMARL = 201,
    N_202 = 202,
    ZONE_203 = 203,
    ZONE_204 = 204,
    ZONE_205 = 205,
    ZONE_206 = 206,
    ZONE_207 = 207,
    ZONE_208 = 208,
    GRATZE = 209,
    B1_210 = 210,
    B2_211 = 211,
    B3_212 = 212,
    B4_213 = 213,
    ZONE_214 = 214,
    ZONE_215 = 215,
    NARVICK = 216,
    ZONE_217 = 217,
    ZONE_218 = 218,
    ZONE_219 = 219,
    ZONE_220 = 220,
    SHUMAN_LED = 221,
    ZONE_222 = 222,
    ZONE_223 = 223,
    ZONE_224 = 224,
    STRAHDA_LED = 225,
    ZONE_226 = 226,
    ZONE_227 = 227,
    ZONE_228 = 228,
    KAMIRNO_LED = 229,
    ZONE_230 = 230,
    ZONE_1F_231 = 231,
    ZONE_2F_232 = 232,
    ZONE_3F_233 = 233,
    ZONE_4F_234 = 234,
    ZONE_5F_235 = 235,
    ZONE_236 = 236,
    CAPSULNSTERS = 237,
    ZONE_238 = 238,
    ZONE_239 = 239,
    T = 240,
    T_FINAL_F = 241,
};

enum MapEvents : u8 {
    WORLD_MAP = 0,
    MAP_OF_SEAFLOOR = 1,
    AREK_DAOS_SHRINE = 2,
    ELCID = 3,
    MAP_4 = 4,
    SECRET_SKILLS_CAVE = 5,
    TO_SUNDLETAN_B1 = 6,
    MAP_2 = 7,
    MAP_8 = 8,
    MAP_9 = 9,
    LAKE_B1 = 10,
    B2 = 11,
    B3 = 12,
    ALUNZE_KINGDOM = 13,
    FOOMY_WOODS = 14,
    CASTLE = 15,
    MAP_16 = 16,
    B2_17 = 17,
    B3_18 = 18,
    B4 = 19,
    B5 = 20,
    MAP_21 = 21,
    MAP_22 = 22,
    NORTH = 23,
    WEST_B1 = 24,
    B2_25 = 25,
    B3_26 = 26,
    B4_27 = 27,
    TANBEL = 28,
    MAP_29 = 29,
    MAP_30 = 30,
    SOUTHEAST_TOWER_1F = 31,
    MAP_2F = 32,
    MAP_3F = 33,
    MAP_4F = 34,
    MAP_5F = 35,
    MAP_6F = 36,
    CLAMENTO = 37,
    MAP_38 = 38,
    RUBY_B1 = 39,
    B2_40 = 40,
    B3_41 = 41,
    B4_42 = 42,
    SMALLPARCELYTE = 43,
    MAP_44 = 44,
    MAP_45 = 45,
    MAP_46 = 46,
    MAP_47 = 47,
    TREASURE_SWORD_1F = 48,
    MAP_2F_49 = 49,
    MAP_3F_50 = 50,
    MAP_4F_51 = 51,
    B1 = 52,
    GORDOVAN = 53,
    MAP_54 = 54,
    MAP_55 = 55,
    WE = 56,
    WE2F = 57,
    WE3F = 58,
    WE4F = 59,
    WE5F = 60,
    WE6F = 61,
    MERIX_VILLAGE = 62,
    MAP_63 = 63,
    BRIDGE_B1 = 64,
    MAP_2_65 = 65,
    MAP_3 = 66,
    MAP_4_67 = 67,
    MAP_5 = 68,
    BOUND = 69,
    MAP_70 = 70,
    DUNGEO = 71,
    N_B2 = 72,
    N_B3 = 73,
    N_B4 = 74,
    MAP_75 = 75,
    ANCIEN = 76,
    MAP_2F_77 = 77,
    MAP_3F_78 = 78,
    MAP_4F_79 = 79,
    MAP_5F_80 = 80,
    MAP_6F_81 = 81,
    MAP_7F = 82,
    MAP_6F_83 = 83,
    MAP_5F_84 = 84,
    MAP_4F_85 = 85,
    ALEYN = 86,
    MAP_87 = 87,
    LIGHTHOUSE_1F = 88,
    MAP_2F_89 = 89,
    MAP_3F_90 = 90,
    MAP_4F_91 = 91,
    MAP_5F_92 = 92,
    MAP_6F_93 = 93,
    PORN = 94,
    PORN_95 = 95,
    PHANTOM_TREE_MOUNTAIN = 96,
    MAP_97 = 97,
    MAP_98 = 98,
    MAP_99 = 99,
    MAP_100 = 100,
    MAP_101 = 101,
    MAP_102 = 102,
    MAP_103 = 103,
    GRUBERIK = 104,
    MAP_105 = 105,
    NARCYSUS = 106,
    MAP_107 = 107,
    MAP_108 = 108,
    ACRIFIC = 109,
    E_2F = 110,
    E_3F = 111,
    E_4F = 112,
    E_5F = 113,
    E_6F = 114,
    KARLLOON = 115,
    MAP_116 = 116,
    MAP_1F = 117,
    MAP_2F_118 = 118,
    MAP_3F_119 = 119,
    B1_120 = 120,
    DOOL = 121,
    MAP_122 = 122,
    MAP_123 = 123,
    MAP_124 = 124,
    LEXIAIA_LABORATORY = 125,
    FL = 126,
    FL_127 = 127,
    FL_128 = 128,
    FL_129 = 129,
    FL_130 = 130,
    FL_131 = 131,
    FL_132 = 132,
    FORFEIT_ISLAND = 133,
    MAP_134 = 134,
    MARKAO = 135,
    DANKIRK = 136,
    MAP_137 = 137,
    AURALIO = 138,
    MAP_139 = 139,
    B1_140 = 140,
    B2_141 = 141,
    B3_142 = 142,
    B4_143 = 143,
    B5_144 = 144,
    FERIM = 145,
    MAP_146 = 146,
    MAP_147 = 147,
    MAP_148 = 148,
    MAP_2F_149 = 149,
    MAP_3F_150 = 150,
    MAP_4F_151 = 151,
    MAP_5F_152 = 152,
    AGURIO = 153,
    MAP_154 = 154,
    TREBLE = 155,
    MAP_156 = 156,
    PICO_FOREST = 157,
    MAP_158 = 158,
    DRAGON_EGG = 159,
    PORTRAVIA = 160,
    MAP_161 = 161,
    KIRMO = 162,
    NO_RETURN = 163,
    MAP_164 = 164,
    MAP_165 = 165,
    ESTO = 166,
    ESTO_167 = 167,
    DIVINE_1F = 168,
    MAP_2F_169 = 169,
    MAP_3F_170 = 170,
    B1_171 = 171,
    BARNAN = 172,
    MAP_173 = 173,
    STH_SUBMA = 174,
    VENGEANC = 175,
    MAP_176 = 176,
    MAP_177 = 177,
    MAP_178 = 178,
    MAP_179 = 179,
    E_B2 = 180,
    DE = 181,
    DE_182 = 182,
    MAP_183 = 183,
    OF_TRUTH_1F = 184,
    MAP_2F_185 = 185,
    MAP_3F_186 = 186,
    MAP_4F_187 = 187,
    MAP_5F_188 = 188,
    MAP_6F_189 = 189,
    CHAED = 190,
    MAP_191 = 191,
    MAP_192 = 192,
    MAP_193 = 193,
    MAP_194 = 194,
    MAP_195 = 195,
    MAP_196 = 196,
    MAP_197 = 197,
    MAP_198 = 198,
    MAP_199 = 199,
    N = 200,
    NPREAMARL = 201,
    N_202 = 202,
    MAP_203 = 203,
    MAP_204 = 204,
    MAP_205 = 205,
    MAP_206 = 206,
    MAP_207 = 207,
    MAP_208 = 208,
    GRATZE = 209,
    B1_210 = 210,
    B2_211 = 211,
    B3_212 = 212,
    B4_213 = 213,
    MAP_214 = 214,
    MAP_215 = 215,
    NARVICK = 216,
    MAP_217 = 217,
    MAP_218 = 218,
    MAP_219 = 219,
    MAP_220 = 220,
    SHUMAN_LED = 221,
    MAP_222 = 222,
    MAP_223 = 223,
    MAP_224 = 224,
    STRAHDA_LED = 225,
    MAP_226 = 226,
    MAP_227 = 227,
    MAP_228 = 228,
    KAMIRNO_LED = 229,
    MAP_230 = 230,
    MAP_1F_231 = 231,
    MAP_2F_232 = 232,
    MAP_3F_233 = 233,
    MAP_4F_234 = 234,
    MAP_5F_235 = 235,
    MAP_236 = 236,
    CAPSULNSTERS = 237,
    MAP_238 = 238,
    MAP_239 = 239,
    T = 240,
    T_FINAL_F = 241,
};

enum Capsule : u8 {
    FOOMY_S = 0,
    FOOMY_M = 1,
    FOOMY_L = 2,
    FOOMY_H = 3,
    GOLD_FOX = 4,
    SHAGGY = 5,
    SPRITE = 6,
    CUPID = 7,
    TWINKLE = 8,
    UNICORN = 9,
    HARD_HAT = 10,
    BLUEBIRD = 11,
    WINGED_HORSE = 12,
    GREEN_TITAN = 13,
    SKY_DRAGON = 14,
    RED_FISH = 15,
    TOADIE = 16,
    SEA_GIANT = 17,
    BLUE_TITAN = 18,
    FISH_HEAD = 19,
    MYCONIDO = 20,
    WOLFMAN = 21,
    MINI_IMP = 22,
    BIG_IMP = 23,
    RED_DRAGON = 24,
    RADDISHER = 25,
    RED_CAP = 26,
    GIANT = 27,
    STONEHEAD = 28,
    CENTAUR = 29,
    ARMOR_DOG = 30,
    WINGED_LION = 31,
    WING_LIZARD = 32,
    BLAZE_DRAGON = 33,
    FIREBIRD = 34,
};

enum IPAttack : u8 {
    REPEAT_ATTACK = 0,
    IRON_KICK = 1,
    MIRROR_BLOCK = 2,
    ZAP = 3,
    TEST = 4,
    BOMB_ATTACK = 5,
    FLAME_ATTACK = 6,
    THUNDER_BLAST = 7,
    WATER_ATTACK = 8,
    ICE_ATTACK = 9,
    LIGHT_ATTACK = 10,
    DIVE_BOMBER = 11,
    DRAGON_FURY = 12,
    BLAZE_ATTACK = 13,
    THUNDERBALL = 14,
    AQUA_ATTACK = 15,
    GLACIAL_BLAST = 16,
    HOLY_ENERGY = 17,
    DEADLY_SMASH = 18,
    DRAGON_RUSH = 19,
    DEVASTATION = 20,
    BATTLECRY = 21,
    BATTLE_FURY = 22,
    FATAL_BLOW = 23,
    MAGIC_REMOVER = 24,
    CONFUSION = 25,
    SLEEP_STINGER = 26,
    STUN_SHOCKER = 27,
    RE_ENERGIZE = 28,
    SACRED_SONG = 29,
    DIVINE_CURE = 30,
    SUDDEN_CURE = 31,
    HOLY_HEALING = 32,
    CRISIS_CURE = 33,
    MAGIC_CURE = 34,
    MAGIC_HEALING = 35,
    MAGIC_REBIRTH = 36,
    REVIVAL_SLEEP = 37,
    RECOVERY = 38,
    PARALYSIS_CURE = 39,
    ANTIDOTE = 40,
    FREE_MAGIC = 41,
    WAKENING = 42,
    REAWAKEN = 43,
    WAVE_MOTION = 44,
    REVIVER = 45,
    REBIRTH = 46,
    REJUVENATION = 47,
    REGENERATION = 48,
    BATTLE_LUST = 49,
    BESERKER = 50,
    IRONCLAD = 51,
    FORCEFIELD = 52,
    FLEET = 53,
    QUICKSILVER = 54,
    LIGHTBULB = 55,
    ILLUMINATION = 56,
    SPELL_REPEL = 57,
    AURA_PROTECT = 58,
    MENACE = 59,
    WEAPONWEAK = 60,
    SWORDSPLITTER = 61,
    WEAKPOINT = 62,
    MELTDOWN = 63,
    WEAKENER = 64,
    SLUGGISH = 65,
    SLOW = 66,
    FORGETFUL = 67,
    DIMWIT = 68,
    SPELLSTRUCK = 69,
    VULNERABLE = 70,
    BOLT = 71,
    THUNDER = 72,
    FIREBALL = 73,
    FIREBIRD = 74,
    VORTEX = 75,
    DRAGON = 76,
    BLIZZARD = 77,
    ICE = 78,
    PERISH = 79,
    DESTROY = 80,
    DREAD = 81,
    DEFLECT = 82,
    FAKE = 83,
    TRICK = 84,
    CONFUSE = 85,
    BRAVERY = 86,
    COURAGE = 87,
    MIRROR = 88,
    STRONGER = 89,
    CHAMPION = 90,
    FIRESTORM = 91,
    THUNDERSHRIEK = 92,
    TORRENT = 93,
    ARCTIC_FREEZE = 94,
    SWOOP = 95,
    DRAGONFIRE = 96,
    CELESTIAL = 97,
    HEALING = 98,
    POWER_HEALING = 99,
    MIRACLE = 100,
    PHOENIX = 101,
    NINJA = 102,
    SAMURAI = 103,
    INCENDIARY = 104,
    FROST = 105,
    VOLTAGE_BOLT = 106,
    GROUNDSHOCK = 107,
    GLOOMY = 108,
    BITE = 109,
    FRENZY = 110,
    VAMPIRE = 111,
    DIVE = 112,
    IMMOBILIZE = 113,
    TAIL_ATTACK = 114,
    TIDAL_WAVE = 115,
    DARK_FORCE = 116,
    HEAD_ATTACK = 117,
    MAGMA_BLAST = 118,
    TRIPLE_ATTACK = 119,
    COMBO_ATTACK = 120,
    GLOOMSPLASH = 121,
    DIAMOND_DUST = 122,
    STARDUST_BLOW = 123,
    AX_ATTACK = 124,
    SCISSOR_SLASH = 125,
    TWISTER = 126,
    FLASH = 127,
    DASH = 128,
    DO_RE_MI = 129,
    TEN_LEGGER = 130,
    BUSTER_ATTACK = 131,
    MEGA_QUAKE = 132,
    SPIDERWEB = 133,
    FURY_FORCE = 134,
    MIRACLE_CARE = 135,
    FLAME_GUARD = 136,
    THUNDER_GUARD = 137,
    WATER_GUARD = 138,
    ICE_GUARD = 139,
    POWER_GUARD = 140,
    SHADOW_GUARD = 141,
    LIGHT_GUARD = 142,
    FLAMEBLOCK = 143,
    THUNDERBLOCK = 144,
    WATER_SCREEN = 145,
    HOLY_SHIELD = 146,
    IRON_BARRIER = 147,
    DARK_MIST = 148,
    HOLY_WALL = 149,
    FLAME_RETURN = 150,
    THUNDERTURN = 151,
    AQUA_MIRROR = 152,
    ICE_MIRROR = 153,
    DARK_MIRROR = 154,
    HOLY_MIRROR = 155,
    BOOMERANG = 156,
    ANGER_MIRROR = 157,
    BRILLIANCE = 158,
    PHOENIX_BLOW = 159,
    SKYSPLITTER = 160,
    FLOOD = 161,
    DEEP_FREEZE = 162,
    SIZZLE = 163,
    HARDBOILED = 164,
    OCTO_STRIKE = 165,
    DOUBLE_SLASH = 166,
    ANCIENT_POWER = 167,
};

enum Word : u16 {
    CONGRATULATIONS = 0,
    SWORDSMANSHIP = 1,
    EARTHQUAKES = 2,
    INTERESTING = 3,
    SINISTRALS = 4,
    UNDERSTAND = 5,
    EVERYTHING = 6,
    CORONATION = 7,
    LIGHTHOUSE = 8,
    PERMISSION = 9,
    EVERYTHING_10 = 10,
    INVENTIONS = 11,
    MISFORTUNE = 12,
    SOMETHING = 13,
    COMMANDER = 14,
    PARCELYTE = 15,
    DESTROYED = 16,
    WONDERFUL = 17,
    DANGEROUS = 18,
    SUNDLETAN = 19,
    DIFFERENT = 20,
    SOMEWHERE = 21,
    NORTHEAST = 22,
    HAPPENING = 23,
    BEAUTIFUL = 24,
    COUNTRIES = 25,
    EXCELLENT = 26,
    SHOULDN_T = 27,
    IMPORTANT = 28,
    PORTRAVIA = 29,
    SOMETHING_30 = 30,
    MONSTERS = 31,
    ANYTHING = 32,
    PRINCESS = 33,
    EXCERION = 34,
    GORDOVAN = 35,
    HAPPENED = 36,
    TREASURE = 37,
    CEREMONY = 38,
    COULDN_T = 39,
    STRONGER = 40,
    YOURSELF = 41,
    EVERYONE = 42,
    FIGHTING = 43,
    HIGHNESS = 44,
    MOUNTAIN = 45,
    TOGETHER = 46,
    WOULDN_T = 47,
    BASEMENT = 48,
    APPEARED = 49,
    DEFEATED = 50,
    PROBABLY = 51,
    POSSIBLE = 52,
    MONSTERS_53 = 53,
    TREASURE_54 = 54,
    ANYWHERE = 55,
    GOODNESS = 56,
    MERMAIDS = 57,
    REMEMBER = 58,
    UPSTAIRS = 59,
    WARRIORS = 60,
    PREAMARL = 61,
    SUDDENLY = 62,
    STRENGTH = 63,
    TRAINING = 64,
    THINKING = 65,
    WHATEVER = 66,
    WHENEVER = 67,
    ALRIGHT = 68,
    THERE_S = 69,
    ALRIGHT_70 = 70,
    THOUGHT = 71,
    NOTHING = 72,
    MAJESTY = 73,
    THROUGH = 74,
    BELIEVE = 75,
    KINGDOM = 76,
    THERE_S_77 = 77,
    WITHOUT = 78,
    SOMEONE = 79,
    WELCOME = 80,
    DESTROY = 81,
    BECAUSE = 82,
    AURALIO = 83,
    JOURNEY = 84,
    VILLAGE = 85,
    WARRIOR = 86,
    ANYTIME = 87,
    HAVEN_T = 88,
    MONSTER = 89,
    CAREFUL = 90,
    DANKIRK = 91,
    LOOKING = 92,
    ANCIENT = 93,
    COUNTRY = 94,
    DOESN_T = 95,
    ALREADY = 96,
    KINGDOM_97 = 97,
    THEY_RE = 98,
    WAITING = 99,
    CHANGED = 100,
    STRANGE = 101,
    FLOWERS = 102,
    PROMISE = 103,
    PROTECT = 104,
    BESIDES = 105,
    WORD_FINALLY = 106,
    AMAZING = 107,
    CAPSULE = 108,
    CURRENT = 109,
    PROBLEM = 110,
    STOPPED = 111,
    TALKING = 112,
    WORRIED = 113,
    DISPLAY = 114,
    FEELING = 115,
    GRANDPA = 116,
    TOWARDS = 117,
    DUNGEON = 118,
    DESTINY = 119,
    VILLAGE_120 = 120,
    REALLY = 121,
    PLEASE = 122,
    THAT_S = 123,
    YOU_RE = 124,
    YOU_RE_125 = 125,
    PEOPLE = 126,
    THAT_S_127 = 127,
    SHOULD = 128,
    STRONG = 129,
    SHRINE = 130,
    ANYWAY = 131,
    WONDER = 132,
    ISLAND = 133,
    BEFORE = 134,
    ENERGY = 135,
    PRINCE = 136,
    AROUND = 137,
    COURSE = 138,
    WHAT_S = 139,
    CASTLE = 140,
    PLEASE_141 = 141,
    BATTLE = 142,
    PIECES = 143,
    ISLAND_144 = 144,
    ALWAYS = 145,
    DEFEAT = 146,
    DIDN_T = 147,
    THANKS = 148,
    PRETTY = 149,
    AREN_T = 150,
    CALLED = 151,
    INSIDE = 152,
    ENGINE = 153,
    WORD_RETURN = 154,
    THINGS = 155,
    CANNOT = 156,
    YOU_LL = 157,
    LITTLE = 158,
    SHRINE_159 = 159,
    COMING = 160,
    ENOUGH = 161,
    HAPPEN = 162,
    BUTTON = 163,
    HUMANS = 164,
    EASILY = 165,
    STOLEN = 166,
    MINUTE = 167,
    REALLY_168 = 168,
    TANBEL = 169,
    WANTED = 170,
    BETTER = 171,
    AGURIO = 172,
    BRIDGE = 173,
    MYSELF = 174,
    PEOPLE_175 = 175,
    PERSON = 176,
    YOU_VE = 177,
    MATTER = 178,
    BEINGS = 179,
    CHANCE = 180,
    INDEED = 181,
    TRYING = 182,
    FRIEND = 183,
    FLOWER = 184,
    LISTEN = 185,
    MASTER = 186,
    SAYING = 187,
    YOU_VE_188 = 188,
    ALUNZE = 189,
    ANYWAY_190 = 190,
    BEYOND = 191,
    DRAGON = 192,
    SISTER = 193,
    RIGHT = 194,
    DON_T = 195,
    SELAN = 196,
    GOING = 197,
    CAN_T = 198,
    ABOUT = 199,
    THERE = 200,
    THINK = 201,
    GUESS = 202,
    LET_S = 203,
    WOULD = 204,
    GADES = 205,
    NEVER = 206,
    HEARD = 207,
    COULD = 208,
    AGAIN = 209,
    POWER = 210,
    DON_T_211 = 211,
    WORLD = 212,
    LIGHT = 213,
    LEXIS = 214,
    HELLO = 215,
    THANK = 216,
    WON_T = 217,
    FIGHT = 218,
    THERE_219 = 219,
    TODAY = 220,
    ARTEA = 221,
    BLADE = 222,
    GREAT = 223,
    SMALL = 224,
    THING = 225,
    FOUND = 226,
    NORTH = 227,
    DEKAR = 228,
    WORRY = 229,
    WOULD_230 = 230,
    CROWN = 231,
    NIGHT = 232,
    PLACE = 233,
    SHALL = 234,
    TOWER = 235,
    FLOOR = 236,
    PARTY = 237,
    THESE = 238,
    SWORD = 239,
    SORRY = 240,
    TOWER_241 = 241,
    WHERE = 242,
    STILL = 243,
    OTHER = 244,
    SPELL = 245,
    THOSE = 246,
    AFTER = 247,
    MIGHT = 248,
    LET_S_249 = 249,
    HILDA = 250,
    PEACE = 251,
    WRONG = 252,
    WOMAN = 253,
    LEAVE = 254,
    READY = 255,
    SUPER = 256,
    ITEMS = 257,
    JEROS = 258,
    KARYN = 259,
    BRING = 260,
    IDURA = 261,
    SINCE = 262,
    UNDER = 263,
    WORD_WHILE = 264,
    YOUNG = 265,
    ISN_T = 266,
    CLOSE = 267,
    DOING = 268,
    GLASS = 269,
    THANK_270 = 270,
    WHERE_271 = 271,
    AHEAD = 272,
    FOLKS = 273,
    LIVES = 274,
    NORTH_275 = 275,
    SWORD_276 = 276,
    SEEMS = 277,
    SOUTH = 278,
    WE_RE = 279,
    WE_LL = 280,
    LATER = 281,
    SENSE = 282,
    TRUTH = 283,
    WE_VE = 284,
    QUITE = 285,
    SHE_S = 286,
    SHE_S_287 = 287,
    UNTIL = 288,
    WAVES = 289,
    BEING = 290,
    FIRST = 291,
    YOU_D = 292,
    APPLE = 293,
    ENEMY = 294,
    LOOKS = 295,
    MADAM = 296,
    SEEMS_297 = 297,
    SOUTH_298 = 298,
    COMES = 299,
    ENTER = 300,
    HAPPY = 301,
    STUFF = 302,
    SHIPS = 303,
    THEIR = 304,
    TRUST = 305,
    MILKA = 306,
    RESET = 307,
    WORDS = 308,
    THAT = 309,
    THIS = 310,
    HAVE = 311,
    WHAT = 312,
    KNOW = 313,
    HERE = 314,
    IT_S = 315,
    WORD_WITH = 316,
    YOUR = 317,
    LIKE = 318,
    WILL = 319,
    JUST = 320,
    BACK = 321,
    THIS_322 = 322,
    WHAT_323 = 323,
    WELL = 324,
    TIME = 325,
    I_LL = 326,
    WORD_FROM = 327,
    IT_S_328 = 328,
    SHIP = 329,
    COME = 330,
    THAT_331 = 331,
    CAVE = 332,
    MUST = 333,
    GOOD = 334,
    SUCH = 335,
    WANT = 336,
    CITY = 337,
    ONLY = 338,
    THEM = 339,
    YOUR_340 = 340,
    TRUE = 341,
    YEAH = 342,
    WHEN = 343,
    TAKE = 344,
    I_VE = 345,
    BEEN = 346,
    MORE = 347,
    RUBY = 348,
    THEY = 349,
    HEAR = 350,
    AWAY = 351,
    DOOR = 352,
    ICON = 353,
    WISH = 354,
    WERE = 355,
    LONG = 356,
    OVER = 357,
    FIND = 358,
    VERY = 359,
    LOOK = 360,
    WHEN_361 = 361,
    MUCH = 362,
    THEN = 363,
    MAKE = 364,
    WENT = 365,
    SAID = 366,
    THEY_367 = 367,
    DUAL = 368,
    GOOD_369 = 369,
    SOME = 370,
    NEED = 371,
    STAY = 372,
    MEAN = 373,
    SURE = 374,
    BALL = 375,
    DOWN = 376,
    HOPE = 377,
    KING = 378,
    FEEL = 379,
    HELP = 380,
    CAME = 381,
    DAOS = 382,
    GIVE = 383,
    WELL_384 = 384,
    EVEN = 385,
    INTO = 386,
    LIFE = 387,
    LOVE = 388,
    NAME = 389,
    SOON = 390,
    COME_391 = 391,
    FINE = 392,
    MOVE = 393,
    STOP = 394,
    DAYS = 395,
    EVIL = 396,
    GUYS = 397,
    KNEW = 398,
    ROOM = 399,
    LEFT = 400,
    SEEN = 401,
    THAN = 402,
    CARE = 403,
    GETS = 404,
    HE_S = 405,
    OPEN = 406,
    TELL = 407,
    TALK = 408,
    ALSO = 409,
    MANY = 410,
    TOLD = 411,
    BEST = 412,
    EVEN_413 = 413,
    GONE = 414,
    ONCE = 415,
    DONE = 416,
    GOLD = 417,
    SHOW = 418,
    WAIT = 419,
    WAIT_420 = 420,
    AMON = 421,
    HE_S_422 = 422,
    HOME = 423,
    LAST = 424,
    LIVE = 425,
    NEXT = 426,
    WORK = 427,
    CASE = 428,
    EVER = 429,
    JUST_430 = 430,
    KIND = 431,
    MIND = 432,
    MADE = 433,
    MEET = 434,
    SAFE = 435,
    TOWN = 436,
    WORD_WITH_437 = 437,
    IRIS = 438,
    TOOK = 439,
    GLAD = 440,
    JYAD = 441,
    LEON = 442,
    REAL = 443,
    THEN_444 = 444,
    THE = 445,
    YOU = 446,
    YOU_447 = 447,
    WORD_AND = 448,
    THE_449 = 449,
    CAN = 450,
    ARE = 451,
    WORD_FOR = 452,
    SEE = 453,
    BUT = 454,
    I_M = 455,
    WORD_NOT = 456,
    WAS = 457,
    YES = 458,
    BUT_459 = 459,
    ALL = 460,
    GET = 461,
    NOW = 462,
    TOO = 463,
    ONE = 464,
    WAY = 465,
    ARE_466 = 466,
    DID = 467,
    OUT = 468,
    WHO = 469,
    HER = 470,
    SEA = 471,
    HAS = 472,
    ANY = 473,
    WHY = 474,
    GOT = 475,
    OUR = 476,
    WHY_477 = 477,
    HIM = 478,
    MAN = 479,
    SAY = 480,
    TIA = 481,
    HUH = 482,
    HEY = 483,
    GUY = 484,
    HOW = 485,
    WORD_AND_486 = 486,
    USE = 487,
    HOW_488 = 488,
    SHE = 489,
    HAD = 490,
    KEY = 491,
    I_D = 492,
    LET = 493,
    OFF = 494,
    MAY = 495,
    WHO_496 = 496,
    DID_497 = 497,
    SAW = 498,
    TWO = 499,
    WORD_TRY = 500,
    YET = 501,
    ASK = 502,
    HMM = 503,
    HIS = 504,
    NOW_505 = 505,
    SIR = 506,
    LET_507 = 507,
    WORD_NOT_508 = 508,
    BAD = 509,
    DIE = 510,
    SHE_511 = 511,
    KING_512 = 512,
    OF = 513,
    MY = 514,
    CCC = 515,
    S = 516,
    AVE = 517,
    WORD_518 = 518,
    WORD_519 = 519,
    TO = 520,
    WORD_IN = 521,
    WORD_522 = 522,
    WORD_IS = 523,
    A = 524,
    IT = 525,
    S_526 = 526,
    BE = 527,
    ME = 528,
    RE = 529,
    AT = 530,
    ON = 531,
    E = 532,
    ST = 533,
    SO = 534,
    WE = 535,
    Y = 536,
    GO = 537,
    DO = 538,
    LE = 539,
    AR = 540,
    D = 541,
    T = 542,
    WORD_AS = 543,
    TE = 544,
    F = 545,
    SE = 546,
    ES = 547,
    AN = 548,
    VE = 549,
    ED = 550,
    WORD_OR = 551,
    HA = 552,
    CH = 553,
    CE = 554,
    S_555 = 555,
    RI = 556,
    CO = 557,
    DE = 558,
    RO = 559,
    HE = 560,
    N = 561,
    ER = 562,
    LL = 563,
    LA = 564,
    UR = 565,
    O = 566,
    NE = 567,
    US = 568,
    NO = 569,
    UN = 570,
    G = 571,
    ND = 572,
    CC = 573,
    NG = 574,
    TR = 575,
    SI = 576,
    NT = 577,
    GE = 578,
    CA = 579,
    RA = 580,
    LY = 581,
    EN = 582,
    TI = 583,
    EA = 584,
    MA = 585,
    PE = 586,
    EL = 587,
    MO = 588,
    OO = 589,
    SS = 590,
    R = 591,
    LO = 592,
    OU = 593,
    AL = 594,
    UL = 595,
    IL = 596,
    K = 597,
    OF_598 = 598,
    FI = 599,
    DI = 600,
    AC = 601,
    PR = 602,
    SA = 603,
    IE = 604,
    TH = 605,
    M = 606,
    AD = 607,
    SH = 608,
    AY = 609,
    KE = 610,
    AI = 611,
    LI = 612,
    WA = 613,
    RS = 614,
    SU = 615,
    TA = 616,
    D_617 = 617,
    UT = 618,
    H = 619,
    RY = 620,
    L = 621,
    RD = 622,
    LD = 623,
    Y_624 = 624,
    HO = 625,
    ID = 626,
    HI = 627,
    MY_628 = 628,
    WI = 629,
    E_630 = 630,
    S_631 = 631,
    BU = 632,
    KI = 633,
    PL = 634,
    EE = 635,
    RT = 636,
    OW = 637,
    FO = 638,
    EM = 639,
};

enum Player : u8 {
    MAXIM = 0,
    SELAN = 1,
    GUY = 2,
    ARTY = 3,
    TIA = 4,
    DEKAR = 5,
    LEXIS = 6,
};

// Event flags (src/enums/flags.py EventFlag, from the TCRF notes). Flag n = bit n%8 of $7E:077E+n/8.
// Party: Maxim=1, Selan=2, Guy=3, Artea=4, Dekar=5, Tia=6, Lexis=7. 242-248 = Iris FOUND_* flags.
enum EventFlag : u8 {
    MAXIM_IN_PARTY = 1,
    SELAN_IN_PARTY = 2,
    GUY_IN_PARTY = 3,
    ARTEA_IN_PARTY = 4,
    DEKAR_IN_PARTY = 5,  // NB: Dekar is flag 5, Tia is flag 6 -- NOT index + 1 for these two.
    TIA_IN_PARTY = 6,
    LEXIS_IN_PARTY = 7,
    JELZE_JOINED = 8,  // Jelze (Foomy)
    FLASH_JOINED = 9,  // Flash (Shaggy)
    NEW_GAME_STARTED = 10,
    GUSTO_JOINED = 12,  // Gusto (Hard hat)
    ZAPPY_JOINED = 13,  // Zappy (Red Fish)
    SULLY_JOINED = 15,  // Sully (Radisher)
    BLAZE_JOINED = 16,  // Blaze (Armor Dog)
    FINISHED_TUTORIAL = 21,
    DINER_WITH_TIA_ELCID = 22,
    MET_IRIS_ELCID_CAVE = 23,
    SAVED_TIA_LAKE_CAVE = 24,
    KILLED_FISH_LAKE_CAVE = 25,
    TALKED_KING_ALUNZE = 26,
    PICKED_UP_CROWN = 27,
    RETURNED_CROWN_ALUNZE = 28,
    KILLED_REGAL_GOBLIN = 29,
    GUY_JOINED_STORY = 30,
    DEFEATED_CAMU = 31,
    RETURNED_HILDA_TANBEL = 32,
    TALKED_ROCHY_CLAMENTO = 33,
    KILLED_SPIDER_RUBY_CAVE = 35,
    RECEIVED_RUBY_APPLE = 36,
    DELIVERED_RUBY_APPLE = 37,
    FIRST_VISIT_PARCELYTE = 38,
    PARCELYTE_CASTLE_FIGHT = 39,
    SELAN_JOINED_STORY = 40,
    KILLED_PIERRE_FIRST = 41,
    KILLED_DANIELLE_FIRST = 42,
    SELAN_CLONES_TALK = 43,
    DEFEATED_PIERRE_DANIELLE = 44,
    TALKED_KING_GORDOVAN = 45,
    PASSED_GADES_GORDOVAN = 46,
    TALKED_KING_PARCELYTE = 47,
    DESTROYED_CRYSTAL_MERIX = 48,
    REPAIRED_BRIDGE_MERIX = 49,
    TALKED_KING_BOUND = 50,
    SAVED_PRINCE_BOUND = 51,
    DEKAR_GUY_JOINED_BOUND = 52,
    SUNDLETAN_EARTHQUAKE = 53,
    IDURA_KIDNAPPED_JEROS = 55,
    SAVED_JEROS = 57,
    TALKED_JYAD_PHANTOM_TREE = 58,
    PORTED_JYAD_ALEYN = 59,
    RESTED_TWICE_ALEYN = 60,
    NARCYSUS_WOMEN_FLEE = 62,
    NARCYSUS_WOMEN_FLEE_ALT = 63,
    IDURA_DEFEATED_SACRIFICE = 64,
    FINISHED_KARLLOON_TEMPLE = 65,
    TALKED_LEXIS_ASSISTANT_TREADOOL = 66,
    TALKED_LEXIS_LAB = 67,
    TALKED_SHIPBUILDER_ALEYN = 68,
    TALKED_FLOWER_GIRL_TREADOOL = 69,
    RECEIVED_PRETTY_FLOWER = 70,
    DELIVERED_PRIPHEA_LEFFA = 71,
    TALKED_KING_DANKIRK = 72,
    RUBY_ICON_MISSING = 73,
    TALKED_JAFFY_RUBY_ICON = 74,
    DELIVERED_RUBY_ICON_ALEX = 75,
    RETURNED_REAL_RUBY_ICON = 76,
    OPENED_WATER_GATE_AURALIO = 77,
    TALKED_FERIM_JEWEL = 78,
    MET_AMON_FIRST = 79,
    RETURNED_FERIM_KING = 80,
    TALKED_IRIS_AGURIO = 81,
    KIRMO_LAB_YES = 83,
    SAVED_MILKA = 84,
    AMON_DEFEATED_DIVINE = 85,
    GOT_SUBMARINE = 86,
    DEFEATED_GHOST_VENGEANCE = 87,
    TALKED_IRIS_BARNAN = 88,
    FINISHED_TOWER_OF_TRUTH = 89,
    FINISHED_DRAGON_MOUNTAIN = 90,
    TALKED_MERMAID_QUEEN = 92,
    DEFEATED_DOOM_SHIP = 93,
    TALKED_MERMAIDS_TEMPLE = 94,
    CHAED_DESTROYED = 95,
    TALKED_LEXIS_ENGINE = 96,
    KILLED_PRISON_SOLDIERS = 97,
    GOT_ENGINE = 98,
    GOT_AIRSHIP = 99,
    TALKED_NARVICK_1 = 100,
    NARVICK_FIRST_MAID = 101,
    GADES_DEFEATED = 102,
    TALKED_NARVICK_2 = 103,
    NARVICK_SECOND_MAID = 104,
    AMON_DEFEATED = 105,
    TALKED_NARVICK_3 = 106,
    NARVICK_THIRD_MAID = 107,
    OBTAINED_DUAL_BLADE = 108,
    PORTED_PORTRAVIA = 109,
    PORTRAVIA_CONVERSATION = 110,
    TALKED_LEXIS_FINAL = 111,
    GADES_DEFEATED_FINAL = 112,
    AMON_DEFEATED_FINAL = 113,
    ERIM_DEFEATED = 114,
    DAOS_DEFEATED = 115,
    FIRST_STONE_DESTROYED = 116,
    SECOND_STONE_DESTROYED = 117,
    THIRD_STONE_DESTROYED = 118,  // destroying the third stone starts the credits/outro
    TUTORIAL_INITIALIZED = 119,
    GUY_LEFT_PARCELYTE = 120,
    RESTED_TWICE_ALEYN_ALT = 121,
    TALKED_KING_ALUNZE_ALT = 124,
    OPENED_SHRINE_HILDA = 125,
    IRIS_JOINED_KARLLOON = 126,
    RECEIVED_SHIP_TREADOOL = 127,
    TALKED_IRIS_AGURIO_ALT = 128,
    DAOS_TELEPORTER_2 = 130,
    IDURA_KIDNAPPED_JEROS_ALT = 132,
    DEFEATED_GADES_ANCIENT_TOWER = 133,
    THIEVES_OPENED_PRISON = 134,
    TALKED_ROCHY_CLAMENTO_ALT = 136,
    MERIX_CAVE_CUTSCENE = 137,
    BOUND_ENTRANCE_CUTSCENE = 138,
    TALKED_JYAD_PHANTOM_TREE_ALT = 140,
    KILLED_LIONS_PHANTOM_TREE = 141,
    KILLED_IDURA_KARLLOON = 142,
    RECEIVED_PRETTY_FLOWER_ALT = 143,
    AMON_DEFEATED_DIVINE_ALT = 144,
    AMON_DEFEATED_DIVINE_ALT2 = 146,
    INSIDE_ANCIENT_CAVE = 147,
    OPENED_WATER_GATE_AURALIO_ALT = 148,
    OPENED_WATER_GATE_AURALIO_ALT2 = 149,
    KEY_GONE_ELCID = 150,
    ALUNZE_SEWER_SCENE = 151,
    TALKED_HILDA_TANBEL = 152,
    USED_SHIP_ALEYN = 153,
    TALKED_DEKAR_FIRST = 154,
    BOUND_GUARD_GADES = 155,
    IDURA_KIDNAPPED_JEROS_ALT2 = 156,
    DEKAR_GUY_JOINED_SHRINE = 157,
    TUTORIAL_CAVE_OLD_GUY = 158,
    TUTORIAL_JELLY_BEATEN = 159,
    TUTORIAL_MOVE_PILLAR = 160,
    TUTORIAL_JUMP_DOWN = 161,
    TUTORIAL_KILL_ALL = 162,
    TUTORIAL_CUT_GRASS = 163,
    ALUNZE_PASSED_OUT_GUY = 164,
    PICOLINA_AFTER_MILKA = 167,
    TALKED_ABEL_ALUNZE = 169,
    PICKED_UP_CROWN_ALT = 170,
    TUTORIAL_R_BUTTON = 171,
    TUTORIAL_UNDO_MAGIC = 172,
    KILLED_CLOWNS_SWORD_SHRINE = 177,
    DEKAR_GUY_JOINED_BOUND_ALT = 178,
    TALKED_BOY_TREBLE = 183,
    TALKED_GIRL_FOOMY = 185,
    DIVINE_POWER_PLATFORM = 186,
    FINISHED_KARLLOON_TEMPLE_ALT = 190,
    KILLED_EGG_DRAGON = 193,
    ANCIENT_CAVE_BOSS_KILLED = 195,
    GIFT_MODE = 196,  // party members standing in the pub of Gruberik (works in standard + Retry mode)
    DESTROYED_STATUES_ANCIENT_TOWER = 199,
    IRIS_TREASURE_01 = 200,
    IRIS_TREASURE_02 = 201,
    IRIS_TREASURE_03 = 202,
    IRIS_TREASURE_04 = 203,
    IRIS_TREASURE_05 = 204,
    IRIS_TREASURE_06 = 205,
    IRIS_TREASURE_07 = 206,
    IRIS_TREASURE_08 = 207,
    IRIS_TREASURE_09 = 208,
    IRIS_TREASURE_10 = 209,
    RETURNED_IRIS_SWORD = 210,
    RETURNED_IRIS_SHIELD = 211,
    RETURNED_IRIS_HELMET = 212,
    RETURNED_IRIS_ARMOR = 213,
    RETURNED_IRIS_RING = 214,
    RETURNED_IRIS_JEWEL = 215,
    RETURNED_IRIS_STAFF = 216,
    RETURNED_IRIS_POT = 217,
    RETURNED_IRIS_TIARA = 218,
    RETURNED_ANCIENT_CAVE_BOSS = 219,
    UNDO_MAGIC_RECEIVED = 240,
    UNDO_MAGIC_RECEIVED_ALT = 241,
    FOUND_MAXIM = 242,
    FOUND_SELAN = 243,
    FOUND_GUY = 244,
    FOUND_ARTEA = 245,
    FOUND_TIA = 246,
    FOUND_DEKAR = 247,
    FOUND_LEXIS = 248,
};


// =====================================================================================================
//  3. SMALL VALUE ENUMS AND BITFIELDS
// =====================================================================================================

// Event-list classes (the six offsets after a map's "PH" header).
enum EventClass : u8 {
    SETUP_MAP  = 0,   // A-class: runs when the map is set up
    LOAD_MAP   = 1,   // B-class: entrance cutscenes; index == spawn "entrance" byte
    REFERENCED = 2,   // C-class: called from other scripts
    NPC        = 3,   // D-class: talk-to-NPC scripts (index == NPC index)
    TILE       = 4,   // E-class: step-on tile triggers (ZoneData section 5)
    UNK_5      = 5,
    UNK_6      = 6
};

// L2BASM target selector (opcode 0x32). 0x05 combines with a previous target for "all".
enum BattleTarget : u8 {
    RandomFoe   = 0x01,
    AllModifier = 0x05,
    Self        = 0x06
};

// L2BASM status effect (opcodes 0x26 / 0x27). Status byte bits use the same order.
enum StatusEffect : u8 {
    Poison       = 0x00,
    Silence      = 0x01,
    InstantDeath = 0x02,
    Paralysis    = 0x03,
    Confusion    = 0x04,
    Sleep        = 0x05,
    Status6      = 0x06,
    Mirror       = 0x07
};

// L2BASM stat selector (opcodes 0x13 / 0x14 / 0x15 / 0x4E). [info] L2_Effects.txt.
enum StatRegister : u8 {
    CurHP = 0x00, CurMP = 0x01, MaxHP = 0x02, MaxMP = 0x03, ATP = 0x04, DFP = 0x05,
    STR = 0x06, AGL = 0x07, INT = 0x08, GUT = 0x09, MGR = 0x0A, IP = 0x0B, Level = 0x0C,
    TempATP = 0x0D, TempDFP = 0x0E, TempSTR = 0x0F, TempAGL = 0x10, TempINT = 0x11,
    TempGUT = 0x12, TempMGR = 0x13, Status = 0x14
};

// Elemental / effectiveness mask (L2BASM 0x1F / 0x21 / 0x22, spell element). Combined masks show as numbers.
bitfield ElementMask {
    vs_dragons : 1;   // 0x0001
    vs_insects : 1;   // 0x0002
    ice        : 1;   // 0x0004
    thunder    : 1;   // 0x0008
    earth      : 1;   // 0x0010
    vs_sea     : 1;   // 0x0020
    bit6       : 1;
    bit7       : 1;
    wind       : 1;   // 0x0100
    fire       : 1;   // 0x0200
    water      : 1;   // 0x0400
    soil       : 1;   // 0x0800
    light      : 1;   // 0x1000
    shadow     : 1;   // 0x2000
    vs_hard    : 1;   // 0x4000
    vs_flying  : 1;   // 0x8000
};

// Who may use / equip something (spells byte 10, items byte 8).
bitfield CharacterMask {
    maxim : 1; selan : 1; guy : 1; artea : 1; tia : 1; dekar : 1; lexis : 1; unused : 1;
};

// IP targeting cursor (IP record byte 3). [info] L2_IPDataFormat.txt
enum IPCursor : u8 {
    MenuHand    = 0x00,
    Sword       = 0x01,   // attack IPs
    Staff       = 0x02,   // spell IPs
    Pouch       = 0x03,   // items
    ChangeArrow = 0x04,
    Invisible   = 0xFF
};

// IP targeting mode (IP record byte 4).
enum IPTargetMode : u8 {
    NoTarget        = 0x00,   // all enemies / all allies / self
    AlliesSeveral   = 0x01,
    AllyOne         = 0x02,
    EnemiesSeveral  = 0x81,
    EnemyOne        = 0x82
};

// Shop header byte 0 (src/enums/flags.py ShopIdentifier).
enum ShopIdentifier : u8 {
    Generic = 0x00,
    Combat  = 0x01,
    Unused  = 0x02,   // most are unused, but not all (Bound Kingdom, Tia's shop)
    Spell   = 0x03
};

// Inventory / item-with-quantity word: item index in the low 9 bits, quantity above.
bitfield ItemStack {
    item     : 9;
    quantity : 7;
};


// =====================================================================================================
//  4. L2BASM  (battle / AI / effect bytecode)
// =====================================================================================================
//  One bytecode language runs monster attack/defense AI, capsule attack/reaction AI, item menu/battle/
//  weapon/armor effects, spell effects, IP effects, capsule-attack effects and the shared $42
//  subroutines. Interpreter: $85:B452 (parser), opcode jump table $85:B483 (93 entries, $00-$5C).
//
//  Operands are little-endian. Jump targets are u16 offsets from the "jump origin":
//    monster / capsule / item / spell records -> the record start
//    $42 subroutines                          -> the subroutine start
//    IP effects                               -> the table entry target (the $FF marker before the script)
//  Registers $80-$8F are script-local. Known RAM-ish registers used by the $42 bodies: $2A = damage
//  (negative hurts), $27 = attack element/effectiveness, $4E/$50/$52/$54/$56/$58 = target status
//  protections (poison/silence/instant death/paralysis/confusion/sleep).
//  Crash codes: a script that reaches 02, 31, 33, 34, 38, 39, 3A or 3B resets or hangs the game.

// Operand byte count per opcode: src/scripting/l2basm/opcodes.py PARAM_COUNTS
//   (0x46 = 3: condition + u16 jump; 0x3D = 1 and 0x4C = 1 from RAN-RAN step).
// With these, every vanilla monster / item / spell / IP / $42 / capsule / CapAttack script area decodes
// linearly with no unknown opcode and ends exactly at its record end (checked against the ROM).
fn l2basm_param_count(u8 op) {
    match (op) {
        (0x00 | 0x01 | 0x02 | 0x28 | 0x29 | 0x2A | 0x2E | 0x31 | 0x33 | 0x34 | 0x37 | 0x38 | 0x39 |
         0x3A | 0x3B | 0x3C | 0x41 | 0x43 | 0x49 | 0x4D | 0x4F | 0x50 | 0x51 | 0x52 | 0x58 | 0x59 |
         0x5B | 0x5C): { return 0; }
        (0x11 | 0x19 | 0x1A | 0x1B | 0x1C | 0x1D | 0x1E | 0x2C | 0x2D | 0x2F | 0x30 | 0x32 | 0x35 |
         0x36 | 0x3D | 0x3E | 0x40 | 0x4C | 0x53 | 0x54 | 0x5A): { return 1; }
        (0x03 | 0x04 | 0x12 | 0x13 | 0x14 | 0x15 | 0x1F | 0x20 | 0x23 | 0x25 | 0x26 | 0x27 | 0x2B |
         0x42 | 0x44 | 0x47 | 0x4E | 0x56): { return 2; }
        (0x05 | 0x0C | 0x0D | 0x0E | 0x0F | 0x10 | 0x16 | 0x17 | 0x18 | 0x3F | 0x46 | 0x55 | 0x57): { return 3; }
        (0x24): { return 4; }
        (0x06 | 0x07 | 0x08 | 0x09 | 0x0A | 0x0B | 0x21 | 0x22): { return 5; }
        (_): { return 0; }   // unknown opcode (0x45, 0x48, 0x4A, 0x4B, >0x5C): parsers stop here
    }
};

// L2BASM opcode names (src/scripting/l2basm/opcodes.py _TYPED names + _COMMENTS).
fn l2basm_op_name(u8 op) {
    match (op) {
        (0x00): { return "00 end: END"; }
        (0x01): { return "01 execute: Execute (don't exit) > I.E. For multiple actions"; }
        (0x02): { return "02 op_02: Reset's game."; }
        (0x03): { return "03 goto: GoTo"; }
        (0x04): { return "04 on_fail: On Failure GoTo"; }
        (0x05): { return "05 on_chance: On Chance GoTo"; }
        (0x06): { return "06 if_eq: If Equal GoTo"; }
        (0x07): { return "07 if_ne: If Not Equal GoTo"; }
        (0x08): { return "08 if_gt: If Greater GoTo"; }
        (0x09): { return "09 if_lt: If Less GoTo"; }
        (0x0A): { return "0A if_ge: If Greater or Equal GoTo"; }
        (0x0B): { return "0B if_le: If Less or Equal GoTo"; }
        (0x0C): { return "0C set_reg: Register Set"; }
        (0x0D): { return "0D add_reg: Register ADD +"; }
        (0x0E): { return "0E sub_reg: Register SUB -"; }
        (0x0F): { return "0F mul_reg: Register MUL *"; }
        (0x10): { return "10 div_reg: Register DIV /"; }
        (0x11): { return "11 rand: Register Rand"; }
        (0x12): { return "12 op_12: Unknown"; }
        (0x13): { return "13 op_13: Register Set Stat"; }
        (0x14): { return "14 op_14: Stat Set Register"; }
        (0x15): { return "15 op_15: Register Set Stat Self"; }
        (0x16): { return "16 op_16: Register AND"; }
        (0x17): { return "17 op_17: Register OR"; }
        (0x18): { return "18 op_18: Register XOR"; }
        (0x19): { return "19 op_19: Unknown"; }
        (0x1A): { return "1A op_1A: Register NEG"; }
        (0x1B): { return "1B op_1B: Unknown"; }
        (0x1C): { return "1C op_1C: Unknown"; }
        (0x1D): { return "1D op_1D: Cancel and continue?"; }
        (0x1E): { return "1E display_name_monster: Display Attack Name"; }
        (0x1F): { return "1F op_1F: Add Element"; }
        (0x20): { return "20 op_20: Critical Hit Chance"; }
        (0x21): { return "21 physical_damage: Physical Damage"; }
        (0x22): { return "22 magical_damage: Magical Damage"; }
        (0x23): { return "23 op_23: Bunny Sword"; }
        (0x24): { return "24 op_24: Restore Stat"; }
        (0x25): { return "25 op_25: Intensify Stat"; }
        (0x26): { return "26 op_26: Recover From Status"; }
        (0x27): { return "27 apply_status: Apply Status Effect"; }
        (0x28): { return "28 physical_attack: Physical Attack"; }
        (0x29): { return "29 defend: Defend"; }
        (0x2A): { return "2A flee: Flee"; }
        (0x2B): { return "2B use_item: Use Item"; }
        (0x2C): { return "2C cast_spell: Monster Cast Spell"; }
        (0x2D): { return "2D op_2D: Call Companions"; }
        (0x2E): { return "2E op_2E: Unknown"; }
        (0x2F): { return "2F op_2F: Unknown"; }
        (0x30): { return "30 op_30: Unknown"; }
        (0x31): { return "31 op_31: Unknown"; }
        (0x32): { return "32 target: Target"; }
        (0x33): { return "33 op_33: Reset game"; }
        (0x34): { return "34 op_34: Reset game"; }
        (0x35): { return "35 op_35: Special Item"; }
        (0x36): { return "36 op_36: Unknown"; }
        (0x37): { return "37 op_37: Weapon Physical Attack"; }
        (0x38): { return "38 op_38: Reset game"; }
        (0x39): { return "39 op_39: Reset game"; }
        (0x3A): { return "3A op_3A: Reset game"; }
        (0x3B): { return "3B op_3B: Reset game"; }
        (0x3C): { return "3C op_3C: Add INT to Damage"; }
        (0x3D): { return "3D op_3D: Unknown, 1 operand (RAN-RAN step: list of 3D XX after 4C 03)"; }
        (0x3E): { return "3E display_name: Display CM Attack Name"; }
        (0x3F): { return "3F learnable: Learnable Attack"; }
        (0x40): { return "40 op_40: Unknown"; }
        (0x41): { return "41 op_41: Wait > Checking Situation"; }
        (0x42): { return "42 call: Subroutine"; }
        (0x43): { return "43 return: Return from Subroutine"; }
        (0x44): { return "44 op_44: Unknown"; }
        (0x46): { return "46 branch_46: conditional branch: condition byte + u16 jump (item armor scripts)"; }
        (0x47): { return "47 op_47: Unknown"; }
        (0x49): { return "49 op_49: Unknown"; }
        (0x4C): { return "4C op_4C: Unknown, 1 operand (RAN-RAN step)"; }
        (0x4D): { return "4D op_4D: Unknown"; }
        (0x4E): { return "4E op_4E: Load Register > Stat Register"; }
        (0x4F): { return "4F op_4F: Exit without executing effect code"; }
        (0x50): { return "50 op_50: No Re-targetting Spells"; }
        (0x51): { return "51 op_51: Dark Reflector Effect"; }
        (0x52): { return "52 op_52: Reflector?"; }
        (0x53): { return "53 op_53: Unknown"; }
        (0x54): { return "54 op_54: Cast IP Spell?"; }
        (0x55): { return "55 op_55: Unsigned Division?"; }
        (0x56): { return "56 op_56: Attack Name Duration"; }
        (0x57): { return "57 op_57: Item Effectiveness > Spell"; }
        (0x58): { return "58 op_58: Empty temp stat registers. (Eerie Light Effect)"; }
        (0x59): { return "59 op_59: Empty temp stat registers. (Enemies)"; }
        (0x5A): { return "5A battle_anim: Call Battle Animation"; }
        (0x5B): { return "5B op_5B: Lose on Master Suicide"; }
        (0x5C): { return "5C op_5C: Hide damage dealt"; }
        (_): { return std::format("{:02X} unknown opcode", op); }
    }
};

// $42 subroutine descriptions, read from the bodies (opcodes.py SUBROUTINE_DESCRIPTIONS).
fn subroutine_name(u8 index) {
    match (index) {
        (0x00): { return "42 00: fire damage x2"; }
        (0x01): { return "42 01: thunder damage x2"; }
        (0x02): { return "42 02: water damage x2"; }
        (0x03): { return "42 03: ice damage x2"; }
        (0x04): { return "42 04: only anti-flying: damage x2; only earth: damage 0"; }
        (0x05): { return "42 05: light damage x2"; }
        (0x06): { return "42 06: fire damage /2"; }
        (0x07): { return "42 07: thunder damage /2"; }
        (0x08): { return "42 08: water damage /2"; }
        (0x09): { return "42 09: ice damage /2"; }
        (0x0A): { return "42 0A: light damage /2"; }
        (0x0B): { return "42 0B: neutral-only damage /2"; }
        (0x0C): { return "42 0C: only anti-dragon: damage x2"; }
        (0x0D): { return "42 0D: shadow damage x2"; }
        (0x0E): { return "42 0E: shadow damage /2"; }
        (0x0F): { return "42 0F: only anti-hard: damage x2"; }
        (0x10): { return "42 10: only anti-insect: damage x2"; }
        (0x11): { return "42 11: full protection: clear $4E $50 $54 $56 $58 (poison, silence, paralysis, confusion, sleep)"; }
        (0x12): { return "42 12: healing turns into damage; clear $52 (instant death); op 35"; }
        (0x13): { return "42 13: DFP soaks damage: $2A = -(DFP/2 + (-$2A - DFP/2)/10)"; }
        (0x14): { return "42 14: non-neutral damage /2"; }
        (0x15): { return "42 15: element in reg $81: damage 0"; }
        (0x16): { return "42 16: element in reg $80: damage heals instead"; }
        (0x17): { return "42 17: only anti-hard: damage /2"; }
        (0x18): { return "42 18: element in reg $81: damage /2, reg $86 - 1"; }
        (0x19): { return "42 19: element in reg $81: damage 0, reg $86 - 1"; }
        (0x1A): { return "42 1A: element in reg $81: op 51"; }
        (0x1B): { return "42 1B: $52 (instant death) / reg $80"; }
        (0x1C): { return "42 1C: $4E / reg $80"; }
        (0x1D): { return "42 1D: $56 / reg $80"; }
        (0x1E): { return "42 1E: $54 / reg $80"; }
        (0x1F): { return "42 1F: $58 / reg $80"; }
        (0x20): { return "42 20: $50 / reg $80"; }
        (0x21): { return "42 21: reg $80 = own ATP x 1.5"; }
        (0x22): { return "42 22: $2A = -(reg $80 x 2 + target DFP / 2)"; }
        (0x23): { return "42 23: reg $80 = own ATP + temporary ATP bonus"; }
        (0x24): { return "42 24: damage 0 unless $2A > 0"; }
        (0x25): { return "42 25: reg $80 = % of HP lost; reg $81 = GUT x 25 / reg $82"; }
        (0x26): { return "42 26: reg $80 = 3; reg $81 = RAND(3) + 1"; }
        (0x27): { return "42 27: reg $80 - 1; reg $81 + 1, wrapping 4 to 1"; }
        (0x28): { return "42 28: evade: unless $23 == 2, a faster target may dodge (damage 0)"; }
        (_): { return std::format("42 {:02X}: undocumented", index); }
    }
};

fn fmt_l2basm_op(u8 op)     { return l2basm_op_name(op); };
fn fmt_subroutine(u8 index) { return subroutine_name(index); };

// `origin` is the script's jump origin (see above); every jump_target is a pointer to origin + value.
struct BattleInstruction<auto origin> {
    u32 jump_origin = origin;
    u8 opcode [[format("fmt_l2basm_op")]];
    match (opcode) {
        (0x03 | 0x04): { Ref16<jump_origin> jump_target; }
        (0x05):        { u8 chance; Ref16<jump_origin> jump_target [[comment("taken with probability chance/256 (?)")]]; }
        (0x06 | 0x07 | 0x08 | 0x09 | 0x0A | 0x0B): { u8 reg; u16 value; Ref16<jump_origin> jump_target; }
        (0x0C | 0x0D | 0x0E | 0x0F | 0x10 | 0x16 | 0x17 | 0x18): { u8 reg; u16 value; }
        (0x11):        { u8 reg [[comment("reg = RAND(reg)")]]; }
        (0x13 | 0x14 | 0x15 | 0x4E): { u8 reg; StatRegister stat; }
        (0x1E | 0x3E): { u8 attack_name [[comment("0x1E: enemy attack name (0x2F2D7 table); 0x3E: capsule attack (CapAttack index, ends the turn)")]]; }
        (0x1F):        { ElementMask element; }
        (0x20):        { u16 crit_chance; }
        (0x21 | 0x22): { ElementMask element; u16 base_damage; u8 extra; }
        (0x24):        { u8 stat_type; u16 base_value; u8 fluctuation; }
        (0x25):        { u8 stat_type; u8 intensity; }
        (0x26 | 0x27): { StatusEffect status; u8 probability; }
        (0x2B):        { Item item; }
        (0x2C | 0x54): { Spell spell [[comment("0x2C: cast (uses MP, freezes capsules); 0x54: MP-free cast, no name shown")]]; }
        (0x2D):        { MonsterId monster; }
        (0x32):        { BattleTarget target; }
        (0x35):        { u8 special_type; }
        (0x3F):        { u8 slot; Ref16<jump_origin> jump_target [[comment("learnable (capsule) attack slot; jump if not learned (?)")]]; }
        (0x46):        { u8 condition; Ref16<jump_origin> jump_target [[comment("conditional branch in item armor scripts: falls through to the 'full' protection, jumps to the partial one (e.g. Water gaunt -> 42 08)")]]; }
        (0x42):        { u8 subroutine [[format("fmt_subroutine")]]; u8 zero; }
        (0x5A):        { u8 animation; }
        (_):           { u8 operands[l2basm_param_count(opcode)]; }
    }
};

// Decode up to and including the first END (0x00). A script's handler blocks often sit past its first
// END (reached by branches); use BattleScriptRegion when the end of the script area is known.
struct BattleScript<auto origin> {
    BattleInstruction<origin> instructions[while(std::mem::read_unsigned($, 1) != 0x00)];
    u8 end [[format("fmt_l2basm_op")]];
};

// Decode every instruction in [$, endAddr): the whole script area of a record, handlers included.
struct BattleScriptRegion<auto endAddr, auto origin> {
    BattleInstruction<origin> instructions[while($ < endAddr)];
};


// =====================================================================================================
//  5. L2SASM  (event / map script bytecode)
// =====================================================================================================
//  Interpreter: $80:9CB8-$80:9D3D (parser), opcode handlers $80:9D3E-$80:C10E, jump table at
//  $80:CA14 (file 0x4A14, 205 entries = opcodes $00-$CC; section 6, bank $80). Byte fetcher $80:C0B7.
//  Jump operands (ADDR) are u16 offsets from the start of the script's event-list block.
//  Text (TEXT operands) uses a dictionary codec: 0x05 XX / 0x06 XX = word XX from dictionary 1
//  (0x76A00) pages, 0x0A YY XX = copy from earlier text (LZ back-reference, count = high nibble + 2,
//  pointer = low 12 bits + 2 back from here), 0x01 / 0x0B end a quote, 0x03 = line break, 0x09 = hero name.

// L2SASM opcode names: short names from the old EventOp enum, descriptions from
// src/structures/event_script/opcodes.py op_codes (info/L2_ScriptEvents.txt).
fn event_op_name(u8 op) {
    match (op) {
        (0x00): { return "00 EndEvent: => END"; }
        (0x01): { return "01 Op01: => IN TEXT MODE: End of quote"; }
        (0x02): { return "02 Op02: => BRK"; }
        (0x03): { return "03 Op03: => IN TEXT MODE: line break"; }
        (0x04): { return "04 Op04: XX => IN TEXT MODE: Pause ([P XX])"; }
        (0x05): { return "05 Op05: XX => IN TEXT MODE: 05-shift"; }
        (0x06): { return "06 Op06: XX => IN TEXT MODE: 06-shift"; }
        (0x07): { return "07 Op07: XX => ???"; }
        (0x08): { return "08 TalkSpeak: => The character you're talking to speaks."; }
        (0x09): { return "09 Op09: => IN TEXT MODE: Hero's name (Maxim, if you didn't change it)"; }
        (0x0A): { return "0A Op0A: XX YY => 0A-pointer (relative)"; }
        (0x0B): { return "0B Op0B: => IN TEXT MODE: Selection Cursor (replaces 0x01 as EOQ byte). See 0x10"; }
        (0x0C): { return "0C Op0C: => IN TEXT MODE: ? + line break"; }
        (0x0D): { return "0D Op0D: => IN TEXT MODE: + line break"; }
        (0x0E): { return "0E Op0E: => IN TEXT MODE: , + line break"; }
        (0x0F): { return "0F Op0F: => IN TEXT MODE: . + line break"; }
        (0x10): { return "10 Choice: XX (P1 P1, ...) => XX Choice, 2-byte pointers to replies."; }
        (0x11): { return "11 Op11: => BRK"; }
        (0x12): { return "12 BranchVar: XX YY (P1 P1, ...) => ??? YY = the number of pointers"; }
        (0x13): { return "13 CharSpeak: XX => Character XX speaks spontaneously"; }
        (0x14): { return "14 BranchState: XX ... ? => ??? (0x14 FF => 2-bytes long instruction)"; }
        (0x15): { return "15 BranchFlagSet: XX YY ZZ => If the event flag number XX is set => JUMP TO [script start offset + ZZYY]"; }
        (0x16): { return "16 Warp: XX YY ZZ => (EXIT) go to map number XX; jump to part YY of the script (?); screen at position ZZ"; }
        (0x17): { return "17 Rest: XX => XX: - 0x00 => rest (at an inn)"; }
        (0x18): { return "18 Shop: XX => Enter shop menu, XX: shop number"; }
        (0x19): { return "19 Church: => Enter church menu"; }
        (0x1A): { return "1A SetFlag: XX => Set event bit number XX"; }
        (0x1B): { return "1B ClearFlag: XX => Clear event bit number XX"; }
        (0x1C): { return "1C Jump: XX YY => JUMP TO [script start offset + YYXX]"; }
        (0x1D): { return "1D SetVar: XX YY => Set Variable"; }
        (0x1E): { return "1E AddVar: XX YY => Add Value to Variable"; }
        (0x20): { return "20 GetItem0: XX YY => Get YY copies of item number 0x00XX"; }
        (0x21): { return "21 GetItem1: XX YY => Get YY copies of item number 0x01XX"; }
        (0x22): { return "22 GetGold: XX YY => Get YYXX GOLD"; }
        (0x23): { return "23 LearnSpell: XX YY => Party member XX learns the spell YY"; }
        (0x24): { return "24 RemoveItem0: XX YY => Remove item 0XX"; }
        (0x25): { return "25 RemoveItem1: XX YY => Remove item 1XX"; }
        (0x28): { return "28 Op28: => ?"; }
        (0x29): { return "29 IncreaseStat: XX YY ZZ => Randomly increases a pot. stat+ of character XX by max ZZ?"; }
        (0x2B): { return "2B CharJoin: XX => Character XX joins the party"; }
        (0x2C): { return "2C CharLeave: XX => Character XX leaves the party"; }
        (0x2D): { return "2D CharAppear: XX => Character XX appears"; }
        (0x2E): { return "2E CharDisappear: XX => Character XX disappears"; }
        (0x30): { return "30 MoveChar: XX YY => Instantly move character XX to pre-defined location YY"; }
        (0x31): { return "31 TurnChar: XX YY => Character XX turns (during conversation)"; }
        (0x32): { return "32 NpcWander: XX YY => Change NPC wander behavior"; }
        (0x33): { return "33 WalkRoute: XX YY => Character YY walks route XX"; }
        (0x34): { return "34 ChangeSprite: XX YY => Change the sprite of character XX (YY = new sprite number)"; }
        (0x35): { return "35 MoveRoamNPC: XX YY ZZ => Move roaming NPC"; }
        (0x37): { return "37 Pause: XX => Pause (duration: XX)"; }
        (0x38): { return "38 PauseLong: XX => Pause (Longer)"; }
        (0x39): { return "39 Op39: => dummy?"; }
        (0x3B): { return "3B ShowMapAt: XX => Show part of the map at pre-defined position XX"; }
        (0x3C): { return "3C GatherBehindMaxim: => Gather Behind Maxim"; }
        (0x3D): { return "3D HideBehindMaxim: XX => Hide Behind Maxim"; }
        (0x40): { return "40 KeyCheck: => Key check? (Only used in Ancient Cave lobby)"; }
        (0x41): { return "41 Op41: XX YY => Camera related (follow for X steps?)"; }
        (0x42): { return "42 Op42: => same as 0x00"; }
        (0x43): { return "43 OverwriteTiles: XX YY => Overwrite Map Tiles"; }
        (0x45): { return "45 Op45: XX YY ZZ => ?"; }
        (0x47): { return "47 SpeechBorder: XX => Speech border type"; }
        (0x48): { return "48 Op48: XX YY => ?"; }
        (0x49): { return "49 Op49: XX => ?"; }
        (0x4A): { return "4A Op4A: XX => ? (appearance of text in text boxes)"; }
        (0x4B): { return "4B BattleMusic: XX => Select music for battle?"; }
        (0x4C): { return "4C Sound: XX => Sound? (XX: sound number)"; }
        (0x4D): { return "4D Op4D: XX => ? (sound-related?) (can EXIT)"; }
        (0x4F): { return "4F Op4F: XX => dummy?"; }
        (0x50): { return "50 Op50: => ?"; }
        (0x51): { return "51 Op51: => ?"; }
        (0x53): { return "53 BossBattle: XX => Boss battle with boss party number XX"; }
        (0x54): { return "54 OpenDoor: XX => Open locked door? (Entrance index?)"; }
        (0x55): { return "55 Op55: XX => ?"; }
        (0x56): { return "56 StopEarthquake: => Stop earthquake. See opcode 0x5A."; }
        (0x57): { return "57 Op57: => ?"; }
        (0x58): { return "58 FadeBlack: XX => Fade to black"; }
        (0x59): { return "59 Luminosity: XX => Luminosity"; }
        (0x5A): { return "5A Earthquake: XX YY ZZ => Make an earthquake"; }
        (0x5B): { return "5B PlayCutscene: XX YY => Play Cutscene"; }
        (0x5E): { return "5E Op5E: XX => ? (EXIT)"; }
        (0x60): { return "60 Op60: XX YY => ?"; }
        (0x61): { return "61 MaximSpeak: => Maxim speaks spontaneously (also: Erim in the intro)"; }
        (0x62): { return "62 SelanSpeak: => Selan speaks"; }
        (0x63): { return "63 GuySpeak: => Guy speaks"; }
        (0x64): { return "64 ArteaSpeak: => Artea speaks"; }
        (0x65): { return "65 DekarSpeak: => Dekar speaks"; }
        (0x66): { return "66 TiaSpeak: => Tia speaks"; }
        (0x67): { return "67 LexisSpeak: => Lexis speaks"; }
        (0x68): { return "68 LoadNPC: XX YY => Character XX use sprite YY (used in map pre-scripts)"; }
        (0x69): { return "69 SetMapProps: XX => Set Map Properties (escapable, etc.)"; }
        (0x6A): { return "6A BranchFlagClear: XX YY ZZ => If the event flag number XX is clear => JUMP TO [script start offset + ZZYY]"; }
        (0x6B): { return "6B Op6B: => ?"; }
        (0x6C): { return "6C MoveCharXY: XX YY ZZ => character XX moves; YY: horizontally, ZZ: vertically"; }
        (0x6D): { return "6D CreditsText1: XX YY => display text like Main programmer"; }
        (0x6E): { return "6E CreditsText2: XX YY => display text like Akihiro Suzuki"; }
        (0x6F): { return "6F ChangeMusic: XX => Change map music"; }
        (0x70): { return "70 MusicOff: => map music off"; }
        (0x71): { return "71 Op71: => ?"; }
        (0x72): { return "72 Op72: => ? (sound-related)"; }
        (0x73): { return "73 Animation: XX YY => display an animation"; }
        (0x74): { return "74 BattleBackground: XX => Select the background for battles on that map"; }
        (0x75): { return "75 Op75: => ?"; }
        (0x76): { return "76 Op76: => ?"; }
        (0x77): { return "77 Op77: XX => same as 0xBE"; }
        (0x78): { return "78 Op78: => ?"; }
        (0x79): { return "79 Op79: => ?"; }
        (0x7B): { return "7B LoadMonsterNPC: XX YY => Load Monster NPC"; }
        (0x7C): { return "7C Op7C: XX => Set ship upgrades flag"; }
        (0x7D): { return "7D Op7D: XX => Set ship location flag"; }
        (0x7E): { return "7E Op7E: XX => Set ship on map flag"; }
        (0x7F): { return "7F Op7F: XX => Set exit town in ship flag"; }
        (0x80): { return "80 Op80: XX => Set a ship sprite"; }
        (0x81): { return "81 CapsuleJoins: XX => A Capsule Monster joins your party"; }
        (0x82): { return "82 Op82: => ?"; }
        (0x83): { return "83 CallExit: XX => Call Exit (EXITS, only used for Chaed)"; }
        (0x85): { return "85 Op85: XX YY => ?"; }
        (0x86): { return "86 Op86: XX YY => Character XX moves YY Animation"; }
        (0x87): { return "87 Op87: XX YY => ?"; }
        (0x88): { return "88 SetMapProps2: => Set Map Properties"; }
        (0x89): { return "89 Op89: XX => ?"; }
        (0x8A): { return "8A Op8A: => ?"; }
        (0x8B): { return "8B Op8B: XX YY ZZ => ?"; }
        (0x8C): { return "8C GetItemHold: XX YY ZZ => ZZ = the sprite that Maxim holds (Gets item)"; }
        (0x8D): { return "8D Op8D: X1..X6 => Wave-warping animation of the Sinistrals at pre-defined position X2"; }
        (0x8E): { return "8E Op8E: XX YY ZZ => ?"; }
        (0x8F): { return "8F Op8F: XX YY ZZ => Wave motion up-down"; }
        (0x90): { return "90 Op90: XX YY ZZ => Wave motion right-left"; }
        (0x91): { return "91 Op91: XX YY => ? (affects the last event flag)"; }
        (0x92): { return "92 Op92: XX => ? (affects the last event flag)"; }
        (0x94): { return "94 Op94: XX YY ZZ =>"; }
        (0x95): { return "95 Op95: XX YY ZZ => Screen tint animation"; }
        (0x97): { return "97 Op97: => ?"; }
        (0x98): { return "98 Op98: XX YY => Character XX thunder-warps (at the position YY?)"; }
        (0x99): { return "99 Op99: XX => ?"; }
        (0x9A): { return "9A Op9A: XX => ?"; }
        (0x9C): { return "9C Op9C: XX YY ZZ => ?"; }
        (0x9D): { return "9D Op9D: XX => ?"; }
        (0x9E): { return "9E OpenDialog: XX => open a dialog window, XX: top to bottom"; }
        (0x9F): { return "9F Op9F: XX YY ZZ => Wave motion shrink"; }
        (0xA0): { return "A0 OpA0: X1..X6 => ?"; }
        (0xA1): { return "A1 OpA1: XX YY => ?"; }
        (0xA2): { return "A2 OpA2: XX => ? (can EXIT)"; }
        (0xA3): { return "A3 OpA3: XX YY => Character XX... moves?"; }
        (0xA4): { return "A4 OpA4: => Pixelation of the screen for a very short time"; }
        (0xA5): { return "A5 OpA5: => load-a-game screen (after losing a boss battle)"; }
        (0xA6): { return "A6 OpA6: => ?"; }
        (0xA7): { return "A7 OpA7: XX => ?"; }
        (0xA8): { return "A8 OpA8: XX => 0xA8 00: leave items at level 1; 0xA8 01: take back items and stats"; }
        (0xA9): { return "A9 OpA9: XX YY => ?"; }
        (0xAA): { return "AA OpAA: => ?"; }
        (0xAB): { return "AB OpAB: XX => Check if you have enough dragon eggs"; }
        (0xAD): { return "AD OpAD: XX YY ZZ => Dragon eggs related? (Egg Dragon Shrine)"; }
        (0xAE): { return "AE OpAE: XX => ?"; }
        (0xAF): { return "AF OpAF: XX YY => Character XX flickers #YY: related to frequency"; }
        (0xB0): { return "B0 OpB0: XX => ?"; }
        (0xB1): { return "B1 OpB1: XX YY => ? (affects character number XX)"; }
        (0xB3): { return "B3 OpB3: XX => Party Members Change Facing"; }
        (0xB4): { return "B4 OpB4: XX YY ZZ => ?"; }
        (0xB5): { return "B5 OpB5: => ?"; }
        (0xB6): { return "B6 OpB6: XX YY => ?"; }
        (0xB7): { return "B7 OpB7: XX => ?"; }
        (0xB8): { return "B8 OpB8: => ? (can EXIT)"; }
        (0xB9): { return "B9 FillIP: XX => Fill IP bar of party member XX"; }
        (0xBA): { return "BA OpBA: XX => ?"; }
        (0xBB): { return "BB ShowReport: => Show the current report"; }
        (0xBC): { return "BC OpBC: => ? (EXIT)"; }
        (0xBD): { return "BD OpBD: XX YY => ?"; }
        (0xBE): { return "BE OpBE: XX => same as 0x77"; }
        (0xBF): { return "BF OpBF: XX YY ZZ => ?"; }
        (0xC0): { return "C0 OpC0: XX YY ZZ => ?"; }
        (0xC1): { return "C1 OpC1: XX YY => ?"; }
        (0xC2): { return "C2 OpC2: X1..X6 => ?"; }
        (0xC3): { return "C3 OpC3: X1..X6 => ?"; }
        (0xC4): { return "C4 ScrollScreen: XX YY => Scroll the screen to position x = XX y = YY"; }
        (0xC5): { return "C5 OpC5: => ?"; }
        (0xC6): { return "C6 OpC6: XX YY => Displays animation XX on sprite YY?"; }
        (0xC7): { return "C7 OpC7: => ?"; }
        (0xC9): { return "C9 OpC9: X1..X7 => ?"; }
        (0xCA): { return "CA OpCA: XX YY ZZ => ?"; }
        (0xCB): { return "CB OpCB: XX => ?"; }
        (0xCC): { return "CC OpCC: => ?"; }
        (_): { return std::format("{:02X} unknown", op); }
    }
};

fn fmt_event_op(u8 op) { return event_op_name(op); };

// Total size of the fixed (integer-only) operands. Opcodes with TEXT / ADDR / POINTERS / VARIABLE
// shapes are handled explicitly in EventInstruction.
fn event_fixed_len(u8 op) {
    match (op) {
        (0x00 | 0x0C | 0x0D | 0x11 | 0x19 | 0x28 | 0x39 | 0x3C | 0x42 | 0x50 | 0x51 | 0x56 | 0x57 |
         0x6B | 0x70 | 0x71 | 0x72 | 0x75 | 0x76 | 0x78 | 0x79 | 0x82 | 0x88 | 0x8A | 0x97 | 0xA4 |
         0xA5 | 0xA6 | 0xAA | 0xB5 | 0xB8 | 0xBB | 0xBC | 0xC5 | 0xC7 | 0xCC): { return 0; }
        (0x07 | 0x17 | 0x18 | 0x1A | 0x1B | 0x2B | 0x2C | 0x2D | 0x2E | 0x37 | 0x38 | 0x3B | 0x3D |
         0x47 | 0x49 | 0x4A | 0x4B | 0x4C | 0x4D | 0x4F | 0x53 | 0x54 | 0x55 | 0x58 | 0x59 | 0x5E |
         0x69 | 0x6F | 0x74 | 0x77 | 0x7C | 0x7D | 0x7E | 0x7F | 0x80 | 0x81 | 0x83 | 0x89 | 0x92 |
         0x99 | 0x9A | 0x9D | 0xA2 | 0xA7 | 0xA8 | 0xAB | 0xAE | 0xB0 | 0xB3 | 0xB7 | 0xB9 | 0xBA |
         0xBE | 0xCB): { return 1; }
        (0x01 | 0x02 | 0x03 | 0x04 | 0x05 | 0x06 | 0x1D | 0x1E | 0x20 | 0x21 | 0x22 | 0x23 | 0x24 |
         0x25 | 0x30 | 0x31 | 0x32 | 0x33 | 0x34 | 0x40 | 0x41 | 0x43 | 0x48 | 0x5B | 0x60 | 0x68 |
         0x73 | 0x7B | 0x85 | 0x86 | 0x87 | 0x91 | 0x98 | 0xA1 | 0xA3 | 0xA9 | 0xAF | 0xB1 | 0xB6 |
         0xBD | 0xC1 | 0xC4 | 0xC6): { return 2; }
        (0x16 | 0x29 | 0x35 | 0x45 | 0x5A | 0x6C | 0x8B | 0x8C | 0x8E | 0x8F | 0x90 | 0x94 | 0x95 |
         0x9C | 0x9F | 0xAD | 0xB4 | 0xBF | 0xC0 | 0xCA): { return 3; }
        (0x8D | 0xA0 | 0xC2 | 0xC3): { return 6; }
        (0xC9): { return 7; }
        (_): { return 0; }
    }
};

// Extra bytes after one sub-code of the 0x14 condition chain (event_script/script.py::_parse_variable).
fn event_var_extra(u8 code) {
    if ((code & 0xF0) == 0xF0) { return 2; }
    if ((code & 0xF0) == 0xC0) { return 4; }
    if ((code & 0xF0) == 0x10) { return 2; }
    if ((code & 0xE0) == 0x20) { return 2; }
    return 1;
};

// Text run up to its terminator. Leaves a 0x00 in place (so the script's END still fires) and consumes
// a 0x01 / 0x0B message-continue terminator. The dictionary / back-reference codec is not expanded.
struct EventText {
    u8 chars[while(
        std::mem::read_unsigned($, 1) != 0x00 &&
        std::mem::read_unsigned($, 1) != 0x01 &&
        std::mem::read_unsigned($, 1) != 0x0B)] [[color("81C784")]];
    if (std::mem::read_unsigned($, 1) == 0x01 || std::mem::read_unsigned($, 1) == 0x0B) {
        u8 terminator;
    }
};

// A 16-bit event address: an offset from the map's event-list block (`base`).
struct EventAddr<auto base> {
    u32 jump_origin = base;
    Ref16<jump_origin> target;
};

struct EventPointers<auto base> {
    u8 count;
    EventAddr<base> addresses[count];
};

struct EventVarSub {
    u8 code;
    u8 extra[event_var_extra(code)];
};

struct EventVariableChain {
    EventVarSub subs[while(std::mem::read_unsigned($, 1) != 0xFF)];
    u8 terminator;
};

struct EventInstruction<auto base> {
    u32 jump_origin = base;
    u8 opcode [[format("fmt_event_op")]];
    match (opcode) {
        (0x08 | 0x61 | 0x62 | 0x63 | 0x64 | 0x65 | 0x66 | 0x67): { EventText text; }
        (0x13):        { u8 voice; EventText text; }
        (0x9E):        { u8 position; EventText text; }
        (0x6D | 0x6E): { u16 position; EventText text; }
        (0x10):        { EventPointers<base> replies; }
        (0x12):        { u8 variable; EventPointers<base> targets; }
        (0x14):        { EventVariableChain condition; }
        (0x15 | 0x6A): { EventFlag flag; Ref16<jump_origin> jump_target; }
        (0x1C):        { Ref16<jump_origin> jump_target; }
        (0x1A | 0x1B): { EventFlag flag; }
        (0x20):        { u8 item [[comment("item index 0x000-0x0FF")]]; u8 count; }
        (0x21):        { u8 item [[comment("item index 0x100-0x1FF")]]; u8 count; }
        (0x24):        { u8 item [[comment("item index 0x000-0x0FF")]]; u8 count; }
        (0x25):        { u8 item [[comment("item index 0x100-0x1FF")]]; u8 count; }
        (0x22):        { u16 gold; }
        (0x16):        { Zone map; u8 event; u8 position; }
        (0x18):        { u8 shop [[comment("index into the shop table 0xBEE9F")]]; }
        (0x23):        { Player character; Spell spell; }
        (0x2B | 0x2C | 0x2D | 0x2E): { Player character [[comment("party flag is NOT index+1: Tia = 6, Dekar = 5")]]; }
        (0x53):        { u8 boss_formation [[comment("boss battle; probably an index into the boss formation table 0xBC53D (?)")]]; }
        (0x68):        { u8 npc_slot; u8 sprite; }
        (0x81):        { u8 species [[comment("capsule species 0-6 (Foomy, Shaggy, Hard Hat, Red Fish, Myconido, Raddisher, Armor Dog); join routine $82:E7AA")]]; }
        (_):           { u8 operands[event_fixed_len(opcode)]; }
    }
};

struct EventScript<auto base> {
    EventInstruction<base> instructions[while(std::mem::read_unsigned($, 1) != 0x00)];
    u8 end [[format("fmt_event_op")]];
};

// One event-list entry: event index + offset of its script from the event-list block base.
// True when no earlier entry of the event list starting at `list` has the same script offset.
fn first_in_event_list(u32 list, u32 entry) {
    u16 v = std::mem::read_unsigned(entry + 1, 2);
    u32 at = list;
    while (at < entry) {
        if (std::mem::read_unsigned(at + 1, 2) == v) { return false; }
        at = at + 3;
    }
    return true;
};

struct EventListEntry<auto base, auto list> {
    u32 jump_origin = base;
    u32 entry = $;
    u8 index;
    u16 offset [[no_unique_address, hidden]];
    if (!first_in_event_list(list, entry)) {
        u16 shared_offset [[comment("same script as an earlier entry of this list")]];
    } else if (offset >= 14 && (base + offset) < 0x7289E) {
        Ref16<jump_origin> script_ref; EventScript<base> script @ script_ref.target;
    } else {
        u16 script_offset;
    }
};

struct EventList<auto base> {
    u32 listStart = $;
    EventListEntry<base, listStart> entries[while(std::mem::read_unsigned($, 1) != 0xFF)];
    u8 terminator;
};

// A map's event-list block: "PH" magic + 6 offsets (EventClass 0..5) relative to the block start.
struct EventBlock {
    u64 blockBase = $;
    char magic[2];
    u16 listOffsets[6];
    if (listOffsets[0] >= 14) { EventList<blockBase> setup_map  @ (blockBase + listOffsets[0]); }
    if (listOffsets[1] >= 14) { EventList<blockBase> load_map   @ (blockBase + listOffsets[1]); }
    if (listOffsets[2] >= 14) { EventList<blockBase> referenced @ (blockBase + listOffsets[2]); }
    if (listOffsets[3] >= 14) { EventList<blockBase> npc        @ (blockBase + listOffsets[3]); }
    if (listOffsets[4] >= 14) { EventList<blockBase> tile       @ (blockBase + listOffsets[4]); }
    if (listOffsets[5] >= 14) { EventList<blockBase> unk5       @ (blockBase + listOffsets[5]); }
};

// Map name: ASCII with 0x0A XX YY back-references into the name pool (low 12 bits = source offset
// from $87:8000, i.e. file 0x38000; high 4 bits = count - 2), terminated by 0x00.
struct MapNameChunk {
    u8 c;
    if (c == 0x0A) { u16 reference; }
};
struct MapName {
    MapNameChunk chunks[while(std::mem::read_unsigned($, 1) != 0x00)];
    u8 terminator;
} [[color("81C784")]];


// =====================================================================================================
//  6. GAME DATA, BANK BY BANK
// =====================================================================================================

//  Every table here is typed and checked against the vanilla ROM. Raw ranges (text blobs, graphics,
//  SPC, free space, unknown data) are in section 7 so nothing is described twice.

// ---------------------------------------------------------------------------------- bank $80 (0x000000)

// SNES internal header and vectors (LoROM: $00:FFB0-$00:FFFF = file 0x7FB0-0x7FFF).
struct SnesHeader {
    char maker_code[2];       // "E9"
    char game_code[4];        // "ANIE"
    u8 reserved[10];
    char title[21];           // "Lufia II(Estpolis II)"
    u8 map_mode;              // 0x30 = LoROM, FastROM
    u8 rom_type;
    u8 rom_size;              // 0x0C = 4 MiB rounded up
    u8 sram_size;             // 0x03 = 8 KiB (the AP base patch raises it to 32 KiB at $80:FFD8)
    u8 region;                // 0x01 = North America
    u8 developer;             // 0x33 = extended header
    u8 version;
    u16 checksum_complement;
    u16 checksum;
    u16 native_vectors[8]    [[comment("unused, unused, COP, BRK, ABORT, NMI, unused, IRQ")]];
    u16 emulation_vectors[8] [[comment("unused, unused, COP, unused, ABORT, NMI, RESET, IRQ/BRK")]];
};
SnesHeader snes_header @ 0x7FB0;

// L2SASM opcode jump table: one bank-$80 address per event opcode $00-$CC. [reli] "subtract $7E00".
struct EventOpHandler {
    u16 address [[no_unique_address, hidden]];
    u8 opcode = ($ - 0x4A14) / 2;
    BankRef<0x80> handler;
} [[format("fmt_event_handler")]];
fn fmt_event_handler(ref EventOpHandler h) {
    return std::format("$80:{:04X}  {}", h.address, event_op_name(h.opcode));
};
EventOpHandler event_opcode_handlers[205] @ 0x4A14;

// ---------------------------------------------------------------------------------- bank $81 (0x008000)

// Battle action dispatcher: $81:A85C does JMP ($A867,X) on ($7F:F454 & $1F). [reli] + capsule-ram.md
struct BattleActionHandler {
    u16 address [[no_unique_address, hidden]];
    Ref16<0> handler;   // bank $81: file offset == SNES address
} [[format("fmt_action_handler")]];
fn fmt_action_handler(ref BattleActionHandler h) { return std::format("$81:{:04X}", h.address); };
BattleActionHandler battle_action_handlers[32] @ 0xA867 [[comment("index = action type: $0B = capsule attack (3E XX, capsule only), ...")]];

// Code operands that hold table addresses (LDA long,X + CLC + ADC #table). Moving a table means
// rewriting these. [iris] scripting/l2basm/records.py TABLE_REFS, l2basm-pointer-tables.
LoRomRef ref_monster_table    @ 0xFB28  [[comment("LDA $9685C0,X: monster table (5 more long refs up to 0xFBE7; ADC at 0xFC35/0xFCF7; LDA $85C0,Y at 0xFC32/0xFCF4)")]];
LoRomRef ref_item_table       @ 0xF29D  [[comment("LDA $96CF69,X: item table (also 0x1C69E; ADC #$CF69 at 0xF2A1)")]];
LoRomRef ref_ip_effect_table  @ 0xF46E  [[comment("LDA $95F1EF,X in $81:F46B: IP effect table (ADC #$F1EF operand at 0xF473)")]];
LoRomRef ref_spell_table      @ 0xF451  [[comment("LDA $95FA5B,X in $81:F446: spell table (ADC at 0xF455)")]];
LoRomRef ref_cap_attack_table @ 0xF479  [[comment("LDA $97F63B,X in $81:F476: CapAttack table (ADC #$F63B operand at 0xF47E; records must stay in bank $97)")]];

// ---------------------------------------------------------------------------------- bank $83 (0x018000)

LoRomRef ref_capsule_table @ 0x143A3 [[comment("LDA $97DCB8,X: capsule table (ADC at 0x143A7)")]];

// New-game setup ($83:AD80, run once per new game). Iris set_spawn_location edits these operands.
u8 spawn_map      @ 0x1ADAC [[comment("LDA #map at $83:ADAB -> STA $05AC (vanilla 0x03 = Elcid)")]];
u8 spawn_entrance @ 0x1ADB4 [[comment("LDA #entrance at $83:ADB3 -> $05B8; must be a LOAD_MAP event index of the map (vanilla 0x02)")]];

// Ancient Cave floor configuration ($83:9F49-$83:9FA8). [reli]
struct AncientCaveConfig {
    u16 tsa_resource[3]      [[comment("A7 resource number of the TSA: first / middle / last floors")]];
    u8  floor_type[10]       [[comment("per 10 floors: 0 = Tower, 1 = Labyrinth, 2 = Cave")]];
    u16 level_resource[3]    [[comment("A7 resource number of the level (bg) data")]];
    u16 bg_tiles_resource[3] [[comment("A7 resource number of the bg tiles")]];
    u16 theme[3]             [[comment("music: 0x05 Tower, 0x08 Labyrinth, 0x17 Cave")]];
};
AncientCaveConfig ancient_cave_config @ 0x19F49;
LoRomRef ancient_cave_data_ptrs[4] @ 0x19F73 [[comment("Ancient Cave related data in bank $94")]];
LoRomRef ancient_cave_palettes[12] @ 0x19F85 [[comment("palettes in bank $9B used by the Ancient Cave")]];

// ---------------------------------------------------------------------------------- bank $84 (0x020000)

// IP compendium: 168 IPs. Table entries are bank-$84 addresses ($84:9060 -> file 0x21060).
struct IPRecord {
    u16 effect [[comment("index into ip_effects (several IPs share an effect; the item's script decides)")]];
    u8 animation;
    IPCursor cursor;
    IPTargetMode target_mode;
    u8 ip_cost [[comment("IP gauge cost (%)")]];
    CString name;
};
struct IPEntry {
    BankRef<0x84> record_ref; IPRecord record @ record_ref.target;
};
IPEntry ip_compendium[168] @ 0x20F10;

// ---------------------------------------------------------------------------------- bank $85 (0x028000)

// New-game inventory (item | quantity << 9), then the 7 character templates (new-game party data).
ItemStack starting_inventory[2] @ 0x2B2AA [[comment("10 Potions, 1 Arrow (the Arrow is Maxim's dungeon item too)")]];

struct CharacterTemplate {
    char name[5];
    u8 zero;
    u8 level             [[comment("vanilla.py CharLevelObject")]];
    u8 status            [[comment("starting status (stun, ...)")]];
    u16 unknown          [[comment("copied to $7E:1854 (?)")]];
    Spell spells[while(std::mem::read_unsigned($, 1) != 0xFF)];
    u8 spells_end;
    u24 xp               [[comment("vanilla.py CharExpObject")]];
    Item weapon, armor, shield, helmet, ring, jewel;
    Item dungeon_item    [[comment("Maxim's at 0x2B2CA = vanilla.py addresses['starting_tool']")]];
    u8 separator;
};
CharacterTemplate character_templates[7] @ 0x2B2B0;

// L2BASM opcode jump table ($85:B483): bank-$85 address of the handler of each opcode $00-$5C.
struct L2basmOpHandler {
    u16 address [[no_unique_address, hidden]];
    u8 opcode = ($ - 0x2B483) / 2;
    BankRef<0x85> handler;
} [[format("fmt_l2basm_handler")]];
fn fmt_l2basm_handler(ref L2basmOpHandler h) {
    return std::format("$85:{:04X}  {}", h.address, l2basm_op_name(h.opcode));
};
L2basmOpHandler l2basm_opcode_handlers[93] @ 0x2B483;

// Battle messages (" cured.", " wakes up.", ...) and enemy attack names (L2BASM 1E XX; the leading
// 0xE0 byte of each name is a control code). Entries are bank-$85 addresses.
struct BankStringPtr85 {
    BankRef<0x85> text_ref; CString text @ text_ref.target;
};
BankStringPtr85 battle_messages[7]      @ 0x2EFD3;
BankStringPtr85 enemy_attack_names[138] @ 0x2F2D7;

// ---------------------------------------------------------------------------------- bank $86 (0x030000)

u8 world_map_themes[5] @ 0x32410 [[comment("music: sea (ground->sea), undersea, sky, ?, sea (undersea->sea); others are hard-coded")]];

// ---------------------------------------------------------------------------------- bank $87 (0x038000)

// Map table: 242 x 8 bytes. Event list and NPC-load script are 15-bit offsets from 0x38000 (bank $87);
// the high byte selects the 32 KiB bank: pointer = 0x38000 + (low | high << 15). Both kinds of script
// take their jump addresses relative to the event-list block. Event scripts end at 0x7289E.
struct MapScriptSet {
    u32 index = ($ - 0x38010) / 8;
    u16 eventlist_lowbytes;
    u8  eventlist_highbyte;
    u16 npc_lowbytes;
    u8  npc_highbyte;
    if (first_with_value(0x38016, 8, 2, index)) { Ref16<0x38000> name_ref; MapName name @ name_ref.target; }
    else                                        { u16 name_offset [[comment("same name as an earlier map")]]; }
    u64 evPtr  = 0x38000 + (eventlist_lowbytes | (eventlist_highbyte << 15));
    u64 npcPtr = 0x38000 + (npc_lowbytes | (npc_highbyte << 15));
    if (evPtr < 0x300000 && peek8(evPtr) == 0x50 && peek8(evPtr + 1) == 0x48 && first_with_value(0x38010, 8, 3, index)) {
        EventBlock event_block @ evPtr;
    }
    if (npcPtr > 0x3801E && npcPtr < 0x3AE4D && first_with_value(0x38013, 8, 3, index)) {
        EventScript<evPtr> npc_load_script @ npcPtr;
    }
};
MapScriptSet maps[242] @ 0x38010;

struct RoamingNPC {
    u8 map_npc_event_index;
    u8 sprite_index;
    Zone map_index;
    u8 map_npc_index;
};
RoamingNPC roaming_npcs[34] @ 0x3AE4E;

// ---------------------------------------------------------------------------------- bank $8E (0x070000)

// Credits text references: LDA $919AFF,X operands (vanilla.py credits_pointer1-6).
LoRomRef credits_ref_1 @ 0x73449;
LoRomRef credits_ref_2 @ 0x73496;
LoRomRef credits_ref_3 @ 0x7349D;
LoRomRef credits_ref_4 @ 0x734B3;
LoRomRef credits_ref_5 @ 0x73503;
LoRomRef credits_ref_6 @ 0x73511;

// Warp spell destinations. Entries are bank-$8E addresses.
struct WarpDestination {
    Zone map;
    u8 unknown1;
    u8 unknown2;
    CString name;
};
struct WarpPtr {
    BankRef<0x8E> dest_ref; WarpDestination dest @ dest_ref.target;
};
WarpPtr warp_destinations[28] @ 0x7506E;

u16 bit_masks[16] @ 0x758C3 [[comment("0x0001 .. 0x8000, used by $82:FB51")]];
u8 capsule_species_byte[7] @ 0x76485 [[comment("$8E:E485: per-species byte copied to $7E:11A6+s by $82:C515 (meaning unknown)")]];
u8 capsule_start_levels[7] @ 0x764C4 [[comment("$8E:E4C4: capsule level when it joins, per species (vanilla.py CapsuleLevelObject)")]];
LoRomRef hero_battle_sprites[7] @ 0x765C2 [[comment("Maxim, Selan, Guy, Artea, Tia, Dekar, Lexis")]];

// Dictionary 1 (event text and descriptions): 640 words, entries relative to the table.
struct WordPtr {
    Ref16<0x076A00> word_ref; CString word @ word_ref.target;
};
WordPtr dictionary1[640] @ 0x76A00;

// ---------------------------------------------------------------------------------- bank $8F (0x078000)

// Per-map puzzle data (switches, bridges, ...): 0xFFFFFF = none, else an offset from 0x78000.
struct PuzzlePtr {
    u24 value [[no_unique_address, hidden]];
    if (value == 0xFFFFFF) { u24 none; }
    else                   { Ref24<0x078000> data; }
};
PuzzlePtr puzzle_data[242] @ 0x78000;

// ---------------------------------------------------------------------------------- bank $91 (0x088000)

// Chest contents: one u16 entry per map index, relative to the table, each pointing at an
// 0xFF-terminated list of 3-byte chests. [iris] verified: map 6 -> 3 chests at 0x8BABB.
bitfield ChestMisc1 {
    slot      : 6 [[comment("per-map chest slot, same id as ZoneData section 18")]];
    item_high : 1 [[comment("bit 8 of the item index")]];
    unknown   : 1;
};
struct ChestRecord {
    ChestMisc1 misc1;
    u8 misc2;
    u8 item_low;
};
struct ChestList {
    ChestRecord chests[while(std::mem::read_unsigned($, 1) != 0xFF)];
    u8 terminator;
};
struct ChestMapPtr {
    u32 index = ($ - 0x8B8B5) / 2;
    u16 offset [[no_unique_address, hidden]];
    if (offset == 0xFFFF)                    { u16 unused [[comment("slots 242-255 are 0xFFFF filler")]]; }
    else if ((0x8B8B5 + offset) < 0x8BAB5)   { u16 unused [[comment("points into the table itself: never read (map 0)")]]; }
    else if (!first_with_value(0x8B8B5, 2, 2, index)) { u16 shared_offset [[comment("same list as an earlier map")]]; }
    else                                     { Ref16<0x08B8B5> list_ref; ChestList list @ list_ref.target; }
};
ChestMapPtr chests_by_map[256] @ 0x8B8B5;

Item iris_treasures[9]   @ 0x8FFCA [[comment("Iris treasure item list (without the Power Jelly)")]];
Item ancient_chests_2[9] @ 0x8FFDC [[comment("vanilla.py AncientChest2Object")]];

// ---------------------------------------------------------------------------------- bank $94 (0x0A0000)

Item blue_chests[41]      @ 0xA6EA0 [[comment("blue chest item list (vanilla.py BlueChestObject)")]];
Item ancient_chests_1[31] @ 0xA713D [[comment("vanilla.py AncientChest1Object")]];

// ---------------------------------------------------------------------------------- bank $95 (0x0A8000)

// IP effect scripts: 141 entries relative to the table; each target is a 0xFF marker + L2BASM.
// The jump origin of these scripts is the marker. Accessor $81:F46B.
struct IPEffect<auto end> {
    u64 recStart = $;
    u8 marker [[comment("0xFF")]];
    BattleScriptRegion<end, recStart> script;
};
struct IPEffectPtr {
    u16 offset [[no_unique_address, hidden]];
    Ref16<0x0AF1EF> effect_ref; IPEffect<next_target(0xAF1EF, 141, 0xAF1EF, 0xAF1EF + offset, 0xAFA5B)> effect @ effect_ref.target;
};
IPEffectPtr ip_effects[141] @ 0xAF1EF;

// Spells: 40 entries relative to the table; record + L2BASM effect script. Accessor $81:F446.
struct SpellRecord<auto end> {
    u64 recStart = $;
    char name[8];
    u8 unk1;
    u8 element [[comment("element / animation class (?)")]];
    CharacterMask users;
    u8 unk4;
    u8 mp_cost;
    u16 zero;
    u16 price;
    u16 script_offset [[comment("record-relative (0x13 in vanilla)")]];
    BattleScriptRegion<end, recStart> script @ (recStart + script_offset);
};
struct SpellPtr {
    u16 offset [[no_unique_address, hidden]];
    Ref16<0x0AFA5B> spell_ref; SpellRecord<next_target(0xAFA5B, 40, 0xAFA5B, 0xAFA5B + offset, 0xAFF16)> spell @ spell_ref.target;
};
SpellPtr spells[40] @ 0xAFA5B;

// ---------------------------------------------------------------------------------- bank $96 (0x0B0000)

// Monster compendium: 224 entries relative to the table. Fixed 33-byte block, then 3-byte markers
// until 0x00 (03 = item drop, 07 = attack script, 08 = defense script), then the scripts.
// Base patches (FRUE, Spekkio, Kureji) move this table to 0x282000 ($D0:A000).
bitfield MonsterDrop {
    item   : 9;
    chance : 7 [[comment("p = chance * 2; probably probability * 4, e.g. Vampire p=100 -> 25%")]];
};
struct MonsterMarker<auto origin> {
    u32 jump_origin = origin;
    u8 marker [[comment("03 = drop, 07 = attack script, 08 = defense script")]];
    if (marker == 0x03) { MonsterDrop drop; }
    else                { Ref16<jump_origin> script [[comment("record-relative")]]; }
};
struct MonsterRecord<auto end> {
    u64 recStart = $;
    char name[13];
    u8 level;
    u8 unknown        [[comment("0x32 for all monsters except Armor goblin / Regal Goblin (0x36)")]];
    u8 battle_sprite  [[comment("1-134; see enemy_battle_sprite_meta / A7 resources")]];
    u8 palette;
    u16 hp, mp, atp, dfp;
    u8 agl_half, int_half, gut_half, mgr_half;
    u16 exp, gold;
    MonsterMarker<recStart> markers[while(std::mem::read_unsigned($, 1) != 0x00)];
    u8 header_end;
    if ($ < end) { BattleScriptRegion<end, recStart> scripts; }
};
struct MonsterPtr {
    u16 offset [[no_unique_address, hidden]];
    Ref16<0x0B05C0> monster_ref; MonsterRecord<next_target(0xB05C0, 224, 0xB05C0, 0xB05C0 + offset, 0xB4F69)> monster @ monster_ref.target;
};
MonsterPtr monsters[224] @ 0xB05C0;

// Item compendium: 467 entries relative to the table. 13 common bytes, then one u16 per set bit of
// the flags word (bit order), then the scripts. Script offsets are record-relative.
bitfield ItemUsability {
    most_useful   : 1;
    equipable     : 1;
    unused2       : 1;
    cursed        : 1;
    fruit         : 1;
    unsellable    : 1 [[comment("scenario/dungeon items, Jewel sonar, Iris treasures, Dragon egg, Dual blade")]];
    usable_menu   : 1;
    usable_battle : 1;
};
bitfield ItemByte1 {
    unknown0 : 5;
    ban_ancient_cave : 1;
    unknown6 : 2;
};
bitfield ItemType {
    weapon : 1; armor : 1; shield : 1; helmet : 1; ring : 1; jewel : 1; unknown6 : 1; unknown7 : 1;
};
bitfield ItemProperties {
    menu_effect      : 1;   // word: menu script offset
    battle_effect    : 1;   // word: battle script offset
    weapon_effect    : 1;   // word: weapon script offset
    armor_effect     : 1;   // word: armor script offset
    increase_atp     : 1;
    increase_dfp     : 1;
    increase_str     : 1;
    increase_agl     : 1;
    increase_int     : 1;
    increase_gut     : 1;
    increase_mgr     : 1;
    unused11         : 1;
    unused12         : 1;
    battle_animation : 1;   // word: animation number (Potion = 97)
    unknown14        : 1;
    ip_effect        : 1;   // word: 1-based IP number (IP n = ip_compendium[n-1])
};
struct ItemRecord<auto end> {
    u64 recStart = $;
    u32 jump_origin = recStart;
    ItemUsability usability;
    ItemByte1 byte1;
    u8 targeting;
    u8 icon;
    u8 sprite;
    u16 price;
    ItemType item_type;
    CharacterMask equipable_by;
    ItemProperties properties;
    u16 zero;
    u16 f = std::mem::read_unsigned(recStart + 9, 2);
    if (f & 0x0001) { Ref16<jump_origin> menu_script; }
    if (f & 0x0002) { Ref16<jump_origin> battle_script; }
    if (f & 0x0004) { Ref16<jump_origin> weapon_script; }
    if (f & 0x0008) { Ref16<jump_origin> armor_script; }
    if (f & 0x0010) { s16 atp_bonus; }
    if (f & 0x0020) { s16 dfp_bonus; }
    if (f & 0x0040) { s16 str_bonus; }
    if (f & 0x0080) { s16 agl_bonus; }
    if (f & 0x0100) { s16 int_bonus; }
    if (f & 0x0200) { s16 gut_bonus; }
    if (f & 0x0400) { s16 mgr_bonus; }
    if (f & 0x0800) { u16 word11; }
    if (f & 0x1000) { u16 word12; }
    if (f & 0x2000) { u16 battle_animation; }
    if (f & 0x4000) { u16 word14; }
    if (f & 0x8000) { u16 ip_number [[comment("1-based: IP n = ip_compendium[n-1]")]]; }
    if ($ < end) { BattleScriptRegion<end, recStart> scripts; }
};
struct ItemPtr {
    u16 offset [[no_unique_address, hidden]];
    Ref16<0x0B4F69> item_ref; ItemRecord<next_target(0xB4F69, 467, 0xB4F69, 0xB4F69 + offset, 0xB7ADD)> item @ item_ref.target;
};
ItemPtr items[467] @ 0xB4F69;

// $42 subroutines (42 XX 00): 41 entries relative to the table. Jump origin = subroutine start.
// Accessor at 0x2BD99 (LDA #$96 : STA $BD; LDA $96FADD,X; ADC #$FADD).
struct Subroutine<auto end> {
    u64 recStart = $;
    BattleScriptRegion<end, recStart> body;
};
struct SubroutinePtr {
    u16 offset [[no_unique_address, hidden]];
    u8 index = ($ - 0xB7ADD) / 2;
    Ref16<0x0B7ADD> subroutine_ref; Subroutine<next_target(0xB7ADD, 41, 0xB7ADD, 0xB7ADD + offset, 0xB7E3A)> subroutine @ subroutine_ref.target;
} [[format("fmt_subroutine_ptr")]];
fn fmt_subroutine_ptr(ref SubroutinePtr p) { return subroutine_name(p.index); };
SubroutinePtr subroutines_42[41] @ 0xB7ADD;
u16 colors_after_subroutines[128] @ 0xB7E3A [[comment("15-bit colours (0x0422, 0x7C00, 0x001F, ...): [reli] says 'palette?' at 0xB7E3C, but the colours start right after the last $42 body (0xB7E39)")]];

// ---------------------------------------------------------------------------------- bank $97 (0x0B8000)

// Item / spell / IP descriptions. Pointers are relative to 0xB8000; the text (0xB85B4-0xBB0A0) is
// compressed with dictionary 2 and is not decoded here.
struct DescPtr {
    Ref16<0x0B8000> text;
};
DescPtr item_descriptions[512]  @ 0xB8000 [[comment("467 used; the rest point at the empty text")]];
DescPtr spell_descriptions[49]  @ 0xB8400;
DescPtr ip_descriptions[169]    @ 0xB8462;

// Level-up growth: per character 14 rows x 8 bytes (HP, MP, STR, AGL, INT, GUT, MGR, ?).
struct GrowthRow { u8 hp, mp, str_, agl, int_, gut, mgr, unknown; };
struct CharacterGrowth { GrowthRow rows[14]; };
CharacterGrowth character_growth[7] @ 0xBB62C;

// Level-1 base stats.
struct CharacterStats { u16 hp, mp, str_, agl, int_, gut, mgr; };
CharacterStats character_base_stats[7] @ 0xBB93C;
u16 unknown_per_character[7] @ 0xBB99E [[comment("all 20 in vanilla (?); [reli] calls 0xBB99E-0xBBB9B 'EXP at next level', but the map formation table starts at 0xBB9AC")]];

// Map formations: 248 entries relative to the table; each body runs to the next target.
struct MapFormationBody<auto end> {
    u8 entries[end - $] [[comment("probably formation ids of the map's roaming monsters (unverified)")]];
};
struct MapFormationPtr {
    u32 index = ($ - 0xBB9AC) / 2;
    u16 offset [[no_unique_address, hidden]];
    if (!first_with_value(0xBB9AC, 2, 2, index)) { u16 shared_offset [[comment("same body as an earlier map")]]; }
    else { Ref16<0x0BB9AC> body_ref; MapFormationBody<next_target(0xBB9AC, 248, 0xBB9AC, 0xBB9AC + offset, 0xBBE93)> body @ body_ref.target; }
};
MapFormationPtr map_formations[248] @ 0xBB9AC;

// Enemy parties (formations): 192 x 8 monster ids, 0xFF = empty slot. Pending formation id: $7F:F8A4.
struct Formation { MonsterId monsters[8]; };
Formation formations[192] @ 0xBBE93;

// Boss parties: 39 entries relative to the table; bodies run to the next target.
struct BossFormationBody<auto end> {
    MonsterId monsters[6] [[comment("0xFF = empty (layout partly unverified)")]];
    u8 rest[end - $];
};
struct BossFormationPtr {
    u32 index = ($ - 0xBC53D) / 2;
    u16 offset [[no_unique_address, hidden]];
    if (!first_with_value(0xBC53D, 2, 2, index)) { u16 shared_offset [[comment("same party as an earlier entry")]]; }
    else { Ref16<0x0BC53D> body_ref; BossFormationBody<next_target(0xBC53D, 39, 0xBC53D, 0xBC53D + offset, 0xBCA1D)> body @ body_ref.target; }
};
BossFormationPtr boss_formations[39] @ 0xBC53D;

// Enemy battle sprite metadata ($97:CA64, read by $81:FB8E and $81:FBA2; AND #$1F1F).
struct SpriteMeta { u8 width; u8 height_misc; };
SpriteMeta enemy_battle_sprite_meta[134] @ 0xBCA64;

struct CapsulePalette { u16 colors[16]; };
CapsulePalette capsule_palettes[35] @ 0xBD258;

// Capsule monsters: 35 entries relative to the table (7 species x 5 forms; index = species*5 + form-1).
// 35-byte stats, an 8-byte header with two record-relative script offsets, then L2BASM.
// The reaction script is passive protection (42 XX subroutines), not an action.
struct CapsuleStats {
    char name[12];
    u8 zero;
    u8 capsule_class;
    u8 alignment;
    u8 start_skills[3]   [[comment("CapAttack indices")]];
    u8 upgrade_skills[3];
    u8 hp, attack, defense, strength, agility, intelligence, guts, magic_resistance;
    u8 hp_factor, strength_factor, agility_factor, intelligence_factor, guts_factor, magic_resistance_factor;
};
struct CapsuleRecord<auto end> {
    u64 recStart = $;
    CapsuleStats stats;
    u16 unknown0;
    u16 attack_offset   [[comment("0x2B for all 35; RAM copy at $7E:1129")]];
    u16 reaction_offset [[comment("RAM copy at $7E:112B")]];
    u16 unknown1;
    BattleScriptRegion<recStart + reaction_offset, recStart> attack_script   @ (recStart + attack_offset);
    BattleScriptRegion<end, recStart>                        reaction_script @ (recStart + reaction_offset);
};
struct CapsulePtr {
    u16 offset [[no_unique_address, hidden]];
    Ref16<0x0BDCB8> capsule_ref; CapsuleRecord<next_target(0xBDCB8, 35, 0xBDCB8, 0xBDCB8 + offset, 0xBEE9F)> capsule @ capsule_ref.target;
};
CapsulePtr capsules[35] @ 0xBDCB8;

// Shops: 63 entries relative to the table (0 = unused shop). Header: identifier, type, zero.
// Item shops list u16 items with a u16 0 divider between sections; spell shops (type & 0x20) list
// u8 spells terminated by 0xFF. No prices: they come from the item / spell records.
struct ShopItems<auto stop> {
    Item entries[while($ < stop)];
};
struct ShopSpells<auto stop> {
    Spell spells[while($ < stop && std::mem::read_unsigned($, 1) != 0xFF)];
    if ($ < stop && std::mem::read_unsigned($, 1) == 0xFF) { u8 terminator; }
};
struct ShopDef<auto stop> {
    ShopIdentifier identifier;
    u8 shop_type [[comment("bitmask; & 0x20 = spell shop")]];
    u8 zero;
    if (shop_type & 0x20) { ShopSpells<stop> body; }
    else                  { ShopItems<stop>  body; }
};
struct ShopPtr {
    u16 offset [[no_unique_address, hidden]];
    if (offset != 0) {
        Ref16<0x0BEE9F> shop_ref; ShopDef<next_target(0xBEE9F, 63, 0xBEE9F, 0xBEE9F + offset, 0xBF63B)> shop @ shop_ref.target;
    } else {
        u16 unused_shop;
    }
};
ShopPtr shops[63] @ 0xBEE9F;

// Capsule attacks (CapAttack, 84 records $00-$53): name number, animation, L2BASM effect script.
// Run by 3E XX from a capsule attack script; accessor $81:F476, caller $81:AD51 (bank fixed to $97).
// None of the vanilla records contains a jump.
struct CapAttackRecord<auto end> {
    u64 recStart = $;
    u8 name_number [[comment("index into capsule_attack_names")]];
    u8 animation   [[comment("0xF0 = physical; Inferno 0x82, Healing aura 0x2D")]];
    BattleScriptRegion<end, recStart> script;
};
struct CapAttackPtr {
    u16 offset [[no_unique_address, hidden]];
    Ref16<0x0BF63B> attack_ref; CapAttackRecord<next_target(0xBF63B, 84, 0xBF63B, 0xBF63B + offset, 0xBFC40)> attack @ attack_ref.target;
};
CapAttackPtr capsule_attacks[84] @ 0xBF63B;

// Battle backgrounds ($97:FD40, see sub near $81:B9C8).
struct BattleBackground {
    u8 bg_data  [[comment("A7 resource number - 0x179")]];
    u8 tileset  [[comment("A7 resource number - 0x16C")]];
    u8 palette;
    u8 unknown;
};
BattleBackground battle_backgrounds[24] @ 0xBFD40;

// Scenario items ($97:FDA0), 0xFFFF-terminated (see sub $82:FB51).
struct ScenarioItems {
    Item items[while(std::mem::read_unsigned($, 2) != 0xFFFF)];
    u16 terminator;
};
ScenarioItems scenario_items @ 0xBFDA0;

// ---------------------------------------------------------------------------------- bank $9E (0x0F0000)

struct ItemName { char name[12]; } [[format("fmt_item_name"), sealed]];
fn fmt_item_name(ref ItemName n) { return n.name; };
ItemName item_names[467] @ 0xF47E8;

// Dictionary 2 (item / spell / IP descriptions): 624 words relative to the table.
struct Word2Ptr {
    Ref16<0x0F5DCC> word_ref; CString word @ word_ref.target;
};
Word2Ptr dictionary2[624] @ 0xF5DCC;

// ---------------------------------------------------------------------------------- bank $A5 (0x128000)

// Capsule attack names (SP list / CapAttack name numbers): 78 entries relative to the table.
struct CapAttackNamePtr {
    Ref16<0x12DF00> name_ref; CString name @ name_ref.target;
};
CapAttackNamePtr capsule_attack_names[78] @ 0x12DF00;

// ---------------------------------------------------------------------------------- bank $A7 (0x138000)

// Resource table: 681 x u24 offsets from 0x138000 (resource number = index), split by kind below.
// Covers SPC data, title/credits graphics, per-map bg data / TSA / tiles, battle backgrounds,
// capsule and enemy battle sprites, battle animations, intro and Mode-7 graphics. [reli] + [iris]
struct Resource {
    Ref24<0x138000> data;
};
Resource res_spc[0x3F]                  @ 0x138000 [[comment("0x000-0x03E: SPC (music / sound)")]];
Resource res_title_screens              @ 0x1380BD [[comment("0x03F: bg data and tiles of the title screens")]];
Resource res_credits_tiles              @ 0x1380C0 [[comment("0x040: credits / 'The End' tiles")]];
Resource res_map_bg_data[240]           @ 0x1380C3 [[comment("0x041-0x130: compressed bg (layout) data of maps 0x02-0xF1; chest sprites live here")]];
Resource res_map_tsa[27]                @ 0x138393 [[comment("0x131-0x14B: bg TSA (shared by maps with the same tiles)")]];
Resource res_map_bg_tiles[20]           @ 0x1383E4 [[comment("0x14C-0x15F: bg tiles")]];
Resource res_160_16B[12]                @ 0x138420 [[comment("0x160-0x16B: unknown")]];
Resource res_battle_bg_tiles[13]        @ 0x138444 [[comment("0x16C-0x178: battle background tiles")]];
Resource res_battle_bg_data[20]         @ 0x13846B [[comment("0x179-0x18C: battle background data")]];
Resource res_18D_193[7]                 @ 0x1384A7 [[comment("0x18D-0x193: unknown (0x18E battle related)")]];
Resource res_capsule_battle_sprites[35] @ 0x1384BC [[comment("0x194-0x1B6 (vanilla.py CapSpritePTRObject)")]];
Resource res_enemy_battle_sprites[134]  @ 0x138525 [[comment("0x1B7-0x23C")]];
Resource res_23D_23F[3]                 @ 0x1386B7 [[comment("0x23D-0x23F: unknown (0x23F battle related)")]];
Resource res_battle_animations[67]      @ 0x1386C0 [[comment("0x240-0x282: battle animation graphics (?); 0x24C = Drowsy")]];
Resource res_intro[6]                   @ 0x138789 [[comment("0x283-0x288: intro (Arek's island): tiles bg1/2, tiles bg3, sprites, bg data bg2, bg1, bg3")]];
Resource res_289_28A[2]                 @ 0x13879B [[comment("0x289-0x28A: unknown")]];
Resource res_mode7[5]                   @ 0x1387A1 [[comment("0x28B-0x28F: overworld tiles, overworld map, logo sprite, undersea tiles, undersea map")]];
Resource res_290_2A8[25]                @ 0x1387B0 [[comment("0x290-0x2A8: unknown (Excerion, Doom Island sphere, ...)")]];

// ---------------------------------------------------------------------------------- bank $CF (0x278000)

// Map sprite table: 251 entries (bank-$CF addresses) to 5-byte sprite records.
struct MapSprite {
    u8 shape        [[comment("voice pitch / dimensions / tile arrangement (?)")]];
    u8 palette      [[comment("1-7")]];
    LoRomRef first_tile;
};
struct MapSpritePtr {
    u32 index = ($ - 0x27F000) / 2;
    BankRef<0xCF> sprite_ref;
    if (first_with_value(0x27F000, 2, 2, index)) { MapSprite sprite @ sprite_ref.target; }
};
MapSpritePtr map_sprites[251] @ 0x27F000;

u8 monster_movement[112] @ 0x27F6B5 [[comment("roaming monster movement bytes (vanilla.py MonsterMoveObject)")]];
u8 map_tsa_numbers[240]     @ 0x27F730 [[comment("bg TSA number per map 0x02-0xF1")]];
u8 map_tile_numbers[240]    @ 0x27F820 [[comment("bg tiles number per map 0x02-0xF1")]];
u8 map_layer_bytes[240]     @ 0x27F910 [[comment("bg layers data byte per map 0x02-0xF1")]];
u8 map_palette_numbers[240] @ 0x27FA0A [[comment("palette number per map 0x02-0xF1")]];
struct MapPalettePtr {
    BankRef<0x9B> palette;
};
MapPalettePtr map_palette_ptrs[87] @ 0x27FAFA [[comment("palettes of dungeons and towns in bank $9B")]];
u8 map_anim_palette_numbers[240] @ 0x27FBA8 [[comment("per map 0x02-0xF1: number of a pointer at 0x27FC98 (animated tile palettes?)")]];
u16 anim_palette_ptrs[18]   @ 0x27FC98 [[comment("bank unknown")]];

// ZoneData: per-map object data (exits, trigger tiles, NPCs, waypoints, chests, ...). One LoROM
// pointer per map. Blob = u16 size, 21 u16 section offsets (from the blob start), sections
// terminated by 0xFF (empty sections share one lone 0xFF and are left out here). Works anywhere,
// incl. the expansion area.
struct Boundary { u8 west; u8 north; u8 south; u8 east; };
struct ZoneExit     { u8 index; Boundary boundary; u8 misc; u8 dest_x; u8 dest_y; Zone dest_map; };
struct ZoneTile     { u8 index; Boundary boundary; };                       // fires E-class event `index`
struct ZoneNPC      { u8 index; u8 x; u8 y; Boundary boundary; u8 misc; };
struct ZoneWaypoint { u8 index; u8 x; u8 y; u8 misc; u16 offsets; };
struct ZoneChest    { u8 slot; u8 x; u8 y; u8 kind [[comment("1-4, chest graphic/kind (?)")]]; };
struct ZoneList<T> {
    T records[while(std::mem::read_unsigned($, 1) != 0xFF)];
    u8 terminator;
};
struct ZoneRaw<auto end> { u8 bytes[end - $]; };

fn zone_section_end(u32 base, u32 i) {
    u32 cur = std::mem::read_unsigned(base + 2 + i * 2, 2);
    u32 best = std::mem::read_unsigned(base, 2);
    u32 j = 0;
    while (j < 21) {
        u32 o = std::mem::read_unsigned(base + 2 + j * 2, 2);
        if (o > cur && o < best) { best = o; }
        j = j + 1;
    }
    return base + best;
};

struct ZoneData {
    u64 base = $;
    u16 size;
    u16 section_offsets[21];
    if (peek8(base + section_offsets[0])  != 0xFF) { ZoneRaw<zone_section_end(base, 0)>  s00_layout_objects  @ (base + section_offsets[0]); }
    if (peek8(base + section_offsets[2])  != 0xFF) { ZoneList<ZoneExit>     s02_exits     @ (base + section_offsets[2]); }
    if (peek8(base + section_offsets[5])  != 0xFF) { ZoneList<ZoneTile>     s05_tiles     @ (base + section_offsets[5]); }
    if (peek8(base + section_offsets[7])  != 0xFF) { ZoneList<ZoneNPC>      s07_npcs      @ (base + section_offsets[7]); }
    if (peek8(base + section_offsets[8])  != 0xFF) { ZoneList<ZoneWaypoint> s08_waypoints @ (base + section_offsets[8]); }
    if (peek8(base + section_offsets[16]) != 0xFF) { ZoneRaw<zone_section_end(base, 16)> s16_dungeon_objects @ (base + section_offsets[16]); }
    if (peek8(base + section_offsets[17]) != 0xFF) { ZoneRaw<zone_section_end(base, 17)> s17_dungeon_objects @ (base + section_offsets[17]); }
    if (peek8(base + section_offsets[18]) != 0xFF) { ZoneList<ZoneChest>    s18_chests    @ (base + section_offsets[18]); }
    if (peek8(base + section_offsets[19]) != 0xFF) { ZoneRaw<zone_section_end(base, 19)> s19_dungeon_objects @ (base + section_offsets[19]); }
};
struct ZonePtr {
    LoRomRef zone_ref; ZoneData zone @ zone_ref.target;
};
ZonePtr zone_data[242] @ 0x27FCBC;

// Sprite graphics tail (structures/sprites.py); only present when the file reaches 0x2FE000
// (in the 3 MiB file it lies in the 0x280000 mirror).
struct SpriteBankTail {
    if (std::mem::size() > 0x2FE000) { Gfx tail[std::mem::size() - 0x2FE000] @ 0x2FE000; }
};
SpriteBankTail sprite_bank_tail @ 0x0;


// =====================================================================================================
//  7. CODE AND DATA MAP
// =====================================================================================================
//  Every subroutine, jump table and data range the docs describe, grouped per bank. Each entry is a
//  Code / Data / Text / Gfx / Spc / Free / Unknown array. Entries with an unknown end are 1 byte long
//  and say "end unknown". Generated once from [reli] + [iris] notes; maintain by hand from now on.
//  Each comment starts with the SNES address. Offsets QUOTED INSIDE [reli] comments are the doc's
//  headered file offsets: subtract 0x200. Where the doc's two address columns disagreed, the comment
//  says which one was used. Section 6 has the typed, verified versions of most data ranges.

struct Bank80Map {
    Code sub_8000[0x9A] @ 0x000000 [[comment("$80:8000 Subroutine: [reli]")]];
    Code sub_8000_2[0xB] @ 0x00009B [[comment("$80:809B (continued from $80:8000) Subroutine: [reli]")]];
    Code sub_8000_3[0x28] @ 0x0000A7 [[comment("$80:80A7 (continued from $80:8000) Subroutine: [reli]")]];
    Code sub_8000_4[0x3] @ 0x0000D0 [[comment("$80:80D0 (continued from $80:8000) Subroutine: [reli]")]];
    Code sub_809A @ 0x00009A [[comment("$80:809A AP hook: patch copy protection | CMP $710000 ; overwrites CMP $702000 [ap] (end unknown)")]];
    Code sub_80A6 @ 0x0000A6 [[comment("$80:80A6 AP hook: patch copy protection | CMP $710000 ; overwrites CMP $702000 [ap] (end unknown)")]];
    Code sub_80CF @ 0x0000CF [[comment("$80:80CF AP hook: intro skip | DB=$80, x=1, m=1 | JML $8383BD ; overwrites JML $808281 [ap] (end unknown)")]];
    Code sub_80D3[0xE] @ 0x0000D3 [[comment("$80:80D3 Subroutine: [reli]")]];
    Code sub_80E1[0x36] @ 0x0000E1 [[comment("$80:80E1 Subroutine: [reli]")]];
    Code sub_8117[0xFA] @ 0x000117 [[comment("$80:8117 Subroutine: [reli]")]];
    Data data_8211[0x74] @ 0x000211 [[comment("$80:8211 Data? [reli]")]];
    Code sub_8285[0x14] @ 0x000285 [[comment("$80:8285 Subroutine: [reli]")]];
    Code sub_8299[0x2E] @ 0x000299 [[comment("$80:8299 Subroutine: Random number generator. I *think* it returns (in low-A) a number in range [#$00, low-A[. [reli]")]];
    Code sub_82C7[0x20] @ 0x0002C7 [[comment("$80:82C7 Subroutine: Also rand number generator? Simpler that the one at $80:8299. I *think* it returns (in low-A) a number in range [#$00, #$FF]. [reli] || PRNG: JSL returns the next random byte in 8-bit A [iris]")]];
    Code sub_82E7[0x46] @ 0x0002E7 [[comment("$80:82E7 Subroutine: [reli]")]];
    Code sub_832D[0x1F] @ 0x00032D [[comment("$80:832D Subroutine: Called by sub at $80:8299 (Random number generator) [doc's file column says 0x000499 (copy error); SNES column used] [reli]")]];
    Code sub_834C[0x2C] @ 0x00034C [[comment("$80:834C Subroutine: This sub is used to multiply a 2-bytes number (at [$4E, $4F]) by a 1-byte number (at $50) . The result is a 3-bytes number (at [$51, $52, $53]) Before: [doc's file column says 0x000499 (copy error); SNES column used] [reli]")]];
    Code sub_8378[0xD8] @ 0x000378 [[comment("$80:8378 Subroutine: [reli]")]];
    Code sub_8450[0x36] @ 0x000450 [[comment("$80:8450 Subroutine: [reli]")]];
    Code sub_8486[0x39] @ 0x000486 [[comment("$80:8486 Subroutine: [reli]")]];
    Data data_84BF[0x16E] @ 0x0004BF [[comment("$80:84BF Data... [reli]")]];
    Code sub_862D[0x93] @ 0x00062D [[comment("$80:862D Subroutine: ... 00/86BF: 40 RTI [reli]")]];
    Code sub_86C0 @ 0x0006C0 [[comment("$80:86C0 Subroutine: 00/86C0: 40 RTI [reli] (end unknown)")]];
    Code sub_86C1[0x42] @ 0x0006C1 [[comment("$80:86C1 Subroutine: [reli]")]];
    Code sub_8703[0xA4] @ 0x000703 [[comment("$80:8703 Subroutine: Sub that reads the 'Joy' registers. [reli]")]];
    Code sub_87A7[0x55] @ 0x0007A7 [[comment("$80:87A7 Subroutine: ??? [reli]")]];
    Code sub_87FC[0x32] @ 0x0007FC [[comment("$80:87FC Subroutine: [reli]")]];
    Code sub_882E[0x21] @ 0x00082E [[comment("$80:882E Subroutine: [reli]")]];
    Code sub_884F[0x17] @ 0x00084F [[comment("$80:884F Subroutine: [reli]")]];
    Code sub_8866[0x12] @ 0x000866 [[comment("$80:8866 Subroutine: [reli]")]];
    Code sub_8878[0x14] @ 0x000878 [[comment("$80:8878 Subroutine: [reli]")]];
    Code sub_888C[0x21] @ 0x00088C [[comment("$80:888C Subroutine: [reli]")]];
    Code sub_88AD[0x1B] @ 0x0008AD [[comment("$80:88AD Subroutine: [reli]")]];
    Code sub_88AD_2[0x11] @ 0x0008C9 [[comment("$80:88C9 (continued from $80:88AD) Subroutine: [reli]")]];
    Code sub_88C8 @ 0x0008C8 [[comment("$80:88C8 Subroutine: [reli] (end unknown)")]];
    Code sub_88DA[0xF] @ 0x0008DA [[comment("$80:88DA Subroutine: [reli]")]];
    Code sub_88E9[0x5] @ 0x0008E9 [[comment("$80:88E9 Subroutine: [reli]")]];
    Code sub_88EE[0xBC] @ 0x0008EE [[comment("$80:88EE Subroutine: [reli]")]];
    Code sub_89AA[0xAD] @ 0x0009AA [[comment("$80:89AA Subroutine: [reli]")]];
    Data data_8A57 @ 0x000A57 [[comment("$80:8A57 Data? [reli] (end unknown)")]];
    Data data_8A81[0x18] @ 0x000A81 [[comment("$80:8A81 Pointers to subs ($80:8A99 to $80:8B3F) [reli]")]];
    Code sub_8A99[0x14] @ 0x000A99 [[comment("$80:8A99 Subroutine: [reli]")]];
    Code sub_8AAD[0x18] @ 0x000AAD [[comment("$80:8AAD Subroutine: [reli]")]];
    Code sub_8AC5[0x15] @ 0x000AC5 [[comment("$80:8AC5 Subroutine: [reli]")]];
    Code sub_8ADA[0x1D] @ 0x000ADA [[comment("$80:8ADA Subroutine: [reli]")]];
    Code sub_8AF7[0x12] @ 0x000AF7 [[comment("$80:8AF7 Subroutine: [reli]")]];
    Code sub_8B09[0x9] @ 0x000B09 [[comment("$80:8B09 Subroutine: [reli]")]];
    Code sub_8B12[0x9] @ 0x000B12 [[comment("$80:8B12 Subroutine: [reli]")]];
    Code sub_8B1B[0x9] @ 0x000B1B [[comment("$80:8B1B Subroutine: [reli]")]];
    Code sub_8B24[0x9] @ 0x000B24 [[comment("$80:8B24 Subroutine: [reli]")]];
    Code sub_8B2D[0x9] @ 0x000B2D [[comment("$80:8B2D Subroutine: [reli]")]];
    Code sub_8B36[0x9] @ 0x000B36 [[comment("$80:8B36 Subroutine: [reli]")]];
    Code sub_8B3F[0x18] @ 0x000B3F [[comment("$80:8B3F Subroutine: [reli]")]];
    Code sub_8B57[0x1C] @ 0x000B57 [[comment("$80:8B57 Subroutine: [reli]")]];
    Code sub_8B73[0x34] @ 0x000B73 [[comment("$80:8B73 Subroutine: [reli]")]];
    Code sub_8BA7[0xB] @ 0x000BA7 [[comment("$80:8BA7 Subroutine: [reli]")]];
    Code sub_8BB2[0x18] @ 0x000BB2 [[comment("$80:8BB2 Subroutine: [reli]")]];
    Code sub_8BCA[0x33] @ 0x000BCA [[comment("$80:8BCA Subroutine: [reli]")]];
    Data data_8E16[0x87] @ 0x000E16 [[comment("$80:8E16 Data? [reli]")]];
    Code sub_8E9D[0x19A] @ 0x000E9D [[comment("$80:8E9D Subroutine: Involved in the loading/decompressing of background data [reli]")]];
    Code sub_9037[0x28] @ 0x001037 [[comment("$80:9037 Subroutine: [reli]")]];
    Code sub_905F[0x14] @ 0x00105F [[comment("$80:905F Subroutine: [reli]")]];
    Code sub_9073[0x26] @ 0x001073 [[comment("$80:9073 Subroutine: [reli]")]];
    Code sub_9099[0x30] @ 0x001099 [[comment("$80:9099 Subroutine: [reli]")]];
    Code sub_90C9[0x1C] @ 0x0010C9 [[comment("$80:90C9 Subroutine: [reli]")]];
    Code sub_90E5[0x17] @ 0x0010E5 [[comment("$80:90E5 Subroutine: Called by: sub at $80:8E9D [reli]")]];
    Code sub_90FC[0x20] @ 0x0010FC [[comment("$80:90FC Subroutine: Called by: ? - sub at $80:90E5 ? [reli]")]];
    Code sub_911C[0x2F] @ 0x00111C [[comment("$80:911C Subroutine: [reli]")]];
    Code sub_914B[0x39] @ 0x00114B [[comment("$80:914B Subroutine: [reli]")]];
    Code sub_9184[0x4F] @ 0x001184 [[comment("$80:9184 Subroutine: [reli]")]];
    Code sub_91D3[0xC] @ 0x0011D3 [[comment("$80:91D3 Subroutine: Start: A = b|????????|???xxxxx| (|high|low|) End: X = A = b|xxxxx000|00000000| Called by: ? - sub at $80:90E5 - sub at $80:90FC ? [reli]")]];
    Code sub_91DF[0xBB] @ 0x0011DF [[comment("$80:91DF Subroutine: [reli]")]];
    Code sub_91DF_2[0x9] @ 0x00129B [[comment("$80:929B (continued from $80:91DF) Subroutine: [reli]")]];
    Code sub_929A @ 0x00129A [[comment("$80:929A AP hook: logo skip | DB=$80, x=0, m=1 | LDA.b #$00 ; overwrites LDA.b #$80 [ap] (end unknown)")]];
    Code sub_92A4[0x13] @ 0x0012A4 [[comment("$80:92A4 Subroutine: [reli]")]];
    Data data_92B7[0x14] @ 0x0012B7 [[comment("$80:92B7 Pointers for sub at $80:92A4 [reli]")]];
    Code sub_92CB[0x33] @ 0x0012CB [[comment("$80:92CB Subroutine: [reli]")]];
    Code sub_92FE[0xE] @ 0x0012FE [[comment("$80:92FE Subroutine: [reli]")]];
    Code sub_930C[0x14] @ 0x00130C [[comment("$80:930C Subroutine: [reli]")]];
    Code sub_9320[0x10] @ 0x001320 [[comment("$80:9320 Subroutine: [reli]")]];
    Code sub_9330[0x16] @ 0x001330 [[comment("$80:9330 Subroutine: [reli]")]];
    Code sub_9346[0xE] @ 0x001346 [[comment("$80:9346 Subroutine: [reli]")]];
    Code sub_9354[0x3] @ 0x001354 [[comment("$80:9354 Subroutine: [reli]")]];
    Code sub_9357[0x2C] @ 0x001357 [[comment("$80:9357 Subroutine: [reli]")]];
    Code sub_9383[0x53] @ 0x001383 [[comment("$80:9383 Subroutine: [reli]")]];
    Code sub_93D6[0x28] @ 0x0013D6 [[comment("$80:93D6 Subroutine: [reli]")]];
    Code sub_93FE[0x1C] @ 0x0013FE [[comment("$80:93FE Subroutine: Involved in the loading of map themes [reli]")]];
    Code sub_941A[0x10E] @ 0x00141A [[comment("$80:941A Subroutine: [reli]")]];
    Code sub_9528[0x13] @ 0x001528 [[comment("$80:9528 Subroutine: Called by: - sub at $80:B8B1 [reli]")]];
    Code sub_953B[0x19] @ 0x00153B [[comment("$80:953B Subroutine: [reli]")]];
    Code sub_9554[0x16] @ 0x001554 [[comment("$80:9554 Subroutine: [reli]")]];
    Code sub_956A[0x13] @ 0x00156A [[comment("$80:956A Subroutine: [reli]")]];
    Code sub_957D[0x55] @ 0x00157D [[comment("$80:957D Subroutine: [reli]")]];
    Code sub_95D2[0xD] @ 0x0015D2 [[comment("$80:95D2 Subroutine: [reli]")]];
    Code sub_95DF[0x11] @ 0x0015DF [[comment("$80:95DF Subroutine: [reli]")]];
    Code sub_95F0[0x11] @ 0x0015F0 [[comment("$80:95F0 Subroutine: Called by: - sub at $80:B8DC [reli]")]];
    Code sub_9601[0x11] @ 0x001601 [[comment("$80:9601 Subroutine: [reli]")]];
    Code sub_9612[0x11] @ 0x001612 [[comment("$80:9612 Subroutine: [reli]")]];
    Code sub_9623[0x11] @ 0x001623 [[comment("$80:9623 Subroutine: [reli]")]];
    Code sub_9634[0x10] @ 0x001634 [[comment("$80:9634 Subroutine: [reli]")]];
    Code sub_9644[0x11] @ 0x001644 [[comment("$80:9644 Subroutine: [reli]")]];
    Code sub_9655[0x1A] @ 0x001655 [[comment("$80:9655 Subroutine: [reli]")]];
    Code sub_966F[0x16] @ 0x00166F [[comment("$80:966F Subroutine: [reli]")]];
    Code sub_9685[0xD] @ 0x001685 [[comment("$80:9685 Subroutine: [reli]")]];
    Code sub_9692[0xD] @ 0x001692 [[comment("$80:9692 Subroutine: [reli]")]];
    Code sub_969F[0x1A] @ 0x00169F [[comment("$80:969F Subroutine: [reli]")]];
    Code sub_96B9[0x13] @ 0x0016B9 [[comment("$80:96B9 Subroutine: [reli]")]];
    Code sub_96CC[0x11] @ 0x0016CC [[comment("$80:96CC Subroutine: [reli]")]];
    Code sub_96DD[0x15] @ 0x0016DD [[comment("$80:96DD Subroutine: [reli]")]];
    Code sub_96F2[0x11] @ 0x0016F2 [[comment("$80:96F2 Subroutine: Called by: - sub at $80:B8C7 [reli]")]];
    Code sub_99FD[0xD] @ 0x0019FD [[comment("$80:99FD Subroutine: Called by: - sub at $80:9528 - sub at $80:96F2 [reli]")]];
    Code sub_9A0A[0x2A] @ 0x001A0A [[comment("$80:9A0A Subroutine: Called by: - sub at $80:9528 - sub at $80:96F2 [reli]")]];
    Data data_9A34 @ 0x001A34 [[comment("$80:9A34 Data? [reli] (end unknown)")]];
    Data data_9A59[0x9] @ 0x001A59 [[comment("$80:9A59 Data? [reli]")]];
    Data data_9A62[0x11E] @ 0x001A62 [[comment("$80:9A62 Pointers to data at [$001D80] [reli]")]];
    Data data_9B80[0x8F] @ 0x001B80 [[comment("$80:9B80 Some data... all #$FF... [reli]")]];
    Code sub_9C0F[0x63] @ 0x001C0F [[comment("$80:9C0F Subroutine: [reli]")]];
    Code sub_9CD9 @ 0x001CD9 [[comment("$80:9CD9 event interpreter sets DBR to the script bank: LDA $09B9 : PHA : PLB (why events need banks $80-$BF) [iris] (end unknown)")]];
    Code sub_9D3E[0xE] @ 0x001D3E [[comment("$80:9D3E Subroutine: Implementation of L2SASM opcode $08 [reli]")]];
    Code sub_9D4C[0x64] @ 0x001D4C [[comment("$80:9D4C Subroutine: (actually: [$9D4C, $9DB2] Implementation of L2SASM opcodes $00 and $42 [reli]")]];
    Code sub_9DB0[0x3] @ 0x001DB0 [[comment("$80:9DB0 Subroutine: Implementation of L2SASM opcode $84 00/9DB0: 28 PLP 00/9DB1: AB PLB 00/9DB2: 6B RTL [reli]")]];
    Code sub_9DB3[0x21] @ 0x001DB3 [[comment("$80:9DB3 Subroutine: Implementation of L2SASM opcode $01 [reli]")]];
    Code sub_9DD4 @ 0x001DD4 [[comment("$80:9DD4 Subroutine: Implementation of L2SASM opcode $02 00/9DD4: 00 BRK [reli] (end unknown)")]];
    Code sub_9DD5[0x6] @ 0x001DD5 [[comment("$80:9DD5 Subroutine: Implementation of L2SASM opcode $03 [reli]")]];
    Code sub_9DDB[0x1F] @ 0x001DDB [[comment("$80:9DDB Subroutine: [reli]")]];
    Code sub_9DFA[0x4B] @ 0x001DFA [[comment("$80:9DFA Subroutine: Implementation of L2SASM opcode $04 [reli]")]];
    Code sub_9E45[0x9] @ 0x001E45 [[comment("$80:9E45 Subroutine: Implementation of L2SASM opcode $05 [reli]")]];
    Code sub_9E4E[0x35] @ 0x001E4E [[comment("$80:9E4E Subroutine: Implementation of L2SASM opcode $06 [reli]")]];
    Code sub_9E83[0x45] @ 0x001E83 [[comment("$80:9E83 Subroutine: Implementation of L2SASM opcode $0A [reli]")]];
    Code sub_9EC8[0xE] @ 0x001EC8 [[comment("$80:9EC8 Subroutine: Implementation of L2SASM opcode $07 $07 XX ... [reli]")]];
    Code sub_9ED6[0x1A] @ 0x001ED6 [[comment("$80:9ED6 Subroutine: Implementation of L2SASM opcode $09 [reli]")]];
    Code sub_9EF0[0x4] @ 0x001EF0 [[comment("$80:9EF0 Subroutine: Implementation of L2SASM opcode $0C [reli]")]];
    Code sub_9EF4[0x4] @ 0x001EF4 [[comment("$80:9EF4 Subroutine: Implementation of L2SASM opcode $0D [reli]")]];
    Code sub_9EF8[0x4] @ 0x001EF8 [[comment("$80:9EF8 Subroutine: Implementation of L2SASM opcode $0E [reli]")]];
    Code sub_9EFC[0x14] @ 0x001EFC [[comment("$80:9EFC Subroutine: Implementation of L2SASM opcode $0F [reli]")]];
    Code sub_9F10[0x27] @ 0x001F10 [[comment("$80:9F10 Subroutine: Implementation of L2SASM opcode $10 [reli]")]];
    Code sub_9F37[0x95] @ 0x001F37 [[comment("$80:9F37 Subroutine: Implementation of L2SASM opcode $0B [reli]")]];
    Code sub_9FCC[0x1B] @ 0x001FCC [[comment("$80:9FCC Subroutine: [reli]")]];
    Code sub_9FE7[0x32] @ 0x001FE7 [[comment("$80:9FE7 Subroutine: [reli]")]];
    Code sub_A019[0x28] @ 0x002019 [[comment("$80:A019 Subroutine: [reli]")]];
    Code sub_A041[0x2D] @ 0x002041 [[comment("$80:A041 Subroutine: Implementation of L2SASM opcode $12 [reli]")]];
    Code sub_A06E[0x6] @ 0x00206E [[comment("$80:A06E Subroutine: Implementation of L2SASM opcode $13 [reli]")]];
    Code sub_A074[0x158] @ 0x002074 [[comment("$80:A074 Subroutine: Implementation of L2SASM opcode $14 [reli]")]];
    Code sub_A1CC[0x18] @ 0x0021CC [[comment("$80:A1CC Subroutine: Is a part of the implementation of L2SASM opcode $14 (called by sub at $80:A074) - load next script byte: a character number ($00 -> $06) - X = start address of the character data in the RAM (in bank $7E) [reli]")]];
    Code sub_A1E4[0x12] @ 0x0021E4 [[comment("$80:A1E4 Subroutine: Is a part of the implementation of L2SASM opcode $14 (called by sub at $80:A074) [reli]")]];
    Code sub_A1F6[0x73] @ 0x0021F6 [[comment("$80:A1F6 Subroutine: Is a part of the implementation of L2SASM opcode $14 (sub at $80:A074 jumps here) [reli]")]];
    Code sub_A269[0x1F] @ 0x002269 [[comment("$80:A269 Subroutine: Is a part of the implementation of L2SASM opcode $14 (sub at $80:A074 jumps here) [reli]")]];
    Code sub_A288[0x14] @ 0x002288 [[comment("$80:A288 Subroutine: Implementation of L2SASM opcode $15 [reli]")]];
    Code sub_A29C[0x14] @ 0x00229C [[comment("$80:A29C Subroutine: Implementation of L2SASM opcode $6A [reli]")]];
    Code sub_A2B0[0xA] @ 0x0022B0 [[comment("$80:A2B0 Subroutine: Implementation of L2SASM opcode $6B [reli]")]];
    Code sub_A2BA[0x27] @ 0x0022BA [[comment("$80:A2BA Subroutine: Implementation of L2SASM opcode $16 [reli]")]];
    Code sub_A2E1[0x4A] @ 0x0022E1 [[comment("$80:A2E1 Subroutine: Implementation of L2SASM opcode $17 [reli]")]];
    Code sub_A32B[0x25] @ 0x00232B [[comment("$80:A32B Subroutine: Implementation of L2SASM opcode $18 [reli]")]];
    Code sub_A350[0x18] @ 0x002350 [[comment("$80:A350 Subroutine: [reli]")]];
    Code sub_A368[0xA] @ 0x002368 [[comment("$80:A368 Subroutine: [reli]")]];
    Code sub_A372[0x20] @ 0x002372 [[comment("$80:A372 Subroutine: Implementation of L2SASM opcode $19 [reli]")]];
    Code sub_A392[0x1A] @ 0x002392 [[comment("$80:A392 Subroutine: Implementation of L2SASM opcode $1A [reli]")]];
    Code sub_A3AC[0x1A] @ 0x0023AC [[comment("$80:A3AC Subroutine: Implementation of L2SASM opcode $1B [reli]")]];
    Code sub_A3C6[0x19] @ 0x0023C6 [[comment("$80:A3C6 Subroutine: Implementation of L2SASM opcode $1C [reli]")]];
    Code sub_A3DF[0xE] @ 0x0023DF [[comment("$80:A3DF Subroutine: Implementation of L2SASM opcode $1D $1D XX YY $079E,#$XX = #$YY [reli]")]];
    Code sub_A3ED[0x12] @ 0x0023ED [[comment("$80:A3ED Subroutine: Implementation of L2SASM opcode $1E $1E XX YY $079E,#$XX = $079E,#$XX + #$YY [reli]")]];
    Code sub_A3FF[0x15] @ 0x0023FF [[comment("$80:A3FF Subroutine: Implementation of L2SASM opcode $1F [reli]")]];
    Code sub_A414[0xB] @ 0x002414 [[comment("$80:A414 Subroutine: Implementation of L2SASM opcode $20 [reli]")]];
    Code sub_A41F[0xC] @ 0x00241F [[comment("$80:A41F Subroutine: Implementation of L2SASM opcode $21 [reli]")]];
    Code sub_A42B[0xA] @ 0x00242B [[comment("$80:A42B Subroutine: [reli]")]];
    Code sub_A42B_2[0x4A] @ 0x002436 [[comment("$80:A436 (continued from $80:A42B) Subroutine: [reli]")]];
    Code sub_A435 @ 0x002435 [[comment("$80:A435 STA $7FD4F1 in the script item-get path (AP hook ScriptTX) [ap] || AP hook: transmit checks from script events | DB=$8E, x=0, m=1 | JML ScriptTX ; overwrites STA $7FD4F1 [ap] (end unknown)")]];
    Code sub_A480[0x9] @ 0x002480 [[comment("$80:A480 Subroutine: Implementation of L2SASM opcode $22 22 XX YY A = #$YYXX ... => get #$YYXX GOLD (and ensure that total GOLD doesn't go past 9999999) ----- Calls: sub at $80:BF12 [reli]")]];
    Code sub_A489[0x14] @ 0x002489 [[comment("$80:A489 Subroutine: Implementation of L2SASM opcode $23 [reli] || event opcode 23 handler: learn spell (spell -> $0A0B, character in A, JSL $82:FD3D) [iris]")]];
    Code sub_A49D[0x9] @ 0x00249D [[comment("$80:A49D Subroutine: Implementation of L2SASM opcode $24 $24 XX YY $09D0 = #$00 $09CF = XX $09CE = #$00 $09CD = YY ... ----- Calls: sub at $80:A4B1 [reli]")]];
    Code sub_A4A6[0xB] @ 0x0024A6 [[comment("$80:A4A6 Subroutine: Implementation of L2SASM opcode $25 $25 XX YY $09D0 = #$01 $09CF = XX $09CE = #$00 $09CD = YY ... ----- Calls: sub at $80:A4B1 [reli]")]];
    Code sub_A4B1[0x1A] @ 0x0024B1 [[comment("$80:A4B1 Subroutine: [reli]")]];
    Code sub_A4CB[0x9] @ 0x0024CB [[comment("$80:A4CB Subroutine: Implementation of L2SASM opcode $26 [reli]")]];
    Code sub_A4D4[0x9] @ 0x0024D4 [[comment("$80:A4D4 Subroutine: Implementation of L2SASM opcode $27 (dummy 3-bytes instruction?) [reli]")]];
    Code sub_A4DD[0x13] @ 0x0024DD [[comment("$80:A4DD Subroutine: Implementation of L2SASM opcode $28 [reli]")]];
    Code sub_A4F0[0x1B] @ 0x0024F0 [[comment("$80:A4F0 Subroutine: Implementation of L2SASM opcode $B9 [reli]")]];
    Code sub_A50B[0x12] @ 0x00250B [[comment("$80:A50B Subroutine: Implementation of L2SASM opcode $BA [reli]")]];
    Code sub_A51D[0x2D] @ 0x00251D [[comment("$80:A51D Subroutine: Implementation of L2SASM opcode $BB [reli]")]];
    Code sub_A54A[0x4C] @ 0x00254A [[comment("$80:A54A Subroutine: Implementation of L2SASM opcode $29 [reli]")]];
    Data data_A596[0x1C] @ 0x002596 [[comment("$80:A596 Pointers? Data? [reli]")]];
    Code sub_A5B2[0xA] @ 0x0025B2 [[comment("$80:A5B2 Subroutine: X = next script byte * 2 [reli]")]];
    Code sub_A5BC[0xC] @ 0x0025BC [[comment("$80:A5BC Subroutine: Implementation of L2SASM opcode $2A (dummy 4-bytes instruction?) [reli]")]];
    Code sub_A5C8[0x37] @ 0x0025C8 [[comment("$80:A5C8 Subroutine: Implementation of L2SASM opcode $2B [reli]")]];
    Code sub_A5FF[0x3B] @ 0x0025FF [[comment("$80:A5FF Subroutine: Implementation of L2SASM opcode $2C [reli]")]];
    Code sub_A63A[0x3F] @ 0x00263A [[comment("$80:A63A Subroutine: Implementation of L2SASM opcode $2D [reli]")]];
    Code sub_A679[0x35] @ 0x002679 [[comment("$80:A679 Subroutine: Implementation of L2SASM opcode $2E [reli]")]];
    Code sub_A6AE[0x14] @ 0x0026AE [[comment("$80:A6AE Subroutine: Implementation of L2SASM opcodes $77 and $BE [reli]")]];
    Code sub_A6C2[0x25] @ 0x0026C2 [[comment("$80:A6C2 Subroutine: Implementation of L2SASM opcode $78 [reli]")]];
    Code sub_A6E7[0x22] @ 0x0026E7 [[comment("$80:A6E7 Subroutine: Implementation of L2SASM opcode $79 [reli]")]];
    Code sub_A709[0x12] @ 0x002709 [[comment("$80:A709 Subroutine: Implementation of L2SASM opcode $7A [reli]")]];
    Code sub_A71B[0x13] @ 0x00271B [[comment("$80:A71B Subroutine: Implementation of L2SASM opcode $2F [reli]")]];
    Code sub_A72E[0x1F] @ 0x00272E [[comment("$80:A72E Subroutine: Implementation of L2SASM opcode $30 [reli]")]];
    Code sub_A794[0x23] @ 0x002794 [[comment("$80:A794 Subroutine: Implementation of L2SASM opcode $31 [reli]")]];
    Data data_A7B7[0x4] @ 0x0027B7 [[comment("$80:A7B7 Data for L2BASM opcode $31? [reli]")]];
    Code sub_A7BB[0x54] @ 0x0027BB [[comment("$80:A7BB Subroutine: Implementation of L2SASM opcode $32 [reli]")]];
    Code sub_A80F[0xE9] @ 0x00280F [[comment("$80:A80F Subroutine: Implementation of L2SASM opcode $33 [reli]")]];
    Code sub_A8F8[0x3E] @ 0x0028F8 [[comment("$80:A8F8 Subroutine: Implementation of L2SASM opcode $34 [reli]")]];
    Code sub_A936[0x18] @ 0x002936 [[comment("$80:A936 Subroutine: Implementation of L2SASM opcode $86 [reli]")]];
    Code sub_A94E[0xE] @ 0x00294E [[comment("$80:A94E Subroutine: Implementation of L2SASM opcode $A3 [reli]")]];
    Code sub_A95C[0x2A] @ 0x00295C [[comment("$80:A95C Subroutine: Implementation of L2SASM opcode $BF [reli]")]];
    Code sub_A986[0x17] @ 0x002986 [[comment("$80:A986 Subroutine: [reli]")]];
    Code sub_A99D[0x1A] @ 0x00299D [[comment("$80:A99D Subroutine: Implementation of L2SASM opcode $8C [reli]")]];
    Code sub_A9B7[0x7] @ 0x0029B7 [[comment("$80:A9B7 Subroutine: Implementation of L2SASM opcode $A0 [reli]")]];
    Code sub_A9BE[0x7] @ 0x0029BE [[comment("$80:A9BE Subroutine: Implementation of L2SASM opcode $8D [reli]")]];
    Code sub_A9C5[0x7] @ 0x0029C5 [[comment("$80:A9C5 Subroutine: Implementation of L2SASM opcode $C3 [reli]")]];
    Code sub_A9CC[0x7] @ 0x0029CC [[comment("$80:A9CC Subroutine: Implementation of L2SASM opcode $C2 [reli]")]];
    Code sub_A9D3[0x8] @ 0x0029D3 [[comment("$80:A9D3 Subroutine: Implementation of L2SASM opcode $C8 [reli]")]];
    Code sub_A9DB[0x8] @ 0x0029DB [[comment("$80:A9DB Subroutine: Implementation of L2SASM opcode $C9 [reli]")]];
    Code sub_A9E3[0x1F] @ 0x0029E3 [[comment("$80:A9E3 Subroutine: [reli]")]];
    Code sub_AA02[0x1E] @ 0x002A02 [[comment("$80:AA02 Subroutine: [reli]")]];
    Code sub_AA20[0x23] @ 0x002A20 [[comment("$80:AA20 Subroutine: [reli]")]];
    Code sub_AA43[0x6] @ 0x002A43 [[comment("$80:AA43 Subroutine: Implementation of L2SASM opcode $8E [reli]")]];
    Code sub_AA49[0x1E] @ 0x002A49 [[comment("$80:AA49 Subroutine: Implementation of L2SASM opcode $9F [reli]")]];
    Code sub_AA67[0x1C] @ 0x002A67 [[comment("$80:AA67 Subroutine: [reli]")]];
    Code sub_AA83[0x1E] @ 0x002A83 [[comment("$80:AA83 Subroutine: Implementation of L2SASM opcode $8F [reli]")]];
    Code sub_AAA1[0x1E] @ 0x002AA1 [[comment("$80:AAA1 Subroutine: Implementation of L2SASM opcode $90 [reli]")]];
    Code sub_AABF[0x27] @ 0x002ABF [[comment("$80:AABF Subroutine: Implementation of L2SASM opcode $9A [reli]")]];
    Code sub_AAE6[0x37] @ 0x002AE6 [[comment("$80:AAE6 Subroutine: Implementation of L2SASM opcode $A1 [reli]")]];
    Code sub_AB1D[0x16] @ 0x002B1D [[comment("$80:AB1D Subroutine: Implementation of L2SASM opcode $A2 [reli]")]];
    Code sub_AB33[0x12] @ 0x002B33 [[comment("$80:AB33 Subroutine: [reli]")]];
    Code sub_AB45[0xC] @ 0x002B45 [[comment("$80:AB45 Subroutine: Implementation of L2SASM opcode $A5 [reli]")]];
    Code sub_AB51[0x7C] @ 0x002B51 [[comment("$80:AB51 Subroutine: Implementation of L2SASM opcode $A6 [reli]")]];
    Data data_ABCD[0x3] @ 0x002BCD [[comment("$80:ABCD Data for L2SASM opcode $A6? [reli]")]];
    Code sub_ABD0[0x29] @ 0x002BD0 [[comment("$80:ABD0 Subroutine: Implementation of L2SASM opcode $A8 [reli]")]];
    Code sub_ABF9[0x1F] @ 0x002BF9 [[comment("$80:ABF9 Subroutine: Implementation of L2SASM opcode $A9 [reli]")]];
    Code sub_AC18[0x10] @ 0x002C18 [[comment("$80:AC18 Subroutine: Implementation of L2SASM opcode $AA [reli]")]];
    Code sub_AC28[0x20] @ 0x002C28 [[comment("$80:AC28 Subroutine: Implementation of L2SASM opcode $AB [reli]")]];
    Code sub_AC48[0x22] @ 0x002C48 [[comment("$80:AC48 Subroutine: Implementation of L2SASM opcode $AC [reli]")]];
    Code sub_AC6A[0x9] @ 0x002C6A [[comment("$80:AC6A Subroutine: Implementation of L2SASM opcode $AD [reli]")]];
    Code sub_AC73[0x17] @ 0x002C73 [[comment("$80:AC73 Subroutine: Implementation of L2SASM opcode $AE [reli]")]];
    Code sub_AC8A[0x1D] @ 0x002C8A [[comment("$80:AC8A Subroutine: Implementation of L2SASM opcode $B6 [reli]")]];
    Code sub_ACA7[0x16] @ 0x002CA7 [[comment("$80:ACA7 Subroutine: Implementation of L2SASM opcode $B7 [reli]")]];
    Code sub_ACBD[0x25] @ 0x002CBD [[comment("$80:ACBD Subroutine: Implementation of L2SASM opcode $AF [reli]")]];
    Code sub_ACE2[0x20] @ 0x002CE2 [[comment("$80:ACE2 Subroutine: Implementation of L2SASM opcode $B0 [reli]")]];
    Code sub_AD02[0x10] @ 0x002D02 [[comment("$80:AD02 Subroutine: Implementation of L2SASM opcode $B1 [reli]")]];
    Code sub_AD12[0x1C] @ 0x002D12 [[comment("$80:AD12 Subroutine: Implementation of L2SASM opcode $B2 [reli]")]];
    Code sub_AD2F[0xA] @ 0x002D2F [[comment("$80:AD2F Subroutine: Implementation of L2SASM opcode $B3 [reli]")]];
    Code sub_AD39[0x98] @ 0x002D39 [[comment("$80:AD39 Subroutine: [reli]")]];
    Code sub_ADD1[0xB] @ 0x002DD1 [[comment("$80:ADD1 Subroutine: Implementation of L2SASM opcode $B5 [reli]")]];
    Code sub_ADDC[0x10] @ 0x002DDC [[comment("$80:ADDC Subroutine: Implementation of L2SASM opcode $B8 [reli]")]];
    Code sub_ADEC[0x17] @ 0x002DEC [[comment("$80:ADEC Subroutine: Implementation of L2SASM opcode $A7 [reli]")]];
    Code sub_AE03[0x21] @ 0x002E03 [[comment("$80:AE03 Subroutine: Implementation of L2SASM opcode $91 [reli]")]];
    Code sub_AE24[0x12] @ 0x002E24 [[comment("$80:AE24 Subroutine: Implementation of L2SASM opcode $92 [reli]")]];
    Code sub_AE36[0x6] @ 0x002E36 [[comment("$80:AE36 Subroutine: [reli]")]];
    Code sub_AE3C[0x6] @ 0x002E3C [[comment("$80:AE3C Subroutine: [reli]")]];
    Code sub_AE42[0x81] @ 0x002E42 [[comment("$80:AE42 Subroutine: Implementation of L2SASM opcode $93 [reli]")]];
    Code sub_AEC3[0x2F] @ 0x002EC3 [[comment("$80:AEC3 Subroutine: [reli]")]];
    Code sub_AEF2[0x41] @ 0x002EF2 [[comment("$80:AEF2 Subroutine: Implementation of L2SASM opcode $9B [reli]")]];
    Code sub_AF33[0x20] @ 0x002F33 [[comment("$80:AF33 Subroutine: [reli]")]];
    Code sub_AF53[0x8] @ 0x002F53 [[comment("$80:AF53 Subroutine: Implementation of L2SASM opcode $95 [reli]")]];
    Code sub_AF5B[0x8] @ 0x002F5B [[comment("$80:AF5B Subroutine: Implementation of L2SASM opcode $94 [reli]")]];
    Code sub_AF63[0x8] @ 0x002F63 [[comment("$80:AF63 Subroutine: Implementation of L2SASM opcode $96 [reli]")]];
    Code sub_AF6B[0xC] @ 0x002F6B [[comment("$80:AF6B Subroutine: Implementation of L2SASM opcode $97 [reli]")]];
    Code sub_AF77[0x49] @ 0x002F77 [[comment("$80:AF77 Subroutine: [reli]")]];
    Code sub_AFC0[0x27] @ 0x002FC0 [[comment("$80:AFC0 Subroutine: Implementation of L2SASM opcode $9C [reli]")]];
    Code sub_AFE7[0x1E] @ 0x002FE7 [[comment("$80:AFE7 Subroutine: Implementation of L2SASM opcode $89 [reli]")]];
    Code sub_B005[0x1C] @ 0x003005 [[comment("$80:B005 Subroutine: Implementation of L2SASM opcode $36 [reli]")]];
    Code sub_B021[0x33] @ 0x003021 [[comment("$80:B021 Subroutine: Implementation of L2SASM opcode $98 [reli]")]];
    Code sub_B054[0x12] @ 0x003054 [[comment("$80:B054 Subroutine: Implementation of L2SASM opcode $99 [reli]")]];
    Code sub_B066[0x12] @ 0x003066 [[comment("$80:B066 Subroutine: Implementation of L2SASM opcode $9D [reli]")]];
    Code sub_B078[0x45] @ 0x003078 [[comment("$80:B078 Subroutine: Implementation of L2SASM opcode $6C [reli]")]];
    Code sub_B0BD[0x6] @ 0x0030BD [[comment("$80:B0BD Subroutine: Implementation of L2SASM opcode $8B [reli]")]];
    Code sub_B0C3[0x28] @ 0x0030C3 [[comment("$80:B0C3 Subroutine: Implementation of L2SASM opcode $C0 [reli]")]];
    Code sub_B0EB[0x2C] @ 0x0030EB [[comment("$80:B0EB Subroutine: [reli]")]];
    Code sub_B117[0x11] @ 0x003117 [[comment("$80:B117 Subroutine: Implementation of L2SASM opcode $C1 [reli]")]];
    Code sub_B128[0x36] @ 0x003128 [[comment("$80:B128 Subroutine: Implementation of L2SASM opcode $6D [reli]")]];
    Data data_B15E[0x60] @ 0x00315E [[comment("$80:B15E Data? [reli]")]];
    Code sub_B1BE[0x39] @ 0x0031BE [[comment("$80:B1BE Subroutine: Implementation of L2SASM opcode $6E [reli]")]];
    Data data_B1F7[0x60] @ 0x0031F7 [[comment("$80:B1F7 Data? [reli]")]];
    Code sub_B257[0x12] @ 0x003257 [[comment("$80:B257 Subroutine: Implementation of L2SASM opcode $73 [reli]")]];
    Code sub_B269[0x3E] @ 0x003269 [[comment("$80:B269 Subroutine: Implementation of L2SASM opcode $C6 [reli]")]];
    Code sub_B2A7[0xA] @ 0x0032A7 [[comment("$80:B2A7 Subroutine: Implementation of L2SASM opcode $74 2-bytes instruction. $7F:F8A0 (ZST $204B3) = next script byte [reli]")]];
    Code sub_B2B1[0x3A] @ 0x0032B1 [[comment("$80:B2B1 Subroutine: Implementation of L2SASM opcode $35 [reli]")]];
    Code sub_B2EB[0x21] @ 0x0032EB [[comment("$80:B2EB Subroutine: Implementation of L2SASM opcode $37 [reli]")]];
    Code sub_B30C[0x32] @ 0x00330C [[comment("$80:B30C Subroutine: Implementation of L2SASM opcode $38 [reli]")]];
    Code sub_B33E[0x3] @ 0x00333E [[comment("$80:B33E Subroutine: Implementation of L2SASM opcode $39 BRL $009D00 (that's all) (dummy 1-byte instruction?) [reli]")]];
    Code sub_B341[0xE] @ 0x003341 [[comment("$80:B341 Subroutine: Implementation of L2SASM opcode $3A $120A = next script byte $120B = next script byte $56 = $120A $57 = #$00 $58 = $120B $59 = #$00 ... (calls 3 subs) [reli]")]];
    Code sub_B34F[0x25] @ 0x00334F [[comment("$80:B34F Subroutine: Implementation of L2SASM opcode $3B [reli]")]];
    Code sub_B374[0x23] @ 0x003374 [[comment("$80:B374 Subroutine: [reli]")]];
    Code sub_B397[0x6D] @ 0x003397 [[comment("$80:B397 Subroutine: Implementation of L2SASM opcode $3C [reli]")]];
    Code sub_B404[0x67] @ 0x003404 [[comment("$80:B404 Subroutine: [reli]")]];
    Code sub_B46B[0x19] @ 0x00346B [[comment("$80:B46B Subroutine: Implementation of L2SASM opcode $3D [reli]")]];
    Code sub_B484[0x8] @ 0x003484 [[comment("$80:B484 Subroutine: Implementation of L2SASM opcode $3E $00:0583 (ZST $01196) = #$80 [reli]")]];
    Code sub_B48C[0x8] @ 0x00348C [[comment("$80:B48C Subroutine: Implementation of L2SASM opcode $3F $00:0583 (ZST $01196) = #$0F [reli]")]];
    Code sub_B494[0x7] @ 0x003494 [[comment("$80:B494 Subroutine: Implementation of L2SASM opcode $40 [reli]")]];
    Code sub_B49B[0x12] @ 0x00349B [[comment("$80:B49B Subroutine: Implementation of L2SASM opcode $75 $7E:120A = $7E:06BA $7E:120B = $7E:06E2 ... ----- Calls: sub at $80:B374 [reli]")]];
    Code sub_B4AD[0x17] @ 0x0034AD [[comment("$80:B4AD Subroutine: Implementation of L2SASM opcode $C4 [reli]")]];
    Code sub_B4C4[0xCE] @ 0x0034C4 [[comment("$80:B4C4 Subroutine: Implementation of L2SASM opcode $41 [reli]")]];
    Code sub_B592[0x2C] @ 0x003592 [[comment("$80:B592 Subroutine: [reli]")]];
    Data data_B5BE[0x8] @ 0x0035BE [[comment("$80:B5BE Pointers to subs ($80:B5C6 to $80:B5DE) [reli]")]];
    Code sub_B5C6[0x8] @ 0x0035C6 [[comment("$80:B5C6 Subroutine: [reli]")]];
    Code sub_B5CE[0x8] @ 0x0035CE [[comment("$80:B5CE Subroutine: [reli]")]];
    Code sub_B5D6[0x8] @ 0x0035D6 [[comment("$80:B5D6 Subroutine: [reli]")]];
    Code sub_B5DE[0x8] @ 0x0035DE [[comment("$80:B5DE Subroutine: [reli]")]];
    Code sub_B5E6[0x45] @ 0x0035E6 [[comment("$80:B5E6 Subroutine: [reli]")]];
    Code sub_B62B[0x1B] @ 0x00362B [[comment("$80:B62B Subroutine: Implementation of L2SASM opcode $87 [reli]")]];
    Code sub_B646[0x13] @ 0x003646 [[comment("$80:B646 Subroutine: Implementation of L2SASM opcode $BC [reli]")]];
    Code sub_B659[0x24] @ 0x003659 [[comment("$80:B659 Subroutine: Implementation of L2SASM opcode $C7 [reli]")]];
    Code sub_B67D[0x19] @ 0x00367D [[comment("$80:B67D Subroutine: Implementation of L2SASM opcode $CA $CA XX YY ZZ X = #$00XX $7F:D020,X = YY $7F:D021,X = ZZ [reli]")]];
    Code sub_B696[0x9] @ 0x003696 [[comment("$80:B696 Subroutine: Implementation of L2SASM opcode $CB Store the next script byte at $7E:0B52 [reli]")]];
    Code sub_B69F[0x14] @ 0x00369F [[comment("$80:B69F Subroutine: Implementation of L2SASM opcode $CC [reli]")]];
    Code sub_B6B3[0x41] @ 0x0036B3 [[comment("$80:B6B3 Subroutine: Implementation of L2SASM opcode $BD [reli]")]];
    Code sub_B6F4[0x2D] @ 0x0036F4 [[comment("$80:B6F4 Subroutine: Implementation of L2SASM opcode $B4 [reli]")]];
    Code sub_B721[0xC] @ 0x003721 [[comment("$80:B721 Subroutine: Implementation of L2SASM opcode $88 [reli]")]];
    Code sub_B72D[0x3D] @ 0x00372D [[comment("$80:B72D Subroutine: Implementation of L2SASM opcode $43 [reli]")]];
    Code sub_B76A[0x3C] @ 0x00376A [[comment("$80:B76A Subroutine: [reli]")]];
    Code sub_B7A6[0xE] @ 0x0037A6 [[comment("$80:B7A6 Subroutine: Implementation of L2SASM opcode $44 [reli]")]];
    Code sub_B7B4[0xE] @ 0x0037B4 [[comment("$80:B7B4 Subroutine: Implementation of L2SASM opcode $45 [reli]")]];
    Code sub_B7C2[0x13] @ 0x0037C2 [[comment("$80:B7C2 Subroutine: Implementation of L2SASM opcode $46 [reli]")]];
    Code sub_B7D5[0x11] @ 0x0037D5 [[comment("$80:B7D5 Subroutine: X = next script byte * 2 $7E:0054 = next2 script byte $7E:0055 = next3 script byte [reli]")]];
    Code sub_B7E6[0x9] @ 0x0037E6 [[comment("$80:B7E6 Subroutine: Implementation of L2SASM opcode $47 [reli]")]];
    Code sub_B7EF[0xF] @ 0x0037EF [[comment("$80:B7EF Subroutine: Implementation of L2SASM opcode $48 [reli]")]];
    Code sub_B7FE[0x1B] @ 0x0037FE [[comment("$80:B7FE Subroutine: Implementation of L2SASM opcode $9E [reli]")]];
    Code sub_B819[0x1E] @ 0x003819 [[comment("$80:B819 Subroutine: [reli]")]];
    Code sub_B837[0x9] @ 0x003837 [[comment("$80:B837 Subroutine: Implementation of L2SASM opcode $49 $49 XX $1265 = #$XX [reli]")]];
    Code sub_B840[0x9] @ 0x003840 [[comment("$80:B840 Subroutine: Implementation of L2SASM opcode $4A $4A XX $09AD = #$XX [reli]")]];
    Code sub_B849[0x28] @ 0x003849 [[comment("$80:B849 Subroutine: Implementation of L2SASM opcode $4B [reli]")]];
    Code sub_B871[0x16] @ 0x003871 [[comment("$80:B871 Subroutine: Implementation of L2SASM opcode $70 [reli]")]];
    Code sub_B887[0x16] @ 0x003887 [[comment("$80:B887 Subroutine: Implementation of L2SASM opcode $6F [reli]")]];
    Code sub_B89D[0x14] @ 0x00389D [[comment("$80:B89D Subroutine: Implementation of L2SASM opcode $71 [reli]")]];
    Code sub_B8B1[0xC] @ 0x0038B1 [[comment("$80:B8B1 Subroutine: Implementation of L2SASM opcode $72 [reli]")]];
    Code sub_B8BD[0xA] @ 0x0038BD [[comment("$80:B8BD Subroutine: Implementation of L2SASM opcode $4C [reli]")]];
    Code sub_B8C7[0x15] @ 0x0038C7 [[comment("$80:B8C7 Subroutine: Implementation of L2SASM opcode $4D [reli]")]];
    Code sub_B8DC[0x11] @ 0x0038DC [[comment("$80:B8DC Subroutine: Implementation of L2SASM opcode $4E [reli]")]];
    Code sub_B8ED[0x6] @ 0x0038ED [[comment("$80:B8ED Subroutine: Implementation of L2SASM opcode $4F (dummy 2-bytes instruction?) [reli]")]];
    Code sub_B8F3[0x6] @ 0x0038F3 [[comment("$80:B8F3 Subroutine: Implementation of L2SASM opcode $50 Store #$00 at $7E:1260 [reli]")]];
    Code sub_B8F9[0x7] @ 0x0038F9 [[comment("$80:B8F9 Subroutine: Implementation of L2SASM opcode $51 [reli]")]];
    Code sub_B900[0x9] @ 0x003900 [[comment("$80:B900 Subroutine: Implementation of L2SASM opcode $52 Store the next script byte at $7E:1260 [reli]")]];
    Code sub_B909[0x10] @ 0x003909 [[comment("$80:B909 Subroutine: Implementation of L2SASM opcode $53 [reli] || LDA $0BBB: party level saved before a scripted battle [iris]")]];
    Code sub_B909_2[0xF] @ 0x00391D [[comment("$80:B91D (continued from $80:B909) Subroutine: Implementation of L2SASM opcode $53 [reli] || LDA $0BBB: party level saved before a scripted battle [iris]")]];
    Code sub_B919[0x4] @ 0x003919 [[comment("$80:B919 STA.l $7FF8A4: scripted / boss battle formation (id from the script via $80:C0B7) [iris]")]];
    Code sub_B92C[0x11] @ 0x00392C [[comment("$80:B92C Subroutine: Implementation of L2SASM opcode $54 [reli]")]];
    Code sub_B93D[0x11] @ 0x00393D [[comment("$80:B93D Subroutine: Implementation of L2SASM opcode $55 [reli]")]];
    Code sub_B94E[0x7] @ 0x00394E [[comment("$80:B94E Subroutine: Implementation of L2SASM opcode $56 [reli]")]];
    Code sub_B955[0xD] @ 0x003955 [[comment("$80:B955 Subroutine: Implementation of L2SASM opcode $C5 [reli]")]];
    Code sub_B962[0x1C] @ 0x003962 [[comment("$80:B962 Subroutine: Implementation of L2SASM opcode $8A [reli]")]];
    Code sub_B97E[0x11] @ 0x00397E [[comment("$80:B97E Subroutine: [reli]")]];
    Code sub_B98F[0xE] @ 0x00398F [[comment("$80:B98F Subroutine: Implementation of L2SASM opcode $57 [reli]")]];
    Code sub_B99D[0x15] @ 0x00399D [[comment("$80:B99D Subroutine: Implementation of L2SASM opcode $76 [reli]")]];
    Code sub_B9B2 @ 0x0039B2 [[comment("$80:B9B2 Subroutine: Implementation of L2SASM opcode $58 [reli] (end unknown)")]];
    Code sub_B9DA[0x26] @ 0x0039DA [[comment("$80:B9DA Subroutine: Implementation of L2SASM opcode $59 [reli]")]];
    Code sub_BA00[0x1C] @ 0x003A00 [[comment("$80:BA00 Subroutine: Implementation of L2SASM opcode $A4 [reli]")]];
    Code sub_BA1C[0x1D] @ 0x003A1C [[comment("$80:BA1C Subroutine: Implementation of L2SASM opcode $5A [reli]")]];
    Code sub_BA39[0x1C] @ 0x003A39 [[comment("$80:BA39 Subroutine: Implementation of L2SASM opcode $5B [reli]")]];
    Data data_BA55[0x12] @ 0x003A55 [[comment("$80:BA55 Pointers to subs [reli]")]];
    Code sub_BA67[0x2] @ 0x003A67 [[comment("$80:BA67 Subroutine: [reli]")]];
    Code sub_BA69[0x2E] @ 0x003A69 [[comment("$80:BA69 Subroutine: [reli]")]];
    Code sub_BA97[0xB] @ 0x003A97 [[comment("$80:BA97 Subroutine: [reli]")]];
    Code sub_BAA2[0x27] @ 0x003AA2 [[comment("$80:BAA2 Subroutine: [reli]")]];
    Code sub_BAC9[0x24] @ 0x003AC9 [[comment("$80:BAC9 Subroutine: [reli]")]];
    Code sub_BAED[0x4] @ 0x003AED [[comment("$80:BAED Subroutine: [reli]")]];
    Code sub_BAF1[0x6E] @ 0x003AF1 [[comment("$80:BAF1 Subroutine: [reli]")]];
    Code sub_BB70[0x24] @ 0x003B70 [[comment("$80:BB70 Subroutine: [reli]")]];
    Code sub_BB94[0x57] @ 0x003B94 [[comment("$80:BB94 Subroutine: [reli]")]];
    Code sub_BBEB[0x1A] @ 0x003BEB [[comment("$80:BBEB Subroutine: Implementation of L2SASM opcode $5E [reli]")]];
    Code sub_BC05[0x6] @ 0x003C05 [[comment("$80:BC05 Subroutine: Implementation of L2SASM opcode $5F (dummy 2-bytes instruction?) [reli]")]];
    Code sub_BC0B[0xE] @ 0x003C0B [[comment("$80:BC0B Subroutine: Implementation of L2SASM opcode $60 Use to modify the SNES registers [$2100, $21FF] from the script? [reli]")]];
    Code sub_BC19[0x4] @ 0x003C19 [[comment("$80:BC19 Subroutine: Implementation of L2SASM opcode $61 [reli]")]];
    Code sub_BC1D[0x4] @ 0x003C1D [[comment("$80:BC1D Subroutine: Implementation of L2SASM opcode $62 [reli]")]];
    Code sub_BC21[0x4] @ 0x003C21 [[comment("$80:BC21 Subroutine: Implementation of L2SASM opcode $63 [reli]")]];
    Code sub_BC25[0x4] @ 0x003C25 [[comment("$80:BC25 Subroutine: Implementation of L2SASM opcode $64 [reli]")]];
    Code sub_BC29[0x4] @ 0x003C29 [[comment("$80:BC29 Subroutine: Implementation of L2SASM opcode $65 [reli]")]];
    Code sub_BC2D[0x4] @ 0x003C2D [[comment("$80:BC2D Subroutine: Implementation of L2SASM opcode $66 [reli]")]];
    Code sub_BC31[0xC] @ 0x003C31 [[comment("$80:BC31 Subroutine: Implementation of L2SASM opcode $67 [reli]")]];
    Code sub_BC3D[0x18] @ 0x003C3D [[comment("$80:BC3D Subroutine: Implementation of L2SASM opcode $68 [reli]")]];
    Code sub_BC55[0x43] @ 0x003C55 [[comment("$80:BC55 Subroutine: Implementation of L2SASM opcode $7B [reli]")]];
    Code sub_BC98[0x24] @ 0x003C98 [[comment("$80:BC98 Subroutine: [reli]")]];
    Code sub_BCBC[0x28] @ 0x003CBC [[comment("$80:BCBC Subroutine: Implementation of L2SASM opcode $69 [reli]")]];
    Code sub_BCE4[0x54] @ 0x003CE4 [[comment("$80:BCE4 Subroutine: Called by sub at $80:9C72 (L2SASM parser) $80:9EC8 (implementation of L2SASM opcode $07) [reli]")]];
    Code sub_BD38[0x34] @ 0x003D38 [[comment("$80:BD38 Subroutine: [reli]")]];
    Code sub_BD6C[0x9] @ 0x003D6C [[comment("$80:BD6C Subroutine: Implementation of L2SASM opcode $7C 2-bytes instruction. $7E:09DF (ZST $015F2) = next script byte $7C XX => Set a 'ship byte' $XX - $00 => no sub, no air - $01 => sub, no air - $02 => sub, air [reli]")]];
    Code sub_BD75[0x9] @ 0x003D75 [[comment("$80:BD75 Subroutine: Implementation of L2SASM opcode $7D 2-bytes instruction. $7E:09EE (ZST $01601) = next script byte [reli]")]];
    Code sub_BD7E[0x9] @ 0x003D7E [[comment("$80:BD7E Subroutine: Implementation of L2SASM opcode $7E 2-bytes instruction. $7E:09E0 (ZST $015F3) = next script byte $7E CC => Set a 'ship byte' $XX - $FF => ship is not on the map - $00 => ship is on the map [reli]")]];
    Code sub_BD87[0x9] @ 0x003D87 [[comment("$80:BD87 Subroutine: Implementation of L2SASM opcode $7F 2-bytes instruction. $7E:09E1 (ZST $015F4) = next script byte [reli]")]];
    Code sub_BD90[0x9] @ 0x003D90 [[comment("$80:BD90 Subroutine: Implementation of L2SASM opcode $80 2-bytes instruction. $7E:09E2 (ZST $015F5) = next script byte [reli]")]];
    Code sub_BD99[0x7] @ 0x003D99 [[comment("$80:BD99 Subroutine: Implementation of L2SASM opcode $81 [reli]")]];
    Code sub_BD99_2[0x1A] @ 0x003DA1 [[comment("$80:BDA1 (continued from $80:BD99) Subroutine: Implementation of L2SASM opcode $81 [reli]")]];
    Code sub_BDA0 @ 0x003DA0 [[comment("$80:BDA0 hooked by zero_capsule_command (can clear the owned capsule flags and $0A7F) [iris] (end unknown)")]];
    Code sub_BDBB[0xF] @ 0x003DBB [[comment("$80:BDBB Subroutine: Implementation of L2SASM opcode $82 [reli]")]];
    Code sub_BDCA[0x27] @ 0x003DCA [[comment("$80:BDCA Subroutine: Implementation of L2SASM opcode $83 [reli]")]];
    Code sub_BDF1[0x29] @ 0x003DF1 [[comment("$80:BDF1 Subroutine: Implementation of L2SASM opcode $85 [reli]")]];
    Code sub_BE1A[0x4] @ 0x003E1A [[comment("$80:BE1A Subroutine: [reli]")]];
    Code sub_BE1E[0x12] @ 0x003E1E [[comment("$80:BE1E Subroutine: After calling sub at $80:BE30, - load A with an event byte address of the event byte = #$77E + value at $56 - AND $57 [reli]")]];
    Code sub_BE30[0x15] @ 0x003E30 [[comment("$80:BE30 Subroutine: A = byyyyyxxx STA $54 Store b000yyyyy at $56 n = b00000xxx ; set bit n of $57 (all other bits = 0) [reli] || event flag helper: flag n -> byte $077E + n/8, mask bit n%8 [iris]")]];
    Data data_BE45[0x8] @ 0x003E45 [[comment("$80:BE45 $01 02 04 08 10 20 40 80 Data for sub at $80:BE30 [reli]")]];
    Code sub_BE4D[0x14] @ 0x003E4D [[comment("$80:BE4D Subroutine: [reli]")]];
    Code sub_BE61[0x14] @ 0x003E61 [[comment("$80:BE61 Subroutine: [reli]")]];
    Code sub_BE75[0x14] @ 0x003E75 [[comment("$80:BE75 Subroutine: [reli]")]];
    Code sub_BE89[0x26] @ 0x003E89 [[comment("$80:BE89 Subroutine: [reli]")]];
    Code sub_BEAF[0x59] @ 0x003EAF [[comment("$80:BEAF Subroutine: [reli]")]];
    Code sub_BF08 @ 0x003F08 [[comment("$80:BF08 Subroutine: Implementation of L2SASM opcode $5C 00/BF08: 00 BRK [reli] (end unknown)")]];
    Code sub_BF09 @ 0x003F09 [[comment("$80:BF09 Subroutine: Implementation of L2SASM opcode $5D 00/BF09: 00 BRK [reli] (end unknown)")]];
    Code sub_BF0A @ 0x003F0A [[comment("$80:BF0A Subroutine: Implementation of L2SASM opcode $11 00/BF0A: 00 BRK [reli] (end unknown)")]];
    Code sub_BF0B[0x7] @ 0x003F0B [[comment("$80:BF0B Subroutine: [reli]")]];
    Code sub_BF12[0x31] @ 0x003F12 [[comment("$80:BF12 Subroutine: [reli]")]];
    Code sub_BF43[0x2C] @ 0x003F43 [[comment("$80:BF43 Subroutine: [reli]")]];
    Code sub_BF6F[0x23] @ 0x003F6F [[comment("$80:BF6F Subroutine: [reli]")]];
    Code sub_BF92[0x18] @ 0x003F92 [[comment("$80:BF92 Subroutine: [reli]")]];
    Code sub_BFAA[0x2F] @ 0x003FAA [[comment("$80:BFAA Subroutine: [reli]")]];
    Code sub_BFD9[0xE] @ 0x003FD9 [[comment("$80:BFD9 Subroutine: [reli]")]];
    Code sub_BFE7[0x13] @ 0x003FE7 [[comment("$80:BFE7 Subroutine: [reli]")]];
    Code sub_BFFA[0x23] @ 0x003FFA [[comment("$80:BFFA Subroutine: [reli]")]];
    Code sub_C01D[0x3F] @ 0x00401D [[comment("$80:C01D Subroutine: [reli]")]];
    Code sub_C05C[0x37] @ 0x00405C [[comment("$80:C05C Subroutine: [reli]")]];
    Code sub_C093[0x24] @ 0x004093 [[comment("$80:C093 Subroutine: [reli]")]];
    Code sub_C0B7[0x19] @ 0x0040B7 [[comment("$80:C0B7 Subroutine: script-related LDA $0000,Y with $8000 =< Y =< $FFFF then INY but if Y < $8000: INC $09B9 and DB LDY #$8000 => load low A with 1 ROM byte ----- Called by: ... sub at $80:C0D0 ... [reli] || event script byte fetcher: LDA $0000,y : INY [iris]")]];
    Code sub_C0D0[0xA] @ 0x0040D0 [[comment("$80:C0D0 Subroutine: script-related A = yyxx with xx = LDA $0000,Y yy = LDA $0001,Y (see sub at $80:C0B7!) => load A with 2 ROM bytes ----- Calls sub at $80:C0B7 [reli]")]];
    Code sub_C0DA[0x12] @ 0x0040DA [[comment("$80:C0DA Subroutine: [reli]")]];
    Code sub_C0EC[0x16] @ 0x0040EC [[comment("$80:C0EC Subroutine: [reli]")]];
    Code sub_C102[0xD] @ 0x004102 [[comment("$80:C102 Subroutine: [reli]")]];
    Code sub_C10F[0xD] @ 0x00410F [[comment("$80:C10F Subroutine: [reli]")]];
    Code sub_C11C[0x12] @ 0x00411C [[comment("$80:C11C Subroutine: Reset bit 0 of [$0622, $0649] [reli]")]];
    Code sub_C12E[0x67] @ 0x00412E [[comment("$80:C12E Subroutine: [reli]")]];
    Code sub_C195[0x12] @ 0x004195 [[comment("$80:C195 Subroutine: [reli]")]];
    Code sub_C1A7[0x1C] @ 0x0041A7 [[comment("$80:C1A7 Subroutine: [reli]")]];
    Code sub_C1C3[0x1C] @ 0x0041C3 [[comment("$80:C1C3 Subroutine: [reli]")]];
    Code sub_C1DF[0x1E] @ 0x0041DF [[comment("$80:C1DF Subroutine: [reli]")]];
    Code sub_C1FD[0x1D] @ 0x0041FD [[comment("$80:C1FD Subroutine: [reli]")]];
    Code sub_C21A[0x23] @ 0x00421A [[comment("$80:C21A Subroutine: [reli]")]];
    Code sub_C23D[0x64] @ 0x00423D [[comment("$80:C23D Subroutine: [reli]")]];
    Data data_C2A1[0x64] @ 0x0042A1 [[comment("$80:C2A1 Some data [reli]")]];
    Data data_C305[0x20F] @ 0x004305 [[comment("$80:C305 Some data [reli]")]];
    Data data_C514[0x18] @ 0x004514 [[comment("$80:C514 Some data [reli]")]];
    Code sub_C52C[0x2B] @ 0x00452C [[comment("$80:C52C Subroutine: [reli]")]];
    Code sub_C557[0x17] @ 0x004557 [[comment("$80:C557 Subroutine: [reli]")]];
    Code sub_C56E[0x6F] @ 0x00456E [[comment("$80:C56E Subroutine: [reli]")]];
    Code sub_C5DD[0x40] @ 0x0045DD [[comment("$80:C5DD Subroutine: [reli]")]];
    Code sub_C61D[0x35] @ 0x00461D [[comment("$80:C61D Subroutine: [reli]")]];
    Code sub_C652[0xF2] @ 0x004652 [[comment("$80:C652 Subroutine: [reli]")]];
    Data data_C744[0x40] @ 0x004744 [[comment("$80:C744 Some data for sub at $80:C652 [reli]")]];
    Code sub_C784[0x3A] @ 0x004784 [[comment("$80:C784 Subroutine: [reli]")]];
    Data data_C7BE[0x4] @ 0x0047BE [[comment("$80:C7BE Some data for sub at $80:C784 [reli]")]];
    Code sub_C7C2[0x53] @ 0x0047C2 [[comment("$80:C7C2 Subroutine: [reli]")]];
    Data data_C815[0x2] @ 0x004815 [[comment("$80:C815 Some data for sub at $80:C7C2 [reli]")]];
    Code sub_C817[0x7] @ 0x004817 [[comment("$80:C817 Subroutine: [reli]")]];
    Code sub_C81E[0x7] @ 0x00481E [[comment("$80:C81E Subroutine: [reli]")]];
    Code sub_C825[0xB0] @ 0x004825 [[comment("$80:C825 Subroutine: (doc unsure) [reli]")]];
    Code sub_C8D5[0xEB] @ 0x0048D5 [[comment("$80:C8D5 Subroutine: (doc unsure) [reli]")]];
    Code sub_C9C0[0x54] @ 0x0049C0 [[comment("$80:C9C0 Subroutine: [reli]")]];
    Code sub_CBAE[0x78] @ 0x004BAE [[comment("$80:CBAE Subroutine: [reli]")]];
    Code sub_CC26[0xF] @ 0x004C26 [[comment("$80:CC26 Subroutine: [reli]")]];
    Code sub_CC35[0xD] @ 0x004C35 [[comment("$80:CC35 Subroutine: [reli]")]];
    Code sub_CC42[0x8] @ 0x004C42 [[comment("$80:CC42 Subroutine: [reli]")]];
    Code sub_CC4A[0x17] @ 0x004C4A [[comment("$80:CC4A Subroutine: [reli]")]];
    Code sub_CC61[0x17] @ 0x004C61 [[comment("$80:CC61 Subroutine: [reli]")]];
    Code sub_CC78[0x2F] @ 0x004C78 [[comment("$80:CC78 Subroutine: [reli]")]];
    Code sub_CCA7[0x34] @ 0x004CA7 [[comment("$80:CCA7 Subroutine: [reli]")]];
    Code sub_CCDB[0x42] @ 0x004CDB [[comment("$80:CCDB Subroutine: [reli]")]];
    Code sub_CD1D[0x6] @ 0x004D1D [[comment("$80:CD1D Subroutine: [reli]")]];
    Code sub_CD23[0xF] @ 0x004D23 [[comment("$80:CD23 Subroutine: [reli]")]];
    Code sub_CD32[0xF] @ 0x004D32 [[comment("$80:CD32 Subroutine: [reli]")]];
    Code sub_CD41[0x47] @ 0x004D41 [[comment("$80:CD41 Subroutine: [reli]")]];
    Code sub_CD88[0x3] @ 0x004D88 [[comment("$80:CD88 Subroutine: JSR $E92A [reli]")]];
    Code sub_CD8B[0x47] @ 0x004D8B [[comment("$80:CD8B Subroutine: [reli]")]];
    Code sub_CDD2[0x7] @ 0x004DD2 [[comment("$80:CDD2 Subroutine: [reli]")]];
    Code sub_CDD9[0x42] @ 0x004DD9 [[comment("$80:CDD9 Subroutine: [reli]")]];
    Code sub_CE1B[0xC] @ 0x004E1B [[comment("$80:CE1B Subroutine: [reli]")]];
    Code sub_CE27[0xC] @ 0x004E27 [[comment("$80:CE27 Subroutine: [reli]")]];
    Code sub_CE33[0x29] @ 0x004E33 [[comment("$80:CE33 Subroutine: [reli]")]];
    Code sub_CE5C[0x22] @ 0x004E5C [[comment("$80:CE5C Subroutine: [reli]")]];
    Code sub_CEA0[0x2F] @ 0x004EA0 [[comment("$80:CEA0 Subroutine: [reli]")]];
    Code sub_CECF[0xA] @ 0x004ECF [[comment("$80:CECF Subroutine: [reli]")]];
    Code sub_CED9[0x7] @ 0x004ED9 [[comment("$80:CED9 Subroutine: [reli]")]];
    Code sub_CEE0[0x7] @ 0x004EE0 [[comment("$80:CEE0 Subroutine: [reli]")]];
    Code sub_CEE7[0x7] @ 0x004EE7 [[comment("$80:CEE7 Subroutine: [reli]")]];
    Code sub_CEEE[0x7] @ 0x004EEE [[comment("$80:CEEE Subroutine: [reli]")]];
    Code sub_CF3A[0x29] @ 0x004F3A [[comment("$80:CF3A Subroutine: [reli]")]];
    Code sub_CF63[0x3A] @ 0x004F63 [[comment("$80:CF63 Subroutine: [reli]")]];
    Code sub_CF9D[0xD] @ 0x004F9D [[comment("$80:CF9D Subroutine: [reli]")]];
    Code sub_CFAA[0xD] @ 0x004FAA [[comment("$80:CFAA Subroutine: [reli]")]];
    Code sub_CFB7[0x8] @ 0x004FB7 [[comment("$80:CFB7 Subroutine: [reli]")]];
    Code sub_CFBF[0x19] @ 0x004FBF [[comment("$80:CFBF Subroutine: [reli]")]];
    Code sub_CFD8[0x12] @ 0x004FD8 [[comment("$80:CFD8 Subroutine: [reli]")]];
    Code sub_CFEA[0x12] @ 0x004FEA [[comment("$80:CFEA Subroutine: [reli]")]];
    Code sub_D01D[0x20] @ 0x00501D [[comment("$80:D01D Subroutine: [reli]")]];
    Code sub_D03D[0x14] @ 0x00503D [[comment("$80:D03D Subroutine: [reli]")]];
    Code sub_D051[0x14] @ 0x005051 [[comment("$80:D051 Subroutine: [reli]")]];
    Code sub_D065[0x12] @ 0x005065 [[comment("$80:D065 Subroutine: [reli]")]];
    Code sub_D077[0x10] @ 0x005077 [[comment("$80:D077 Subroutine: [reli]")]];
    Code sub_D087[0x25] @ 0x005087 [[comment("$80:D087 Subroutine: [reli]")]];
    Code sub_D274[0x16] @ 0x005274 [[comment("$80:D274 Subroutine: [reli]")]];
    Code sub_D28A[0x18] @ 0x00528A [[comment("$80:D28A Subroutine: [reli]")]];
    Code sub_D2A2[0x10] @ 0x0052A2 [[comment("$80:D2A2 Subroutine: [reli]")]];
    Code sub_D2BB[0xA] @ 0x0052BB [[comment("$80:D2BB Subroutine: [reli]")]];
    Code sub_D2C5[0xE] @ 0x0052C5 [[comment("$80:D2C5 Subroutine: [reli]")]];
    Code sub_D2D3[0xE] @ 0x0052D3 [[comment("$80:D2D3 Subroutine: [reli]")]];
    Code sub_D2E1[0xD] @ 0x0052E1 [[comment("$80:D2E1 Subroutine: [reli]")]];
    Code sub_D2EE[0xD] @ 0x0052EE [[comment("$80:D2EE Subroutine: [reli]")]];
    Code sub_D30D[0xC] @ 0x00530D [[comment("$80:D30D Subroutine: [reli]")]];
    Code sub_D319[0x1D] @ 0x005319 [[comment("$80:D319 Subroutine: [reli]")]];
    Code sub_D336[0x10] @ 0x005336 [[comment("$80:D336 Subroutine: [reli]")]];
    Code sub_D346[0x11] @ 0x005346 [[comment("$80:D346 Subroutine: [reli]")]];
    Code sub_D3D6[0x50] @ 0x0053D6 [[comment("$80:D3D6 Subroutine: [reli]")]];
    Code sub_D439[0x45] @ 0x005439 [[comment("$80:D439 Subroutine: [reli]")]];
    Code sub_D47E[0x1D] @ 0x00547E [[comment("$80:D47E Subroutine: [reli]")]];
    Code sub_D4B0[0x1A] @ 0x0054B0 [[comment("$80:D4B0 Subroutine: [reli]")]];
    Code sub_D4CA[0x16] @ 0x0054CA [[comment("$80:D4CA Subroutine: [reli]")]];
    Code sub_D4E0[0xC] @ 0x0054E0 [[comment("$80:D4E0 Subroutine: [reli]")]];
    Code sub_D4EC[0x2A] @ 0x0054EC [[comment("$80:D4EC Subroutine: [reli]")]];
    Code sub_D516[0x1D] @ 0x005516 [[comment("$80:D516 Subroutine: [reli]")]];
    Code sub_D533[0x50] @ 0x005533 [[comment("$80:D533 Subroutine: [reli]")]];
    Code sub_D583[0x22] @ 0x005583 [[comment("$80:D583 Subroutine: [reli]")]];
    Code sub_D5A5[0xA] @ 0x0055A5 [[comment("$80:D5A5 Subroutine: [reli]")]];
    Code sub_D5AF[0xD] @ 0x0055AF [[comment("$80:D5AF Subroutine: [reli]")]];
    Code sub_D5BC[0x28] @ 0x0055BC [[comment("$80:D5BC Subroutine: [reli]")]];
    Code sub_D5E4[0x7] @ 0x0055E4 [[comment("$80:D5E4 Subroutine: [reli]")]];
    Code sub_D5EB[0x7] @ 0x0055EB [[comment("$80:D5EB Subroutine: [reli]")]];
    Code sub_D5F2[0x94] @ 0x0055F2 [[comment("$80:D5F2 Subroutine: [reli]")]];
    Code sub_D686[0x2E] @ 0x005686 [[comment("$80:D686 Subroutine: [reli]")]];
    Code sub_D6B4[0x16] @ 0x0056B4 [[comment("$80:D6B4 Subroutine: [reli]")]];
    Code sub_D6CA @ 0x0056CA [[comment("$80:D6CA Subroutine: (doc unsure) [reli] (end unknown)")]];
    Code sub_D6E9 @ 0x0056E9 [[comment("$80:D6E9 Subroutine: [reli] (end unknown)")]];
    Code sub_D73A[0x61] @ 0x00573A [[comment("$80:D73A Subroutine: [reli]")]];
    Code sub_D79B[0x9A] @ 0x00579B [[comment("$80:D79B Subroutine: [reli]")]];
    Code sub_D835[0x14] @ 0x005835 [[comment("$80:D835 Subroutine: [reli]")]];
    Code sub_D849[0x7F] @ 0x005849 [[comment("$80:D849 Subroutine: [reli]")]];
    Code sub_D8C8[0x9] @ 0x0058C8 [[comment("$80:D8C8 Subroutine: [reli]")]];
    Code sub_D8D1[0xF] @ 0x0058D1 [[comment("$80:D8D1 Subroutine: [reli]")]];
    Code sub_D8E0[0x12] @ 0x0058E0 [[comment("$80:D8E0 Subroutine: [reli]")]];
    Code sub_D8F2[0x14] @ 0x0058F2 [[comment("$80:D8F2 Subroutine: [reli]")]];
    Code sub_D906[0x14] @ 0x005906 [[comment("$80:D906 Subroutine: [reli]")]];
    Code sub_D91A[0xA] @ 0x00591A [[comment("$80:D91A Subroutine: [reli]")]];
    Code sub_D924[0x17] @ 0x005924 [[comment("$80:D924 Subroutine: [reli]")]];
    Code sub_D93B[0xF] @ 0x00593B [[comment("$80:D93B Subroutine: [reli]")]];
    Code sub_D94A[0xF] @ 0x00594A [[comment("$80:D94A Subroutine: [reli]")]];
    Code sub_D959[0xF] @ 0x005959 [[comment("$80:D959 Subroutine: [reli]")]];
    Code sub_D968 @ 0x005968 [[comment("$80:D968 Subroutine: (doc unsure) [reli] (end unknown)")]];
    Code sub_D975 @ 0x005975 [[comment("$80:D975 Subroutine: [reli] (end unknown)")]];
    Code sub_D982 @ 0x005982 [[comment("$80:D982 Subroutine: [reli] (end unknown)")]];
    Code sub_D98E @ 0x00598E [[comment("$80:D98E Subroutine: [reli] (end unknown)")]];
    Code sub_D99D @ 0x00599D [[comment("$80:D99D Subroutine: [reli] (end unknown)")]];
    Code sub_D9AC @ 0x0059AC [[comment("$80:D9AC Subroutine: [reli] (end unknown)")]];
    Code sub_D9BB @ 0x0059BB [[comment("$80:D9BB Subroutine: [reli] (end unknown)")]];
    Code sub_D9CB @ 0x0059CB [[comment("$80:D9CB Subroutine: [reli] (end unknown)")]];
    Code sub_D9DB[0x12] @ 0x0059DB [[comment("$80:D9DB Subroutine: [reli]")]];
    Code sub_D9F0[0xC] @ 0x0059F0 [[comment("$80:D9F0 Subroutine: [reli]")]];
    Code sub_D9FC[0x4F] @ 0x0059FC [[comment("$80:D9FC Subroutine: [reli]")]];
    Code sub_DA4B @ 0x005A4B [[comment("$80:DA4B Subroutine: [reli] (end unknown)")]];
    Code sub_DA82 @ 0x005A82 [[comment("$80:DA82 Subroutine: [reli] (end unknown)")]];
    Code sub_DA98 @ 0x005A98 [[comment("$80:DA98 Subroutine: [reli] (end unknown)")]];
    Code sub_DAC9 @ 0x005AC9 [[comment("$80:DAC9 Subroutine: [reli] (end unknown)")]];
    Code sub_DAD7 @ 0x005AD7 [[comment("$80:DAD7 Subroutine: [reli] (end unknown)")]];
    Code sub_DAF2 @ 0x005AF2 [[comment("$80:DAF2 Subroutine: [reli] (end unknown)")]];
    Code sub_DB11 @ 0x005B11 [[comment("$80:DB11 Subroutine: [reli] (end unknown)")]];
    Code sub_DB1E @ 0x005B1E [[comment("$80:DB1E Subroutine: [reli] (end unknown)")]];
    Code sub_DB21 @ 0x005B21 [[comment("$80:DB21 Subroutine: [reli] (end unknown)")]];
    Code sub_DB6A @ 0x005B6A [[comment("$80:DB6A Subroutine: [reli] (end unknown)")]];
    Code sub_DB9D @ 0x005B9D [[comment("$80:DB9D Subroutine: [reli] (end unknown)")]];
    Code sub_DBCA[0x8] @ 0x005BCA [[comment("$80:DBCA Subroutine: [reli]")]];
    Code sub_DBD2[0xB] @ 0x005BD2 [[comment("$80:DBD2 Subroutine: [reli]")]];
    Code sub_DBDD[0x18] @ 0x005BDD [[comment("$80:DBDD Subroutine: [reli]")]];
    Code sub_DBF5[0x18] @ 0x005BF5 [[comment("$80:DBF5 Subroutine: [reli]")]];
    Code sub_DC0D[0x9F] @ 0x005C0D [[comment("$80:DC0D Subroutine: [reli]")]];
    Code sub_DCAC[0x5] @ 0x005CAC [[comment("$80:DCAC Subroutine: [reli]")]];
    Code sub_DCB1[0x5] @ 0x005CB1 [[comment("$80:DCB1 Subroutine: [reli]")]];
    Code sub_DCB6[0x5] @ 0x005CB6 [[comment("$80:DCB6 Subroutine: [reli]")]];
    Code sub_DCBB[0x5] @ 0x005CBB [[comment("$80:DCBB Subroutine: [reli]")]];
    Code sub_DD86[0x9] @ 0x005D86 [[comment("$80:DD86 Subroutine: [reli]")]];
    Code sub_DD8F[0x26] @ 0x005D8F [[comment("$80:DD8F Subroutine: [reli]")]];
    Code sub_DDB5[0x17] @ 0x005DB5 [[comment("$80:DDB5 Subroutine: [reli]")]];
    Code sub_DDCC[0x17] @ 0x005DCC [[comment("$80:DDCC Subroutine: [reli]")]];
    Code sub_DDE3[0xF] @ 0x005DE3 [[comment("$80:DDE3 Subroutine: [reli]")]];
    Code sub_DDF2[0x8] @ 0x005DF2 [[comment("$80:DDF2 Subroutine: [reli]")]];
    Code sub_DDFA @ 0x005DFA [[comment("$80:DDFA Subroutine: [reli] (end unknown)")]];
    Code sub_DE02[0x8] @ 0x005E02 [[comment("$80:DE02 Subroutine: [reli]")]];
    Code sub_DE0A[0x7] @ 0x005E0A [[comment("$80:DE0A Subroutine: [reli]")]];
    Code sub_DE11[0x21] @ 0x005E11 [[comment("$80:DE11 Subroutine: [reli]")]];
    Code sub_DE32[0x20] @ 0x005E32 [[comment("$80:DE32 Subroutine: [reli]")]];
    Code sub_DE52[0x3A] @ 0x005E52 [[comment("$80:DE52 Subroutine: [reli]")]];
    Code sub_DEAA[0x7] @ 0x005EAA [[comment("$80:DEAA Subroutine: [reli]")]];
    Code sub_DEB1[0x7] @ 0x005EB1 [[comment("$80:DEB1 Subroutine: [reli]")]];
    Code sub_DEB8[0x7] @ 0x005EB8 [[comment("$80:DEB8 Subroutine: [reli]")]];
    Code sub_DEBF[0x14] @ 0x005EBF [[comment("$80:DEBF Subroutine: [reli]")]];
    Code sub_DED3[0x7] @ 0x005ED3 [[comment("$80:DED3 Subroutine: [reli]")]];
    Code sub_DEDA[0x7] @ 0x005EDA [[comment("$80:DEDA Subroutine: [reli]")]];
    Code sub_DEE1[0x7] @ 0x005EE1 [[comment("$80:DEE1 Subroutine: [reli]")]];
    Code sub_DEE8[0x7] @ 0x005EE8 [[comment("$80:DEE8 Subroutine: [reli]")]];
    Code sub_DEEF[0x2A] @ 0x005EEF [[comment("$80:DEEF Subroutine: [reli]")]];
    Code sub_DF40[0x29] @ 0x005F40 [[comment("$80:DF40 Subroutine: [reli]")]];
    Code sub_DF69[0x7] @ 0x005F69 [[comment("$80:DF69 Subroutine: [reli]")]];
    Code sub_DF70[0x7] @ 0x005F70 [[comment("$80:DF70 Subroutine: [reli]")]];
    Code sub_DF77[0x7] @ 0x005F77 [[comment("$80:DF77 Subroutine: [reli]")]];
    Code sub_DF7E[0x7] @ 0x005F7E [[comment("$80:DF7E Subroutine: [reli]")]];
    Code sub_E038[0x40] @ 0x006038 [[comment("$80:E038 Subroutine: [reli]")]];
    Code sub_E078[0x25] @ 0x006078 [[comment("$80:E078 Subroutine: [reli]")]];
    Code sub_E09D[0x30] @ 0x00609D [[comment("$80:E09D Subroutine: [reli]")]];
    Code sub_E0CD[0x6] @ 0x0060CD [[comment("$80:E0CD Subroutine: [reli]")]];
    Code sub_E0D3[0x9] @ 0x0060D3 [[comment("$80:E0D3 Subroutine: [reli]")]];
    Code sub_E105[0x2D] @ 0x006105 [[comment("$80:E105 Subroutine: [reli]")]];
    Code sub_E132[0x15] @ 0x006132 [[comment("$80:E132 Subroutine: [reli]")]];
    Code sub_E15A[0x1D] @ 0x00615A [[comment("$80:E15A Subroutine: [reli]")]];
    Code sub_E177[0xA] @ 0x006177 [[comment("$80:E177 Subroutine: [reli]")]];
    Code sub_E181[0xA] @ 0x006181 [[comment("$80:E181 Subroutine: [reli]")]];
    Code sub_E18B[0xD] @ 0x00618B [[comment("$80:E18B Subroutine: [reli]")]];
    Code sub_E198[0xA] @ 0x006198 [[comment("$80:E198 Subroutine: [reli]")]];
    Code sub_E1A2[0xA] @ 0x0061A2 [[comment("$80:E1A2 Subroutine: [reli]")]];
    Code sub_E1AC[0xD] @ 0x0061AC [[comment("$80:E1AC Subroutine: [reli]")]];
    Code sub_E1B9[0x6] @ 0x0061B9 [[comment("$80:E1B9 Subroutine: [reli]")]];
    Code sub_E1BF[0x6] @ 0x0061BF [[comment("$80:E1BF Subroutine: [reli]")]];
    Code sub_E1C5[0x9] @ 0x0061C5 [[comment("$80:E1C5 Subroutine: [reli]")]];
    Code sub_E1CE[0x20] @ 0x0061CE [[comment("$80:E1CE Subroutine: [reli]")]];
    Code sub_E1EE[0x6] @ 0x0061EE [[comment("$80:E1EE Subroutine: [reli]")]];
    Code sub_E1F4[0x6] @ 0x0061F4 [[comment("$80:E1F4 Subroutine: [reli]")]];
    Code sub_E1FA[0x9] @ 0x0061FA [[comment("$80:E1FA Subroutine: [reli]")]];
    Code sub_E203[0x74] @ 0x006203 [[comment("$80:E203 Subroutine: [reli]")]];
    Code sub_E277[0x6] @ 0x006277 [[comment("$80:E277 Subroutine: [reli]")]];
    Code sub_E27D[0x6] @ 0x00627D [[comment("$80:E27D Subroutine: [reli]")]];
    Code sub_E283[0x9] @ 0x006283 [[comment("$80:E283 Subroutine: [reli]")]];
    Code sub_E28C[0x61] @ 0x00628C [[comment("$80:E28C Subroutine: [reli]")]];
    Code sub_E2ED[0x57] @ 0x0062ED [[comment("$80:E2ED Subroutine: [reli]")]];
    Code sub_E344[0xA] @ 0x006344 [[comment("$80:E344 Subroutine: [reli]")]];
    Code sub_E34E[0xA] @ 0x00634E [[comment("$80:E34E Subroutine: [reli]")]];
    Code sub_E358[0xD] @ 0x006358 [[comment("$80:E358 Subroutine: [reli]")]];
    Code sub_E365[0x3B] @ 0x006365 [[comment("$80:E365 Subroutine: [reli]")]];
    Code sub_E3A0[0x39] @ 0x0063A0 [[comment("$80:E3A0 Subroutine: [reli]")]];
    Code sub_E421[0x37] @ 0x006421 [[comment("$80:E421 Subroutine: [reli]")]];
    Code sub_E458[0x49] @ 0x006458 [[comment("$80:E458 Subroutine: [reli]")]];
    Code sub_E4A1[0xE] @ 0x0064A1 [[comment("$80:E4A1 Subroutine: [reli]")]];
    Code sub_E4D8 @ 0x0064D8 [[comment("$80:E4D8 Subroutine: [reli] (end unknown)")]];
    Code sub_E4EB[0xE] @ 0x0064EB [[comment("$80:E4EB Subroutine: [reli]")]];
    Code sub_E50B[0x1F] @ 0x00650B [[comment("$80:E50B Subroutine: [reli]")]];
    Code sub_E52A[0xE] @ 0x00652A [[comment("$80:E52A Subroutine: [reli]")]];
    Code sub_E538[0x1C] @ 0x006538 [[comment("$80:E538 Subroutine: [reli]")]];
    Code sub_E554[0x7] @ 0x006554 [[comment("$80:E554 Subroutine: [reli]")]];
    Code sub_E55B[0xB] @ 0x00655B [[comment("$80:E55B Subroutine: [reli]")]];
    Code sub_E566[0x38] @ 0x006566 [[comment("$80:E566 Subroutine: *might* be related to puzzles [reli]")]];
    Data data_E59E[0x184] @ 0x00659E [[comment("$80:E59E Pointers to subs (see sub at $80:E566) [reli]")]];
    Code sub_E722 @ 0x006722 [[comment("$80:E722 Subroutine: [reli] (end unknown)")]];
    Code sub_E78D[0x52] @ 0x00678D [[comment("$80:E78D Subroutine: [reli]")]];
    Code sub_E92A[0x73] @ 0x00692A [[comment("$80:E92A Subroutine: [reli]")]];
    Code sub_E99D @ 0x00699D [[comment("$80:E99D Subroutine: [reli] (end unknown)")]];
    Code sub_EC78[0x20] @ 0x006C78 [[comment("$80:EC78 Subroutine: [reli]")]];
    Code sub_EC98[0x5A] @ 0x006C98 [[comment("$80:EC98 Subroutine: [reli]")]];
    Code sub_ECF2[0xC] @ 0x006CF2 [[comment("$80:ECF2 Subroutine: [reli]")]];
    Code sub_ECFE[0x10] @ 0x006CFE [[comment("$80:ECFE Subroutine: [reli]")]];
    Code sub_ED0E[0x8E] @ 0x006D0E [[comment("$80:ED0E Subroutine: [reli]")]];
    Code sub_ED9C[0x14F] @ 0x006D9C [[comment("$80:ED9C Subroutine: [reli]")]];
    Code sub_EEEB[0x44] @ 0x006EEB [[comment("$80:EEEB Subroutine: [reli]")]];
    Code sub_EF2F[0x5F] @ 0x006F2F [[comment("$80:EF2F Subroutine: [reli]")]];
    Code sub_EF8E[0x365] @ 0x006F8E [[comment("$80:EF8E Subroutine: [reli]")]];
    Code sub_F2F3[0x45] @ 0x0072F3 [[comment("$80:F2F3 Subroutine: [reli]")]];
    Code sub_F338[0x23] @ 0x007338 [[comment("$80:F338 Subroutine: [reli]")]];
    Code sub_F35B[0x25] @ 0x00735B [[comment("$80:F35B Subroutine: ... RTI ? (doc unsure) [reli]")]];
    Code sub_F3F1[0x19] @ 0x0073F1 [[comment("$80:F3F1 Subroutine: [reli]")]];
    Code sub_F40A[0x20] @ 0x00740A [[comment("$80:F40A Subroutine: [reli]")]];
    Data data_F42A[0x50] @ 0x00742A [[comment("$80:F42A Data [reli]")]];
    Code sub_F47A[0xD] @ 0x00747A [[comment("$80:F47A Subroutine: (doc unsure) [reli]")]];
    Code sub_F6AA[0x1C] @ 0x0076AA [[comment("$80:F6AA Subroutine: [reli]")]];
    Code sub_F6C6[0x6E] @ 0x0076C6 [[comment("$80:F6C6 Subroutine: [reli]")]];
    Code sub_F734[0xE8] @ 0x007734 [[comment("$80:F734 Subroutine: [reli]")]];
    Code sub_F81C[0x5] @ 0x00781C [[comment("$80:F81C Subroutine: [reli]")]];
    Code sub_F821 @ 0x007821 [[comment("$80:F821 Subroutine: [reli] (end unknown)")]];
    Code sub_F9D0 @ 0x0079D0 [[comment("$80:F9D0 Subroutine: [reli] (end unknown)")]];
    Code sub_FAC3 @ 0x007AC3 [[comment("$80:FAC3 Subroutine: [reli] (end unknown)")]];
    Code sub_FBCE[0x4C] @ 0x007BCE [[comment("$80:FBCE Subroutine: [reli]")]];
    Free free_FC1A[0x390] @ 0x007C1A [[comment("$80:FC1A Free space [reli]")]];
};
Bank80Map bank_80 @ 0x000000 [[comment("bank $80: file 0x000000-0x007FFF")]];

struct Bank81Map {
    Code sub_8072 @ 0x008072 [[comment("$81:8072 copies the party: LDA $0A7A : STA $153C : LDX #3 : LDA $0A7B,X : STA $153D,X ... [iris] (end unknown)")]];
    Code sub_8351[0x4E] @ 0x008351 [[comment("$81:8351 Subroutine: [reli]")]];
    Code sub_839F @ 0x00839F [[comment("$81:839F Subroutine: Ancient Cave related (enemies) [doc's file column says 0x00849F (copy error); SNES column used] [reli] (end unknown)")]];
    Code sub_851E @ 0x00851E [[comment("$81:851E Subroutine: Enenmy related [reli] (end unknown)")]];
    Code sub_8959 @ 0x008959 [[comment("$81:8959 AP hook: poison death fix | JSL PoisonDeathFix ; overwrites JSL $859DD4 [ap] (end unknown)")]];
    Code sub_A7F5 @ 0x00A7F5 [[comment("$81:A7F5 battle turn start: actor $7F:F44E == $10 runs the capsule AI via JSL $81:B1A3 [iris] (end unknown)")]];
    Code sub_A80E @ 0x00A80E [[comment("$81:A80E capsule AI call (hooked by capsule_tag) [iris] (end unknown)")]];
    Code sub_A832 @ 0x00A832 [[comment("$81:A832 Subroutine: Called by: sub at $85:B53D [reli] (end unknown)")]];
    Code sub_A85C @ 0x00A85C [[comment("$81:A85C battle action dispatcher: JMP ($A867,X) on $7F:F454 & $1F [iris] (end unknown)")]];
    Code sub_A8A7 @ 0x00A8A7 [[comment("$81:A8A7 Subroutine: RTL $00 $10 $1A $1F [reli] (end unknown)")]];
    Code sub_A8A8 @ 0x00A8A8 [[comment("$81:A8A8 Subroutine: $01 $11 [reli] (end unknown)")]];
    Code sub_A968 @ 0x00A968 [[comment("$81:A968 Subroutine: $02 [reli] (end unknown)")]];
    Code sub_A977 @ 0x00A977 [[comment("$81:A977 Subroutine: $12 [reli] (end unknown)")]];
    Code sub_AA1B @ 0x00AA1B [[comment("$81:AA1B Subroutine: $03 [reli] (end unknown)")]];
    Code sub_AA2E @ 0x00AA2E [[comment("$81:AA2E Subroutine: $13 [reli] (end unknown)")]];
    Code sub_AAD0 @ 0x00AAD0 [[comment("$81:AAD0 Subroutine: $04 $14 [reli] (end unknown)")]];
    Code sub_AB07 @ 0x00AB07 [[comment("$81:AB07 Subroutine: $05 $0A $15 [reli] (end unknown)")]];
    Code sub_AB0C @ 0x00AB0C [[comment("$81:AB0C Subroutine: $08 $18 [reli] (end unknown)")]];
    Code sub_AB94 @ 0x00AB94 [[comment("$81:AB94 Subroutine: $06 $16 [reli] (end unknown)")]];
    Code sub_ABE5 @ 0x00ABE5 [[comment("$81:ABE5 battle escape (hooked by capsule_tag) [iris] (end unknown)")]];
    Code sub_AC72 @ 0x00AC72 [[comment("$81:AC72 Subroutine: $07 $17 [reli] (end unknown)")]];
    Code sub_AD3B[0x16] @ 0x00AD3B [[comment("$81:AD3B Subroutine: $0B $1B [reli]")]];
    Code sub_AD3B_2[0x3A] @ 0x00AD52 [[comment("$81:AD52 (continued from $81:AD3B) Subroutine: $0B $1B [reli]")]];
    Code sub_AD51 @ 0x00AD51 [[comment("$81:AD51 reads a CapAttack record through [$0E] with the bank fixed to $97 [iris] (end unknown)")]];
    Code sub_AD8C @ 0x00AD8C [[comment("$81:AD8C BRK: reached when a non-capsule uses action $0B (L2BASM 3E) [iris]")]];
    Code sub_AD8D @ 0x00AD8D [[comment("$81:AD8D Subroutine: $0C $1C [reli] (end unknown)")]];
    Code sub_AE0F @ 0x00AE0F [[comment("$81:AE0F Subroutine: $0D $1D [reli] (end unknown)")]];
    Code sub_AEE1 @ 0x00AEE1 [[comment("$81:AEE1 Subroutine: $0E $1E [reli] (end unknown)")]];
    Code sub_AF37[0x43] @ 0x00AF37 [[comment("$81:AF37 Subroutine: $0F [reli]")]];
    Code sub_AF7A[0xF] @ 0x00AF7A [[comment("$81:AF7A Subroutine: $09 [reli]")]];
    Code sub_AF89[0x3B] @ 0x00AF89 [[comment("$81:AF89 Subroutine: $19 [reli]")]];
    Code sub_B1A3 @ 0x00B1A3 [[comment("$81:B1A3 capsule AI entry (runs the capsule attack script) [iris] (end unknown)")]];
    Code sub_B2B5[0x26] @ 0x00B2B5 [[comment("$81:B2B5 Subroutine: [reli]")]];
    Code sub_B2DB[0x2D] @ 0x00B2DB [[comment("$81:B2DB Subroutine: [reli]")]];
    Code sub_BCCC[0x7B] @ 0x00BCCC [[comment("$81:BCCC Subroutine: [reli]")]];
    Code sub_DADD @ 0x00DADD [[comment("$81:DADD AP hook: TODO: Allow as optional patch. allow inactive characters to gain exp | DB=$81, x=0, m=1 | NOP ; overwrites BNE $81DAE2 : JMP $DBED [ap] (end unknown)")]];
    Code sub_DAE9 @ 0x00DAE9 [[comment("$81:DAE9 AP hook: isolate exp distribution into a subroutine, to be reused for both active party members and inactive characters | NOP #2 ; overwrites JMP $DBBD [ap] (end unknown)")]];
    Data data_DB3D @ 0x00DB3D [[comment("$81:DB3D (no description) [reli] (end unknown)")]];
    Code sub_DB42 @ 0x00DB42 [[comment("$81:DB42 AP hook: NOP #2 ; overwrites JMP $DBBD [ap] (end unknown)")]];
    Code sub_DD11 @ 0x00DD11 [[comment("$81:DD11 AP hook: DB=$81, x=0, m=1 | JSL HandleInactiveExp ; overwrites LDA $0A8A : CLC [ap] (end unknown)")]];
    Data data_F1E4 @ 0x00F1E4 [[comment("$81:F1E4 (no description) [reli] (end unknown)")]];
    Code sub_F2E3 @ 0x00F2E3 [[comment("$81:F2E3 AP hook: equipment text fix | DB=$9E, x=0, m=1 | NOP #2 ; overwrites BPL $81F2D6 [ap] (end unknown)")]];
    Code sub_F446[0x18] @ 0x00F446 [[comment("$81:F446 Subroutine: $7E:0A0B = spell number -> $7E:0A0D = 2 lower bytes of spell data address [reli] || spell number $0A0B -> record address: LDA $95FA5B,X : ADC #$FA5B [iris]")]];
    Code sub_F46B @ 0x00F46B [[comment("$81:F46B IP effect accessor: LDA $95F1EF,X : CLC : ADC #$F1EF [iris] (end unknown)")]];
    Code sub_F476[0xB] @ 0x00F476 [[comment("$81:F476 CapAttack index -> address: ASL : TAX : LDA $97F63B,X : CLC : ADC #$F63B : RTL [iris]")]];
    Code sub_F4D5[0x14] @ 0x00F4D5 [[comment("$81:F4D5 Subroutine: Push CPU registers, call sub at $81:F4ED, pull registers. Called by: sub at $80:A4CB (?) sub at $81:ED8E (?) ... [reli]")]];
    Code sub_F4E9[0x4] @ 0x00F4E9 [[comment("$81:F4E9 Subroutine: 81/F4E9: 20 ED F4 JSR $F4ED [$81:F4ED] 81/F4EC: 6B RTL [reli]")]];
    Code sub_F4ED[0x8A] @ 0x00F4ED [[comment("$81:F4ED Subroutine: Calculate stats (from base stats) (for characters, Capsule Monsters and enemies). [reli]")]];
    Code sub_F577[0x24] @ 0x00F577 [[comment("$81:F577 Subroutine: [reli]")]];
    Code sub_F723[0x2C] @ 0x00F723 [[comment("$81:F723 Subroutine: [reli]")]];
    Code sub_F74F[0x3A] @ 0x00F74F [[comment("$81:F74F Subroutine: [reli]")]];
    Code sub_F789[0x4] @ 0x00F789 [[comment("$81:F789 Subroutine: [reli]")]];
    Code sub_F78D[0x30] @ 0x00F78D [[comment("$81:F78D Subroutine: [reli]")]];
    Code sub_F7BD[0xD] @ 0x00F7BD [[comment("$81:F7BD Subroutine: Start: X = character number ($00 -> $06) End: X = pointer to character data in the RAM (bank $7E) (from [$85:9EBA, $85:9EC7]) [reli]")]];
    Code sub_F7CA[0x23] @ 0x00F7CA [[comment("$81:F7CA Subroutine: [reli]")]];
    Code sub_F7ED[0x92] @ 0x00F7ED [[comment("$81:F7ED Subroutine: Involved in the levelling up process? [reli]")]];
    Code sub_F87F[0xFA] @ 0x00F87F [[comment("$81:F87F Subroutine: Involved in the levelling up process: Calculate the min stats of a character at a given level. Before: $09FA = character number ($00 -> $06) $09FE = level value After: [reli]")]];
    Code sub_F979[0x70] @ 0x00F979 [[comment("$81:F979 Subroutine: Involved in the levelling up process [reli]")]];
    Code sub_F9E9[0xE0] @ 0x00F9E9 [[comment("$81:F9E9 Subroutine: [reli]")]];
    Code sub_FAC9[0x2C] @ 0x00FAC9 [[comment("$81:FAC9 Subroutine: [reli] || runs a capsule attack's battle script [iris]")]];
    Code sub_FAF5[0x25] @ 0x00FAF5 [[comment("$81:FAF5 Subroutine: [reli]")]];
    Code sub_FB1A[0x3B] @ 0x00FB1A [[comment("$81:FB1A Subroutine: Monster-related sub: parse Gift Bytes Called by sub at $85:D0CD [reli]")]];
    Code sub_FB1A_2[0x23] @ 0x00FB56 [[comment("$81:FB56 (continued from $81:FB1A) Subroutine: Monster-related sub: parse Gift Bytes Called by sub at $85:D0CD [reli]")]];
    Code sub_FB55 @ 0x00FB55 [[comment("$81:FB55 item-drop roll: CMP $09FB (Game Genie ALWAYS_DROP_33 breaks this into an endless loop) [iris] (end unknown)")]];
    Code sub_FB79[0x15] @ 0x00FB79 [[comment("$81:FB79 Subroutine: A = monster number -> A = monster data byte $0E (value: $32 or $36) [reli]")]];
    Code sub_FB8E[0x14] @ 0x00FB8E [[comment("$81:FB8E Subroutine: Before: low A = enemy battle sprite number After: A = (data bytes for enemy battle sprite from ($97:CA64)) AND (#$1F1F) low A = corresponding enemy battle sprite number high A = corresponding enemy battle sprite palette number [reli]")]];
    Code sub_FBA2[0x24] @ 0x00FBA2 [[comment("$81:FBA2 Subroutine: [reli]")]];
    Code sub_FBC6[0x15] @ 0x00FBC6 [[comment("$81:FBC6 Subroutine: Before: low A = enemy number After: low A = corresponding enemy battle sprite number high A = corresponding enemy battle sprite palette number [reli]")]];
    Code sub_FBDB[0x30] @ 0x00FBDB [[comment("$81:FBDB Subroutine: Load Monster number from $09FA and store EXP at [09FC, 09FD] GOLD at [09FE, 09FF] [reli]")]];
    Code sub_FC0B[0xD7] @ 0x00FC0B [[comment("$81:FC0B Subroutine: Load Monster data (stats) from the ROM and store it in the RAM [reli]")]];
    Code sub_FCE2[0x1E] @ 0x00FCE2 [[comment("$81:FCE2 Subroutine: A = monster number -> X = monster compendium entry start offset Called by: sub at $81:B1D4 [reli]")]];
    Code sub_FD00[0x4] @ 0x00FD00 [[comment("$81:FD00 Subroutine: Just a lil'broken subroutine... Doesn't *SEEM* to have any use. Called by: / [reli]")]];
    Free free_FD04[0x2FC] @ 0x00FD04 [[comment("$81:FD04 Free space [reli]")]];
};
Bank81Map bank_81 @ 0x008000 [[comment("bank $81: file 0x008000-0x00FFFF")]];

struct Bank82Map {
    Code sub_85EA @ 0x0105EA [[comment("$82:85EA AP hook: mark bought items as sold out | DB=$83, x=0, m=0 | JSL SoldOut ; overwrites LDA [$FC],Y : AND #$01FF [ap] (end unknown)")]];
    Code sub_AE6F @ 0x012E6F [[comment("$82:AE6F AP hook: use items | DB=$83, x=0, m=1 | JSL SpecialItemUse ; overwrites JSL $81EFDF [ap] (end unknown)")]];
    Code sub_BF44 @ 0x013F44 [[comment("$82:BF44 AP hook: music menu fix | DB=$83, x=0, m=1 | BNE $12 ; overwrites BNE $06 [ap] (end unknown)")]];
    Code sub_C213 @ 0x014213 [[comment("$82:C213 capsule master select (patched by capsule_master_select) [iris] (end unknown)")]];
    Code sub_C261 @ 0x014261 [[comment("$82:C261 RTL: build party member 7 (the capsule) when $0A7F == 7 [iris] (end unknown)")]];
    Code sub_C2FD @ 0x0142FD [[comment("$82:C2FD RTL: capsule reset (levels 1, EXP 0, form 1, rebuild) [iris] (end unknown)")]];
    Code sub_C313 @ 0x014313 [[comment("$82:C313 AP hook: TODO: remove this section, not used for Overworld set capsule monster starting xp | DB=$84, x=0, m=1 | JSL CapsuleStartingXp ; overwrites LDX.w #$0000 : LDA.b #$00 : STA $7FF1AA,X : INX : CPX.w #$0015 : BNE $82C318 [ap] (end unknown)")]];
    Code sub_C352 @ 0x014352 [[comment("$82:C352 RTL: set all 7 owned capsule flags to A, species 0 form 1, rebuild (special new-game start) [iris] (end unknown)")]];
    Code sub_C36A @ 0x01436A [[comment("$82:C36A AP hook: TODO: remove this section, not used for Overworld set starting capsule monster | DB=$83, x=0, m=1 | JSL StartingCapsule ; overwrites STZ $11A3 : LDA.b #$01 [ap] (end unknown)")]];
    Code sub_C37B @ 0x01437B [[comment("$82:C37B RTS: clears $11A5 and $11C2-$11D5 [iris] (end unknown)")]];
    Code sub_C38B[0x26] @ 0x01438B [[comment("$82:C38B Subroutine: Related to CM? [reli] || RTS: capsule record lookup $97:DCB8 + table[species*5 + form-1] -> $09C4 [iris]")]];
    Code sub_C3D3 @ 0x0143D3 [[comment("$82:C3D3 RTS: scratch species, species*3, species*5 -> $09D9/$09DB/$09DD [iris] (end unknown)")]];
    Code sub_C3F8 @ 0x0143F8 [[comment("$82:C3F8 RTS: load member 7 name, level, EXP from the per-species tables [iris] (end unknown)")]];
    Code sub_C443 @ 0x014443 [[comment("$82:C443 RTS: save member 7 level, EXP, name back to the per-species tables [iris] (end unknown)")]];
    Code sub_C515 @ 0x014515 [[comment("$82:C515 RTL: per owned species, $11A6+s = table $8E:E485 [iris] (end unknown)")]];
    Code sub_C554[0x6] @ 0x014554 [[comment("$82:C554 Subroutine: Related to data at $95:FF16 [reli]")]];
    Code sub_C554_2[0x4] @ 0x01455B [[comment("$82:C55B (continued from $82:C554) Subroutine: Related to data at $95:FF16 [reli]")]];
    Code sub_C554_3[0x12] @ 0x014560 [[comment("$82:C560 (continued from $82:C554) Subroutine: Related to data at $95:FF16 [reli]")]];
    Code sub_C554_4[0x4] @ 0x014573 [[comment("$82:C573 (continued from $82:C554) Subroutine: Related to data at $95:FF16 [reli]")]];
    Code sub_C55A @ 0x01455A [[comment("$82:C55A AP hook: relocate capsule cravings table | LDA $D09200,X ; overwrites LDA $95FF16,X [ap] (end unknown)")]];
    Code sub_C55F @ 0x01455F [[comment("$82:C55F AP hook: LDA $D09202,X ; overwrites LDA $95FF18,X [ap] (end unknown)")]];
    Code sub_C572 @ 0x014572 [[comment("$82:C572 AP hook: LDA $D09200,X ; overwrites LDA $95FF16,X [ap] (end unknown)")]];
    Code sub_CB10 @ 0x014B10 [[comment("$82:CB10 capsule feeding (hooked by capsule_feeding_bonus) [iris] (end unknown)")]];
    Code sub_CE23 @ 0x014E23 [[comment("$82:CE23 RTS: member 7 EXP = what its level needs [iris] (end unknown)")]];
    Code sub_CE52 @ 0x014E52 [[comment("$82:CE52 computes the EXP for a level into $1141-$1143 [iris] (end unknown)")]];
    Code sub_D270 @ 0x015270 [[comment("$82:D270 capsule stats (called by $82:C261) [iris] (end unknown)")]];
    Code sub_D283[0x99] @ 0x015283 [[comment("$82:D283 Subroutine: Related to CM level up? [reli]")]];
    Code sub_D31C[0x5C] @ 0x01531C [[comment("$82:D31C Subroutine: Related to CM level up? [reli]")]];
    Code sub_DF50 @ 0x015F50 [[comment("$82:DF50 AP hook: shop item select | DB=$83, x=0, m=1 | JML ShopItemSelected ; overwrites JSR $8B08 : CMP.b #$01 [ap] (end unknown)")]];
    Code sub_E084 @ 0x016084 [[comment("$82:E084 AP hook: track bought shop items | DB=$83, x=0, m=1 | JSL ShopBuy ; overwrites LDA.b #$05 : LDX.w #$0007 [ap] (end unknown)")]];
    Code sub_E10E @ 0x01610E [[comment("$82:E10E AP hook: DB=$83, x=0, m=1 | JSL ShopEquip ; overwrites SEP #$10 : LDX $14DC [ap] (end unknown)")]];
    Code sub_E7AA @ 0x0167AA [[comment("$82:E7AA RTL: capsule joins (event opcode 81 XX; species in DP $31): owned flag, level from $8E:E4C4, naming screen [iris] (end unknown)")]];
    Code sub_E7DB @ 0x0167DB [[comment("$82:E7DB tail of the capsule join (EXP, save, TRB $0B50 #$80); start_capsule enters here [iris] (end unknown)")]];
    Code sub_E80C @ 0x01680C [[comment("$82:E80C add item to the inventory: item $09CF, quantity $09CD (through DBR) [iris] (end unknown)")]];
    Code sub_E8B2 @ 0x0168B2 [[comment("$82:E8B2 capsule naming screen [iris] (end unknown)")]];
    Code sub_EAD5 @ 0x016AD5 [[comment("$82:EAD5 AP hook: restore receiving counters when loading game | DB=$83, x=0, m=1 | JSL LoadRX ; overwrites JSL $809099 [ap] (end unknown)")]];
    Code sub_EB61 @ 0x016B61 [[comment("$82:EB61 AP hook: store receiving counters when saving game | DB=$8A, x=0, m=1 | JSL SaveRX ; overwrites JSL $8090C9 [ap] (end unknown)")]];
    Code sub_FB1F[0x32] @ 0x017B1F [[comment("$82:FB1F Subroutine: Related to the Inventory. [reli]")]];
    Code sub_FB51[0x43] @ 0x017B51 [[comment("$82:FB51 Subroutine: Called by sub at $82:FB1F [reli]")]];
    Code sub_FB94[0x13] @ 0x017B94 [[comment("$82:FB94 Subroutine: If there's a free item slot (#$0000) in the inventory ([$7E:0A8D, $7E:0B4C]): Clear the Carry flag Else: Set the Carry flag [reli]")]];
    Code sub_FBA7 @ 0x017BA7 [[comment("$82:FBA7 Subroutine: [reli] (end unknown)")]];
    Code sub_FD3D @ 0x017D3D [[comment("$82:FD3D learn spell: spell $0A0B, character in A [iris] (end unknown)")]];
    Free free_FFB7[0x49] @ 0x017FB7 [[comment("$82:FFB7 Free space [reli]")]];
};
Bank82Map bank_82 @ 0x010000 [[comment("bank $82: file 0x010000-0x017FFF")]];

struct Bank83Map {
    Code sub_83EB @ 0x0183EB [[comment("$83:83EB force battle: JSL after filling $7F:F8A3/$7F:F8A4 [iris] (end unknown)")]];
    Code sub_845B[0x86] @ 0x01845B [[comment("$83:845B Subroutine: (doc unsure) [reli]")]];
    Code sub_8E4C @ 0x018E4C [[comment("$83:8E4C Subroutine: See L2SASM opcode $40 [reli] (end unknown)")]];
    Code sub_900C[0x7] @ 0x01900C [[comment("$83:900C Subroutine: [reli]")]];
    Code sub_9013[0x5] @ 0x019013 [[comment("$83:9013 Subroutine: Ancient Cave related (probably the main AC sub) (doc unsure) [reli]")]];
    Code sub_9013_2[0xB0] @ 0x019019 [[comment("$83:9019 (continued from $83:9013) Subroutine: Ancient Cave related (probably the main AC sub) (doc unsure) [reli]")]];
    Code sub_9013_3[0x4A] @ 0x0190CA [[comment("$83:90CA (continued from $83:9013) Subroutine: Ancient Cave related (probably the main AC sub) (doc unsure) [reli]")]];
    Code sub_9013_4[0x61] @ 0x019115 [[comment("$83:9115 (continued from $83:9013) Subroutine: Ancient Cave related (probably the main AC sub) (doc unsure) [reli]")]];
    Code sub_9013_5[0x6] @ 0x019177 [[comment("$83:9177 (continued from $83:9013) Subroutine: Ancient Cave related (probably the main AC sub) (doc unsure) [reli]")]];
    Code sub_9013_6[0x28] @ 0x01917E [[comment("$83:917E (continued from $83:9013) Subroutine: Ancient Cave related (probably the main AC sub) (doc unsure) [reli]")]];
    Code sub_9013_7[0x42] @ 0x0191A7 [[comment("$83:91A7 (continued from $83:9013) Subroutine: Ancient Cave related (probably the main AC sub) (doc unsure) [reli]")]];
    Code sub_9013_8[0x269] @ 0x0191EA [[comment("$83:91EA (continued from $83:9013) Subroutine: Ancient Cave related (probably the main AC sub) (doc unsure) [reli]")]];
    Code sub_9013_9[0x574] @ 0x019454 [[comment("$83:9454 (continued from $83:9013) Subroutine: Ancient Cave related (probably the main AC sub) (doc unsure) [reli]")]];
    Code sub_9018 @ 0x019018 [[comment("$83:9018 AP hook: DB=$83, x=0, m=1 | JSL ArchitectMode ; overwrites LDA.b #$7E : PHA : PLB [ap] (end unknown)")]];
    Code sub_90C9 @ 0x0190C9 [[comment("$83:90C9 AP hook: for architect mode: make red chest behavior for iris treasure replacements independent of current inventory by ensuring the same number of RNG calls, no matter if you have the iris item already or not (done by prefilling *all* chests first and potentially overwriting one of them with an iris item afterwards, instead of checking the iris item first and then potentially filling *one fewer* regular chest) | DB=$96, x=0, m=1 | NOP ; overwrites LDY.w #$0000 | BRA + ; go to regular red chest generation | -: ; iris treasure handling happens below [ap] (end unknown)")]];
    Code sub_9114 @ 0x019114 [[comment("$83:9114 AP hook: DB=$7F, x=0, m=1 | NOP #36 ; overwrites all of providence handling | LDA.b #$83 ; (overwritten instruction from org $8391E9) set DB=$83 for floor layout generation | PHA ; (overwritten instruction from org $8391E9) [ap] (end unknown)")]];
    Code sub_9176 @ 0x019176 [[comment("$83:9176 AP hook: increase variety of red chest gear after B9 | DB=$7F, x=0, m=1 | CLC ; {carry clear = disable this feature, carry set = enable this feature} | JSL RedChestGear ; overwrites LDX.w #$1000 : LDA $60 [ap] (end unknown)")]];
    Code sub_917D @ 0x01917D [[comment("$83:917D AP hook: DB=$7F, x=0, m=1 | JSL RunEquipmentRNG ; overwrites LSR : JSR $9E11 [ap] (end unknown)")]];
    Code sub_91A6 @ 0x0191A6 [[comment("$83:91A6 AP hook: for architect mode: make red chest behavior for spell replacements independent of currently learned spells by ensuring the same number of RNG calls, no matter if you have the spell already or not | DB=$7F, x=0, m=1 | JSL SpellRNG ; overwrites LDA.b #$80 : STA $E747,Y [ap] (end unknown)")]];
    Code sub_91E9 @ 0x0191E9 [[comment("$83:91E9 AP hook: red chests are filled below | DB=$7F, x=0, m=1 | NOP ; overwrites LDA.b #$83 : PHA : PLB | BRL - ; go to iris treasure handling | ++: ; floor layout generation happens below [ap] (end unknown)")]];
    Code sub_9453 @ 0x019453 [[comment("$83:9453 AP hook: TODO: Remove, not used for Overworld. door stairs fix | DB=$7F, x=0, m=1 | JSL DoorStairsFix ; overwrites JSR $9B18 : JSR $9D11 [ap] (end unknown)")]];
    Code sub_9A1C @ 0x019A1C [[comment("$83:9A1C Subroutine: Ancien Cave related: fills a floor with enemies. [reli] (end unknown)")]];
    Code sub_9C64 @ 0x019C64 [[comment("$83:9C64 AP hook: TODO: Remove, not used for Overworld. single-node room fix | DB=$7F, x=0, m=1 | BNE + ; overwrites BNE $17 [ap] (end unknown)")]];
    Code sub_9C7B @ 0x019C7B [[comment("$83:9C7B AP hook: DB=$7F, x=0, m=1 | JMP $9BE7 ; overwrites BRA $22 : LDX.w #$00FF [ap] (end unknown)")]];
    Code sub_9C99 @ 0x019C99 [[comment("$83:9C99 AP hook: DB=$7F, x=0, m=1 | INX ; overwrites DEX : CPX.w #$0010 : BCS $E1 [ap] (end unknown)")]];
    Code sub_9E31[0x56] @ 0x019E31 [[comment("$83:9E31 Subroutine: [reli]")]];
    Code sub_9E31_2[0xB7] @ 0x019E88 [[comment("$83:9E88 (continued from $83:9E31) Subroutine: [reli]")]];
    Code sub_9E87 @ 0x019E87 [[comment("$83:9E87 AP hook: report final floor goal completion | JSL FinalFloor ; overwrites STA $0005B0 [ap] (end unknown)")]];
    Data data_9F3F[0xA] @ 0x019F3F [[comment("$83:9F3F Data? [reli]")]];
    Data data_9F73[0xC] @ 0x019F73 [[comment("$83:9F73 Pointers (3 bytes long => 4 pointers) to ??? [reli]")]];
    Data data_9F7F[0x6] @ 0x019F7F [[comment("$83:9F7F Related to the palettes [reli] || related to the Ancient Cave palettes [reli]")]];
    Gfx gfx_9F85[0x24] @ 0x019F85 [[comment("$83:9F85 Pointers (3 bytes long => 12 pointers) to palettes in bank $9B. Palettes used for the Ancient Cave. [reli]")]];
    Code sub_9FA9[0x38] @ 0x019FA9 [[comment("$83:9FA9 Subroutine: [reli]")]];
    Code sub_AB4F @ 0x01AB4F [[comment("$83:AB4F Subroutine: [reli] (end unknown)")]];
    Code sub_ACEF @ 0x01ACEF [[comment("$83:ACEF Subroutine: [reli] (end unknown)")]];
    Code sub_AD80[0x3] @ 0x01AD80 [[comment("$83:AD80 new-game setup: LDA $0B51 : BIT #$02 : BEQ $ADAB (start_capsule hooks these 7 bytes) [iris] || Iris hook: start_capsule.asm: JML over the 7-byte new-game capsule check; rejoins $83:ADAB [iris hook]")]];
    Code sub_AD80_2[0x3] @ 0x01AD84 [[comment("$83:AD84 (continued from $83:AD80) new-game setup: LDA $0B51 : BIT #$02 : BEQ $ADAB (start_capsule hooks these 7 bytes) [iris] || Iris hook: start_capsule.asm: JML over the 7-byte new-game capsule check; rejoins $83:ADAB [iris hook]")]];
    Code sub_AD83 @ 0x01AD83 [[comment("$83:AD83 AP hook: clear receiving counters when starting new game; force 'GIFT' mode | DB=$83, x=0, m=1 | JSL ClearRX ; overwrites BIT #$02 : BEQ $83ADAB [ap] (end unknown)")]];
    Code sub_AD87 @ 0x01AD87 [[comment("$83:AD87 special start: LDA #$07 : STA $0A7F : LDA #$01 : JSL $82:C352 (all capsules, map $68) [iris] (end unknown)")]];
    Code sub_ADAB @ 0x01ADAB [[comment("$83:ADAB normal start: LDA #map : STA $05AC : STZ $05B2 : LDA #entrance : STA $05B8 [iris] (end unknown)")]];
    Code sub_ADC2 @ 0x01ADC2 [[comment("$83:ADC2 end of new-game setup: LDA #$FF : STA $099D : JMP $B18E (new_game.asm hooks here) [iris] || Iris hook: new_game.asm: replaces LDA #$FF : STA $099D : JMP $B18E (unlock warps, start items, Reset spell) [iris hook] (end unknown)")]];
    Code sub_B18E @ 0x01B18E [[comment("$83:B18E shared by new game and load game [iris] (end unknown)")]];
    Code sub_B442 @ 0x01B442 [[comment("$83:B442 AP hook: TODO: Find out if this affects the Overworld Overworld probably doesn't need this shops code. shops | DB=$83, x=1, m=1 | JSL Shop ; overwrites STA $7FD0BF [ap] (end unknown)")]];
    Code sub_B5AD[0xC1] @ 0x01B5AD [[comment("$83:B5AD Subroutine: script-related [reli]")]];
    Code sub_B76E @ 0x01B76E [[comment("$83:B76E Subroutine [reli] (end unknown)")]];
    Code sub_B773 @ 0x01B773 [[comment("$83:B773 AP hook: TODO: remove this section, not used for Overworld enter ancient cave as if coming from the world map | DB=$7E, x=0, m=1 | JSL CaveEntrance ; overwrites LDA $05AC : STA $05B4 [ap] (end unknown)")]];
    Code sub_B9DC[0x2] @ 0x01B9DC [[comment("$83:B9DC REP #$10 before the roaming encounter store [iris]")]];
    Code sub_B9EC[0x4] @ 0x01B9EC [[comment("$83:B9EC STA.l $7FF8A4: roaming map monster (the normal encounter path); --scale-encounters JSL hook [iris] || Iris hook: scale_encounters.asm: JSL over STA.l $7FF8A4 (4 bytes); code at $E2:8065 [iris hook]")]];
    Code sub_BC16 @ 0x01BC16 [[comment("$83:BC16 AP hook: main loop | DB=$83, x=0, m=1 | JSL MainLoop ; overwrites LDA $09A7 : BIT.b #$01 [ap] (end unknown)")]];
    Code sub_BC91 @ 0x01BC91 [[comment("$83:BC91 AP hook: TODO: Implement for Iris receive death link | DB=$83, x=0, m=1 | JSL DeathLinkRX ; overwrites LDA $7FD0AE [ap] (end unknown)")]];
    Code sub_C723 @ 0x01C723 [[comment("$83:C723 Subroutine [reli] (end unknown)")]];
    Code sub_D350 @ 0x01D350 [[comment("$83:D350 Subroutine [reli] (end unknown)")]];
    Code sub_DF87 @ 0x01DF87 [[comment("$83:DF87 Subroutine [reli] (end unknown)")]];
    Code sub_DFFD @ 0x01DFFD [[comment("$83:DFFD Subroutine [reli] (end unknown)")]];
    Code sub_F559 @ 0x01F559 [[comment("$83:F559 chest opening animation [ap] (end unknown)")]];
    Code sub_FC6C @ 0x01FC6C [[comment("$83:FC6C AP hook: TODO: Allow as optional patch. enable run button directional input item crash fix | REP #$10 ; overwrites BEQ $83FC8A : LDA.b #$80 [ap] (end unknown)")]];
    Free free_FFBA[0x46] @ 0x01FFBA [[comment("$83:FFBA Free space [reli]")]];
};
Bank83Map bank_83 @ 0x018000 [[comment("bank $83: file 0x018000-0x01FFFF")]];

struct Bank84Map {
    Code sub_8000[0xC0] @ 0x020000 [[comment("$84:8000 Subroutine: [reli]")]];
    Code sub_80C0[0x13] @ 0x0200C0 [[comment("$84:80C0 Subroutine: [reli]")]];
    Code sub_80D3[0x13] @ 0x0200D3 [[comment("$84:80D3 Subroutine: [reli]")]];
    Code sub_80E6[0x2F] @ 0x0200E6 [[comment("$84:80E6 Subroutine: [reli]")]];
    Code sub_8115[0x30] @ 0x020115 [[comment("$84:8115 Subroutine: [reli]")]];
    Code sub_8145[0x4E] @ 0x020145 [[comment("$84:8145 Subroutine: [reli]")]];
    Code sub_82D5[0x12] @ 0x0202D5 [[comment("$84:82D5 Subroutine: After: $A8 = #$00 $A9 = $A7 * 2 $AA = #$00 $AB = $A7 * 3 $AC = #$00 $AD = #$00 [reli]")]];
    Code sub_8328[0x3B] @ 0x020328 [[comment("$84:8328 Subroutine: [reli]")]];
    Code sub_878A[0x1F] @ 0x02078A [[comment("$84:878A Subroutine: [reli]")]];
    Code sub_878A_2[0xB8] @ 0x0207AA [[comment("$84:87AA (continued from $84:878A) Subroutine: [reli]")]];
    Code sub_87A9 @ 0x0207A9 [[comment("$84:87A9 AP hook: TODO: Remove, not used for AncientCave set initial floor number | JSL InitialFloor ; overwrites TDC : STA $7FE696 [ap] (end unknown)")]];
    Code sub_8862[0xB] @ 0x020862 [[comment("$84:8862 Subroutine: [reli]")]];
    Code sub_886D[0x1B] @ 0x02086D [[comment("$84:886D Subroutine: Blue Chest item test [reli]")]];
    Code sub_8888[0x33] @ 0x020888 [[comment("$84:8888 Subroutine: [reli]")]];
    Code sub_8888_2[0x45] @ 0x0208BC [[comment("$84:88BC (continued from $84:8888) Subroutine: [reli]")]];
    Code sub_8888_3[0x9] @ 0x020902 [[comment("$84:8902 (continued from $84:8888) Subroutine: [reli]")]];
    Code sub_88BB @ 0x0208BB [[comment("$84:88BB AP hook: TODO: Find out if this affects the Overworld start with Providence | DB=$84, x=0, m=0 | JSL Providence ; overwrites LDX.w #$1402 : STX $0A8D [ap] (end unknown)")]];
    Code sub_8901 @ 0x020901 [[comment("$84:8901 AP hook: start inventory | DB=$84, x=0, m=1 | JSL StartInventory ; overwrites JSL $81ED35 [ap] (end unknown)")]];
    Code sub_8B9C @ 0x020B9C [[comment("$84:8B9C AP hook: TODO: find out if this affects the Overworld keep inventory after defeat | DB=$7E, x=0, m=1 | NOP #5 ; overwrites LDA.b #$FF : STA $7FE759 : JSR $8888 [ap] (end unknown)")]];
    Code sub_8BC7 @ 0x020BC7 [[comment("$84:8BC7 Subroutine: [reli] (end unknown)")]];
    Code sub_8E0F[0x101] @ 0x020E0F [[comment("$84:8E0F Subroutine: [reli]")]];
    Data data_F928 @ 0x027928 [[comment("$84:F928 Casino-related code/data? (doc unsure) [reli] (end unknown)")]];
    Free free_FD41[0x2BF] @ 0x027D41 [[comment("$84:FD41 Free space [reli]")]];
};
Bank84Map bank_84 @ 0x020000 [[comment("bank $84: file 0x020000-0x027FFF")]];

struct Bank85Map {
    Text text_8000[0x45] @ 0x028000 [[comment("$85:8000 Text: 'Found ' 'It's locked' 'Used ' 'Ancient Dungeon B' [reli]")]];
    Code sub_8045[0x1D7] @ 0x028045 [[comment("$85:8045 Subroutine: (doc unsure) [reli]")]];
    Code sub_821C[0x4B] @ 0x02821C [[comment("$85:821C Subroutine: [reli]")]];
    Code sub_8267[0xD] @ 0x028267 [[comment("$85:8267 Subroutine: [reli]")]];
    Code sub_8274[0xD] @ 0x028274 [[comment("$85:8274 Subroutine: [reli]")]];
    Code sub_8281[0x1C] @ 0x028281 [[comment("$85:8281 Subroutine: [reli]")]];
    Code sub_829D[0x6D] @ 0x02829D [[comment("$85:829D Subroutine: [reli]")]];
    Data data_830A[0x8] @ 0x02830A [[comment("$85:830A Data $01 02 04 08 10 20 40 80 [reli]")]];
    Code sub_8312[0xD] @ 0x028312 [[comment("$85:8312 Subroutine: [reli]")]];
    Code sub_831F[0x3] @ 0x02831F [[comment("$85:831F Subroutine: [reli]")]];
    Code sub_8322[0xF3] @ 0x028322 [[comment("$85:8322 Subroutine: [reli]")]];
    Code sub_8415[0x94] @ 0x028415 [[comment("$85:8415 Subroutine: [reli]")]];
    Code sub_84A9[0x1D] @ 0x0284A9 [[comment("$85:84A9 Subroutine: [reli]")]];
    Code sub_84C6[0x48] @ 0x0284C6 [[comment("$85:84C6 Subroutine: [reli]")]];
    Code sub_850E[0x7] @ 0x02850E [[comment("$85:850E Subroutine: [reli]")]];
    Code sub_8515[0x7] @ 0x028515 [[comment("$85:8515 Subroutine: [reli]")]];
    Code sub_851C[0x7] @ 0x02851C [[comment("$85:851C Subroutine: [reli]")]];
    Text text_8523[0x32D] @ 0x028523 [[comment("$85:8523 Text for 'Debug mode' code? [reli]")]];
    Code sub_8850[0xB5] @ 0x028850 [[comment("$85:8850 Subroutine: [reli]")]];
    Code sub_8905[0x45] @ 0x028905 [[comment("$85:8905 Subroutine: [reli]")]];
    Code sub_894A[0x9B] @ 0x02894A [[comment("$85:894A Subroutine: [reli]")]];
    Code sub_89E5[0x1E] @ 0x0289E5 [[comment("$85:89E5 Subroutine: [reli]")]];
    Code sub_8A03[0x2B] @ 0x028A03 [[comment("$85:8A03 Subroutine: [reli]")]];
    Code sub_8A2F[0xA] @ 0x028A2F [[comment("$85:8A2F Subroutine: [reli]")]];
    Code sub_8A39[0x5D] @ 0x028A39 [[comment("$85:8A39 Subroutine: [reli]")]];
    Code sub_8A96[0x19] @ 0x028A96 [[comment("$85:8A96 Subroutine: [reli]")]];
    Code sub_8AAF[0x45] @ 0x028AAF [[comment("$85:8AAF Subroutine: [reli]")]];
    Code sub_8AF4[0x2E] @ 0x028AF4 [[comment("$85:8AF4 Subroutine: [reli]")]];
    Code sub_8B22[0x29] @ 0x028B22 [[comment("$85:8B22 Subroutine: [reli]")]];
    Code sub_8B4B[0x75] @ 0x028B4B [[comment("$85:8B4B Subroutine: [reli]")]];
    Code sub_8BC0[0x67] @ 0x028BC0 [[comment("$85:8BC0 Subroutine: [reli]")]];
    Code sub_8C27[0x71] @ 0x028C27 [[comment("$85:8C27 Subroutine: [reli]")]];
    Code sub_8C98[0x96] @ 0x028C98 [[comment("$85:8C98 Subroutine: [reli]")]];
    Code sub_8D2E[0x97] @ 0x028D2E [[comment("$85:8D2E Subroutine: [reli]")]];
    Code sub_8DC5[0xD3] @ 0x028DC5 [[comment("$85:8DC5 Subroutine: [reli]")]];
    Code sub_8E98[0x3A] @ 0x028E98 [[comment("$85:8E98 Subroutine: [reli]")]];
    Code sub_8ED2[0x49] @ 0x028ED2 [[comment("$85:8ED2 Subroutine: [reli]")]];
    Code sub_8F1B[0x2F] @ 0x028F1B [[comment("$85:8F1B Subroutine: [reli]")]];
    Code sub_8F4A[0x1D] @ 0x028F4A [[comment("$85:8F4A Subroutine: [reli]")]];
    Code sub_8F67[0x23] @ 0x028F67 [[comment("$85:8F67 Subroutine: [reli]")]];
    Code sub_8F8A[0xB5] @ 0x028F8A [[comment("$85:8F8A Subroutine: [reli]")]];
    Code sub_903F[0x5A] @ 0x02903F [[comment("$85:903F Subroutine: [reli]")]];
    Code sub_9099[0x23] @ 0x029099 [[comment("$85:9099 Subroutine: [reli]")]];
    Code sub_90BC[0x58] @ 0x0290BC [[comment("$85:90BC Subroutine: [reli]")]];
    Code sub_9114[0x3C] @ 0x029114 [[comment("$85:9114 Subroutine: [reli]")]];
    Code sub_9150[0x23] @ 0x029150 [[comment("$85:9150 Subroutine: [reli]")]];
    Code sub_9173[0x29] @ 0x029173 [[comment("$85:9173 Subroutine: [reli]")]];
    Code sub_919C[0x5] @ 0x02919C [[comment("$85:919C Subroutine: [reli]")]];
    Code sub_91A1[0x3F] @ 0x0291A1 [[comment("$85:91A1 Subroutine: [reli]")]];
    Code sub_948C[0x5B] @ 0x02948C [[comment("$85:948C Subroutine: [reli]")]];
    Code sub_94E7[0x29] @ 0x0294E7 [[comment("$85:94E7 Subroutine: [reli]")]];
    Code sub_9510[0x22] @ 0x029510 [[comment("$85:9510 Subroutine: [reli]")]];
    Code sub_9532[0x46] @ 0x029532 [[comment("$85:9532 Subroutine: (related to the loading of enemy attack names) [reli]")]];
    Code sub_9578[0x4E] @ 0x029578 [[comment("$85:9578 Subroutine: [reli]")]];
    Code sub_95C6[0x38] @ 0x0295C6 [[comment("$85:95C6 Subroutine: [reli]")]];
    Code sub_95FE[0x73] @ 0x0295FE [[comment("$85:95FE Subroutine: [reli]")]];
    Code sub_9671[0x2B] @ 0x029671 [[comment("$85:9671 Subroutine: [reli]")]];
    Code sub_969C[0x14] @ 0x02969C [[comment("$85:969C Subroutine: [reli]")]];
    Code sub_96B0[0xE] @ 0x0296B0 [[comment("$85:96B0 Subroutine: [reli]")]];
    Code sub_96BE[0x6F] @ 0x0296BE [[comment("$85:96BE Subroutine: [reli]")]];
    Code sub_972D @ 0x02972D [[comment("$85:972D Subroutine: RTL [reli] (end unknown)")]];
    Code sub_972E[0x62] @ 0x02972E [[comment("$85:972E Subroutine: [reli]")]];
    Code sub_9790[0x41] @ 0x029790 [[comment("$85:9790 Subroutine: [reli]")]];
    Code sub_97D1[0xB3] @ 0x0297D1 [[comment("$85:97D1 Subroutine: [reli]")]];
    Code sub_9884[0x81] @ 0x029884 [[comment("$85:9884 Subroutine: [reli]")]];
    Code sub_9905 @ 0x029905 [[comment("$85:9905 Subroutine: RTL [reli] (end unknown)")]];
    Code sub_9906[0x16B] @ 0x029906 [[comment("$85:9906 Subroutine: [reli]")]];
    Code sub_9A71[0xC] @ 0x029A71 [[comment("$85:9A71 Subroutine: [reli]")]];
    Code sub_9A7D[0x2D] @ 0x029A7D [[comment("$85:9A7D Subroutine: [reli]")]];
    Code sub_9AAA[0x12] @ 0x029AAA [[comment("$85:9AAA Subroutine: [reli]")]];
    Code sub_9ABC[0x12] @ 0x029ABC [[comment("$85:9ABC Subroutine: [reli]")]];
    Code sub_9ACE[0xF] @ 0x029ACE [[comment("$85:9ACE Subroutine: [reli]")]];
    Code sub_9ADD[0x17] @ 0x029ADD [[comment("$85:9ADD Subroutine: [reli]")]];
    Code sub_9AF4[0x17] @ 0x029AF4 [[comment("$85:9AF4 Subroutine: [reli]")]];
    Code sub_9B0B[0x17] @ 0x029B0B [[comment("$85:9B0B Subroutine: [reli]")]];
    Code sub_9B22[0x17] @ 0x029B22 [[comment("$85:9B22 Subroutine: [reli]")]];
    Code sub_9B50[0x17] @ 0x029B50 [[comment("$85:9B50 Subroutine: [reli]")]];
    Code sub_9B7E[0x17] @ 0x029B7E [[comment("$85:9B7E Subroutine: [reli]")]];
    Code sub_9B95[0x17] @ 0x029B95 [[comment("$85:9B95 Subroutine: [reli]")]];
    Code sub_9BAC[0x17] @ 0x029BAC [[comment("$85:9BAC Subroutine: [reli]")]];
    Code sub_9BC3[0x6] @ 0x029BC3 [[comment("$85:9BC3 Subroutine: [reli]")]];
    Code sub_9BC3_2[0x10] @ 0x029BCA [[comment("$85:9BCA (continued from $85:9BC3) Subroutine: [reli]")]];
    Code sub_9BC9 @ 0x029BC9 [[comment("$85:9BC9 Subroutine: [reli] (end unknown)")]];
    Code sub_9BDA[0x17] @ 0x029BDA [[comment("$85:9BDA Subroutine: [reli]")]];
    Code sub_9BF1[0x17] @ 0x029BF1 [[comment("$85:9BF1 Subroutine: [reli]")]];
    Code sub_9C08[0x17] @ 0x029C08 [[comment("$85:9C08 Subroutine: [reli]")]];
    Code sub_9C1F[0x17] @ 0x029C1F [[comment("$85:9C1F Subroutine: [reli]")]];
    Code sub_9C36[0x17] @ 0x029C36 [[comment("$85:9C36 Subroutine: [reli]")]];
    Code sub_9C4D[0x17] @ 0x029C4D [[comment("$85:9C4D Subroutine: [reli]")]];
    Code sub_9C64[0x17] @ 0x029C64 [[comment("$85:9C64 Subroutine: [reli]")]];
    Code sub_9C7B[0x17] @ 0x029C7B [[comment("$85:9C7B Subroutine: [reli]")]];
    Code sub_9C92[0x17] @ 0x029C92 [[comment("$85:9C92 Subroutine: [reli]")]];
    Code sub_9CA9[0x17] @ 0x029CA9 [[comment("$85:9CA9 Subroutine: [reli]")]];
    Code sub_9CC0[0x17] @ 0x029CC0 [[comment("$85:9CC0 Subroutine: [reli]")]];
    Code sub_9CD7[0x17] @ 0x029CD7 [[comment("$85:9CD7 Subroutine: [reli]")]];
    Code sub_9CEE[0x17] @ 0x029CEE [[comment("$85:9CEE Subroutine: [reli]")]];
    Code sub_9D05[0x17] @ 0x029D05 [[comment("$85:9D05 Subroutine: [reli]")]];
    Code sub_9D1C[0x17] @ 0x029D1C [[comment("$85:9D1C Subroutine: [reli]")]];
    Code sub_9D33[0x17] @ 0x029D33 [[comment("$85:9D33 Subroutine: [reli]")]];
    Code sub_9D4A[0x17] @ 0x029D4A [[comment("$85:9D4A Subroutine: [reli]")]];
    Code sub_9D61[0x17] @ 0x029D61 [[comment("$85:9D61 Subroutine: [reli]")]];
    Code sub_9D78[0x17] @ 0x029D78 [[comment("$85:9D78 Subroutine: [reli]")]];
    Code sub_9D8F[0x17] @ 0x029D8F [[comment("$85:9D8F Subroutine: [reli]")]];
    Code sub_9DA6[0x17] @ 0x029DA6 [[comment("$85:9DA6 Subroutine: [reli]")]];
    Code sub_9DBD[0x17] @ 0x029DBD [[comment("$85:9DBD Subroutine: [reli]")]];
    Code sub_9DD4[0x31] @ 0x029DD4 [[comment("$85:9DD4 Subroutine: [reli]")]];
    Data data_9E05 @ 0x029E05 [[comment("$85:9E05 Pointers? [reli] (end unknown)")]];
    Data data_9E37 @ 0x029E37 [[comment("$85:9E37 Data (see sub at $85:894A) or pointers (see sub at $85:8DC5) [reli] (end unknown)")]];
    Data data_9EBA[0xE] @ 0x029EBA [[comment("$85:9EBA Pointers (2-bytes long): SNES addresses of the heroes' data in the RAM [reli]")]];
    Data data_9EC8[0xC] @ 0x029EC8 [[comment("$85:9EC8 Pointers (2-bytes long): SNES addresses of the current monsters's data in the RAM (during battle) [reli]")]];
    Data data_9ED4[0x2] @ 0x029ED4 [[comment("$85:9ED4 Pointers (2-bytes long): SNES addresses of the current Capsule Monsters's data in the RAM (during battle) [reli]")]];
    Code sub_AB5B[0x1D] @ 0x02AB5B [[comment("$85:AB5B Subroutine: [reli]")]];
    Data data_B395[0xBD] @ 0x02B395 [[comment("$85:B395 Stats and spells of the heroes when they enter the Ancient Cave 27 (= 189 / 7) bytes per hero Byte 0: level Byte 1: status Bytes 2 and 3: ??? (at offsets [+$94, +$95] in the hero's RAM) Byte 4: $FF (because the heroes don't start with spells in the AC) Bytes 5 to 7: Now EXP Bytes 8 and 9: pot. max HP+ Bytes 10 and 11: pot. max MP+ Bytes 12 and 13: pot. ATP+ Bytes 14 and 15: pot. DFP+ Bytes 16 and 17: pot. STR+ Bytes 18 and 19: pot. AGL+ Bytes 20 and 21: pot. INT+ Bytes 22 and 23: pot. GUT+ Bytes 24 and 25: pot. MGR+ Byte 26: IP [reli]")]];
    Code sub_B452[0x21] @ 0x02B452 [[comment("$85:B452 Subroutine: L2BASM parser [reli]")]];
    Code sub_B473[0x10] @ 0x02B473 [[comment("$85:B473 ? Subroutine: Implementation of L2BASM opcode $00 opcode $4F (from $85:B476) [reli]")]];
    Code sub_B53D[0x7] @ 0x02B53D [[comment("$85:B53D ? Subroutine: Implementation of L2BASM opcode $01 (doc unsure) [reli]")]];
    Code sub_B53D_2[0xB] @ 0x02B545 [[comment("$85:B545 (continued from $85:B53D) ? Subroutine: Implementation of L2BASM opcode $01 (doc unsure) [reli]")]];
    Code sub_B544 @ 0x02B544 [[comment("$85:B544 AP hook: TODO: Find out if this is needed for Overworld. mid-turn death fix | JSL MidTurnDeathFix ; overwrites JSL $85CCCE [ap] (end unknown)")]];
    Code sub_B550 @ 0x02B550 [[comment("$85:B550 ? Subroutine: Implementation of L2BASM opcode $02 $85/B550: 00 BRK => reset the game [reli] (end unknown)")]];
    Code sub_B551[0xF] @ 0x02B551 [[comment("$85:B551 Subroutine: Implementation of L2BASM opcode $03 [reli]")]];
    Code sub_B560[0x22] @ 0x02B560 [[comment("$85:B560 Subroutine: Implementation of L2BASM opcode $04 [reli]")]];
    Code sub_B582[0x16] @ 0x02B582 [[comment("$85:B582 Subroutine: Implementation of L2BASM opcode $05 [reli]")]];
    Code sub_B598[0x15] @ 0x02B598 [[comment("$85:B598 Subroutine: Implementation of L2BASM opcode $06 [reli]")]];
    Code sub_B5AD[0x15] @ 0x02B5AD [[comment("$85:B5AD Subroutine: Implementation of L2BASM opcode $07 [reli]")]];
    Code sub_B5C2[0x25] @ 0x02B5C2 [[comment("$85:B5C2 Subroutine: Implementation of L2BASM opcode $08 [reli]")]];
    Code sub_B5E7[0x23] @ 0x02B5E7 [[comment("$85:B5E7 Subroutine: Implementation of L2BASM opcode $09 [reli]")]];
    Code sub_B60A[0x23] @ 0x02B60A [[comment("$85:B60A Subroutine: Implementation of L2BASM opcode $0A [reli]")]];
    Code sub_B62D[0x25] @ 0x02B62D [[comment("$85:B62D Subroutine: Implementation of L2BASM opcode $0B [reli]")]];
    Code sub_B652[0x1E] @ 0x02B652 [[comment("$85:B652 ? Subroutine: Implementation of L2BASM opcode $3F (01) [reli]")]];
    Code sub_B670[0xC] @ 0x02B670 [[comment("$85:B670 Subroutine: Implementation of L2BASM opcode $0C [reli]")]];
    Code sub_B67C[0x1C] @ 0x02B67C [[comment("$85:B67C Subroutine: Implementation of L2BASM opcode $0D [reli]")]];
    Code sub_B698[0x1F] @ 0x02B698 [[comment("$85:B698 Subroutine: Implementation of L2BASM opcode $0E [reli]")]];
    Code sub_B6B7[0x1B] @ 0x02B6B7 [[comment("$85:B6B7 Subroutine: Implementation of L2BASM opcode $0F [reli]")]];
    Code sub_B6D2 @ 0x02B6D2 [[comment("$85:B6D2 Subroutine: Implementation of L2BASM opcode $10 [reli] (end unknown)")]];
    Code sub_B71D[0x1E] @ 0x02B71D [[comment("$85:B71D ? Subroutine: Implementation of L2BASM opcode $55 [reli]")]];
    Code sub_B73B[0x18] @ 0x02B73B [[comment("$85:B73B ? Subroutine: Implementation of L2BASM opcode $11 [reli]")]];
    Code sub_B753[0x28] @ 0x02B753 [[comment("$85:B753 ? Subroutine: Implementation of L2BASM opcode $12 [reli]")]];
    Code sub_B77B[0x2D] @ 0x02B77B [[comment("$85:B77B Subroutine: Implementation of L2BASM opcode $13 [reli]")]];
    Code sub_B7A8[0x27] @ 0x02B7A8 [[comment("$85:B7A8 Subroutine: Implementation of L2BASM opcode $14 [reli]")]];
    Code sub_B7CF[0x4D] @ 0x02B7CF [[comment("$85:B7CF Subroutine: Implementation of L2BASM opcode $15 [reli]")]];
    Code sub_B81C[0x2D] @ 0x02B81C [[comment("$85:B81C Subroutine: Implementation of L2BASM opcode $4E [reli]")]];
    Code sub_B849[0x1B] @ 0x02B849 [[comment("$85:B849 Subroutine: Implementation of L2BASM opcode $16 [reli]")]];
    Code sub_B864[0x1B] @ 0x02B864 [[comment("$85:B864 Subroutine: Implementation of L2BASM opcode $17 [reli]")]];
    Code sub_B87F[0x1B] @ 0x02B87F [[comment("$85:B87F Subroutine: Implementation of L2BASM opcode $18 [reli]")]];
    Code sub_B89A[0x1A] @ 0x02B89A [[comment("$85:B89A Subroutine: Implementation of L2BASM opcode $19 [reli]")]];
    Code sub_B8B4[0x18] @ 0x02B8B4 [[comment("$85:B8B4 Subroutine: Implementation of L2BASM opcode $1A [reli]")]];
    Code sub_B8CC[0x1F] @ 0x02B8CC [[comment("$85:B8CC Subroutine: Implementation of L2BASM opcode $1B [reli]")]];
    Code sub_B8EB[0xC] @ 0x02B8EB [[comment("$85:B8EB Subroutine: Implementation of L2BASM opcode $1C [reli]")]];
    Code sub_B8F7[0xD] @ 0x02B8F7 [[comment("$85:B8F7 ? Subroutine: Implementation of L2BASM opcode $40 [reli]")]];
    Code sub_B904[0x7] @ 0x02B904 [[comment("$85:B904 Subroutine: Implementation of L2BASM opcode $1D [reli]")]];
    Code sub_B90B[0x14] @ 0x02B90B [[comment("$85:B90B Subroutine: Implementation of L2BASM opcode $1E [reli]")]];
    Code sub_B91F[0xD] @ 0x02B91F [[comment("$85:B91F Subroutine: Implementation of L2BASM opcode $1F [reli]")]];
    Code sub_B92C[0x11] @ 0x02B92C [[comment("$85:B92C Subroutine: Implementation of L2BASM opcode $20 [reli]")]];
    Code sub_B93D[0x31] @ 0x02B93D [[comment("$85:B93D Subroutine: Implementation of L2BASM opcode $21 [reli]")]];
    Code sub_B96E[0x4A] @ 0x02B96E [[comment("$85:B96E Subroutine: Implementation of L2BASM opcode $22 [reli]")]];
    Code sub_B9B8[0x22] @ 0x02B9B8 [[comment("$85:B9B8 Subroutine: Implementation of L2BASM opcode $23 [reli]")]];
    Code sub_B9DA[0x28] @ 0x02B9DA [[comment("$85:B9DA Subroutine: Implementation of L2BASM opcode $24 [reli]")]];
    Code sub_BA02[0x26] @ 0x02BA02 [[comment("$85:BA02 Subroutine: Implementation of L2BASM opcode $25 [reli]")]];
    Code sub_BA28[0x1F] @ 0x02BA28 [[comment("$85:BA28 Subroutine: Implementation of L2BASM opcode $26 [reli]")]];
    Code sub_BA47[0x1D] @ 0x02BA47 [[comment("$85:BA47 Subroutine: Implementation of L2BASM opcode $27 [reli]")]];
    Code sub_BA64[0x1D] @ 0x02BA64 [[comment("$85:BA64 Subroutine: Implementation of L2BASM opcode $28 [reli]")]];
    Code sub_BA81 @ 0x02BA81 [[comment("$85:BA81 Subroutine: Implementation of L2BASM opcode $29 [reli] (end unknown)")]];
    Code sub_BA8A[0x9] @ 0x02BA8A [[comment("$85:BA8A Subroutine: Implementation of L2BASM opcode $2A [reli]")]];
    Code sub_BA93[0x13] @ 0x02BA93 [[comment("$85:BA93 ? Subroutine: Implementation of L2BASM opcode $2B (doc unsure) [reli]")]];
    Code sub_BAA6[0x51] @ 0x02BAA6 [[comment("$85:BAA6 ? Subroutine: Implementation of L2BASM opcode $2C (doc unsure) [reli] || L2BASM opcode 2C (cast spell) handler [iris]")]];
    Code sub_BAF7[0x1E] @ 0x02BAF7 [[comment("$85:BAF7 ? Subroutine: (doc unsure) [reli]")]];
    Code sub_BB15[0x31] @ 0x02BB15 [[comment("$85:BB15 ? Subroutine: Implementation of L2BASM opcode $2D (doc unsure) [reli]")]];
    Code sub_BB46[0x9] @ 0x02BB46 [[comment("$85:BB46 ? Subroutine: Implementation of L2BASM opcode $2E (doc unsure) [reli]")]];
    Code sub_BB4F[0x2F] @ 0x02BB4F [[comment("$85:BB4F ? Subroutine: Implementation of L2BASM opcode $2F (doc unsure) [reli]")]];
    Code sub_BB7E[0x23] @ 0x02BB7E [[comment("$85:BB7E ? Subroutine: Implementation of L2BASM opcode $30 (doc unsure) [reli]")]];
    Code sub_BBA1 @ 0x02BBA1 [[comment("$85:BBA1 Subroutine: Implementation of L2BASM opcode $31 $85/BBA1: 00 BRK => reset the game [reli] (end unknown)")]];
    Code sub_BBA2[0x14] @ 0x02BBA2 [[comment("$85:BBA2 Subroutine: Implementation of L2BASM opcode $32 (1) [reli]")]];
    Unknown unk_BBB6[0x14] @ 0x02BBB6 [[comment("$85:BBB6 ? Pointers used by sub at $85:BBA2 [reli]")]];
    Code sub_BBCA[0x3] @ 0x02BBCA [[comment("$85:BBCA ? Subroutine: Implementation of L2BASM instruction $32 00 [reli]")]];
    Code sub_BBCD[0x2B] @ 0x02BBCD [[comment("$85:BBCD ? Subroutine: Implementation of L2BASM instruction $32 01 [reli]")]];
    Code sub_BBF8[0x2E] @ 0x02BBF8 [[comment("$85:BBF8 ? Subroutine: Implementation of L2BASM instruction $32 02 [reli]")]];
    Code sub_BC26[0x13] @ 0x02BC26 [[comment("$85:BC26 ? Subroutine: Implementation of L2BASM instruction $32 03 [reli]")]];
    Code sub_BC39[0x1D] @ 0x02BC39 [[comment("$85:BC39 ? Subroutine: Implementation of L2BASM instruction $32 04 [reli]")]];
    Code sub_BC56[0x10] @ 0x02BC56 [[comment("$85:BC56 ? Subroutine: Implementation of L2BASM instruction $32 05 [reli]")]];
    Code sub_BC66[0xD] @ 0x02BC66 [[comment("$85:BC66 ? Subroutine: Implementation of L2BASM instruction $32 06 [reli]")]];
    Code sub_BC73[0x29] @ 0x02BC73 [[comment("$85:BC73 ? Subroutine: Implementation of L2BASM instruction $32 07 [reli]")]];
    Code sub_BC9C[0x31] @ 0x02BC9C [[comment("$85:BC9C ? Subroutine: Implementation of L2BASM instruction $32 08 [reli]")]];
    Code sub_BCCD @ 0x02BCCD [[comment("$85:BCCD Subroutine: Implementation of L2BASM instruction $32 09 and opcode $33 $85/BCCD: 00 BRK => reset the game [reli] (end unknown)")]];
    Code sub_BCCE @ 0x02BCCE [[comment("$85:BCCE Subroutine: Implementation of L2BASM $34 $85/BCCE: 00 BRK => reset the game [reli] (end unknown)")]];
    Code sub_BCCF[0x9] @ 0x02BCCF [[comment("$85:BCCF ? Subroutine: Implementation of L2BASM opcode $35 [doc's file column says 0x02BE9C (copy error); SNES column used] [reli]")]];
    Code sub_BCD8[0x15] @ 0x02BCD8 [[comment("$85:BCD8 ? Subroutine: Implementation of L2BASM opcode $36 [reli]")]];
    Code sub_BCED @ 0x02BCED [[comment("$85:BCED ? Subroutine: Implementation of L2BASM opcode $37 [reli] (end unknown)")]];
    Code sub_BD2B @ 0x02BD2B [[comment("$85:BD2B Subroutine: Implementation of L2BASM opcode $38 opcode $39 opcode $3A opcode $3B $85/BD2B: 00 BRK => reset the game [reli] (end unknown)")]];
    Code sub_BD2C[0x28] @ 0x02BD2C [[comment("$85:BD2C ? Subroutine: Implementation of L2BASM opcode $3C (doc unsure) [reli]")]];
    Code sub_BD54[0xA] @ 0x02BD54 [[comment("$85:BD54 ? Subroutine: Implementation of L2BASM opcode $3D [reli]")]];
    Code sub_BD5E[0x10] @ 0x02BD5E [[comment("$85:BD5E ? Subroutine: Implementation of L2BASM opcode $3E [reli] || L2BASM opcode 3E: action type $0B -> $7F:F454, XX -> $7F:F456, ends the script turn [iris]")]];
    Code sub_BD6E[0x9] @ 0x02BD6E [[comment("$85:BD6E ? Subroutine: Implementation of L2BASM opcode $41 [reli]")]];
    Code sub_BD77[0x22] @ 0x02BD77 [[comment("$85:BD77 ? Subroutine: Implementation of L2BASM opcode $42 (1) [reli]")]];
    Code sub_BD77_2[0x18] @ 0x02BD9A [[comment("$85:BD9A (continued from $85:BD77) ? Subroutine: Implementation of L2BASM opcode $42 (1) [reli]")]];
    Code sub_BD99 @ 0x02BD99 [[comment("$85:BD99 $42 subroutine accessor: LDA #$96 : STA $BD ; LDA $96FADD,X : ADC #$FADD [iris] (end unknown)")]];
    Code sub_BDB2[0x19] @ 0x02BDB2 [[comment("$85:BDB2 ? Subroutine: Implementation of L2BASM opcode $43 (1) [reli]")]];
    Code sub_BDCB[0xF] @ 0x02BDCB [[comment("$85:BDCB ? Subroutine: Implementation of L2BASM opcode $44 [reli]")]];
    Code sub_BDDA[0x19] @ 0x02BDDA [[comment("$85:BDDA ? Subroutine: Implementation of L2BASM opcode $45 [reli]")]];
    Code sub_BDF3[0x13] @ 0x02BDF3 [[comment("$85:BDF3 ? Subroutine: Implementation of L2BASM opcode $46 [reli]")]];
    Code sub_BE06[0xD] @ 0x02BE06 [[comment("$85:BE06 ? Subroutine: Implementation of L2BASM opcode $47 [reli]")]];
    Code sub_BE13[0x7] @ 0x02BE13 [[comment("$85:BE13 ? Subroutine: Implementation of L2BASM opcode $48 [reli]")]];
    Code sub_BE1A[0x8] @ 0x02BE1A [[comment("$85:BE1A ? Subroutine: Implementation of L2BASM opcode $49 [reli]")]];
    Code sub_BE22[0x9] @ 0x02BE22 [[comment("$85:BE22 ? Subroutine: Implementation of L2BASM opcode $56 [reli]")]];
    Code sub_BE2B[0x18] @ 0x02BE2B [[comment("$85:BE2B ? Subroutine: Implementation of L2BASM opcode $4A [reli]")]];
    Code sub_BE43[0x9] @ 0x02BE43 [[comment("$85:BE43 ? Subroutine: Implementation of L2BASM opcode $4B [reli]")]];
    Code sub_BE4C[0xA] @ 0x02BE4C [[comment("$85:BE4C ? Subroutine: Implementation of L2BASM opcode $4C [reli]")]];
    Code sub_BE56[0x12] @ 0x02BE56 [[comment("$85:BE56 ? Subroutine: Implementation of L2BASM opcode $4D [reli]")]];
    Code sub_BE68[0x15] @ 0x02BE68 [[comment("$85:BE68 ? Subroutine: Implementation of L2BASM opcode $50 [reli]")]];
    Code sub_BE7D[0x19] @ 0x02BE7D [[comment("$85:BE7D ? Subroutine: Implementation of L2BASM opcode $51 [reli]")]];
    Code sub_BE96[0x10] @ 0x02BE96 [[comment("$85:BE96 ? Subroutine: Implementation of L2BASM opcode $52 [reli]")]];
    Code sub_BEA6[0x19] @ 0x02BEA6 [[comment("$85:BEA6 ? Subroutine: [reli]")]];
    Code sub_BEBF[0x1B] @ 0x02BEBF [[comment("$85:BEBF ? Subroutine: Implementation of L2BASM opcode $53 [reli]")]];
    Code sub_BEDA[0x1B] @ 0x02BEDA [[comment("$85:BEDA ? Subroutine: Implementation of L2BASM opcode $54 [reli]")]];
    Code sub_BEF5[0x7E] @ 0x02BEF5 [[comment("$85:BEF5 ? Subroutine: Implementation of L2BASM opcode $57 [reli]")]];
    Code sub_BF73[0x24] @ 0x02BF73 [[comment("$85:BF73 ? Subroutine: Called by sub at $85:BEF5 (impl. of L2BASM opcode $57) [reli]")]];
    Code sub_BF97[0x7] @ 0x02BF97 [[comment("$85:BF97 ? Subroutine: Implementation of L2BASM opcode $58 [reli]")]];
    Code sub_BF9E[0x7] @ 0x02BF9E [[comment("$85:BF9E ? Subroutine: Implementation of L2BASM opcode $59 [reli]")]];
    Code sub_BFA5[0x9] @ 0x02BFA5 [[comment("$85:BFA5 ? Subroutine: Implementation of L2BASM opcode $5A [reli]")]];
    Code sub_BFAE[0x8] @ 0x02BFAE [[comment("$85:BFAE ? Subroutine: Implementation of L2BASM opcode $5B [reli]")]];
    Code sub_BFB6[0x9] @ 0x02BFB6 [[comment("$85:BFB6 ? Subroutine: Implementation of L2BASM opcode $5C [reli]")]];
    Code sub_BFBF[0xB] @ 0x02BFBF [[comment("$85:BFBF ? Subroutine: Implementation of L2BASM opcode $32 (2) $11 (2) low A = next L2BASM script byte [reli]")]];
    Code sub_BFCA[0xE] @ 0x02BFCA [[comment("$85:BFCA ? Subroutine: Implementation of L2BASM opcode $42 (2) $3F (2) [reli]")]];
    Code sub_BFED @ 0x02BFED [[comment("$85:BFED ? Subroutine: Implementation of L2BASM opcode $11 (3) [reli] (end unknown)")]];
    Code sub_C023[0x3C] @ 0x02C023 [[comment("$85:C023 ? Subroutine: [reli]")]];
    Code sub_C28F @ 0x02C28F [[comment("$85:C28F ? Subroutine: Called by: sub at $85:B53D [reli] (end unknown)")]];
    Code sub_C2C9 @ 0x02C2C9 [[comment("$85:C2C9 ? Subroutine: Called by: sub at $85:B53D [reli] (end unknown)")]];
    Code sub_C4DE @ 0x02C4DE [[comment("$85:C4DE ? Subroutine: [reli] (end unknown)")]];
    Code sub_C954 @ 0x02C954 [[comment("$85:C954 ? Subroutine: [reli] (end unknown)")]];
    Code sub_CA22 @ 0x02CA22 [[comment("$85:CA22 ? Subroutine: [reli] (end unknown)")]];
    Code sub_CC69[0x65] @ 0x02CC69 [[comment("$85:CC69 ? Subroutine: [reli]")]];
    Code sub_CCCE[0x15] @ 0x02CCCE [[comment("$85:CCCE ? Subroutine: Clean L2BASM reg $22 to $63 Called by: sub at $85:B53D [reli]")]];
    Code sub_CE21[0x4E] @ 0x02CE21 [[comment("$85:CE21 ? Subroutine: [reli]")]];
    Code sub_D025[0x5B] @ 0x02D025 [[comment("$85:D025 ? Subroutine: Related to the influence of row on damage (main sub) [reli]")]];
    Code sub_D080[0x4D] @ 0x02D080 [[comment("$85:D080 ? Subroutine: Related to the influence of row on damage Called by sub at $85:D025 [reli]")]];
    Code sub_D0CD[0x5DF] @ 0x02D0CD [[comment("$85:D0CD Subroutine: Damage calculation [reli]")]];
    Code sub_D0CD_2[0x64] @ 0x02D6AD [[comment("$85:D6AD (continued from $85:D0CD) Subroutine: Damage calculation [reli]")]];
    Code sub_D6AC @ 0x02D6AC [[comment("$85:D6AC capsule death in battle (hooked by capsule_tag) [iris] (end unknown)")]];
    Code sub_D94F @ 0x02D94F [[comment("$85:D94F ? Subroutine: Displays damage and weapon slash animations during battle [doc's file column says 0x02DD6D (copy error); SNES column used] [reli] (end unknown)")]];
    Code sub_D9C9 @ 0x02D9C9 [[comment("$85:D9C9 ? Subroutine: [reli] (end unknown)")]];
    Code sub_DA11[0x32] @ 0x02DA11 [[comment("$85:DA11 ? Subroutine: [reli]")]];
    Code sub_DA43[0x1C] @ 0x02DA43 [[comment("$85:DA43 ? Subroutine: [reli]")]];
    Code sub_DA5F[0x12] @ 0x02DA5F [[comment("$85:DA5F ? Subroutine: [reli]")]];
    Code sub_DA9C @ 0x02DA9C [[comment("$85:DA9C ? Subroutine: [reli] (end unknown)")]];
    Code sub_DB43 @ 0x02DB43 [[comment("$85:DB43 reads the arctangent table $97:B126 [iris] (end unknown)")]];
    Code sub_DB6D[0x102] @ 0x02DB6D [[comment("$85:DB6D ? Subroutine: Implementation of L2BASM opcode $11 (4) [reli]")]];
    Code sub_DC6F @ 0x02DC6F [[comment("$85:DC6F Subroutine: [reli] (end unknown)")]];
    Code sub_DE1E[0x4E] @ 0x02DE1E [[comment("$85:DE1E Subroutine: [reli]")]];
    Code sub_DE6C[0x22] @ 0x02DE6C [[comment("$85:DE6C Subroutine: [reli]")]];
    Code sub_DE8E[0xF] @ 0x02DE8E [[comment("$85:DE8E Subroutine: [reli]")]];
    Code sub_DE9D[0x3F] @ 0x02DE9D [[comment("$85:DE9D ? Subroutine: [reli]")]];
    Code sub_DEDC[0x59] @ 0x02DEDC [[comment("$85:DEDC ? Subroutine: [reli]")]];
    Code sub_DF35[0xF] @ 0x02DF35 [[comment("$85:DF35 ? Subroutine: [reli]")]];
    Code sub_DF44[0x75] @ 0x02DF44 [[comment("$85:DF44 Subroutine: Involved in the loading of enemy party in RAM before battle [reli]")]];
    Code sub_DFB9[0x74] @ 0x02DFB9 [[comment("$85:DFB9 Subroutine: [reli]")]];
    Code sub_E02D[0xB7] @ 0x02E02D [[comment("$85:E02D Subroutine: [reli]")]];
    Code sub_E0E4[0x90] @ 0x02E0E4 [[comment("$85:E0E4 Subroutine: [reli]")]];
    Code sub_E174 @ 0x02E174 [[comment("$85:E174 Subroutine: [reli] (end unknown)")]];
    Code sub_E4E5[0xDD] @ 0x02E4E5 [[comment("$85:E4E5 Subroutine: [reli]")]];
    Code sub_E5C2[0xA3] @ 0x02E5C2 [[comment("$85:E5C2 Subroutine: [reli]")]];
    Code sub_E665[0xB] @ 0x02E665 [[comment("$85:E665 Subroutine: [reli]")]];
    Code sub_E670[0x52] @ 0x02E670 [[comment("$85:E670 Subroutine: [reli]")]];
    Code sub_EB91[0x4F] @ 0x02EB91 [[comment("$85:EB91 ? Subroutine: ... - ... -> EBC4: decompress enemy battle sprite ... [reli]")]];
    Code sub_EBE0[0x6D] @ 0x02EBE0 [[comment("$85:EBE0 ? Subroutine: [reli]")]];
    Code sub_EC4D[0x34] @ 0x02EC4D [[comment("$85:EC4D ? Subroutine: [reli]")]];
    Code sub_EC81[0x5A] @ 0x02EC81 [[comment("$85:EC81 ? Subroutine: [reli]")]];
    Code sub_ECDB[0x15] @ 0x02ECDB [[comment("$85:ECDB ? Subroutine: [reli]")]];
    Code sub_ECF0[0x61] @ 0x02ECF0 [[comment("$85:ECF0 ? Subroutine: [reli]")]];
    Code sub_ED51[0x61] @ 0x02ED51 [[comment("$85:ED51 ? Subroutine: [reli]")]];
    Code sub_EDB2[0x9] @ 0x02EDB2 [[comment("$85:EDB2 ? Subroutine: [reli]")]];
    Code sub_EDBB[0x20] @ 0x02EDBB [[comment("$85:EDBB ? Subroutine: [reli]")]];
    Code sub_EDDB[0x16] @ 0x02EDDB [[comment("$85:EDDB ? Subroutine: [reli]")]];
    Code sub_EDF1[0x4D] @ 0x02EDF1 [[comment("$85:EDF1 ? Subroutine: [reli]")]];
    Code sub_EE3E[0x44] @ 0x02EE3E [[comment("$85:EE3E ? Subroutine: [reli]")]];
    Code sub_EE82[0x19] @ 0x02EE82 [[comment("$85:EE82 ? Subroutine: [reli]")]];
    Code sub_EE9B[0x6] @ 0x02EE9B [[comment("$85:EE9B ? Subroutine: [reli]")]];
    Code sub_EEA1[0x7F] @ 0x02EEA1 [[comment("$85:EEA1 ? Subroutine: [reli]")]];
    Unknown unk_EF20[0x33] @ 0x02EF20 [[comment("$85:EF20 ? Some L2BASM subroutines [reli]")]];
    Unknown unk_EF53[0x80] @ 0x02EF53 [[comment("$85:EF53 ? EFC9: number of the pointer (in bank $A7) to the 'cast spell' animation of heroes [reli]")]];
    Text text_EFE1[0x2F6] @ 0x02EFE1 [[comment("$85:EFE1 Text: 'battle messages' [reli]")]];
    Text text_F3EB[0x6CB] @ 0x02F3EB [[comment("$85:F3EB Text: enemy attacks names [reli]")]];
    Unknown unk_FE24 @ 0x02FE24 [[comment("$85:FE24 ? Data? [reli] (end unknown)")]];
    Free free_FEB1[0x14F] @ 0x02FEB1 [[comment("$85:FEB1 Free space [reli]")]];
};
Bank85Map bank_85 @ 0x028000 [[comment("bank $85: file 0x028000-0x02FFFF")]];

struct Bank86Map {
    Code sub_97D4 @ 0x0317D4 [[comment("$86:97D4 BMI patched by the AIRSHIP_ANYWHERE Game Genie code [iris] (end unknown)")]];
    Code sub_9CCE[0x3] @ 0x031CCE [[comment("$86:9CCE LDA $0BBB: party level -> Ancient Cave tier [iris]")]];
    Code sub_9CE6[0x4] @ 0x031CE6 [[comment("$86:9CE6 STA.l $7FF8A4: Ancient Cave formation, tier ((level-30) clamped 0..0x12)/2 via $86:9DC7 [iris]")]];
    Code sub_9D5D[0x4] @ 0x031D5D [[comment("$86:9D5D STA.l $7FF8A4: Ancient Cave formation from the table $97:C493 [iris]")]];
    Data data_9DC7 @ 0x031DC7 [[comment("$86:9DC7 Ancient Cave tier -> formation table (read by $86:9CE6) [iris] (end unknown)")]];
    Unknown unk_A410 @ 0x032410 [[comment("$86:A410 ? World Map themes numbers: ($12 20 39 20 12...) (doc unsure) [reli] || Sea (Ground -> Sea) [reli] (end unknown)")]];
    Data data_A411 @ 0x032411 [[comment("$86:A411 Undersea (Sea -> Undersea) [reli] (end unknown)")]];
    Data data_A412 @ 0x032412 [[comment("$86:A412 Sky (Ground -> Sky) [reli] (end unknown)")]];
    Unknown unk_A413 @ 0x032413 [[comment("$86:A413 ? [reli] (end unknown)")]];
    Data data_A414 @ 0x032414 [[comment("$86:A414 Sea (Undersea -> Sea) ? Note: some other World Map themes numbers are hardcoded [reli] (end unknown)")]];
    Free free_FC17[0x3E9] @ 0x037C17 [[comment("$86:FC17 Free space [reli]")]];
};
Bank86Map bank_86 @ 0x030000 [[comment("bank $86: file 0x030000-0x037FFF")]];

struct Bank87Map {
    Gfx gfx_914D @ 0x03914D [[comment("$87:914D Some map data (related to music and sprites) (last starts at $03B03E (or $03B04E?)) [reli] (end unknown)")]];
    Text text_B00F @ 0x03B00F [[comment("$87:B00F Text: 'Erim: Master.' (first quote of the game intro) [reli] (end unknown)")]];
};
Bank87Map bank_87 @ 0x038000 [[comment("bank $87: file 0x038000-0x03FFFF")]];

struct Bank88Map {
    Data data_8000[0xF0] @ 0x040000 [[comment("$88:8000 Script [reli]")]];
    Data data_8000_2[0x8D] @ 0x04016A [[comment("$88:816A (continued from $88:8000) Script [reli]")]];
    Data data_8000_3[0x21F] @ 0x040227 [[comment("$88:8227 (continued from $88:8000) Script [reli]")]];
    Data data_8000_4 @ 0x0404FD [[comment("$88:84FD (continued from $88:8000) Script [reli]")]];
    Data data_8000_5[0x6F] @ 0x04055B [[comment("$88:855B (continued from $88:8000) Script [reli]")]];
    Data data_8000_6[0x4B] @ 0x0405F9 [[comment("$88:85F9 (continued from $88:8000) Script [reli]")]];
    Data data_8000_7[0x4B] @ 0x04067A [[comment("$88:867A (continued from $88:8000) Script [reli]")]];
    Data data_8000_8[0x11E] @ 0x0406FD [[comment("$88:86FD (continued from $88:8000) Script [reli]")]];
    Data data_8000_9[0x60] @ 0x0408C3 [[comment("$88:88C3 (continued from $88:8000) Script [reli]")]];
    Data data_8000_10[0x47] @ 0x04095F [[comment("$88:895F (continued from $88:8000) Script [reli]")]];
    Data data_8000_11[0x73] @ 0x0409E7 [[comment("$88:89E7 (continued from $88:8000) Script [reli]")]];
    Data data_8000_12[0x19] @ 0x040A98 [[comment("$88:8A98 (continued from $88:8000) Script [reli]")]];
    Data data_8000_13[0x2C] @ 0x040AE0 [[comment("$88:8AE0 (continued from $88:8000) Script [reli]")]];
    Data data_8000_14[0xC2] @ 0x040B4E [[comment("$88:8B4E (continued from $88:8000) Script [reli]")]];
    Data data_8000_15[0x38] @ 0x040C32 [[comment("$88:8C32 (continued from $88:8000) Script [reli]")]];
    Data data_8000_16[0x20] @ 0x040C94 [[comment("$88:8C94 (continued from $88:8000) Script [reli]")]];
    Data data_8000_17[0x2B] @ 0x040CDC [[comment("$88:8CDC (continued from $88:8000) Script [reli]")]];
    Data data_8000_18[0x2E8] @ 0x040D42 [[comment("$88:8D42 (continued from $88:8000) Script [reli]")]];
    Data data_8000_19[0x99] @ 0x041062 [[comment("$88:9062 (continued from $88:8000) Script [reli]")]];
    Data data_8000_20[0x4A] @ 0x04112E [[comment("$88:912E (continued from $88:8000) Script [reli]")]];
    Data data_8000_21 @ 0x04174C [[comment("$88:974C (continued from $88:8000) Script [reli]")]];
    Data data_8000_22[0x135] @ 0x04177C [[comment("$88:977C (continued from $88:8000) Script [reli]")]];
    Data data_8000_23[0xDA] @ 0x0418F9 [[comment("$88:98F9 (continued from $88:8000) Script [reli]")]];
    Data data_8000_24 @ 0x041F30 [[comment("$88:9F30 (continued from $88:8000) Script [reli]")]];
    Data data_8000_25 @ 0x042034 [[comment("$88:A034 (continued from $88:8000) Script [reli]")]];
    Data data_8000_26 @ 0x0420BB [[comment("$88:A0BB (continued from $88:8000) Script [reli]")]];
    Data data_8000_27[0x71] @ 0x042149 [[comment("$88:A149 (continued from $88:8000) Script [reli]")]];
    Data data_8000_28[0x50] @ 0x0421E8 [[comment("$88:A1E8 (continued from $88:8000) Script [reli]")]];
    Data data_8000_29[0x61] @ 0x04226C [[comment("$88:A26C (continued from $88:8000) Script [reli]")]];
    Data data_8000_30[0x6B] @ 0x042310 [[comment("$88:A310 (continued from $88:8000) Script [reli]")]];
    Data data_8000_31[0x4D] @ 0x0423A0 [[comment("$88:A3A0 (continued from $88:8000) Script [reli]")]];
    Data data_8000_32[0x62] @ 0x042479 [[comment("$88:A479 (continued from $88:8000) Script [reli]")]];
    Data data_8000_33[0x4A] @ 0x04256B [[comment("$88:A56B (continued from $88:8000) Script [reli]")]];
    Data data_8000_34[0x72] @ 0x042638 [[comment("$88:A638 (continued from $88:8000) Script [reli]")]];
    Data data_8000_35[0x6C] @ 0x0426E5 [[comment("$88:A6E5 (continued from $88:8000) Script [reli]")]];
    Data data_8000_36[0x30] @ 0x0427F5 [[comment("$88:A7F5 (continued from $88:8000) Script [reli]")]];
    Data data_8000_37[0xDB] @ 0x042968 [[comment("$88:A968 (continued from $88:8000) Script [reli]")]];
    Data data_8000_38[0x68] @ 0x042A66 [[comment("$88:AA66 (continued from $88:8000) Script [reli]")]];
    Data data_8000_39[0xA6] @ 0x042AF5 [[comment("$88:AAF5 (continued from $88:8000) Script [reli]")]];
    Data data_8000_40[0x406] @ 0x042BA7 [[comment("$88:ABA7 (continued from $88:8000) Script [reli]")]];
    Data data_8000_41[0x2C5] @ 0x0432CE [[comment("$88:B2CE (continued from $88:8000) Script [reli]")]];
    Data data_8000_42[0x3] @ 0x043688 [[comment("$88:B688 (continued from $88:8000) Script [reli]")]];
    Data data_8000_43[0x4B1] @ 0x043B6F [[comment("$88:BB6F (continued from $88:8000) Script [reli]")]];
    Data data_8000_44[0x4A] @ 0x044058 [[comment("$88:C058 (continued from $88:8000) Script [reli]")]];
    Data data_8000_45[0x39] @ 0x0440D3 [[comment("$88:C0D3 (continued from $88:8000) Script [reli]")]];
    Data data_8000_46[0x96] @ 0x044133 [[comment("$88:C133 (continued from $88:8000) Script [reli]")]];
    Data data_8000_47[0x43] @ 0x044202 [[comment("$88:C202 (continued from $88:8000) Script [reli]")]];
    Data data_8000_48[0x63] @ 0x044285 [[comment("$88:C285 (continued from $88:8000) Script [reli]")]];
    Data data_8000_49[0x1F0] @ 0x04445C [[comment("$88:C45C (continued from $88:8000) Script [reli]")]];
    Data data_8000_50[0x16F] @ 0x04467B [[comment("$88:C67B (continued from $88:8000) Script [reli]")]];
    Data data_8000_51[0x58] @ 0x044873 [[comment("$88:C873 (continued from $88:8000) Script [reli]")]];
    Data data_8000_52[0xA0] @ 0x044987 [[comment("$88:C987 (continued from $88:8000) Script [reli]")]];
    Data data_8000_53[0x55] @ 0x044AD5 [[comment("$88:CAD5 (continued from $88:8000) Script [reli]")]];
    Data data_8000_54[0x37] @ 0x044B75 [[comment("$88:CB75 (continued from $88:8000) Script [reli]")]];
    Data data_8000_55[0xF0] @ 0x044BE4 [[comment("$88:CBE4 (continued from $88:8000) Script [reli]")]];
    Data data_8000_56[0x5D6] @ 0x044EA5 [[comment("$88:CEA5 (continued from $88:8000) Script [reli]")]];
    Data data_8000_57[0x3] @ 0x0459E1 [[comment("$88:D9E1 (continued from $88:8000) Script [reli]")]];
    Data data_8000_58[0x4B] @ 0x045A34 [[comment("$88:DA34 (continued from $88:8000) Script [reli]")]];
    Data data_8000_59[0x46] @ 0x045ABE [[comment("$88:DABE (continued from $88:8000) Script [reli]")]];
    Data data_8000_60[0x54] @ 0x045B49 [[comment("$88:DB49 (continued from $88:8000) Script [reli]")]];
    Data data_8000_61[0x2B] @ 0x045C19 [[comment("$88:DC19 (continued from $88:8000) Script [reli]")]];
    Data data_8000_62[0x8F] @ 0x045C7E [[comment("$88:DC7E (continued from $88:8000) Script [reli]")]];
    Data data_8000_63[0x4F] @ 0x045D41 [[comment("$88:DD41 (continued from $88:8000) Script [reli]")]];
    Data data_8000_64[0x4] @ 0x045FBC [[comment("$88:DFBC (continued from $88:8000) Script [reli]")]];
    Data data_8000_65[0xAA] @ 0x0460F2 [[comment("$88:E0F2 (continued from $88:8000) Script [reli]")]];
    Data data_8000_66[0x439] @ 0x0461AC [[comment("$88:E1AC (continued from $88:8000) Script [reli]")]];
    Data data_8000_67[0x5E] @ 0x046637 [[comment("$88:E637 (continued from $88:8000) Script [reli]")]];
    Data data_8000_68[0x417] @ 0x046740 [[comment("$88:E740 (continued from $88:8000) Script [reli]")]];
    Data data_8000_69[0x3] @ 0x047479 [[comment("$88:F479 (continued from $88:8000) Script [reli]")]];
    Data data_8000_70[0xA] @ 0x047510 [[comment("$88:F510 (continued from $88:8000) Script [reli]")]];
    Data data_8000_71[0x121] @ 0x0475F8 [[comment("$88:F5F8 (continued from $88:8000) Script [reli]")]];
    Data data_8000_72[0x116] @ 0x047764 [[comment("$88:F764 (continued from $88:8000) Script [reli]")]];
    Data data_8000_73[0x6D] @ 0x0478BA [[comment("$88:F8BA (continued from $88:8000) Script [reli]")]];
    Data data_8000_74[0x8D] @ 0x04796F [[comment("$88:F96F (continued from $88:8000) Script [reli]")]];
    Data data_8000_75[0x198] @ 0x047A79 [[comment("$88:FA79 (continued from $88:8000) Script [reli]")]];
    Data data_8000_76[0x18F] @ 0x047C9B [[comment("$88:FC9B (continued from $88:8000) Script [reli]")]];
};
Bank88Map bank_88 @ 0x040000 [[comment("bank $88: file 0x040000-0x047FFF")]];

struct Bank8EMap {
    Free free_A89E[0x762] @ 0x07289E [[comment("$8E:A89E Free space [reli] || free space after the last event script (map241 ends at 0x7289D) [iris]")]];
    Data data_B000 @ 0x073000 [[comment("$8E:B000 Some code? [reli] (end unknown)")]];
    Code sub_BAE7[0xF] @ 0x073AE7 [[comment("$8E:BAE7 Subroutine: Called by L2SASM opcode $B7 [reli]")]];
    Code sub_BAF6[0x21] @ 0x073AF6 [[comment("$8E:BAF6 Subroutine: Called by L2SASM opcode $B7 [reli]")]];
    Code sub_C1EB[0x4] @ 0x0741EB [[comment("$8E:C1EB JSL $83F559 in the chest-open path (AP hook TX) [ap] || AP hook: transmit checks from chests | JML TX ; overwrites JSL $83F559 [ap]")]];
    Code sub_C2DC @ 0x0742DC [[comment("$8E:C2DC chest: item-get done / chest emptied [ap] (end unknown)")]];
    Data data_C7C8[0x3B] @ 0x0747C8 [[comment("$8E:C7C8 'Pointers' to text at $074A03 (add $068200) [reli]")]];
    Text text_C803[0x5B] @ 0x074803 [[comment("$8E:C803 Text: capsule monters 'tastes' [reli] || capsule feeding reactions: 'Ughh - yuk!', 'Mmmm - good!', ... [iris]")]];
    Text text_C8AC[0x2F] @ 0x0748AC [[comment("$8E:C8AC Text: capsule monters 'ALI.' [reli] || capsule 'ALI.' text [iris]")]];
    Data data_CE30[0x93] @ 0x074E30 [[comment("$8E:CE30 'Pointers' to text at $0750C3 (add $068200) [reli]")]];
    Text text_CEC3[0x182] @ 0x074EC3 [[comment("$8E:CEC3 Text: shop dialogs [reli] || shop dialogs ('How many will you sell?', ...) [iris]")]];
    Data data_D0A6[0x2] @ 0x0750A6 [[comment("$8E:D0A6 $FF FF [reli]")]];
    Data data_D8C3[0x20] @ 0x0758C3 [[comment("$8E:D8C3 16 masks that can be used for bitwise operations: #$0001 b0000000000000001 #$0002 b0000000000000010 ... #$4000 b0100000000000000 #$8000 b1000000000000000 (see sub at $82:FB51) [reli]")]];
    Data data_D9A9[0x2F4] @ 0x0759A9 [[comment("$8E:D9A9 Some data? (378 * 2 bytes) (see sub at $86:8CDA) [reli] || 378 u16 values (see sub $86:8CDA) [reli]")]];
    Data data_DC9D[0x10F] @ 0x075C9D [[comment("$8E:DC9D ... [reli]")]];
    Data data_E5A0[0x22] @ 0x0765A0 [[comment("$8E:E5A0 Pointers to data at $0... entries (add $0...) [reli]")]];
    Gfx gfx_E5C2[0x3] @ 0x0765C2 [[comment("$8E:E5C2 Pointers to the battle sprites of the seven heroes: [reli] || - Maxim's battle sprites [reli]")]];
    Gfx gfx_E5C5[0x3] @ 0x0765C5 [[comment("$8E:E5C5 - Selan's battle sprites [reli]")]];
    Gfx gfx_E5C8[0x3] @ 0x0765C8 [[comment("$8E:E5C8 - Guy's battle sprites [reli]")]];
    Gfx gfx_E5CB[0x3] @ 0x0765CB [[comment("$8E:E5CB - Artea's battle sprites [reli]")]];
    Gfx gfx_E5CE[0x3] @ 0x0765CE [[comment("$8E:E5CE - Tia's battle sprites [reli]")]];
    Gfx gfx_E5D1[0x3] @ 0x0765D1 [[comment("$8E:E5D1 - Dekar's battle sprites [reli]")]];
    Gfx gfx_E5D4[0x3] @ 0x0765D4 [[comment("$8E:E5D4 - Lexis' battle sprites [reli]")]];
    Data data_E5D7[0x18] @ 0x0765D7 [[comment("$8E:E5D7 Pointers (see sub at $8E:E710) [reli]")]];
    Code sub_E5EF @ 0x0765EF [[comment("$8E:E5EF Subroutine: [reli] (end unknown)")]];
    Code sub_E642 @ 0x076642 [[comment("$8E:E642 Subroutine: [reli] (end unknown)")]];
    Code sub_E688[0x1F] @ 0x076688 [[comment("$8E:E688 Subroutine: [reli]")]];
    Code sub_E6A7[0x43] @ 0x0766A7 [[comment("$8E:E6A7 Subroutine: [reli]")]];
    Code sub_E6EA[0x16] @ 0x0766EA [[comment("$8E:E6EA Subroutine: [reli]")]];
    Code sub_E700[0x10] @ 0x076700 [[comment("$8E:E700 Subroutine: [reli]")]];
    Code sub_E710[0x41] @ 0x076710 [[comment("$8E:E710 Subroutine: [reli]")]];
    Code sub_E751[0x6F] @ 0x076751 [[comment("$8E:E751 Subroutine: [reli]")]];
    Free free_E7C0[0x240] @ 0x0767C0 [[comment("$8E:E7C0 Free space [reli]")]];
    Text text_EF00[0xE2E] @ 0x076F00 [[comment("$8E:EF00 Text: Dictionary 1 (for script and item/spell/IP descriptions) (words and syllables; sorted by decreasing length) [reli]")]];
    Code sub_FD2E[0x2D2] @ 0x077D2E [[comment("$8E:FD2E Free space [reli] || AP hook: unused region at the end of bank $8E | TODO: start items at $01D2 (index 466) | DB $1E,$0B,$01,$2B,$01,$1A,$02,$00 ; add selan | DB $1E,$0B,$01,$2B,$02,$1A,$03,$00 ; add guy | DB $1E,$0B,$01,$2B,$03,$1A,$04,$00 ; add arty [ap]")]];
};
Bank8EMap bank_8E @ 0x070000 [[comment("bank $8E: file 0x070000-0x077FFF")]];

struct Bank8FMap {
    Data data_82D6[0x7D2A] @ 0x0782D6 [[comment("$8F:82D6 Puzzle data? [reli]")]];
};
Bank8FMap bank_8F @ 0x078000 [[comment("bank $8F: file 0x078000-0x07FFFF")]];

struct Bank90Map {
    Data data_8000[0x3DF3] @ 0x080000 [[comment("$90:8000 Puzzle data? (doc unsure) [reli]")]];
};
Bank90Map bank_90 @ 0x080000 [[comment("bank $90: file 0x080000-0x087FFF")]];

struct Bank91Map {
    Text text_9AFF @ 0x089AFF [[comment("$91:9AFF ending credits, read through $91:9AFF (the LDA operands at 0x73449...) [iris]")]];
    Text text_9B00[0x6C1] @ 0x089B00 [[comment("$91:9B00 Text: credits [reli]")]];
    Data data_A1D4[0x74] @ 0x08A1D4 [[comment("$91:A1D4 Pointers [reli]")]];
    Data data_C0ED @ 0x08C0ED [[comment("$91:C0ED first switch position, Y = 18 [reli] (end unknown)")]];
    Data data_FFCA[0x12] @ 0x08FFCA [[comment("$91:FFCA Iris Treasure item number list (except Power Jelly) [reli]")]];
};
Bank91Map bank_91 @ 0x088000 [[comment("bank $91: file 0x088000-0x08FFFF")]];

struct Bank94Map {
    Unknown unk_D2BF @ 0x0A52BF [[comment("$94:D2BF ??? (Ancient Cave related) (see pointers at $83:9F73) [reli] (end unknown)")]];
    Unknown unk_D54E @ 0x0A554E [[comment("$94:D54E ??? (Ancient Cave related) (see pointers at $83:9F73) [reli] (end unknown)")]];
    Unknown unk_D61F @ 0x0A561F [[comment("$94:D61F ??? (Ancient Cave related) (see pointers at $83:9F73) [reli] (end unknown)")]];
    Data data_D95C[0xCA] @ 0x0A595C [[comment("$94:D95C Enemy party numbers for the AC (enemy parties are at SMC $0BC093) (doc unsure) [reli] || enemy party numbers for the Ancient Cave (?) [reli]")]];
    Data data_EEA0[0x52] @ 0x0A6EA0 [[comment("$94:EEA0 Blue Chest item number list [reli]")]];
};
Bank94Map bank_94 @ 0x0A0000 [[comment("bank $94: file 0x0A0000-0x0A7FFF")]];

struct Bank96Map {
    Gfx gfx_FE3C[0xFE] @ 0x0B7E3C [[comment("$96:FE3C Palette? [reli]")]];
    Unknown unk_FF3A[0x2] @ 0x0B7F3A [[comment("$96:FF3A unknown; bank $96 has no real free space [iris]")]];
    Unknown unk_FF3A_2[0xC3] @ 0x0B7F3D [[comment("$96:FF3D (continued from $96:FF3A) unknown; bank $96 has no real free space [iris]")]];
    Unknown unk_FF3C @ 0x0B7F3C [[comment("$96:FF3C ??? (doc unsure) [reli] (end unknown)")]];
};
Bank96Map bank_96 @ 0x0B0000 [[comment("bank $96: file 0x0B0000-0x0B7FFF")]];

struct Bank97Map {
    Text text_85B4[0x1912] @ 0x0B85B4 [[comment("$97:85B4 Text: item/spell/IP descriptions [reli] || item / spell / IP descriptions, compressed with dictionary 2 (pointers at 0xB8000) [iris]")]];
    Text text_85B4_2[0x80] @ 0x0B9EC7 [[comment("$97:9EC7 (continued from $97:85B4) Text: item/spell/IP descriptions [reli] || item / spell / IP descriptions, compressed with dictionary 2 (pointers at 0xB8000) [iris]")]];
    Text text_85B4_3[0x1159] @ 0x0B9F48 [[comment("$97:9F48 (continued from $97:85B4) Text: item/spell/IP descriptions [reli] || item / spell / IP descriptions, compressed with dictionary 2 (pointers at 0xB8000) [iris]")]];
    Code sub_9EC6 @ 0x0B9EC6 [[comment("$97:9EC6 AP hook: descriptions [ap] (end unknown)")]];
    Code sub_9F47 @ 0x0B9F47 [[comment("$97:9F47 AP hook: descriptions [ap] (end unknown)")]];
    Data data_B126[0x100] @ 0x0BB126 [[comment("$97:B126 $97:B126 arctangent table, read by $85:DB43 (size assumed: the next documented range starts at 0xBB226) [iris]")]];
    Unknown unk_B226 @ 0x0BB226 [[comment("$97:B226 ??? (doc unsure) [reli] (end unknown)")]];
    Data data_B99E[0xE] @ 0x0BB99E [[comment("$97:B99E Related to EXP at next level [reli]")]];
    Data data_C493[0xAA] @ 0x0BC493 [[comment("$97:C493 $97:C493 Ancient Cave formation table used by $86:9D5D (layout unknown) [iris]")]];
    Data data_CB70[0x188] @ 0x0BCB70 [[comment("$97:CB70 Some monster-related data... (related to sprites?) [doc's SNES column says $CB30; the file offset is right] [reli] || monster-related data, maybe sprites [reli]")]];
    Gfx gfx_FC40[0x100] @ 0x0BFC40 [[comment("$97:FC40 Some palettes? [reli] || some palettes (?) [reli]")]];
    Unknown unk_FDE6 @ 0x0BFDE6 [[comment("$97:FDE6 ??? (see sub $81:851E) [reli] (end unknown)")]];
    Data data_FE26[0x20] @ 0x0BFE26 [[comment("$97:FE26 Data (see sub $85:D080) [reli]")]];
};
Bank97Map bank_97 @ 0x0B8000 [[comment("bank $97: file 0x0B8000-0x0BFFFF")]];

struct Bank98Map {
    Data data_8000[0xAB] @ 0x0C0000 [[comment("$98:8000 Pointers to data at $0C02AB (3 bytes long) (add $C0200?) [reli]")]];
    Spc spc_80AB[0x7F55] @ 0x0C00AB [[comment("$98:80AB Data (SPC 'instruments'?) Format: (for each 'instrument') 8 'header bytes' (first 2 bytes: defining length of 'data') + variable number of 'data' bytes [reli] || Data (SPC 'instruments'?) [reli]")]];
};
Bank98Map bank_98 @ 0x0C0000 [[comment("bank $98: file 0x0C0000-0x0C7FFF")]];

struct Bank99Map {
    Gfx gfx_DE6C[0x1C00] @ 0x0CDE6C [[comment("$99:DE6C Graphics: Selan battle sprites [reli]")]];
    Gfx gfx_FF6C[0x80] @ 0x0CFF6C [[comment("$99:FF6C Graphics?: a sprite? [reli]")]];
};
Bank99Map bank_99 @ 0x0C8000 [[comment("bank $99: file 0x0C8000-0x0CFFFF")]];

struct Bank9AMap {
    Gfx gfx_F970[0x600] @ 0x0D7970 [[comment("$9A:F970 Graphics: font (for dialogues?) Tile Layer Pro: 1BPP format. [reli]")]];
    Gfx gfx_FF70[0x80] @ 0x0D7F70 [[comment("$9A:FF70 Graphics: Ruby Apple? [reli]")]];
};
Bank9AMap bank_9A @ 0x0D0000 [[comment("bank $9A: file 0x0D0000-0x0D7FFF")]];

struct Bank9BMap {
    Gfx gfx_BC08[0x4331] @ 0x0DBC08 [[comment("$9B:BC08 Palettes for maps (dungeons and towns) (doc unsure) [reli]")]];
    Free free_FFE8[0x8] @ 0x0DFFE8 [[comment("$9B:FFE8 Free space? [reli]")]];
    Gfx gfx_FFF0[0x10] @ 0x0DFFF0 [[comment("$9B:FFF0 raw sprite graphics (structures/sprites.py sprite bank) [iris]")]];
};
Bank9BMap bank_9B @ 0x0D8000 [[comment("bank $9B: file 0x0D8000-0x0DFFFF")]];

struct Bank9CMap {
    Gfx gfx_8000[0x3400] @ 0x0E0000 [[comment("$9C:8000 Graphics: sprites Ship? [reli]")]];
    Gfx gfx_8000_2[0x1800] @ 0x0E6800 [[comment("$9C:E800 (continued from $9C:8000) Graphics: sprites Ship? [reli]")]];
    Gfx gfx_B400[0x1A00] @ 0x0E3400 [[comment("$9C:B400 Graphics: Dekar battle sprites [reli]")]];
    Gfx gfx_CE00[0x1A00] @ 0x0E4E00 [[comment("$9C:CE00 Graphics: Lexis battle sprites [reli]")]];
};
Bank9CMap bank_9C @ 0x0E0000 [[comment("bank $9C: file 0x0E0000-0x0E7FFF")]];

struct Bank9DMap {
    Gfx gfx_8000[0x6000] @ 0x0E8000 [[comment("$9D:8000 Graphics: sprites [reli]")]];
    Gfx gfx_8000_2[0x800] @ 0x0EF800 [[comment("$9D:F800 (continued from $9D:8000) Graphics: sprites [reli]")]];
    Gfx gfx_E000[0x1800] @ 0x0EE000 [[comment("$9D:E000 Graphics: Maxim battle sprites [reli]")]];
};
Bank9DMap bank_9D @ 0x0E8000 [[comment("bank $9D: file 0x0E8000-0x0EFFFF")]];

struct Bank9EMap {
    Gfx gfx_8000_3[0x2FFF] @ 0x0F0001 [[comment("$9E:8001 (continued from $9E:8000) Graphics: sprites [reli]")]];
    Gfx gfx_8000 @ 0x0F0000 [[comment("$9E:8000 Graphics: Artea battle sprites [reli] (end unknown)")]];
    Text text_C7E8[0x1458] @ 0x0F47E8 [[comment("$9E:C7E8 Text: items/weapons/armor/... names [reli]")]];
    Text text_C7E8_2[0x47] @ 0x0F5C41 [[comment("$9E:DC41 (continued from $9E:C7E8) Text: items/weapons/armor/... names [reli]")]];
    Text text_C7E8_3[0xD7] @ 0x0F5C89 [[comment("$9E:DC89 (continued from $9E:C7E8) Text: items/weapons/armor/... names [reli]")]];
    Text text_C7E8_4[0x6B] @ 0x0F5D61 [[comment("$9E:DD61 (continued from $9E:C7E8) Text: items/weapons/armor/... names [reli]")]];
    Code sub_DC40 @ 0x0F5C40 [[comment("$9E:DC40 AP hook: names | DB 'Selan       ' ; overwrites 'Wind key    ' ; TODO instead use 'PURIFIA     ' | DB 'Guy         ' ; overwrites 'Cloud key   ' ; TODO instead use 'Tag ring    ' | DB 'Arty        ' ; overwrites 'Light key   ' ; TODO instead use 'Tag ring    ' | DB 'Dekar       ' ; overwrites 'Sword key   ' ; TODO instead use 'RAN-RAN step' [ap] (end unknown)")]];
    Code sub_DC88 @ 0x0F5C88 [[comment("$9E:DC88 AP hook: names | DB 'JELZE       ' ; overwrites 'Magma key   ' | DB 'FLASH       ' ; overwrites 'Heart key   ' | DB 'GUSTO       ' ; overwrites 'Ghost key   ' | DB 'ZEPPY       ' ; overwrites 'Trial key   ' [ap] (end unknown)")]];
    Code sub_DD60 @ 0x0F5D60 [[comment("$9E:DD60 AP hook: name | DB 'AP item     ' ; overwrites 'Key30       ' [ap] (end unknown)")]];
    Text text_E2AC[0x10CF] @ 0x0F62AC [[comment("$9E:E2AC Text: Dictionary 2 (for item/spell/IP descriptions) [reli]")]];
    Gfx gfx_F37B[0x200] @ 0x0F737B [[comment("$9E:F37B Graphics: sprites (4x4) Enemy map sprites [reli] || - Faces South [reli]")]];
    Gfx gfx_F37B_2[0x1FF] @ 0x0F757C [[comment("$9E:F57C (continued from $9E:F37B) Graphics: sprites (4x4) Enemy map sprites [reli] || - Faces South [reli]")]];
    Gfx gfx_F37B_3[0x1FF] @ 0x0F777C [[comment("$9E:F77C (continued from $9E:F37B) Graphics: sprites (4x4) Enemy map sprites [reli] || - Faces South [reli]")]];
    Gfx gfx_F37B_4[0x1FF] @ 0x0F797C [[comment("$9E:F97C (continued from $9E:F37B) Graphics: sprites (4x4) Enemy map sprites [reli] || - Faces South [reli]")]];
    Gfx gfx_F37B_5[0x1FF] @ 0x0F7B7C [[comment("$9E:FB7C (continued from $9E:F37B) Graphics: sprites (4x4) Enemy map sprites [reli] || - Faces South [reli]")]];
    Data data_F57B @ 0x0F757B [[comment("$9E:F57B - Walks South [reli] (end unknown)")]];
    Data data_F77B @ 0x0F777B [[comment("$9E:F77B - Faces West [reli] (end unknown)")]];
    Data data_F97B @ 0x0F797B [[comment("$9E:F97B - Walks West [reli] (end unknown)")]];
    Data data_FB7B @ 0x0F7B7B [[comment("$9E:FB7B - Faces North [reli] (end unknown)")]];
    Data data_FD7B[0x200] @ 0x0F7D7B [[comment("$9E:FD7B - Walks North [reli]")]];
    Gfx gfx_FF7B[0x80] @ 0x0F7F7B [[comment("$9E:FF7B Graphics: sprite (2x2) [reli]")]];
};
Bank9EMap bank_9E @ 0x0F0000 [[comment("bank $9E: file 0x0F0000-0x0F7FFF")]];

struct Bank9FMap {
    Gfx gfx_8500[0x1000] @ 0x0F8500 [[comment("$9F:8500 Graphics: font Tile Layer Pro: Game Boy format. For menus (including (?) menu icons like sword, ...) [reli]")]];
    Gfx gfx_9500[0x1400] @ 0x0F9500 [[comment("$9F:9500 Graphics: sprites (doc unsure) [reli] || - Guy battle sprites [reli]")]];
    Code sub_A900[0x1180] @ 0x0FA900 [[comment("$9F:A900 - Item sprites (when you get an item from a chest, ...) [reli] || AP hook: sprite | sold out item | org $96F9BA  ; properties [ap]")]];
    Gfx gfx_BA80[0x1000] @ 0x0FBA80 [[comment("$9F:BA80 Graphics: font (or 2 fonts?) Tile Layer Pro: Game Boy format. [reli]")]];
    Gfx gfx_CA80[0x3580] @ 0x0FCA80 [[comment("$9F:CA80 Graphics: sprites [reli]")]];
};
Bank9FMap bank_9F @ 0x0F8000 [[comment("bank $9F: file 0x0F8000-0x0FFFFF")]];

struct BankA0Map {
    Gfx gfx_8000[0x8000] @ 0x100000 [[comment("$A0:8000 Graphics: sprites [reli]")]];
};
BankA0Map bank_A0 @ 0x100000 [[comment("bank $A0: file 0x100000-0x107FFF")]];

struct BankA1Map {
    Gfx gfx_8000[0xB80] @ 0x108000 [[comment("$A1:8000 Graphics: sprites [reli]")]];
    Gfx gfx_96F2[0xA00] @ 0x1096F2 [[comment("$A1:96F2 Graphics: sprites [reli] || 'Slashing' animation? [reli]")]];
    Gfx gfx_A0F2[0x800] @ 0x10A0F2 [[comment("$A1:A0F2 Doom Island map sprite(s?) [reli]")]];
    Gfx gfx_B022[0x4F80] @ 0x10B022 [[comment("$A1:B022 Graphics: map sprites (NPCs, enemies, fire arrow, ...) [reli]")]];
    Unknown unk_FFA2[0x5E] @ 0x10FFA2 [[comment("$A1:FFA2 ??? [reli]")]];
};
BankA1Map bank_A1 @ 0x108000 [[comment("bank $A1: file 0x108000-0x10FFFF")]];

struct BankA2Map {
    Gfx gfx_8000[0x8000] @ 0x110000 [[comment("$A2:8000 Graphics: map sprites [reli]")]];
};
BankA2Map bank_A2 @ 0x110000 [[comment("bank $A2: file 0x110000-0x117FFF")]];

struct BankA3Map {
    Gfx gfx_8000[0x1E00] @ 0x118000 [[comment("$A3:8000 Graphics: map sprites [reli]")]];
    Gfx gfx_8000_2[0x61FF] @ 0x119E01 [[comment("$A3:9E01 (continued from $A3:8000) Graphics: map sprites [reli]")]];
    Gfx gfx_9E00 @ 0x119E00 [[comment("$A3:9E00 Erim map sprites [reli] (end unknown)")]];
};
BankA3Map bank_A3 @ 0x118000 [[comment("bank $A3: file 0x118000-0x11FFFF")]];

struct BankA4Map {
    Gfx gfx_8000[0x8000] @ 0x120000 [[comment("$A4:8000 Graphics: map sprites [reli]")]];
};
BankA4Map bank_A4 @ 0x120000 [[comment("bank $A4: file 0x120000-0x127FFF")]];

struct BankA5Map {
    Gfx gfx_8000 @ 0x128000 [[comment("$A5:8000 Graphics: map sprites [reli] (end unknown)")]];
    Gfx gfx_BF00[0x400] @ 0x12BF00 [[comment("$A5:BF00 Arek sprites [reli]")]];
    Text text_DF9C[0x360] @ 0x12DF9C [[comment("$A5:DF9C Text: Capsule Monsters attacks names [reli]")]];
    Gfx gfx_E2FC[0x300] @ 0x12E2FC [[comment("$A5:E2FC Graphics: Text windows ('Game Boy format' with Tile Layer Pro) see sub ~ $83:B03B [reli]")]];
    Gfx gfx_E5FC[0x1800] @ 0x12E5FC [[comment("$A5:E5FC Graphics: sprites (2x2) [reli]")]];
    Gfx gfx_FDFC[0x200] @ 0x12FDFC [[comment("$A5:FDFC Graphics: 1 'dead people' sprite (4x4) [reli]")]];
    Data data_FFFC[0x4] @ 0x12FFFC [[comment("$A5:FFFC $00 00 00 00 [reli]")]];
};
BankA5Map bank_A5 @ 0x128000 [[comment("bank $A5: file 0x128000-0x12FFFF")]];

struct BankA6Map {
    Gfx gfx_8000[0x3000] @ 0x130000 [[comment("$A6:8000 Graphics: sprites [reli]")]];
    Gfx gfx_B000[0xC00] @ 0x133000 [[comment("$A6:B000 Palettes? [reli]")]];
    Gfx gfx_BC00[0x300] @ 0x133C00 [[comment("$A6:BC00 Graphics: sprites [reli]")]];
    Gfx gfx_BC00_2[0x1720] @ 0x134000 [[comment("$A6:C000 (continued from $A6:BC00) Graphics: sprites [reli]")]];
    Gfx gfx_BC00_3[0x1200] @ 0x135820 [[comment("$A6:D820 (continued from $A6:BC00) Graphics: sprites [reli]")]];
    Gfx gfx_BF00[0x100] @ 0x133F00 [[comment("$A6:BF00 Half-palette (128 colors) used for a great number of sprites - almost all the sprites on all maps (towns, dungeons, ...) including sprites on the world map. Known exceptions: sprites used during the flight of Excerion to Doom Island (Excerion, Doom Island, ...). - Not used for the sprites of the status screen and for the battle sprites. [reli] || half-palette used by almost all map sprites (structures/sprites.py palette_offset) [iris]")]];
    Gfx gfx_D720[0x100] @ 0x135720 [[comment("$A6:D720 Dual Blade sprite [reli]")]];
    Data data_F420[0xF0] @ 0x137420 [[comment("$A6:F420 Level up data for CM? (doc unsure) [reli]")]];
    Gfx gfx_F60D[0x480] @ 0x13760D [[comment("$A6:F60D Graphics: sprites [reli]")]];
};
BankA6Map bank_A6 @ 0x130000 [[comment("bank $A6: file 0x130000-0x137FFF")]];

struct BankA7Map {
    Spc spc_87FB[0x7805] @ 0x1387FB [[comment("$A7:87FB SPC [reli] || SPC data after the A7 resource table (banks $A7-$A8) [iris]")]];
};
BankA7Map bank_A7 @ 0x138000 [[comment("bank $A7: file 0x138000-0x13FFFF")]];

struct BankA8Map {
    Spc spc_8000[0x576A] @ 0x140000 [[comment("$A8:8000 SPC [reli]")]];
    Spc spc_D76A[0x105] @ 0x14576A [[comment("$A8:D76A SPC: MUUS 2 [reli]")]];
    Gfx gfx_D86F[0x862] @ 0x14586F [[comment("$A8:D86F Bg data and tiles for Title Screens Natsume / 'Lufia: RotS' (+ other things?) [reli]")]];
    Gfx gfx_E0D1[0x6EA] @ 0x1460D1 [[comment("$A8:E0D1 Tiles for end of game credits and 'The End' screen [reli]")]];
    Data data_E7BB[0x1845] @ 0x1467BB [[comment("$A8:E7BB Level bg data? [reli]")]];
};
BankA8Map bank_A8 @ 0x140000 [[comment("bank $A8: file 0x140000-0x147FFF")]];

struct BankA9Map {
    Data data_8A00 @ 0x148A00 [[comment("$A9:8A00 Level bg data (layer 1) [reli] (end unknown)")]];
    Data data_92C1 @ 0x1492C1 [[comment("$A9:92C1 Level bg data (layer 2) 'The 33 edits a small part near the stairs to map 07(not the one that leads to the switch but the bridge).' (Jigglysaint) [reli] (end unknown)")]];
};
BankA9Map bank_A9 @ 0x148000 [[comment("bank $A9: file 0x148000-0x14FFFF")]];

struct BankB6Map {
    Data data_9917[0x66E9] @ 0x1B1917 [[comment("$B6:9917 Level bg TSA? [reli]")]];
};
BankB6Map bank_B6 @ 0x1B0000 [[comment("bank $B6: file 0x1B0000-0x1B7FFF")]];

struct BankB8Map {
    Gfx gfx_F9D8[0x628] @ 0x1C79D8 [[comment("$B8:F9D8 Tiles: Arek's Shrine [reli]")]];
};
BankB8Map bank_B8 @ 0x1C0000 [[comment("bank $B8: file 0x1C0000-0x1C7FFF")]];

struct BankB9Map {
    Gfx gfx_8000[0x274A] @ 0x1C8000 [[comment("$B9:8000 Tiles: Arek's Shrine [reli]")]];
};
BankB9Map bank_B9 @ 0x1C8000 [[comment("bank $B9: file 0x1C8000-0x1CFFFF")]];

struct BankC2Map {
    Compressed lz_D6E1[0x291F] @ 0x2156E1 [[comment("$C2:D6E1 Battle bg tiles (compressed) [reli]")]];
};
BankC2Map bank_C2 @ 0x210000 [[comment("bank $C2: file 0x210000-0x217FFF")]];

struct BankC3Map {
    Compressed lz_8000[0x8000] @ 0x218000 [[comment("$C3:8000 Battle bg tiles (compressed) [reli]")]];
};
BankC3Map bank_C3 @ 0x218000 [[comment("bank $C3: file 0x218000-0x21FFFF")]];

struct BankC4Map {
    Compressed lz_8000[0x3292] @ 0x220000 [[comment("$C4:8000 Battle bg tiles (compressed) [reli]")]];
    Compressed lz_B292[0x1380] @ 0x223292 [[comment("$C4:B292 Battle bg data (compressed) [reli]")]];
    Compressed lz_DB13[0x24ED] @ 0x225B13 [[comment("$C4:DB13 Capsule Monster battle sprites (compressed) [doc's file column says 0x22B488 (copy error); SNES column used] [reli]")]];
};
BankC4Map bank_C4 @ 0x220000 [[comment("bank $C4: file 0x220000-0x227FFF")]];

struct BankC5Map {
    Compressed lz_8000[0x3288] @ 0x228000 [[comment("$C5:8000 Capsule Monster battle sprites (compressed) [reli]")]];
    Compressed lz_B288 @ 0x22B288 [[comment("$C5:B288 Goblin ($01) battle sprite (compressed) [reli] (end unknown)")]];
};
BankC5Map bank_C5 @ 0x228000 [[comment("bank $C5: file 0x228000-0x22FFFF")]];

struct BankC9Map {
    Compressed lz_9FCB @ 0x249FCB [[comment("$C9:9FCB Daos battle sprite (compressed) [reli] (end unknown)")]];
    Compressed lz_B2CC @ 0x24B2CC [[comment("$C9:B2CC Master ($86) battle sprite (compressed) [reli] (end unknown)")]];
};
BankC9Map bank_C9 @ 0x248000 [[comment("bank $C9: file 0x248000-0x24FFFF")]];

struct BankCBMap {
    Gfx gfx_FB65[0x49B] @ 0x25FB65 [[comment("$CB:FB65 Tiles for intro (Arek's Island panorama) (bg1 and bg2 layers?) [reli]")]];
};
BankCBMap bank_CB @ 0x258000 [[comment("bank $CB: file 0x258000-0x25FFFF")]];

struct BankCCMap {
    Gfx gfx_8000[0x2426] @ 0x260000 [[comment("$CC:8000 Tiles for intro (Arek's Island panorama) (bg1 and bg2 layers?) [reli]")]];
    Gfx gfx_A426[0x1C0F] @ 0x262426 [[comment("$CC:A426 Tiles for intro (Arek's Island panorama) (bg3 layer?) [reli]")]];
    Gfx gfx_C035 @ 0x264035 [[comment("$CC:C035 Tiles for intro (Arek's Island panorama) (sprites) [reli] (end unknown)")]];
    Gfx gfx_DBC2[0x243E] @ 0x265BC2 [[comment("$CC:DBC2 Overworld tiles (Mode 7) [reli]")]];
};
BankCCMap bank_CC @ 0x260000 [[comment("bank $CC: file 0x260000-0x267FFF")]];

struct BankCDMap {
    Gfx gfx_8000[0xC9] @ 0x268000 [[comment("$CD:8000 Overworld tiles (Mode 7) [reli]")]];
    Data data_80C9[0x3F31] @ 0x2680C9 [[comment("$CD:80C9 Overworld 'tile numbers' (Mode 7 map)? [reli]")]];
    Gfx gfx_BFFA[0x18BD] @ 0x26BFFA [[comment("$CD:BFFA Sprite(s) for the big 'Lufia 2 - Rise of the Sinistrals' logo [reli]")]];
    Gfx gfx_D8B7[0xF3C] @ 0x26D8B7 [[comment("$CD:D8B7 Undersea tiles (Mode 7) [reli]")]];
    Data data_E7F3 @ 0x26E7F3 [[comment("$CD:E7F3 Undersea 'tile numbers' (Mode 7 map)? [reli] (end unknown)")]];
};
BankCDMap bank_CD @ 0x268000 [[comment("bank $CD: file 0x268000-0x26FFFF")]];

struct BankCFMap {
    Compressed lz_E2FE[0x2] @ 0x27E2FE [[comment("$CF:E2FE Last piece of compressed data ($00 00) [reli]")]];
    Gfx gfx_E300[0xD00] @ 0x27E300 [[comment("$CF:E300 Graphics: monster map sprites? [reli] || monster map sprites (?) [reli]")]];
    Unknown unk_F6B5 @ 0x27F6B5 [[comment("$CF:F6B5 ? ? [reli] (end unknown)")]];
    Data data_F730[0xF0] @ 0x27F730 [[comment("$CF:F730 Numbers bg TSA for maps $02 to $F1 [reli]")]];
    Gfx gfx_F820[0xF0] @ 0x27F820 [[comment("$CF:F820 Numbers bg tiles for maps $02 to $F1 [reli]")]];
    Data data_F910[0xF0] @ 0x27F910 [[comment("$CF:F910 Numbers bg layers data byte for maps $02 to $F1 [reli]")]];
    Gfx gfx_FA0A[0xF0] @ 0x27FA0A [[comment("$CF:FA0A Numbers Palette numbers for maps $02 to $F1 [reli]")]];
    Gfx gfx_FBA8[0xF0] @ 0x27FBA8 [[comment("$CF:FBA8 Numbers ??? for maps $02 to $F1 (related to palettes for animated tiles (water)?) = number of a pointer at $CF:FC98 [reli]")]];
    Data data_FC98[0x24] @ 0x27FC98 [[comment("$CF:FC98 Pointers (2 bytes long => 18 pointers) (see data at $CF:FBA8) [reli]")]];
};
BankCFMap bank_CF @ 0x278000 [[comment("bank $CF: file 0x278000-0x27FFFF")]];



// =====================================================================================================
//  8. PATCH HOOK SITES
// =====================================================================================================
//  Where patches overwrite vanilla code. Hook sites are entries in the section-7 bank map, tagged
//  [ap] (src/patches/archipelago/ancient_cave/basepatch.asm) or [iris hook] (src/patches/HEROgold/*.asm
//  and patcher.set_spawn_location). The entry sits on the first byte of the overwritten instruction.


// =====================================================================================================
//  9. EXPANSION AREA AND IRIS-OWNED ADDRESSES (patched ROMs only)
// =====================================================================================================
//  0x280000-0x2FFFFF  mirror of 0x200000-0x27FFFF in the 3 MiB file; Iris's free pool (not zeroed).
//  0x282000 ($D0:A000) FRUE / Spekkio / Kureji move the monster table here.
//  0x310000 ($E2:8000) --scale-encounters: 99-byte level -> formation table, 0x310063 LOW,
//                      0x310064 RANGE, 0x310065 hook code (hooked from $83:B9EC).
//  0x320000 ($E4:8000) ZONE_DATA_FREESPACE: relocated ZoneData (emulator-verified, HER-206).
//  0x340000 ($E8:8000) EVENT_SCRIPT_FREESPACE: NOT usable for events (needs banks $80-$BF, HER-232).
//  0x400000           EXPANDED_ROM_SIZE (4 MiB).

struct ScaleEncounters {
    u8 level_to_formation[99];
    s8 low;
    u8 range;
};
struct IrisExpansion {
    if (std::mem::size() > 0x310065) { ScaleEncounters scale_encounters @ 0x310000; }
};
IrisExpansion iris_expansion @ 0x0;


// =====================================================================================================
//  10. RAM MAP (comments only)
// =====================================================================================================
//  $7E:0000-$7E:1FFF is mirrored in banks $00-$3F/$80-$BF; DBR-relative reads only reach it there.
//
//  Party and characters
//    $7E:0A7A         party count / leader byte (copied with the slots at $81:8072)
//    $7E:0A7B-$0A7E   active party slots 1-4: character index ($FF = empty; test slot < 7)
//    $7E:0A7F         party slot 5: $07 when a capsule is in the party, else $FF
//    $7E:0A80+        stat-block pointer per party slot (2 bytes each; $0A88 = $10DF for the capsule)
//    $7E:0A8D-$0B4C   inventory (u16 item | quantity << 9; $0000 = free; see $82:FB94)
//    $7E:0BAD+i*$BE   statblock of character i (0-6 Maxim..Lexis, 7 = capsule at $10DF)
//    $7E:0BBB+i*$BE   level (read by $80:B909 before scripted battles, $86:9CCE for AC tiers)
//    $7E:0BBC+i*$BE   status byte
//    $7E:0B50         bit $80 cleared after a capsule joins;  $7E:0B51 bit 1 = special new-game start
//    $7E:1854         copied from the character templates' unknown u16 (?)
//  Capsule (member 7)
//    $7E:10DF name, $10ED level, $1104 max HP, $1108-$1115 ATP DFP STR AGL INT GUT MGR,
//    $1124-$1126 record pointer (bank $97), $1127-$112E copy of record +0x23..+0x2A
//    ($1129 attack offset, $112B reaction offset), $1130 HP, $1134-$113D base stats,
//    $113E-$1140 EXP, $1141-$1143 EXP for level ($82:CE52), $1144 capsule index (species*5+form-1)
//    $11A3 species (0-6), $11A4 form (1-5), $11A5 cleared by $82:C37B, $11A6+s per-species byte,
//    $11BB+s owned flag, $11C2-$11D5 cleared by $82:C37B, $10EE cleared when built, $10F0 (capsule_tag)
//    $7F:F180+s*5 name per species, $7F:F1A3+s level per species, $7F:F1AA+s*3 EXP per species
//  Events and maps
//    $7E:077E+n/8     event flag n = bit n%8 (low bit first); helper $80:BE30
//    $7E:097B-$0996   warp destinations unlocked (0x00 locked, 0xFF unlocked)
//    $7E:099D         set to $FF at the end of the new-game setup ($83:ADC2)
//    $7E:099E-$09A0   address of the current map script (set by $83:B5AD from $05AC)
//    $7E:09B9         event script bank (interpreter: LDA $09B9 : PHA : PLB)
//    $7E:05AC         current map number;  $7E:05B8 entrance (spawn) number;  $7E:05B2 cleared at spawn
//    $7E:0A0B         spell number for $81:F446 (-> $0A0D = low word of the spell record)
//    $7E:09CD/$09CF   quantity / item for the add-item routine $82:E80C
//    $7E:09FA/$09FC/$09FE  monster number / EXP / GOLD scratch ($81:FBDB); also char number / level ($81:F87F)
//    $7E:0A1C-$0A29   min stats at a level (HP MP STR AGL INT GUT MGR), output of $81:F87F
//    $7E:09C4         low word of the active capsule record ($82:C38B); $09D9/$09DB/$09DD species*1/*3/*5
//  Battle
//    $7F:F44E         acting unit ($10 = the capsule)
//    $7F:F454/$F456   chosen action type / its parameter (dispatcher $81:A85C)
//    $7F:F8A3         battle type ($FF scripted; 0 for roaming monsters; $FE only from the AP death link)
//    $7F:F8A4         pending formation id (writers: $80:B919, $86:9CE6, $86:9D5D, $83:B9EC)
//    $7F:D4EF         chest item id being opened (AP: bit $0200 = Iris item, $4200 = blue chest)
//    $7F:D4F1         stored by $80:A435 (script item get)
//  Archipelago base patch SRAM: $F0:2000+ (check counters, received items).
