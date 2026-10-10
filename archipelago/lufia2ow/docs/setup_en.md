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
