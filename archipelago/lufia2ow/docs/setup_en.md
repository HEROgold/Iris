# Lufia II Overworld setup guide

## What you need

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 or later, with this world installed.
- The US Lufia II: Rise of the Sinistrals ROM (No-Intro, 2.5MB; headered or not).
- [SNI](https://github.com/alttpo/sni/releases) and an emulator or console it supports.

## Playing

1. Generate a game with a `Lufia II Overworld` YAML. You get an `.apl2ow` patch.
2. Open the patch with the Archipelago launcher; it builds the ROM from your US ROM.
3. Start SNI and the SNI client, load the ROM and connect to the room.

## What works so far

Red chests and the story rewards whose script sets a flag are checks. Tools, keys and story items are shuffled too,
following the vanilla story order: each dungeon still opens at its usual story moment, and the logic makes sure you
can get the keys and tools it needs before you need them. Items from other worlds arrive in the field with the usual
"found" message. The goal is defeating Daos.

Not yet: the four story rewards without a flag, the Ancient Cave, the Dragon Egg shrine's wishes, death link.

## Open World's starting leader and extras

These YAML options only work with `open_world: true`; the linear game ignores them.

- `leader`: maxim (default), selan, guy, artea, tia, dekar, lexis, or random. The leader starts the game in the party,
  Maxim leaves at the end of the first scene, and Maxim becomes an item in the pool in the leader's place.
- `cave_bridge_orb`: none (default), orb_check (touching the orb on Cave Bridge B5 is a check), or guard (an NPC
  blocks the orb, as in terrorwave's open world).
- `escapable_dungeons`: Escape and Warp work in every dungeon except the seafloor, the Karlloon Shrine and Daos'
  Shrine.
- `extra_npcs`: any of secondary_tool_tip, capsule_tips, tanbel_inn, egg_key_trader and egg_wishes. egg_key_trader is
  left out with the dragon_eggs goal, because the eggs are needed for the wishes.

Each of these is a set of byte changes on top of the open-world base patch, which keeps room for every one of them.
They all ship with the world, so nothing here needs Iris.

Iris has the same choices as command-line flags (`--leader`, `--npc-secondary-tool-tip`, `--npc-capsule-tips`,
`--npc-tanbel-inn`, `--npc-cave-bridge-orb-guard`, `--npc-egg-key-trader`, `--npc-egg-wishes`, `--orb-check`,
`--escapable-dungeons`, see `iris/args.py`). They only change ROMs you build with Iris yourself, not Archipelago
games. Nothing is Iris-only right now; an extra Iris gains later can only become a YAML option once the open-world
base patch keeps room for it.
