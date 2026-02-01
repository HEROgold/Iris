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

// Shop pointers
struct Shop {
    u16 reference_pointer;
};
Shop shops[63] @ 0xBEE9F;

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
