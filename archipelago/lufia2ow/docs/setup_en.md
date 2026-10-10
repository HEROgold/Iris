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

Red chests are the checks. Progression items (tools and keys) stay in their vanilla chests; everything else in the
chests is shuffled across the multiworld. Your own items aren't sent to other worlds yet, and receiving items isn't
supported. The goal is defeating Daos.
