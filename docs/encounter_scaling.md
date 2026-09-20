# Encounter scaling, and how Lufia II picks a battle formation

Reference notes behind `--scale-encounters` ([patches/HEROgold/scale_encounters.py](../patches/HEROgold/scale_encounters.py)
and its `.asm`). Most of this is ROM knowledge that is useful well beyond that one patch, so it is
recorded here rather than only in the patch header.

Everything below was derived **statically**, by pattern-scanning a vanilla ROM for the relevant
store/load instructions — no emulator session was needed. The scan is easy to reproduce: search the
headerless ROM for the opcode bytes and convert file offsets to LoROM with
`snes = ((0x80 + (off >> 15)) << 16) | 0x8000 | (off & 0x7FFF)`.


## The pending-battle bytes

| Address | Meaning |
|---|---|
| `$7F:F8A3` | battle type |
| `$7F:F8A4` | pending formation id (1 byte, indexes the 192-entry table at headerless `0xBBE93`) |

A battle is queued by filling these in and then calling the "force battle" routine `JSL $83:83EB`.


## Every writer of `$7F:F8A4`

Scanning for `8F A4 F8 7F` (`STA.l`), `8D A4 F8` / `9D A4 F8` / `99 A4 F8` (`STA` abs / abs,X /
abs,Y) finds **exactly four** sites in the whole ROM. There are no others.

### `$80:B919` — scripted / boss battle

```
$80:B909  AD BB 0B      LDA $0BBB          ; party level -> saved for the battle
          8F F7 D4 7F   STA.l $7FD4F7
          A9 FF         LDA #$FF
          8F A3 F8 7F   STA.l $7FF8A3      ; battle type $FF
          20 B7 C0      JSR $C0B7          ; fetch next event-script byte
          8F A4 F8 7F   STA.l $7FF8A4      ; ...that byte IS the formation id
          22 5B 84 83   JSL $83845B
```

`$80:C0B7` is the event-script byte fetcher (`LDA $0000,y : INY : ...`), so the formation comes
straight out of the script stream. This is the event-opcode battle path — bosses and cutscene
fights. Leave it alone.

### `$86:9CE6` — Ancient Cave (already level-scaled by the game)

```
$86:9CCE  AD BB 0B      LDA $0BBB          ; party level
          38 E9 1E      SEC : SBC #$1E     ; level - 30
          B0 02 A9 00   BCS +2 : LDA #$00  ; clamp low
          C9 14 90 02   CMP #$14 : BCC +2
          A9 12         LDA #$12           ; clamp high
          4A            LSR                ; /2 -> difficulty tier
          18 65 00 AA   CLC : ADC $00 : TAX
          BD C7 9D      LDA $9DC7,X        ; tier table
          8F A4 F8 7F   STA.l $7FF8A4
```

Worth knowing in its own right: **the Ancient Cave already scales its encounters by party level**,
on a `(level - 30) / 2` tier curve clamped to `0..0x12`.

### `$86:9D5D` — Ancient Cave, second path

Table-driven from `$97:C493`. Leave it alone.

### `$83:B9EC` — the roaming map monster (the normal-encounter path)

```
$83:B9DC  C2 10         REP #$10           ; X/Y 16-bit
          7B            TDC                ; A = 0 ...
          8F A3 F8 7F   STA.l $7FF8A3      ; ...so battle type here is 0, NOT $FE
          A5 65 AA      LDA $65 : TAX      ; index of the NPC you touched
          BD FA 05      LDA $05FA,X        ; that NPC's type byte
          38 E9 50      SEC : SBC #$50     ; - $50  -> formation id
$83:B9EC  8F A4 F8 7F   STA.l $7FF8A4
          22 EB 83 83   JSL $8383EB        ; force battle
```

This is the one to hook for "normal encounters".

> **Caution.** A guard of the form `LDA $7FF8A3 : CMP #$FE` does *not* identify a normal battle.
> `#$FE` is what the Archipelago basepatch writes for its own death-link battle; the real
> roaming-monster path writes **0** here (via `TDC`). Gating on `#$FE` rejects every real encounter.

Because each of the four paths has its own store, hooking one site is inherently scoped — no
runtime battle-type test is needed to keep bosses, events and the Ancient Cave out.

**Hook convenience:** the vanilla instruction at `$83:B9EC` is `STA.l $7FF8A4`, which is 4 bytes —
exactly the size of a `JSL`. It can be replaced with no NOP padding, and the hooked routine just
replays the displaced store. On entry `A` is 8-bit and holds the vanilla formation id; `X`/`Y` are
16-bit (`REP #$10` at `$83:B9DC`).


## Party RAM

### Character statblocks — `$0BB8 + i*$BE`

Statblocks are `$BE` bytes apart. The Archipelago basepatch kills the whole party by writing status
bytes at `$0BBC`, `$0C7A`, `$0D38`, `$0DF6`, `$0EB4`, `$0F72`, `$1030` — i.e.
`status(i) = $0BBC + i*$BE`, for character indexes 0..6 (Maxim, Selan, Guy, Arty, Tia, Dekar,
Lexis).

### The level byte — `$0BBB + i*$BE`

The level sits one byte below the status byte. Two independent sites read `$0BBB` (character 0):
`$80:B909` before a scripted battle, and `$86:9CCE` to derive the Ancient Cave difficulty tier. It
is never written by either. So `$0BBB` is not merely *a* level byte — it is the one the game itself
uses to scale encounter difficulty.

This also matches the ROM template-record layout documented in
[structures/character.py](../structures/character.py): `level(1), status(1), unknown(2), spells...`.

### Active party slots — `$0A7B..$0A7E`

Four bytes, each a character index. Confirmed by the block copy at `$81:807A`:

```
$81:8072  AD 7A 0A      LDA $0A7A
          8D 3C 15      STA $153C
          A2 03 00      LDX #$0003
$81:807A  BD 7B 0A      LDA $0A7B,X
          9D 3D 15      STA $153D,X
          CA 10 F7      DEX : BPL -
```

The value used for an *unused* slot has not been confirmed. Rather than depend on one sentinel,
treat a slot as live only when it holds a real character index (`< 7`); that is correct whatever the
game stores in empty slots, and it rejects unexpected values instead of dereferencing them.


## Other useful idioms in this ROM

- **PRNG:** `JSL $80:82C7` returns the next random byte in 8-bit `A`.
- **Random in `[0, n)`:** `LDA n : STA $4202 : JSL $8082C7 : STA $4203`, wait 8 cycles, then read
  `$4217` (`RDMPYH`) — the high byte of `n * random`. Used throughout the Archipelago basepatch.
- **Divide:** 16-bit dividend to `$4204/$4205`, 8-bit divisor to `$4206`, wait 16 cycles, quotient
  in `$4214`. A zero divisor hangs the divide unit — always guard it.


## Free space: the ROM has none, and `EMPTY_BYTES` is wrong

Worth knowing before reserving space for any patch. The base cart is a **full 3 MB** (`0x300000`),
and a scan for runs of `$00`/`$FF` finds exactly **one** blank region of 1 KB or more in the entire
file — `0x0F8D3E-0x0F9220`, about 1.2 KB. That is all the slack there is.

`constants.EMPTY_BYTES` does **not** describe this ROM. Its first range starts at `0x286A10`, which
holds real game data (visibly structured, not fill). Anything that allocates from
`EMPTY_BYTES[0].start` — the `structures/zone.py` bump allocator and the event-script allocator both
do — is writing over live data. Treat that as a known hazard, not a supported allocation source.

The workable space is **past the end of the original ROM**: LoROM can map banks `$80-$FF`, i.e. 4 MB,
so expanding the file from 3 MB to 4 MB yields a clean megabyte at `0x300000-0x3FFFFF`.

`--scale-encounters` therefore reserves headerless `0x310000-0x3103FF` (SNES `$E2:8000`):

| Offset | SNES | Size | Contents |
|---|---|---|---|
| `0x310000` | `$E2:8000` | 99 | level 1..99 -> best-fit formation id, baked by Python |
| `0x310063` | `$E2:8063` | 1 | `LOW` end of the offset band, two's complement |
| `0x310064` | `$E2:8064` | 1 | `RANGE` = `HIGH - LOW + 1` |
| `0x310065` | `$E2:8065` | — | the asar-assembled hook routine |

The `.asm` claims it with an explicit `org`, never `freecode`, so asar's freespace scanner cannot
hand these bytes to another patch. As a backstop the Python side refuses to bake if the block is not
blank — `unlock_warps.asm` and the Ancient Cave basepatch *do* use `freecode`, and asar has never
heard of our reservation, so a future collision fails loudly instead of silently corrupting one of
the two patches.
