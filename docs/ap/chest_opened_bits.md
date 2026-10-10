# Where the game stores "chest opened" (Iris-Dev#10)

Static analysis of the vanilla US ROM (2026-10-10). Not yet confirmed in an emulator.

## Answer

A red chest's "opened" state is one bit in WRAM:

    byte = $7E:093B + (n >> 3)
    bit  = n & 7          (mask from the table at $80:BE45: 01 02 04 ... 80)

`n` is the chest number. For the 171 red chests it is Iris's global chest index (`ChestObject.pointers`, 0x00-0xAA,
the keys of `CHEST_NAMES` and `CHEST_MAP`): `ChestObject.misc2` holds its low 8 bits and `misc1` bit 7 its bit 8.
The field runs to at least `$7E:093B + 0x20` for numbers 256 and up.

## How it was found

- `$8E:C080` is the chest interaction handler. It walks the current map's entries in the table at `$91:B8B5`,
  where each map's entry list starts at the word `$91:B8B5 + 2 * map` (an offset from `$91:B8B5`; map in `$05AC`,
  cached in `$7F:D1A0` by `$80:E858`). Each entry is 3 bytes and `$FF` ends a list:
  - byte 0: chest slot on the map (bits 0-4), item bit 8 (bit 6), chest-number bit 8 (bit 7)
  - byte 1: chest number, low 8 bits
  - byte 2: item, low 8 bits
  These are exactly Iris's `ChestObject` records (`misc1`, `misc2`, `item_low_byte`).
- `$8E:C338` loads the entry's chest number into `$7F:D4F1` and its bit 8 into `$7F:D4F2`; `$8E:C34F` turns that into
  the byte offset `X` and mask `A` (via `$80:E898`, adding `$20` to `X` when bit 8 is set).
- `$8E:C15D` (`BIT $093B,X`) skips a chest that is already open; `$8E:C1A7` (`ORA $093B,X : STA $093B,X`) marks it
  open after the item is given.
- Decoding every map's list finds all 171 Iris chest indices on the map Iris's `CHEST_MAP` puts them on. The table
  also holds 20 numbers Iris doesn't list (172-260); what they are is still open.

The other branch of the handler (`$8E:C0AD`, a per-map bit byte at `$7F:E733` and item words at `$7F:E746`) is
rebuilt for each map and isn't saved; it fits the Ancient Cave's blue chests, which are rolled again on every floor.

## For the client

Read the bitfield from `$7E:093B` and report chest `n` when its bit is set. Whether `$093B` is part of the save data
(so a reloaded game keeps it) still needs an emulator check.
