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
Monster monsters[224] @ 0xB05C0;

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
Capsule capsules[35] @ 0xBDCB8;

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

