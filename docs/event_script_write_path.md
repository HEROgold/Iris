# Event-script write path — findings & the relocator TODO

In-repo copy of the key facts about editing Lufia II event scripts in Iris, so they travel with the code.
(A fuller narrative also lives in the out-of-repo notes at `../../docs/event_scripts/05_compile_and_freespace.md`.)

## The write path is in-place only

A modified (`dirty`) `EventScript` recompiles at its **original pointer** and must fit `len(self.raw)`
(the gap to the next pointer). `EventScript.write()` raises `ValueError` if it would overrun. There is no
relocation wired in: `structures/event_script/allocator.py` (`FreeSpaceAllocator`) exists but is unused.

Replacing a script with **shorter** content is fine (this is how the Elcid party toggle works). **Growing**
an existing script is effectively impossible — see below.

## Why existing scripts can't grow (measured 2026-07)

Trying to insert a 2-byte `1A(found_flag)` after every `2B` party-join (`patches/HEROgold/found_flags.py`)
patched **0 of ~22** join scripts. Two independent reasons:

1. **Packed to the byte.** Recompiling a typical join script reproduces its exact size (`delta == 0`) — no
   room for +2.
2. **The text codec inflates on re-encode.** `decode_text` expands each `0x0A` `<REPEAT>` back-reference to
   the literal bytes it points at, but `encode_text` never re-emits `0x0A`, so dialogue-heavy scripts
   recompile *larger* than the original (e.g. +36 B on a 5.7 KB script) **before any edit**.

Growth therefore needs **relocation**, and the tracked free pool is out of reach:

- `constants.EMPTY_BYTES` starts at `0x286a10` (~2.6 MB). Event-list entries store
  `script.pointer - event_list_pointer` as a **16-bit** offset (`EventList.write` enforces `0..0xFFFF`), so
  a script must sit within **64 KB** of its map's event-list block (`~0x3xxxx`). The far pool is ~2.4 MB
  away — unreachable.
- The event bank `0x38000–0x80000` has ~**156 free bytes** total (padding scan). No nearby room.

## The fix (deferred spike): a per-map event-container relocator

Move a map's **whole** event container as a unit — the `PH` block + all six class tables + every script —
into the far pool, and repoint the map record. This keeps every internal offset valid because they are all
relative to the block base, which moves together.

1. Compile all of the map's scripts; lay out a fresh contiguous image (`PH` + six class offsets, each
   class's `index/offset` table, all script bodies). Keep each script inside one 32 KB bank and within
   64 KB of the new block base (`allocator.allocate(..., near=[new_block_base])`).
2. Repoint the map record (`MapEventObject` eventlist low/high, npc low/high). `offset = low | (high << 15)`
   supports the large offset, so the block base *can* live in `EMPTY_BYTES` even though 16-bit entry
   offsets can't.
3. The NPC-load script is referenced separately (base = map bank base `0x38000`, not the block base) —
   confirm in an emulator how the game bases NPC-script jumps before moving it.
4. Reclaim the vacated original range into the freelist so other maps can reuse it (this is the only way to
   get reachable space back).

**Learn from terrorwave** (`randomizer.py` `Script.compile` `:3585`, `allocate` `:4020`): it fits arbitrary
changes by freeing every original script range on load and repacking wholesale. Must be **emulator-
validated** — byte-identity round-trips only prove structure, not that the moved scripts still run.

## Related fix already landed: party-membership flags

Party-membership event flags are **not** `character_index + 1`. Flag **5 = Dekar**, **6 = Tia** (swapped),
proved by the event dump (`2B(04)`→`1A(06)` for Tia, `2B(05)`→`1A(05)` for Dekar) and the TCRF flag notes.
`PlayableCharacter.party_flag` uses an authoritative per-index map; all 256 flags are named in
`enums/flags.EventFlag` (with `name_of()/all_flags()/free_flags()`). Iris' "found/unlocked" flags are
`EventFlag.FOUND_MAXIM..FOUND_LEXIS` = 242..248 (blank TCRF slots); avoid 240/241 (Undo magic) and 250-255
(volatile post-boss).
