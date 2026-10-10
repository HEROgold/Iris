"""Human-readable location names for Lufia II's 171 red chests (Iris-Dev#31).

Keyed by global chest index (0x00-0xAA, see ``structures.chest_location``). Names follow
"<dungeon/area> <floor>, <position> chest (<vanilla item>)"; the item is the vanilla content, kept as a
recognisable label and unchanged when contents are randomized.

Sources and confidence:
- Dungeon names: ROM map names (hexpat map titles such as "Cave to Sundletan"), the dungeon list of the
  dkolke/lufia2r-webtracker ``data/locations.json`` (e.g. Gordovan West Tower, North Dungeon, Ancient Tower,
  North Lighthouse, Tower of Truth, Divine Shrine, Phantom Tree Mountain, Flower Mountain, Tower of Sacrifice)
  and Iris's ``args.ALL_CITIES`` dungeon order.
- Positions: derived from each chest's ZoneData section-18 (x, y) relative to the other chests on the same map
  (the chest_location.placement ordering); coordinates are appended where two chests would otherwise collide.
- Individual chests were NOT matched against a GameFAQs treasure list. Entries marked ``# guessed`` have a
  dungeon/floor attribution inferred from map id, floor text fragments in the ROM and item progression;
  entries marked ``# dungeon from tracker/ROM`` have a confirmed dungeon but a position-derived chest label.
"""

CHEST_NAMES: dict[int, str] = {
    0x00: "Cave to Sundletan B1, north-east chest (Escape)",  # dungeon from ROM map name
    0x01: "Cave to Sundletan B1, south-west chest (Antidote)",  # dungeon from ROM map name
    0x02: "Cave to Sundletan B1, north-west chest (Life potion)",  # dungeon from ROM map name
    0x03: "Cave to Sundletan B2, west chest (Power potion)",  # dungeon from ROM map name
    0x04: "Cave to Sundletan B2, north-east chest (Dragon egg)",  # dungeon from ROM map name
    0x05: "Cave to Sundletan B2, south-east chest at (35,35) (Magic jar)",  # dungeon from ROM map name
    0x06: "Cave to Sundletan B2, south-east chest (Hide armor)",  # dungeon from ROM map name
    0x07: "Sundletan Cave B2, south-west chest (Power potion)",  # guessed from map position
    0x08: "Sundletan Cave B2, east chest (Insect crush)",  # guessed from map position
    0x09: "Sundletan Cave B2, north-east chest at (39,6) (Speedy ring)",  # guessed from map position
    0x0a: "Sundletan Cave B2, north-east chest (Miracle)",  # guessed from map position
    0x0b: "Sundletan Cave B3, chest (Lake key)",  # guessed from map position
    0x0c: "Lake Cave B2, south-west chest (Bomb)",  # guessed from map position
    0x0d: "Lake Cave B2, east chest (Headband)",  # guessed from map position
    0x0e: "Lake Cave B2, north-east chest (Water jewel)",  # guessed from map position
    0x0f: "Lake Cave B3, west chest (Escape)",  # guessed from map position
    0x10: "Lake Cave B3, east chest (Coat)",  # guessed from map position
    0x11: "Lake Cave B4, east chest (Secret fruit)",  # guessed from map position
    0x12: "Lake Cave B4, north-west chest (Dragon egg)",  # guessed from map position
    0x13: "Lake Cave B4, north-east chest (Miracle)",  # guessed from map position
    0x14: "Lake Cave B4, south chest (Light knife)",  # guessed from map position
    0x15: "Alunze Northwest Cave B1, north-west chest (Hi-Potion)",  # guessed from map position
    0x16: "Alunze Northwest Cave B1, south-east chest at (34,36) (Eron hat)",  # guessed from map position
    0x17: "Alunze Northwest Cave B1, south-east chest (Tuff buckler)",  # guessed from map position
    0x18: "Alunze Northwest Cave B2, north-east chest (Horse rock)",  # guessed from map position
    0x19: "Alunze Northwest Cave B2, south-west chest at (17,25) (Brave)",  # guessed from map position
    0x1a: "Alunze Northwest Cave B2, south-west chest (Miracle)",  # guessed from map position
    0x1b: "Alunze Northwest Cave B3, north-east chest (Jet helm)",  # guessed from map position
    0x1c: "Alunze Northwest Cave B3, south-west chest at (19,31) (Hi-Potion)",  # guessed from map position
    0x1d: "Alunze Northwest Cave B3, south-west chest at (20,31) (Hi-Magic)",  # guessed from map position
    0x1e: "Alunze Northwest Cave B3, south-west chest (Power brace)",  # guessed from map position
    0x1f: "Alunze Northwest Cave B3, west chest at (25,14) (Light armor)",  # guessed from map position
    0x20: "Alunze Northwest Cave B3, west chest (Witch ring)",  # guessed from map position
    0x21: "Alunze Northwest Cave B4, north-east chest (Shrine key)",  # guessed from map position
    0x22: "Alunze Northwest Cave B4, south-west chest (Miracle)",  # guessed from map position
    0x23: "Tanbel Tower 3F, chest (Sky key)",  # guessed from map position
    0x24: "Tanbel Tower 5F, chest (Jute helmet)",  # guessed from map position
    0x25: "Tanbel Tower 6F, centre chest at (15,5) (Fire dagger)",  # guessed from map position
    0x26: "Tanbel Tower 6F, centre chest at (17,6) (Camu armor)",  # guessed from map position
    0x27: "Tanbel Tower 6F, centre chest (Pearl brace)",  # guessed from map position
    0x28: "Ruby Cave B3, north-west chest (Flame fruit)",  # guessed from map position
    0x29: "Ruby Cave B3, south-east chest at (25,54) (Aqua whip)",  # guessed from map position
    0x2a: "Ruby Cave B3, south-east chest (Fury helmet)",  # guessed from map position
    0x2b: "Ruby Cave B4, chest (Ruby key)",  # guessed from map position
    0x2c: "Parcelyte Shrine, chest (Holy wings)",  # guessed from map position
    0x2d: "Parcelyte Castle 2F, south-west chest (Bat rock)",  # guessed from map position
    0x2e: "Parcelyte Castle 2F, north-east chest (Mind ring)",  # guessed from map position
    0x2f: "Treasure Sword Shrine 4F, chest (Treas. sword)",  # guessed from map position
    0x30: "Treasure Sword Shrine B1, east chest at (28,27) (Sword key)",  # guessed from map position
    0x31: "Treasure Sword Shrine B1, east chest (Anger brace)",  # guessed from map position
    0x32: "Treasure Sword Shrine B1, south-east chest at (29,35) (Cold rapier)",  # guessed from map position
    0x33: "Treasure Sword Shrine B1, south-east chest (Undead ring)",  # guessed from map position
    0x34: "Treasure Sword Shrine B1, north-west chest (Round shield)",  # guessed from map position
    0x35: "Gordovan West Tower 1F, chest (Eagle rock)",  # dungeon from tracker/ROM
    0x36: "Gordovan West Tower 2F, south chest (Speed potion)",  # dungeon from tracker/ROM
    0x37: "Gordovan West Tower 2F, north chest (Muscle ring)",  # dungeon from tracker/ROM
    0x38: "Gordovan West Tower 4F, north-west chest (Wind key)",  # dungeon from tracker/ROM
    0x39: "Gordovan West Tower 4F, north-east chest (Hook)",  # dungeon from tracker/ROM
    0x3a: "Gordovan West Tower 4F, south-east chest (Miracle)",  # dungeon from tracker/ROM
    0x3b: "Gordovan West Tower 6F, centre chest at (14,6) (Scimitar)",  # dungeon from tracker/ROM
    0x3c: "Gordovan West Tower 6F, centre chest (Block shield)",  # dungeon from tracker/ROM
    0x3d: "Bridge Cave B2, chest (Regain)",  # guessed from map position
    0x3e: "Bridge Cave B3, chest (Hi-Magic)",  # guessed from map position
    0x3f: "North Dungeon B1, chest (Thunder ring)",  # dungeon from tracker/ROM
    0x40: "North Dungeon B2, east chest (Deadly sword)",  # dungeon from tracker/ROM
    0x41: "North Dungeon B2, west chest (Thunder ax)",  # dungeon from tracker/ROM
    0x42: "North Dungeon B3, west chest (Life potion)",  # dungeon from tracker/ROM
    0x43: "North Dungeon B3, east chest (Dragon egg)",  # dungeon from tracker/ROM
    0x44: "Ancient Tower 3F, north-east chest (Protect ring)",  # dungeon from tracker/ROM
    0x45: "Ancient Tower 3F, west chest (Pumkin jewel)",  # dungeon from tracker/ROM
    0x46: "Ancient Tower 3F, south chest (Muscle ring)",  # dungeon from tracker/ROM
    0x47: "Ancient Tower 4F, west chest (Cloud key)",  # dungeon from tracker/ROM
    0x48: "Ancient Tower 4F, north-west chest (Miracle)",  # dungeon from tracker/ROM
    0x49: "Ancient Tower 4F, south-east chest (Fayza shield)",  # dungeon from tracker/ROM
    0x4a: "Ancient Tower 5F, chest (Magic bikini)",  # dungeon from tracker/ROM
    0x4b: "North Lighthouse 1F, centre chest at (42,11) (Mystery ring)",  # dungeon from tracker/ROM
    0x4c: "North Lighthouse 1F, centre chest at (43,11) (Dragon egg)",  # dungeon from tracker/ROM
    0x4d: "North Lighthouse 1F, centre chest (Big shield)",  # dungeon from tracker/ROM
    0x4e: "North Lighthouse 3F, chest (Cancer rock)",  # dungeon from tracker/ROM
    0x4f: "North Lighthouse 4F, centre chest (Light key)",  # dungeon from tracker/ROM
    0x50: "North Lighthouse 4F, north-east chest (Bee rock)",  # dungeon from tracker/ROM
    0x51: "North Lighthouse 4F, south-west chest (Fire ring)",  # dungeon from tracker/ROM
    0x52: "Phantom Tree Mountain, chest (Tree key)",  # dungeon from tracker/ROM
    0x53: "Gruberik Cave (unidentified map 0x62), chest (Fire arrow)",  # guessed from map position
    0x54: "Narcysus area cave (unidentified map 0x64), chest (Water ring)",  # guessed from map position
    0x55: "Tower of Sacrifice, chest (Narcysus key)",  # dungeon from tracker/ROM
    0x56: "Tower of Sacrifice 3F, chest (Ice ring)",  # dungeon from tracker/ROM
    0x57: "Karlloon Shrine 2F, chest (Dekar blade)",  # guessed from map position
    0x58: "Karlloon Shrine 3F, chest (Lion fang)",  # guessed from map position
    0x59: "Karlloon Shrine B1, chest (Fury ring)",  # guessed from map position
    0x5a: "Flower Mountain (map 0x7E), chest (Flower key)",  # dungeon from tracker/ROM
    0x5b: "Flower Mountain (map 0x7F), chest (Hammer)",  # dungeon from tracker/ROM
    0x5c: "Flower Mountain (map 0x81), centre chest at (33,15) (Dragon egg)",  # dungeon from tracker/ROM
    0x5d: "Flower Mountain (map 0x81), centre chest at (32,16) (Flying ax)",  # dungeon from tracker/ROM
    0x5e: "Flower Mountain (map 0x81), centre chest (Power ring)",  # dungeon from tracker/ROM
    0x5f: "Flower Mountain (map 0x82), south chest (Life potion)",  # dungeon from tracker/ROM
    0x60: "Flower Mountain (map 0x82), north chest (Snake rock)",  # dungeon from tracker/ROM
    0x61: "Flower Mountain (map 0x83), chest (Burn sword)",  # dungeon from tracker/ROM
    0x62: "Dankirk Dungeon B2, centre chest at (45,4) (Hi-Magic)",  # guessed from map position
    0x63: "Dankirk Dungeon B2, centre chest (Earth fruit)",  # guessed from map position
    0x64: "Dankirk Dungeon B3, east chest (Fury ribbon)",  # guessed from map position
    0x65: "Dankirk Dungeon B3, west chest at (4,31) (Dragon egg)",  # guessed from map position
    0x66: "Dankirk Dungeon B3, west chest at (5,31) (Figgoru)",  # guessed from map position
    0x67: "Dankirk Dungeon B3, west chest (Flame jewel)",  # guessed from map position
    0x68: "Dankirk Dungeon B4, chest (Dankirk key)",  # guessed from map position
    0x69: "Trial key cave (unidentified map 0x94), chest (Trial key)",  # guessed from map position
    0x6a: "Ferim Tower 3F, chest (Stun gun)",  # guessed from map position
    0x6b: "Ferim Tower 4F, east chest (Mysto jewel)",  # guessed from map position
    0x6c: "Ferim Tower 4F, west chest (Samu jewel)",  # guessed from map position
    0x6d: "Unidentified area (map 0xA5), chest (Aqua sword)",  # guessed from map position
    0x6e: "Divine Shrine 1F, chest (Revive armor)",  # dungeon from tracker/ROM
    0x6f: "Divine Shrine 2F, chest (Heart key)",  # dungeon from tracker/ROM
    0x70: "Divine Shrine 3F, south-east chest (Dragon egg)",  # dungeon from tracker/ROM
    0x71: "Divine Shrine 3F, north-west chest (Holy whip)",  # dungeon from tracker/ROM
    0x72: "Divine Shrine B1, chest (Rocket ring)",  # dungeon from tracker/ROM
    0x73: "Unidentified dungeon (map 0xb0), chest (Heal armor)",  # guessed from map position
    0x74: "Unidentified dungeon (map 0xb1), south-east chest (Evil jewel)",  # guessed from map position
    0x75: "Unidentified dungeon (map 0xb1), north-west chest (Bright armor)",  # guessed from map position
    0x76: "Unidentified dungeon (map 0xb2), chest (Cursed bow)",  # guessed from map position
    0x77: "Unidentified dungeon (map 0xb3), chest (Ghost key)",  # guessed from map position
    0x78: "Unidentified dungeon (map 0xb4), north-west chest (Power robe)",  # guessed from map position
    0x79: "Unidentified dungeon (map 0xb4), south-east chest at (27,21) (Freeze sword)",  # guessed from map position
    0x7a: "Unidentified dungeon (map 0xb4), south-east chest (Boom sword)",  # guessed from map position
    0x7b: "Tower of Truth 2F, chest (Super sword)",  # dungeon from tracker/ROM
    0x7c: "Tower of Truth 4F, centre chest at (19,40) (Song rock)",  # dungeon from tracker/ROM
    0x7d: "Tower of Truth 4F, centre chest at (20,40) (Ghost ring)",  # dungeon from tracker/ROM
    0x7e: "Tower of Truth 4F, centre chest (Ghostclothes)",  # dungeon from tracker/ROM
    0x7f: "Tower of Truth 5F, chest (Truth key)",  # dungeon from tracker/ROM
    0x80: "Dragon Mountain area (map 0xc0), chest (Magma key)",  # guessed from map position
    0x81: "Dragon Mountain area (map 0xc1), north-west chest (Gorgon rock)",  # guessed from map position
    0x82: "Dragon Mountain area (map 0xc1), south-west chest at (2,41) (Hipower ring)",  # guessed from map position
    0x83: "Dragon Mountain area (map 0xc1), south-west chest (S-witch ring)",  # guessed from map position
    0x84: "Dragon Mountain area (map 0xc1), north-east chest at (22,17) (Hidora rock)",  # guessed from map position
    0x85: "Dragon Mountain area (map 0xc1), north-east chest at (22,5) (S-myst ring)",  # guessed from map position
    0x86: "Dragon Mountain area (map 0xc1), north-east chest at (23,5) (S-power ring)",  # guessed from map position
    0x87: "Dragon Mountain area (map 0xc1), north-east chest (Miracle)",  # guessed from map position
    0x88: "Dragon Mountain area (map 0xc2), west chest (Sonic ring)",  # guessed from map position
    0x89: "Dragon Mountain area (map 0xc2), east chest at (48,13) (Lizard blow)",  # guessed from map position
    0x8a: "Dragon Mountain area (map 0xc2), east chest at (49,13) (Legend helm)",  # guessed from map position
    0x8b: "Dragon Mountain area (map 0xc2), east chest at (48,14) (Mega shield)",  # guessed from map position
    0x8c: "Dragon Mountain area (map 0xc2), east chest (Holy robe)",  # guessed from map position
    0x8d: "Dragon Mountain area (map 0xc3), south-east chest at (45,14) (Magic scale)",  # guessed from map position
    0x8e: "Dragon Mountain area (map 0xc3), south-east chest at (46,14) (S-pro ring)",  # guessed from map position
    0x8f: "Dragon Mountain area (map 0xc3), south-east chest (Miracle)",  # guessed from map position
    0x90: "Dragon Mountain area (map 0xc3), west chest (S-mind ring)",  # guessed from map position
    0x91: "Dragon Mountain area (map 0xc3), north chest (Angry ring)",  # guessed from map position
    0x92: "Dragon Mountain area (map 0xc3), centre chest (Kraken rock)",  # guessed from map position
    0x93: "Dragon Mountain area (map 0xc7), chest (Miracle)",  # guessed from map position
    0x94: "Unidentified dungeon B2 (map 0xD3), chest (Miracle)",  # guessed from map position
    0x95: "Unidentified dungeon B3 (map 0xD4), chest (Basement key)",  # guessed from map position
    0x96: "Shuman Tower, south chest (S-thun ring)",  # dungeon from ROM map name
    0x97: "Shuman Tower, south-west chest (S-water ring)",  # dungeon from ROM map name
    0x98: "Shuman Tower, north-east chest (S-ice ring)",  # dungeon from ROM map name
    0x99: "Kamirno Tower, chest (S-fire ring)",  # dungeon from ROM map name
    0x9a: "Unidentified tower 1F (map 0xE7), south-west chest (Miracle)",  # guessed from map position
    0x9b: "Unidentified tower 1F (map 0xE7), south chest (Miracle)",  # guessed from map position
    0x9c: "Unidentified tower 1F (map 0xE7), north-east chest at (41,12) (Miracle)",  # guessed from map position
    0x9d: "Unidentified tower 1F (map 0xE7), north-east chest at (42,12) (Miracle)",  # guessed from map position
    0x9e: "Unidentified tower 1F (map 0xE7), north-east chest (Miracle)",  # guessed from map position
    0x9f: "Unidentified tower 2F (map 0xE8), west chest (Miracle)",  # guessed from map position
    0xa0: "Unidentified tower 2F (map 0xE8), east chest (Miracle)",  # guessed from map position
    0xa1: "Unidentified tower 3F (map 0xE9), centre chest at (15,9) (Miracle)",  # guessed from map position
    0xa2: "Unidentified tower 3F (map 0xE9), centre chest (Miracle)",  # guessed from map position
    0xa3: "Unidentified tower 4F (map 0xEA), south-west chest (Miracle)",  # guessed from map position
    0xa4: "Unidentified tower 4F (map 0xEA), north chest (Miracle)",  # guessed from map position
    0xa5: "Unidentified tower 4F (map 0xEA), south-east chest (Miracle)",  # guessed from map position
    0xa6: "Doom Island (map 0xEF), west chest (Secret fruit)",  # guessed from map position
    0xa7: "Doom Island (map 0xEF), east chest (Secret fruit)",  # guessed from map position
    0xa8: "Doom Island (map 0xF0), centre chest at (7,7) (Light jewel)",  # guessed from map position
    0xa9: "Doom Island (map 0xF0), centre chest at (7,8) (Dragon ring)",  # guessed from map position
    0xaa: "Doom Island (map 0xF0), centre chest (Brill helm)",  # guessed from map position
}
