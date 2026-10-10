# Scenario items: where the story takes key items away

Research for the Archipelago plan (Iris-Dev#13). The data comes from static analysis of the vanilla US ROM
(`Lufia II - Rise of the Sinistrals (USA).sfc` with the header stripped) and an event dump made with
`structures.event_script.dump_all`. Nothing here has been checked in an emulator yet. Points marked
**(guess)** are not verified.

Addresses are written as `headerless file offset / SNES LoROM address`.

## Summary

- `$97:FDA0` is **not** a removal list. It maps bit numbers to item ids for the *scenario-item bitfield*
  at RAM `$7E:091E-$0925`. Scenario items are not stored in the normal inventory (`$0A8D`, 96 word slots).
  Each one is a single "held" bit.
- The story takes these items away only through event opcode `0x25 XX YY` ("Remove item 1XX"). Its handler
  clears the item's bit. **Seven** key items are removed this way (see the table). No other code clears bits
  in the bitfield, except the new-game initialiser.
- Game Genie `1DE6-3DDC` (`NO_SCENARIO_ITEMS`) does **not** stop the removals. It writes `RTS` into the
  "is this scenario item held?" routine, so every scenario-item check reports "held". In practice it removes
  the need to own scenario items at all. Its name means "no scenario items needed".

## 1. The list at `$97:FDA0`

| | Offset / SNES |
|---|---|
| Start | `0x0BFDA0 / $97:FDA0` |
| Terminator `$FFFF` | `0x0BFDE4 / $97:FDE4` |
| Entry `$97:FDAC` (patched by lufia2ac) | `0x0BFDAC / $97:FDAC` (entry 6) |

The format is little-endian words, one item id per entry, and `$FFFF` ends the list. The readers stop at
`$FFFF` or after 64 entries (`CPX #$0080`), which is the size of the 64-bit bitfield. In vanilla it has
**34 entries**: the ids 428-461 (`$01AC-$01CD`), in order. Entry *i* is bit `i % 16` of word `i / 16` in
`$091E` (the mask comes from the table at `$8E:D8C3` = `1, 2, 4, ... $8000`).

| Entry | Id | Name | Entry | Id | Name |
|---|---|---|---|---|---|
| 0 | 428 | TREAS_SWORD | 17 | 445 | BASEMENT_KEY |
| 1 | 429 | DOOR_KEY | 18 | 446 | NARCYSUS_KEY |
| 2 | 430 | SHRINE_KEY | 19 | 447 | TRUTH_KEY |
| 3 | 431 | SKY_KEY | 20 | 448 | MERMAID_JADE |
| 4 | 432 | LAKE_KEY | 21 | 449 | ENGINE |
| 5 | 433 | RUBY_KEY | 22 | 450 | ANCIENT_KEY |
| 6 | 434 | WIND_KEY | 23 | 451 | PRETTY_FLWR |
| 7 | 435 | CLOUD_KEY | 24 | 452 | GLASS_ANGEL |
| 8 | 436 | LIGHT_KEY | 25 | 453 | VIP_CARD |
| 9 | 437 | SWORD_KEY | 26 | 454 | KEY26 |
| 10 | 438 | TREE_KEY | 27 | 455 | KEY27 |
| 11 | 439 | FLOWER_KEY | 28 | 456 | KEY28 |
| 12 | 440 | MAGMA_KEY | 29 | 457 | KEY29 |
| 13 | 441 | HEART_KEY | 30 | 458 | KEY30 |
| 14 | 442 | GHOST_KEY | 31 | 459 | CROWN |
| 15 | 443 | TRIAL_KEY | 32 | 460 | RUBY_APPLE |
| 16 | 444 | DANKIRK_KEY | 33 | 461 | PURIFIA |

These key items are **not** scenario items: the tools 423-427 (HOOK, BOMB, ARROW, FIRE_ARROW, HAMMER) and
462-466 (TAG_RING ... LAST). They are kept somewhere else, and this report does not cover them.

**What the lufia2ac patch does.** `basepatch_code.asm` writes `DW $0000 x6` at `$97:FDAC`, which zeroes
entries 6-11 (ids 434-439). The Ancient Cave patch reuses those ids as party-member items. Zeroing them takes
them out of the scenario system, so they live in the normal inventory and use the normal add and remove paths.
The patch is not about story removals.

## 2. Routines

RAM: `$091E-$0925` holds the scenario bitfield, `$09CF` the item id argument, `$09CD` the quantity, `$0A8D`
the normal inventory, and `$54` is scratch.

### Lookup / "held?" (`0x017B51 / $82:FB51`, called with JSR, 16-bit A/X)

```
82FB51  AND #$01FF
82FB54  STA $54              ; item id
82FB56  LDX #$0000
82FB59  LDA $97FDA0,X        ; scan the scenario list
82FB5D  CMP #$FFFF
82FB60  BEQ $FB8F            ;  end of list -> not a scenario item
82FB62  CMP $54
82FB64  BEQ $FB6F            ;  found at byte offset X (= 2*entry)
82FB66  INX / INX
82FB68  CPX #$0080
82FB6B  BNE $FB59
82FB6D  BRA $FB8F
82FB6F  TXA, LSR x5, ASL, TAY ; Y = word offset into $091E (entry/16 * 2)
82FB77  TXA, AND #$001F, TAX  ; X = 2*(entry%16)
82FB7C  LDA $8ED8C3,X        ; bit mask
82FB80  AND $091E,Y          ; <-- Game Genie 1DE6-3DDC: this byte $39 becomes $60 (RTS)
82FB83  BEQ $FB8A
82FB85  LDA #$0000 : CLC : RTS   ; A=0, C=0 : scenario item, held
82FB8A  LDA #$0001 : SEC : RTS   ; A=1, C=1 : scenario item, not held
82FB8F  LDA #$0002 : SEC : RTS   ; A=2, C=1 : not a scenario item
```

On exit, X and Y still hold the mask index and word offset. The add and remove routines use them.

### Add (`0x017A2E / $82:FA2E`, from the get-item path at `$82:F9F2`)

It calls `$FB51`. If the item is a scenario item that is not yet held, it runs
`LDA $8ED8C3,X : ORA $091E,Y : STA $091E,Y`. If the result is 2, the caller falls back to the normal
inventory.

### Remove (`0x017A57 / $82:FA57`, JSL; its worker is `$82:FA77`)

```
82FA57  JSR $FA77            ; try the scenario bitfield first
82FA5A  CMP #$0002 : BNE $FA70   ; it was a scenario item: done
82FA5F  LDA $09CF : JSL $82FB1F  ; else find it in the normal inventory...
82FA68  LDA $09CD : JSR $FAD0    ; ...and subtract quantity $09CD
...
82FA77  LDA $09CF : JSR $FB51
82FA7D  CMP #$0002 : BEQ -> A=2  ; not scenario
82FA82  CMP #$0001 : BEQ -> A=1  ; scenario, not held: nothing to do
82FA87  LDA $8ED8C3,X
82FA8B  EOR $091E,Y          ; clear the held bit
82FA8E  STA $091E,Y
```

The only caller of `$82:FA57` is the event-opcode handler at `0x0024B1 / $80:A4B1`. It stores the operands
in `$09CF` (item) and `$09CD` (quantity), and it serves opcodes `0x24`/`0x25` "Remove item". This means **the
story removes scenario items only through these event opcodes**. The bytes `$091E-$0925` are written in only
three places: the add (`$82:FA45`), the remove (`$82:FA8E`) and the new-game clear
(`0x01AE66 / $83:AE66`, `LDX #7 : STZ $091E,X : DEX : BPL`).

### Count / has item (`0x017B1F / $82:FB1F`, JSL)

It returns `A=1, C=0` for a scenario item that is held. Otherwise it searches `$0A8D` and returns the
quantity with C=0, or `A=0, C=1` if the item is not found. It is called from the event engine at
`$80:A1EA`. That is probably the "if party has item" condition, but the exact opcode was not traced
**(guess)**. It is also called from about ten menu and shop sites.

### Scenario menu (`0x017C3F / $82:FC3F`)

Given n, this routine finds the n-th set bit in `$091E` and returns `$97FDA0[bit]`, so the menu lists the
held scenario items. The Game Genie code does not affect it.

### What the Game Genie code changes exactly

`1DE6-3DDC` decodes to `$82:FB80 = $60` (file `0x017B80`, vanilla `$39`). The routine then returns right
after `LDA $8ED8C3,X`, for every item it **finds in the list**. At that point A holds the bit mask (never 0)
and C=0, because the last carry-affecting instruction is the `ASL` of a value of 3 or less. The effects:

- `$82:FB1F` (count/has) sees C=0, so every scenario item counts as held (1 copy). Every "do you have X"
  gate passes.
- Add (`$FA2E`): A is a mask, so neither 0 nor 2 (except for entry 1, see below), and it ORs the bit in.
  This behaves as normal.
- Remove (`$FA77`): the item is not rejected, so it **EORs** (toggles) the bit. A removal still clears a
  held item. Removing an item you do not hold would set its bit.
- Side effects: entry 0 (TREAS_SWORD, mask 1) looks like "not held" to remove, so its removal is a no-op.
  Entry 1 (DOOR_KEY, mask 2) looks like "not a scenario item" to add and remove, which fall back to the
  normal inventory.

Conclusion: the code makes owning scenario items unnecessary. It does not keep removed items. It is not the
right tool for AP. To keep items, the AP patch should drop or skip the seven `0x25` removals below, or
gate the checks on AP-received state.

## 3. Event-script removals

Here is every `0x24`/`0x25` instruction in the vanilla event dump (36 048 lines, all map event containers):

| Map | Script | Offset | Instruction | Item |
|---|---|---|---|---|
| `$10` (Alunze castle) | `10-B-59` | `011B`, `01BF`, `0259`, `02B4` | `25(CB-01)` | 459 CROWN (one per reward choice) |
| `$17` (shrine north of Sundletan) | `17-B-17` | `021E`, `040D` | `25(AE-01)` | 430 SHRINE_KEY |
| `$26` (Tanbel, Rochy's house) | `26-B-55` | `03E3` | `25(CC-01)` | 460 RUBY_APPLE |
| `$2F` (Parcelyte) | `2F-B-55` | `0E82` | `25(AC-01)` | 428 TREAS_SWORD |
| `$69` (Ancient Cave bar?) **(guess)** | `69-B-59` | `003A` ... `02BF` | `25(9C..A4-01)` | 412-420 IRIS_* (not key items, not scenario items) |
| `$7B` (Leefa's home; town is a guess, maybe Forfeit) | `7B-B-24` | `031D` | `25(C3-01)` | 451 PRETTY_FLWR |
| `$89` (Bound Kingdom castle) | `89-B-25` | `0784` | `25(C4-01)` | 452 GLASS_ANGEL |
| `$A2` (Kirmo) | `A2-B-2C` | `0D58` | `25(C1-01)` | 449 ENGINE |

There is no `0x24` removal of a key item, because `0x24` can only reach ids below 256. The map names come from
the dialogue in each map and the lookups. Only Kirmo (and "North" for `$17`) are named in `lookups/zones.py`.

Not covered: scripts outside the map event containers, if any exist. A raw byte search for `25 xx 01` is too
noisy to settle this.

## 4. Removed key items and their story points

| Id | Name | Removed by | Map / script | Story point (event bit set next to it) |
|---|---|---|---|---|
| 428 | TREAS_SWORD | script `0x25` | `$2F` Parcelyte, `2F-B-55` | Selan joins in Parcelyte after the Treasure Sword is returned. The King's reward waits in the castle basement. Sets bit `$2D`. |
| 430 | SHRINE_KEY | script `0x25` | `$17`, `17-B-17` | Using the small shrine key to open the shrine door for Hilda (from Tanbel, stuck at Sundletan). Sets bit `$7D`. |
| 449 | ENGINE | script `0x25` | `$A2` Kirmo, `A2-B-2C` | The Engine is installed in the Excerion before the flight west to Narvick. Sets bit `$63`, ship upgrade `7C(02)`. |
| 451 | PRETTY_FLWR | script `0x25` | `$7B`, `7B-B-24` | Selan gives the pretty flower to Leefa. Sets bit `$47`. |
| 452 | GLASS_ANGEL | script `0x25` | `$89` Bound castle, `89-B-25` | Maxim presents it as the Ruby Icon to the King of Bound, who spots the imitation. Sets bit `$4B`. The link between GLASS_ANGEL and "fake Ruby Icon" is a guess based on the item id. |
| 459 | CROWN | script `0x25` | `$10` Alunze castle, `10-B-59` | The crown goes back to the King of Alunze (reward of 500/1000/2000/3000 gold, or the "Princess" joke). Sets bit `$1C`. |
| 460 | RUBY_APPLE | script `0x25` | `$26` Tanbel, `26-B-55` | The Ruby Apple from the North Cave goes to Rochy, which gives permission to pass the small shrine. |

The list at `$97:FDA0` removes nothing by itself. No other key item (keys, MERMAID_JADE, VIP_CARD, tools,
PURIFIA, ...) is removed by an event script in the vanilla dump.

For logic, each item is "held from pickup until the event bit above is set". After that the item no longer
gates anything, because the game moves the story forward in the same script.

## Open questions (need an emulator)

1. Confirm with a RAM watch that `$7E:091E-$0925` is the scenario bitfield and that each script above
   clears the expected bit.
2. Confirm the effects of the Game Genie code: gates pass without the item, the TREAS_SWORD removal is a
   no-op, and DOOR_KEY falls back to the inventory.
3. Which event opcode reaches `$80:A1E4` / `$82:FB1F` (the "has item" condition)? Which scripts check each
   scenario item?
4. Where do the tools (423-427) and 462-466 live, and does anything remove them? They are not in the
   scenario list.
5. Check the map identifications that are guesses (`$69`, `$7B`, `$17`) and the GLASS_ANGEL story point.
6. Does Ancient Cave opcode `0xA8` (which stashes and restores items through `$82:FBA7`/`$82:FBC6`, copying
   `$0A8D` <-> `$7E:8000`) leave the scenario bitfield alone? Static reading says yes: it only copies `$0A8D`.
