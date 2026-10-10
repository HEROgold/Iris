# Event-script item grants

Every `0x20 XX YY` (item `0x00XX`) and `0x21 XX YY` (item `0x01XX`) instruction in the vanilla event scripts.
`flagged` means the same script contains a set-event-bit (`0x1A`) instruction; its flag numbers are listed.
Address is the headerless ROM address of the item operand byte (read back from the ROM and verified).

Generated with: `python tools/dump_item_grants.py --file <vanilla-rom> --vanilla --out docs/ap/item_grants.md`

- Grants: 44
- Distinct items: 43
- Flagged: 40; unflagged: 4
- Key items (423-466) granted: 10
- Grants in NPC-load scripts (class X): 0
- Address readback mismatches: 0

| Map | Map name | Script | Address | Item | Item name | Count | Flag | Flag numbers |
|---|---|---|---|---|---|---|---|---|
| 07 | 2 | 07-C-01 | 03E434 | 429 | Door key | 1 | flagged | 23 (MET_IRIS_ELCID_CAVE) |
| 14 | B5 | 14-C-03 | 042027 | 459 | Crown | 1 | flagged | 27 (PICKED_UP_CROWN) |
| 26 |  | 26-A-01 | 046C75 | 323 | Ear jewel | 1 | unflagged |  |
| 26 |  | 26-B-18 | 046B15 | 452 | Glass angel | 1 | flagged | 74 (TALKED_JAFFY_RUBY_ICON) |
| 2A | B4 | 2A-B-18 | 04733C | 460 | Ruby apple | 1 | flagged | 36 (RECEIVED_RUBY_APPLE) |
| 3D | We6F | 3D-C-01 | 04EBB0 | 108 | Gades blade | 1 | flagged | 46 (PASSED_GADES_GORDOVAN) |
| 3F |  | 3F-B-1B | 04F610 | 43 | Dragon egg | 1 | unflagged |  |
| 7E | Fl | 7E-C-01 | 05C7FC | 451 | Pretty flwr. | 1 | flagged | 70 (RECEIVED_PRETTY_FLOWER) |
| 8B |  | 8B-B-25 | 05FBE0 | 453 | VIP card | 1 | flagged | 149 (OPENED_WATER_GATE_AURALIO_ALT2), 148 (OPENED_WATER_GATE_AURALIO_ALT) |
| 9F | Dragon Egg | 9F-B-50 | 06314E | 17 | Life potion | 10 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063151 | 18 | Spell potion | 10 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063154 | 20 | Speed potion | 10 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063157 | 21 | Mind potion | 10 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 06315A | 19 | Power potion | 10 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 06315D | 22 | Brave | 10 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 0631A6 | 46 | Secret fruit | 20 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 0631A9 | 47 | Holy fruit | 20 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 0631AC | 48 | Breeze fruit | 20 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 0631AF | 49 | Charm fruit | 20 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 0631B2 | 50 | Dark fruit | 20 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 0631B5 | 51 | Earth fruit | 20 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 0631B8 | 52 | Flame fruit | 20 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 0631BB | 53 | Magic fruit | 20 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063205 | 261 | Old shield | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063251 | 347 | S-power ring | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063254 | 349 | S-pro ring | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063257 | 348 | S-mind ring | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 06325A | 350 | S-witch ring | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 06325D | 355 | S-myst ring | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063260 | 346 | S-thun ring | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063263 | 343 | S-fire ring | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063266 | 344 | S-water ring | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063269 | 345 | S-ice ring | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063394 | 112 | Egg sword | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| 9F | Dragon Egg | 9F-B-50 | 063397 | 360 | Egg ring | 1 | flagged | 193 (KILLED_EGG_DRAGON) |
| BF |  | BF-B-2D | 06B111 | 448 | Mermaid jade | 1 | flagged | 145 (FREE_91) |
| D6 |  | D6-C-02 | 06E444 | 449 | Engine | 1 | unflagged |  |
| DC |  | DC-C-01 | 06F49A | 226 | Pearl armor | 1 | flagged | 102 (GADES_DEFEATED) |
| E0 |  | E0-C-01 | 06F863 | 322 | Pearl helmet | 1 | flagged | 105 (AMON_DEFEATED) |
| E4 |  | E4-C-01 | 06FA48 | 270 | Pearl shield | 1 | flagged | 191 (FREE_BF) |
| E4 |  | E4-C-01 | 06FD62 | 54 | Dual blade | 1 | flagged | 191 (FREE_BF) |
| F0 | t | F0-B-52 | 0723E2 | 450 | Ancient key | 1 | unflagged |  |
| F1 | t Final F | F1-C-01 | 0727E9 | 450 | Ancient key | 1 | flagged | 209 (IRIS_TREASURE_10), 195 (ANCIENT_CAVE_BOSS_KILLED), 250 (FREE_FA), 250 (FREE_FA) |
| F1 | t Final F | F1-C-01 | 07289A | 45 | Providence | 1 | flagged | 209 (IRIS_TREASURE_10), 195 (ANCIENT_CAVE_BOSS_KILLED), 250 (FREE_FA), 250 (FREE_FA) |
