// Increase evaluation ceilings: the script walkers below place thousands of
// nested, computed-address patterns (224 monsters + 242 maps + 141 IP effects,
// each fanning out into per-instruction structs).
#pragma pattern_limit 4000000
#pragma array_limit 4000000

import std.mem;   // std::mem::read_unsigned, used for terminator look-ahead

struct character {
    u16 health;
    u16 mana;
    u16 strength;
    u16 agil;
    u16 intel;
    u16 gut;
    u16 mgr;
};

struct initEquip {
    u16 weapon;
    u16 armor;
    u16 shield;
    u16 helmet;
    u16 ring;
    u16 jewel;
};

struct charLevel {
    u8 level;
};

struct charXp {
    u24 xp;
};

struct FullCharacter {
    u48 name;
    charLevel;
    u24 empty;
    u8 ff;
    charXp;
    initEquip;
};

FullCharacter Maxim @ 0x2B2B0;
FullCharacter Selan @ 0x2B2CD;
FullCharacter Guy @ 0x2B2F1;
FullCharacter Arty @ 0x2B30E;
FullCharacter Tia @ 0x2B333;
FullCharacter Dekar @ 0x2B353;
FullCharacter Lexis @ 0x2B370;

// Overworld palettes
struct OverPalette {
    u8 palette_index;
    u8 unknown[12];
};
OverPalette overPalettes[3] @ 0x36CA6;

// Overworld sprites metadata
struct OverSprite {
    u8 unknown[3];
    u24 sprite_pointer;
};
OverSprite overSprites[6] @ 0x37086;

// Map event table
struct MapEventEntry {
    u16 eventlist_lowbytes;
    u8 eventlist_highbyte;
    u16 npc_lowbytes;
    u8 npc_highbyte;
    u16 map_name_pointer;
};
MapEventEntry mapEvents[242] @ 0x38010;

// Roaming NPCs
struct RoamingNPC {
    u8 map_npc_event_index;
    u8 sprite_index;
    u8 map_index;
    u8 map_npc_index;
};
RoamingNPC roamingNPCs[34] @ 0x3AE4E;

// Capsule level entries
struct CapsuleLevel {
    u8 level;
};
CapsuleLevel capsuleLevels[7] @ 0x764C4;

// Word pointers
struct WordPtr {
    u16 word_pointer;
};
WordPtr words[640] @ 0x76A00;

// Ancient chests and blue chests
struct AncientChest2 {
    u16 item_index;
};
AncientChest2 ancientChests2[9] @ 0x8FFDC;

struct BlueChest {
    u16 item_index;
};
BlueChest blueChests[41] @ 0xA6EA0;

struct AncientChest1 {
    u16 item_index;
};
AncientChest1 ancientChests1[31] @ 0xA713D;

// Monster table
struct Monster {
    u8 name[13];
    u8 level;
    u8 unknown;
    u8 battle_sprite;
    u8 palette;
    u16 hp;
    u16 mp;
    u16 attack;
    u16 defense;
    u8 agility;
    u8 intelligence;
    u8 guts;
    u8 magic_resistance;
    u16 xp;
    u16 gold;
    u8 misc;
};
// NOTE: 0xB05C0 is a *pointer table* (224 x u16 relative offsets), not a contiguous record
// array -- reading `Monster` records straight off 0xB05C0 misaligns (it parses the pointer
// bytes as fields). The monster records are instead placed, correctly aligned, via the
// pointer-accurate `monsterScripts` walk at the bottom of this file (which also adds the
// inline attack/defense scripts). So no direct `Monster monsters[224] @ 0xB05C0;` here.

// Item names (text table)
struct ItemName {
    u8 name[12];
};
ItemName itemNames[467] @ 0xF47E8;

// Character base stats table
struct CharacterStats {
    u16 hp;
    u16 mp;
    u16 strength;
    u16 agl;
    u16 int;
    u16 gut;
    u16 mgr;
};
CharacterStats characters[7] @ 0xBB93C;

// Map formations
struct MapFormation {
    u16 reference_pointer;
};
MapFormation mapFormations[248] @ 0xBB9AC;

// Formation entries
struct Formation {
    u8 monster_indexes[8];
};
Formation formations[192] @ 0xBBE93;

// Boss formation pointers
struct BossFormation {
    u16 reference_pointer;
};
BossFormation bossFormations[39] @ 0xBC53D;

// Sprite metadata
struct SpriteMeta {
    u8 width;
    u8 height_misc;
};
SpriteMeta spriteMeta[134] @ 0xBCA64;

// Cap palette colors (16 colors, each 2 bytes)
struct CapPalette {
    u16 colors[16];
};
CapPalette capPalettes[35] @ 0xBD258;

// Capsule definitions (partial mapping)
struct Capsule {
    u8 name[12];
    u8 zero;
    u8 capsule_class;
    u8 alignment;
    u8 start_skills[3];
    u8 upgrade_skills[3];
    u8 hp;
    u8 attack;
    u8 defense;
    u8 strength;
    u8 agility;
    u8 intelligence;
    u8 guts;
    u8 magic_resistance;
    u8 hp_factor;
    u8 strength_factor;
    u8 agility_factor;
    u8 intelligence_factor;
    u8 guts_factor;
    u8 magic_resistance_factor;
};
// NOTE: 0xBDCB8 is a *pointer table* (35 x u16 relative offsets), not a contiguous record
// array -- reading `Capsule` records straight off 0xBDCB8 misaligns (it parses the pointer
// bytes as fields). The `Capsule` struct is instead placed, correctly aligned, via the
// pointer-accurate `capsuleScripts` walk at the bottom of this file (which also adds the
// attack/reaction scripts). So no direct `Capsule capsules[35] @ 0xBDCB8;` placement here.

// Shop pointers and definitions
struct ShopItem {
    u16 item_index;
    u16 price;
};

// Shop data header: read by `Shop.from_table` as `unknown1`, `shop_type`, `zero`.
// The shop body (sections and items) follows this 3-byte header and is
// variable-length; code in `structures/shop.py` discovers section boundaries
// using the next table pointer for the following shop.
struct ShopDef {
    u8 identifier; // unknown1 in code, mapped to ShopIdentifier
    u8 shop_type;  // mapped to ShopTypes
    u8 zero;       // should be 0x00
    // shop sections and items follow here (variable length)
};

// Each entry in the shops table is a 2-byte reference to the shop data.
// The reference values are likely offsets; if they need a bank/base addition,
// adjust accordingly when viewing in ImHex.
struct ShopPointer {
    u16 reference_pointer;
    // Shop data is stored at base + reference_pointer. Base address taken from
    // vanilla layout: first shop start at 0x000BF09F.
    ShopDef shop @ (0x000BF09F + reference_pointer);
};

ShopPointer shops[63] @ 0xBEE9F;

// Cap attacks
struct CapAttack {
    u8 unknown;
    u8 animation;
};
CapAttack capAttacks[84] @ 0xBF63B;

// Cap sprite pointers (3-byte pointers)
struct CapSpritePtr {
    u24 sprite_pointer;
};
CapSpritePtr capSpritePtrs[35] @ 0x1384BC;

// Monster movement
struct MonsterMove {
    u8 movement;
};
MonsterMove monsterMoves[112] @ 0x27F6B5;

// Map metadata (3-byte reference)
struct MapMeta {
    u24 reference_pointer;
};
MapMeta mapMeta[242] @ 0x27FCBC;

// --- Mirrors of classes from src/tables/vanilla.py ---

// EventInstObject
struct EventInstObject {
    u16 reference_pointer;
};
EventInstObject eventInstObjects[205] @ 0x4A14;

// IPAttackObject (pointer list - scattered addresses)
struct IPAttackObject {
    u16 effect;
    u8 animation;
    u8 target_cursor;
    u8 target_mode;
    u8 ip_cost;
};
// Pointers: see `IPAttackObject.pointers` in src/tables/vanilla.py

// CharLevelObject (per-character pointers)
struct CharLevelObject {
    u8 level;
};
// Pointers: see `CharLevelObject.pointers` in src/tables/vanilla.py

// CharExpObject
struct CharExpObject {
    u24 xp;
};
// Pointers: see `CharExpObject.pointers` in src/tables/vanilla.py

// InitialEquipObject
struct InitialEquipObject {
    u16 weapon;
    u16 armor;
    u16 shield;
    u16 helmet;
    u16 ring;
    u16 jewel;
};
// Pointers: see `InitialEquipObject.pointers` in src/tables/vanilla.py

// ChestObject (many individual chest pointers)
struct ChestObject {
    u8 misc1; // bitfields: u00 u01 u02 u03 u04 u05 item_high_bit u07
    u8 misc2;
    u8 item_low_byte;
};
// Chest pointers: see `ChestObject.pointers` in src/tables/vanilla.py

// SpellObject
struct SpellObject {
    u8 name[8];
    u8 unk1;
    u8 element;
    u8 characters_flags;
    u8 unk4;
    u8 mp_cost;
    u16 zero;
    u16 price;
};
// Spell pointers: see `SpellObject.pointers` in src/tables/vanilla.py

// ItemObject (record layout placeholder)
struct ItemObject {
    u8 usability;
    u8 unknown;
    u8 targetting;
    u8 icon;
    u8 sprite;
    u16 price;
    u8 item_type;
    u8 equipability;
    u8 misc1;
    u8 misc2;
    u16 zero;
};
ItemObject itemObjects[467] @ 0xB4F69;

// CharGrowthObject (per-character pointers)
struct CharGrowthObject {
    u8 hp;
    u8 mp;
    u8 strength;
    u8 agl;
    u8 int;
    u8 gut;
    u8 mgr;
    u8 unk;
};
// Pointers: see `CharGrowthObject.pointers` in src/tables/vanilla.py

// TownSpriteObject (pointer list)
struct TownSpriteObject {
    u8 unknown;
    u8 palette_index;
    u24 sprite_pointer;
};
// Pointers: see `TownSpriteObject.pointers` in src/tables/vanilla.py

// CapSpritePTRObject alias (already have CapSpritePtr above)
struct CapSpritePTRObject {
    u24 sprite_pointer;
};
CapSpritePTRObject capSpritePTRObjects[35] @ 0x1384BC;


// IP Attack struct placeholder
struct IPAttack {
    u16 effect;
    u8 animation;
    u8 target_cursor;
    u8 target_mode;
    u8 ip_cost;
};
// Pointers for IPAttacks (scattered addresses) - see vanilla.py for full list
// 0x21060, 0x21074, 0x21084, 0x21097, 0x210A1, ...

// Chest entry placeholder
struct Chest {
    u8 misc1[1]; // bitfields: u00 u01 u02 u03 u04 u05 item_high_bit u07
    u8 misc2;
    u8 item_low_byte;
};
// Many chest pointers exist (see vanilla.py `ChestObject.pointers`) — listed there.

// Spell entry (partial)
struct Spell {
    u8 name[8];
    u8 unk1;
    u8 element;
    u8 characters_flags; // bitmask for which characters can use
    u8 unk4;
    u8 mp_cost;
    u16 zero;
    u16 price;
};
// Spell pointers are listed in vanilla.py (many addresses)

// Item record (partial layout, conservative fields)
struct Item {
    u8 usability; // bitflags / enum
    u8 unknown;
    u8 targeting;
    u8 icon;
    u8 sprite;
    u16 price;
    u8 item_type;
    u8 equipability;
    u8 misc1;
    u8 misc2;
    u16 zero;
};
Item items[467] @ 0xB4F69;

// Char growth pointers (per-character pointers) - see vanilla.py `CharGrowthObject.pointers`
// Town sprite pointers (see `TownSpriteObject.pointers` near 0x27F1F6)


// =====================================================================================
//  SCRIPTS / OPCODES
//  -------------------------------------------------------------------------------------
//  In-place disassembly of the game's four bytecode systems, mirrored from the Iris
//  Python codebase:
//    * Monster attack / defense scripts (L2BASM) -- structures/battlescript.py + monster.py
//    * Event / map / zone / tile / NPC scripts    -- structures/event_script/*
//    * IP-effect scripts (L2BASM)                 -- structures/ip_attack.py
//    * Capsule reaction scripts (L2BASM)          -- structures/capsule.py (location TODO)
//
//  Caveats (see the plan / skills for detail):
//    A. Linear parse: a script is read up to its first top-level END (0x00). Blocks that
//       are only reachable via a forward GoTo/branch past that END are not rendered.
//    B. Spell operands are shown numerically (SpellObject uses scattered pointers, so
//       there is no contiguous table to link into). Items/maps/characters/shops link.
//    C. Capsule scripts: RESOLVED. Each capsule record stores two u16 offsets (relative
//       to record start) -- attack (+37, const 0x2B) and reaction (+39, variable) -- so
//       both scripts are decoded. Verified across all 35 capsules.
//    D. Event text is shown as a raw byte run (+ named control prefixes) up to its
//       terminator -- the word-dictionary / <REPEAT> LZ codec is not reproduced here.
//    E. Targets the vanilla US (de-headered) ROM; addresses match the Python tables 1:1.
// =====================================================================================


// ----- Named operand value-spaces (the backbone of the cross-linking) ----------------

enum ScriptType : u8 {
    ATTACK  = 0x07,
    DEFENSE = 0x08
};

// Battle/party character index order (Maxim 0 .. Lexis 6), per monster.py.
enum PlayableCharacter : u8 {
    Maxim = 0,
    Selan = 1,
    Guy   = 2,
    Artea = 3,
    Tia   = 4,
    Dekar = 5,
    Lexis = 6
};

enum EventClass : u8 {
    SETUP_MAP  = 0,
    LOAD_MAP   = 1,
    REFERENCED = 2,
    NPC        = 3,
    TILE       = 4,
    UNK_5      = 5,
    UNK_6      = 6
};

// Battle-script target selector (opcode 0x32). 0x05 is the "all" modifier.
enum BattleTarget : u8 {
    RandomFoe    = 0x01,
    AllModifier  = 0x05,
    Self         = 0x06
};

// Status altering effect (battle opcode 0x27).
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

// Elemental mask (battle opcodes 0x1F / 0x21 / 0x22). Combined masks render numerically.
enum Element : u16 {
    Neutral     = 0x0000,
    VsDragons   = 0x0001,
    VsInsects   = 0x0002,
    Ice         = 0x0004,
    Thunder     = 0x0008,
    Earth       = 0x0010,
    VsSea       = 0x0020,
    Wind        = 0x0100,
    Fire        = 0x0200,
    Water       = 0x0400,
    Soil        = 0x0800,
    Light       = 0x1000,
    Shadow      = 0x2000,
    VsHard      = 0x4000,
    VsFlying    = 0x8000
};

// Battle-script subroutine index (opcode 0x42 XX 00) -- elemental weakness/protection.
enum Subroutine : u8 {
    WeakFire        = 0x00,
    WeakThunder     = 0x01,
    WeakWater       = 0x02,
    WeakIce         = 0x03,
    WeakFlyingEarth = 0x04,
    WeakLight       = 0x05,
    ProtFire        = 0x06,
    ProtThunder     = 0x07,
    ProtWater       = 0x08,
    ProtIce         = 0x09,
    ProtLight       = 0x0A,
    ProtNeutral     = 0x0B,
    WeakVsDragons   = 0x0C,
    WeakShadow      = 0x0D,
    ProtShadow      = 0x0E,
    IsHard          = 0x0F,
    IsInsect        = 0x10,
    ProtAllStatus   = 0x11,
    Undead          = 0x12,
    CoreReduceMagic = 0x13,
    GoremProtect    = 0x14,
    MiracleCare     = 0x24
};

// Battle-script (L2BASM) opcodes -- battlescript.py::op_codes (single-byte keys only).
enum BattleOp : u8 {
    END                 = 0x00,
    Execute             = 0x01,
    Reset02             = 0x02,
    GoTo                = 0x03,
    OnFailGoTo          = 0x04,
    OnChanceGoTo        = 0x05,
    IfEqGoTo            = 0x06,
    IfNeGoTo            = 0x07,
    IfGtGoTo            = 0x08,
    IfLtGoTo            = 0x09,
    IfGeGoTo            = 0x0A,
    IfLeGoTo            = 0x0B,
    RegSet              = 0x0C,
    RegAdd              = 0x0D,
    RegSub              = 0x0E,
    RegMul              = 0x0F,
    RegDiv              = 0x10,
    RegRand             = 0x11,
    Unk12               = 0x12,
    RegSetStat          = 0x13,
    StatSetReg          = 0x14,
    RegSetStatSelf      = 0x15,
    RegAnd              = 0x16,
    RegOr               = 0x17,
    RegXor              = 0x18,
    Unk19               = 0x19,
    RegNeg              = 0x1A,
    Unk1B               = 0x1B,
    Unk1C               = 0x1C,
    CancelContinue      = 0x1D,
    DisplayAttackName   = 0x1E,
    AddElement          = 0x1F,
    CritHitChance       = 0x20,
    PhysicalDamage      = 0x21,
    MagicalDamage       = 0x22,
    BunnySword          = 0x23,
    RestoreStat         = 0x24,
    IntensifyStat       = 0x25,
    RecoverStatus       = 0x26,
    ApplyStatus         = 0x27,
    PhysicalAttack      = 0x28,
    Defend              = 0x29,
    Flee                = 0x2A,
    UseItem             = 0x2B,
    CastSpell           = 0x2C,
    CallCompanions      = 0x2D,
    Unk2E               = 0x2E,
    Unk2F               = 0x2F,
    Unk30               = 0x30,
    Reset31             = 0x31,
    Target              = 0x32,
    Reset33             = 0x33,
    Reset34             = 0x34,
    SpecialItem         = 0x35,
    Unk36               = 0x36,
    WeaponAttack        = 0x37,
    Reset38             = 0x38,
    Reset39             = 0x39,
    Reset3A             = 0x3A,
    Reset3B             = 0x3B,
    AddIntDamage        = 0x3C,
    DisplayCMAttackName = 0x3E,
    LearnableAttack     = 0x3F,
    Unk40               = 0x40,
    CheckSituation      = 0x41,
    Subroutine          = 0x42,
    ReturnSub           = 0x43,
    Unk44               = 0x44,
    Unk47               = 0x47,
    Unk49               = 0x49,
    Unk4D               = 0x4D,
    LoadRegStatReg      = 0x4E,
    ExitNoEffect        = 0x4F,
    NoRetarget          = 0x50,
    DarkReflector       = 0x51,
    Reflector           = 0x52,
    Unk53               = 0x53,
    CastIPSpell         = 0x54,
    UnsignedDiv         = 0x55,
    AttackNameDuration  = 0x56,
    ItemEffSpell        = 0x57,
    EmptyTempAllies     = 0x58,
    EmptyTempEnemies    = 0x59,
    CallBattleAnim      = 0x5A,
    LoseOnMasterSuicide = 0x5B,
    HideDamage          = 0x5C
};

// Event-script opcodes -- the meaningful subset of opcodes.py::OPERAND_SHAPES.
// Bytes not listed here still parse (their length comes from event_fixed_len) and
// simply render numerically.
enum EventOp : u8 {
    EndEvent          = 0x00,
    TalkSpeak         = 0x08,
    Choice            = 0x10,
    BranchVar         = 0x12,
    CharSpeak         = 0x13,
    BranchState       = 0x14,
    BranchFlagSet     = 0x15,
    Warp              = 0x16,
    Rest              = 0x17,
    Shop              = 0x18,
    Church            = 0x19,
    SetFlag           = 0x1A,
    ClearFlag         = 0x1B,
    Jump              = 0x1C,
    SetVar            = 0x1D,
    AddVar            = 0x1E,
    GetItem0          = 0x20,
    GetItem1          = 0x21,
    GetGold           = 0x22,
    LearnSpell        = 0x23,
    RemoveItem0       = 0x24,
    RemoveItem1       = 0x25,
    IncreaseStat      = 0x29,
    CharJoin          = 0x2B,
    CharLeave         = 0x2C,
    CharAppear        = 0x2D,
    CharDisappear     = 0x2E,
    MoveChar          = 0x30,
    TurnChar          = 0x31,
    NpcWander         = 0x32,
    WalkRoute         = 0x33,
    ChangeSprite      = 0x34,
    MoveRoamNPC       = 0x35,
    Pause             = 0x37,
    PauseLong         = 0x38,
    ShowMapAt         = 0x3B,
    GatherBehindMaxim = 0x3C,
    HideBehindMaxim   = 0x3D,
    KeyCheck          = 0x40,
    OverwriteTiles    = 0x43,
    SpeechBorder      = 0x47,
    BattleMusic       = 0x4B,
    Sound             = 0x4C,
    BossBattle        = 0x53,
    OpenDoor          = 0x54,
    StopEarthquake    = 0x56,
    FadeBlack         = 0x58,
    Luminosity        = 0x59,
    Earthquake        = 0x5A,
    PlayCutscene      = 0x5B,
    MaximSpeak        = 0x61,
    SelanSpeak        = 0x62,
    GuySpeak          = 0x63,
    ArteaSpeak        = 0x64,
    DekarSpeak        = 0x65,
    TiaSpeak          = 0x66,
    LexisSpeak        = 0x67,
    LoadNPC           = 0x68,
    SetMapProps       = 0x69,
    BranchFlagClear   = 0x6A,
    MoveCharXY        = 0x6C,
    CreditsText1      = 0x6D,
    CreditsText2      = 0x6E,
    ChangeMusic       = 0x6F,
    MusicOff          = 0x70,
    Animation         = 0x73,
    BattleBackground  = 0x74,
    LoadMonsterNPC    = 0x7B,
    CapsuleJoins      = 0x81,
    CallExit          = 0x83,
    SetMapProps2      = 0x88,
    GetItemHold       = 0x8C,
    OpenDialog        = 0x9E,
    FillIP            = 0xB9,
    ShowReport        = 0xBB,
    ScrollScreen      = 0xC4
};


// ----- Operand-length dispatch (mirrors the Python opcode tables) --------------------

// Battle: operand byte count == op_codes[op].params. Undefined bytes -> 0.
fn battle_param_count(u8 op) {
    match (op) {
        (0x00 | 0x01 | 0x02 | 0x28 | 0x29 | 0x2A | 0x31 | 0x33 | 0x34 | 0x36 | 0x37 |
         0x38 | 0x39 | 0x3A | 0x3B | 0x3C | 0x40 | 0x41 | 0x43 | 0x49 | 0x4D | 0x4F |
         0x50 | 0x51 | 0x52 | 0x58 | 0x59 | 0x5B | 0x5C): { return 0; }
        (0x19 | 0x1A | 0x1B | 0x1C | 0x1D | 0x2C | 0x2D | 0x2E | 0x2F | 0x30 | 0x32 |
         0x35 | 0x3E | 0x53 | 0x54 | 0x5A): { return 1; }
        (0x03 | 0x04 | 0x11 | 0x12 | 0x13 | 0x14 | 0x15 | 0x1E | 0x1F | 0x20 | 0x23 |
         0x25 | 0x26 | 0x27 | 0x2B | 0x42 | 0x44 | 0x47 | 0x4E | 0x56): { return 2; }
        (0x05 | 0x0C | 0x0D | 0x0E | 0x0F | 0x10 | 0x16 | 0x17 | 0x18 | 0x3F | 0x55 |
         0x57): { return 3; }
        (0x24): { return 4; }
        (0x06 | 0x07 | 0x08 | 0x09 | 0x0A | 0x0B | 0x21 | 0x22): { return 5; }
        (_): { return 0; }
    }
};

// Event: total byte count of the *fixed* (integer-only) operand shapes. Opcodes whose
// shape contains TEXT/ADDR/POINTERS/VARIABLE are handled explicitly in EventInstruction
// and never reach this function.
fn event_fixed_len(u8 op) {
    match (op) {
        (0x00 | 0x0C | 0x0D | 0x11 | 0x19 | 0x28 | 0x39 | 0x3C | 0x42 | 0x50 | 0x51 |
         0x56 | 0x57 | 0x6B | 0x70 | 0x71 | 0x72 | 0x75 | 0x76 | 0x78 | 0x79 | 0x82 |
         0x88 | 0x8A | 0x97 | 0xA4 | 0xA5 | 0xA6 | 0xAA | 0xB5 | 0xB8 | 0xBB | 0xBC |
         0xC5 | 0xC7 | 0xCC): { return 0; }
        (0x07 | 0x17 | 0x18 | 0x1A | 0x1B | 0x2B | 0x2C | 0x2D | 0x2E | 0x37 | 0x38 |
         0x3B | 0x3D | 0x47 | 0x49 | 0x4A | 0x4B | 0x4C | 0x4D | 0x4F | 0x53 | 0x54 |
         0x55 | 0x58 | 0x59 | 0x5E | 0x69 | 0x6F | 0x74 | 0x77 | 0x7C | 0x7D | 0x7E |
         0x7F | 0x80 | 0x81 | 0x83 | 0x89 | 0x92 | 0x99 | 0x9A | 0x9D | 0xA2 | 0xA7 |
         0xA8 | 0xAB | 0xAE | 0xB0 | 0xB3 | 0xB7 | 0xB9 | 0xBA | 0xBE | 0xCB): { return 1; }
        (0x01 | 0x02 | 0x03 | 0x04 | 0x05 | 0x06 | 0x1D | 0x1E | 0x20 | 0x21 | 0x22 |
         0x23 | 0x24 | 0x25 | 0x30 | 0x31 | 0x32 | 0x33 | 0x34 | 0x40 | 0x41 | 0x43 |
         0x48 | 0x60 | 0x68 | 0x73 | 0x7B | 0x85 | 0x86 | 0x87 | 0x91 | 0x98 | 0xA1 |
         0xA3 | 0xA9 | 0xAF | 0xB1 | 0xB6 | 0xBD | 0xC1 | 0xC4 | 0xC6): { return 2; }
        (0x16 | 0x29 | 0x35 | 0x45 | 0x5A | 0x6C | 0x8B | 0x8C | 0x8E | 0x8F | 0x90 |
         0x94 | 0x95 | 0x9C | 0x9F | 0xAD | 0xB4 | 0xBF | 0xC0 | 0xCA): { return 3; }
        (0x8D | 0xA0 | 0xC2 | 0xC3): { return 6; }
        (0xC9): { return 7; }
        (_): { return 0; }
    }
};

// Extra bytes consumed by a sub-code inside the 0x14 condition chain
// (mirrors event_script/script.py::_parse_variable).
fn event_var_extra(u8 code) {
    if ((code & 0xF0) == 0xF0) { return 2; }
    if ((code & 0xF0) == 0xC0) { return 4; }
    if ((code & 0xF0) == 0x10) { return 2; }
    if ((code & 0xE0) == 0x20) { return 2; }
    return 1;
};


// ----- L2BASM (shared by monster attack/defense, IP effects, capsule reactions) ------

struct BattleInstruction {
    BattleOp opcode;
    u8 op = u8(opcode);
    match (op) {
        (0x03 | 0x04): { u16 target; }
        (0x05):        { u8 chance; s16 target; }
        (0x0C | 0x0D | 0x0E | 0x0F | 0x10 | 0x16 | 0x17 | 0x18): { u8 reg; u16 value; }
        (0x1F):        { Element element; }
        (0x21 | 0x22): { Element element; u16 base_damage; u8 misc; }
        (0x27):        { StatusEffect status; u8 probability; }
        (0x2B):        { u16 item; if (item < 467) { ItemName item_ref @ (0xF47E8 + item * 12); } }
        (0x2C | 0x54): { u8 spell; }
        (0x32):        { BattleTarget target; }
        (0x42):        { Subroutine subroutine; u8 zero; }
        (_):           { u8 operands[battle_param_count(op)]; }
    }
};

// A script runs up to (but not including) its first top-level END (0x00) -- see Caveat A.
struct BattleScript {
    BattleInstruction instructions[while(std::mem::read_unsigned($, 1) != 0x00)];
    BattleOp end;
};


// ----- Monster attack / defense scripts ----------------------------------------------
//  0xB05C0 is a 224-entry table of u16 offsets relative to the table base; each points
//  to a variable-length record whose trailing bytes carry the inline script header(s).
//  The script bytecode itself lives at (record_start + header_offset).

struct MonsterRecord {
    u64 recStart = $;                 // record base -- header offsets are relative to this
    Monster fixed;                    // existing canonical fixed record (ends with `misc`)
    if (fixed.misc == 0x03) {         // drop item, then an optional script marker
        u8 item_low;
        u8 item_high;
        u8 script_marker;
        if (script_marker == 0x07) {
            u16 atk_offset;
            BattleScript attack_script @ (recStart + atk_offset);
            u8 def_marker;
            if (def_marker == 0x08) {
                u16 def_offset;
                BattleScript defense_script @ (recStart + def_offset);
            }
        } else if (script_marker == 0x08) {
            u16 def_offset;
            BattleScript defense_script @ (recStart + def_offset);
        }
    } else if (fixed.misc == 0x07) {  // attack script (and maybe a trailing defense one)
        u16 atk_offset;
        BattleScript attack_script @ (recStart + atk_offset);
        u8 def_marker;
        if (def_marker == 0x08) {
            u16 def_offset;
            BattleScript defense_script @ (recStart + def_offset);
        }
    } else if (fixed.misc == 0x08) {  // defense script only
        u16 def_offset;
        BattleScript defense_script @ (recStart + def_offset);
    }
};

struct MonsterPtr {
    u16 rel;
    MonsterRecord rec @ (0xB05C0 + rel);
};
MonsterPtr monsterScripts[224] @ 0xB05C0;


// ----- IP-effect scripts -------------------------------------------------------------
//  Pointer table [0xAF3EF, 0xAF508] (141 x u16 relative to 0xAF3EF); L2BASM scripts live
//  at [0xAF509, 0xAFC5A], each preceded by a 0xFF marker (ip_attack.py docstring).

struct IpScript {
    if (std::mem::read_unsigned($, 1) == 0xFF) { u8 ff_marker; }   // separator (if present)
    BattleScript script;
};
struct IpPtr {
    u16 rel;
    IpScript entry @ (0xAF3EF + rel);
};
IpPtr ipEffectScripts[141] @ 0xAF3EF;


// ----- Capsule attack + reaction scripts (Caveat C RESOLVED) -------------------------
//  Reverse-engineered from the ROM (verified across all 35 capsules): after the 35-byte
//  fixed record, an 8-byte header carries two u16 script offsets (relative to record
//  start), then the L2BASM bytecode. Directly analogous to the monster attack/defense
//  two-offset model -- capsule.py's `assert _1 == 0x2B` is asserting the attack offset is
//  43, and its discarded `_2`/"mana" byte is the reaction offset.
//    +35 u16 unknown0        (== 0x0000)
//    +37 u16 attack_offset   (== 0x002B == 43 for all 35)   -> attack/decision script
//    +39 u16 reaction_offset (varies; starts a 0x42 resistance block) -> reaction script
//    +41 u16 unknown1        (== 0x0000)
//    +43 L2BASM bytecode
//  attack_script and reaction_script overlap on purpose: the reaction handler is a
//  sub-region of the attack blob past its first END, so placing it separately is what
//  makes it render as instructions instead of hiding behind Caveat A.

struct CapsuleRecord {
    u64 recStart = $;
    Capsule stats;                    // existing 35-byte fixed record
    u16 unknown0;                     // +35 (0x0000)
    u16 attack_offset;                // +37 (0x002B == 43)
    u16 reaction_offset;              // +39 (entry of the reaction/defense handler)
    u16 unknown1;                     // +41 (0x0000)
    BattleScript attack_script   @ (recStart + attack_offset);
    BattleScript reaction_script @ (recStart + reaction_offset);
};
struct CapsulePtr {
    u16 rel;
    CapsuleRecord rec @ (0xBDCB8 + rel);
};
CapsulePtr capsuleScripts[35] @ 0xBDCB8;


// ----- Event / map / zone / tile / NPC scripts ---------------------------------------

// Variable-length text run (raw bytes + control prefixes) up to a terminator -- Caveat D.
// Leaves a 0x00 terminator in place so the enclosing script's END detection still fires;
// consumes 0x01/0x0B (message-continue) terminators.
struct EventText {
    u8 chars[while(
        std::mem::read_unsigned($, 1) != 0x00 &&
        std::mem::read_unsigned($, 1) != 0x01 &&
        std::mem::read_unsigned($, 1) != 0x0B)];
    u8 term_peek = std::mem::read_unsigned($, 1);
    if (term_peek == 0x01 || term_peek == 0x0B) {
        u8 terminator;
    }
};

// POINTERS shape: a count byte then that many 2-byte local addresses.
struct EventPointers {
    u8 count;
    u16 addresses[count];
};

// One sub-code of the 0x14 condition chain (guaranteed code != 0xFF by the caller).
struct EventVarSub {
    u8 code;
    u8 extra[event_var_extra(code)];
};
struct EventVariableChain {
    EventVarSub subs[while(std::mem::read_unsigned($, 1) != 0xFF)];
    u8 terminator;                    // 0xFF
};

struct EventInstruction {
    EventOp opcode;
    u8 op = u8(opcode);
    match (op) {
        (0x08 | 0x61 | 0x62 | 0x63 | 0x64 | 0x65 | 0x66 | 0x67): { EventText text; }
        (0x13):        { u8 voice; EventText text; }
        (0x9E):        { u8 position; EventText text; }
        (0x6D | 0x6E): { u16 position; EventText text; }
        (0x10):        { EventPointers replies; }
        (0x12):        { u8 variable; EventPointers targets; }
        (0x14):        { EventVariableChain condition; }
        (0x15 | 0x6A): { u8 flag; u16 jump_target; }
        (0x1C):        { u16 jump_target; }
        (0x1A | 0x1B): { u8 flag; }
        (0x20):        { u8 item; u8 count; if (item < 467) { ItemName item_ref @ (0xF47E8 + item * 12); } }
        (0x21):        { u8 item; u8 count; if ((0x100 + item) < 467) { ItemName item_ref @ (0xF47E8 + (0x100 + item) * 12); } }
        (0x22):        { u16 gold; }
        (0x16):        { u8 map; u8 event; u8 position; if (map < 242) { MapEventEntry map_ref @ (0x38010 + map * 8); } }
        (0x18):        { u8 shop; if (shop < 63) { ShopPointer shop_ref @ (0xBEE9F + shop * 2); } }
        (0x23):        { PlayableCharacter character; u8 spell; }
        (0x2B | 0x2C | 0x2D | 0x2E): { PlayableCharacter character; }
        (0x68):        { u8 npc_slot; u8 sprite; }
        (_):           { u8 operands[event_fixed_len(op)]; }
    }
};

struct EventScript {
    EventInstruction instructions[while(std::mem::read_unsigned($, 1) != 0x00)];
    EventOp end;
};

// Each event list is a table of (index, offset) entries terminated by 0xFF; every offset
// is relative to the event-list block base and locates one script's bytecode.
struct EventListEntry<auto base> {
    u8 index;
    u16 offset;
    if (offset >= 14 && (base + offset) < 0x7289E) {
        EventScript script @ (base + offset);
    }
};
struct EventList<auto base> {
    EventListEntry<base> entries[while(std::mem::read_unsigned($, 1) != 0xFF)];
    u8 terminator;                    // 0xFF
};

// The per-map event-list block: "PH" magic + 6 relative offsets (EventClass 0..5).
struct EventBlock {
    u64 blockBase = $;
    char magic[2];                    // "PH"
    u16 listOffsets[6];
    if (listOffsets[0] >= 14) { EventList<blockBase> setup_map  @ (blockBase + listOffsets[0]); }
    if (listOffsets[1] >= 14) { EventList<blockBase> load_map   @ (blockBase + listOffsets[1]); }
    if (listOffsets[2] >= 14) { EventList<blockBase> referenced @ (blockBase + listOffsets[2]); }
    if (listOffsets[3] >= 14) { EventList<blockBase> npc        @ (blockBase + listOffsets[3]); }
    if (listOffsets[4] >= 14) { EventList<blockBase> tile       @ (blockBase + listOffsets[4]); }
    if (listOffsets[5] >= 14) { EventList<blockBase> unk5       @ (blockBase + listOffsets[5]); }
};

// The 8-byte map header (mirror of MapEventEntry) plus the reconstructed script pointers.
//  event_list_pointer = 0x38000 + (low | (high << 15));  same for the separate NPC list.
struct MapScriptSet {
    u16 eventlist_lowbytes;
    u8 eventlist_highbyte;
    u16 npc_lowbytes;
    u8 npc_highbyte;
    u16 map_name_pointer;
    u64 evPtr  = 0x38000 + (eventlist_lowbytes | (eventlist_highbyte << 15));
    u64 npcPtr = 0x38000 + (npc_lowbytes | (npc_highbyte << 15));
    if (evPtr < 0x300000 &&
        std::mem::read_unsigned(evPtr, 1) == 0x50 &&
        std::mem::read_unsigned(evPtr + 1, 1) == 0x48) {          // "PH" magic guard
        EventBlock block @ evPtr;
    }
    if (npcPtr > 0x3801E && npcPtr < 0x3AE4D) {                   // within the event bank
        EventScript npc_load_script @ npcPtr;
    }
};
MapScriptSet mapScripts[242] @ 0x38010;

