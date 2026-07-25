; Iris: scale normal enemy encounters to the party's average level.
;
; Companion to scale_encounters.py, which bakes the data this routine reads:
;   $D0:EA10  99 bytes  level 1..99 -> best-matching formation id
;   $D0:EA73  1 byte    LOW  end of the offset band, two's complement
;   $D0:EA74  1 byte    RANGE, i.e. HIGH - LOW + 1
;   $D0:EA75  this code
; The whole block is reserved in constants.py (SCALE_ENCOUNTERS_*) and taken off the front of
; EMPTY_BYTES, so it uses an explicit `org` -- never `freecode`, which would let asar's freespace
; scanner hand these bytes to another patch.
;
; What it does: when the game has queued a *normal* enemy battle it averages the live party's
; levels, adds a random offset from the baked band, clamps to 1..99 and overwrites the pending
; formation id at $7F:F8A4 with the table entry for that level.
;
; Known addresses (all confirmed):
;   $7F:F8A3  battle type, #$FE = normal enemy battle (see archipelago basepatch_code.asm)
;   $7F:F8A4  pending formation id, 1 byte
;   $7E:0A7B..$7E:0A7E  the four active party slots, each a character index; $FF = empty slot
;   character statblocks are $BE apart: the death-link code writes the status byte of Maxim..Lexis
;   at $0BBC/$0C7A/$0D38/$0DF6/$0EB4/$0F72/$1030, i.e. status(i) = $0BBC + i*$BE
;   $80:82C7  PRNG, returns the next random byte in 8-bit A
;
; ---------------------------------------------------------------------------------------------
; STILL TO CONFIRM IN AN EMULATOR (Mesen-S / bsnes-plus write-breakpoint on $7F:F8A4):
;
;   1. THE HOOK SITE. The ROM instruction that writes $7FF8A4 on the normal-encounter path is not
;      documented anywhere in this repo, so the `org` that redirects into this routine is left
;      commented out below and the patch currently assembles the routine without calling it.
;      Touch a roaming map monster with the breakpoint armed, record the writer PC, the vanilla
;      bytes there, and the M/X/DBR state, then confirm a scripted/boss fight does NOT hit the
;      same writer. Fill in the `org` and replay the displaced instruction(s) at `.replay`.
;   2. !level_offset below -- inferred, not observed. structures/character.py documents the ROM
;      template record as level(1), status(1), unknown(2), spells...; if RAM keeps that order the
;      level sits one byte *below* the known status byte, hence -1. Verify by memory-searching a
;      known party level around $7E:0B00-$7E:1100.
;   3. That $FF really is the empty-slot sentinel in $0A7B..$0A7E (compare a party of 1 vs 4) and
;      that capsule monsters never occupy one of those four slots.
; ---------------------------------------------------------------------------------------------

lorom

!table          = $D0EA10
!low_byte       = $D0EA73
!range_byte     = $D0EA74

!empty_slot     = $FF
!party_slots    = $7E0A7B       ; four bytes, one character index per active slot
!stat_stride    = $BE           ; bytes between two characters' statblocks
!status_0       = $0BBC         ; status byte of character index 0 (Maxim) -- confirmed
!level_offset   = -1            ; level byte relative to the status byte -- INFERRED, see above
!level_0        = !status_0+!level_offset
!min_level      = 1
!max_level      = 99

; Add one party slot's level to the running sum at $01,s and bump the live-member count in Y.
; Entry/exit: 16-bit A and X/Y. Uses long addressing throughout so DBR does not matter.
macro add_slot(slot)
    sep #$20
    lda.l !party_slots+<slot>
    cmp.b #!empty_slot
    beq ?empty
    sta.l $004202               ; WRMPYA = character index
    lda.b #!stat_stride
    sta.l $004203               ; WRMPYB -- starts index * $BE
    nop                         ; the multiply needs 8 cycles before RDMPYL/H is valid
    nop
    nop
    nop
    rep #$30
    iny                         ; count this member
    lda.l $004216               ; index * $BE
    clc
    adc.w #!level_0
    tax
    sep #$20
    lda.l $7E0000,x             ; this member's level
    rep #$30
    and.w #$00FF
    clc
    adc $01,s                   ; running sum of levels
    sta $01,s
?empty:
    rep #$30
endmacro

; org <writer PC>            ; TODO(step 0): 4 bytes -> jsl scale_encounter, NOPs for the remainder
;     jsl scale_encounter

org $D0EA75
scale_encounter:
    php
    rep #$30                    ; fix the index width before pushing, so the pulls match
    phx
    phy
.replay:
    ; TODO(step 0): replay here whatever instruction(s) the hook overwrote at the writer PC.
    sep #$20
    lda.l $7FF8A3
    cmp.b #$FE                  ; only normal enemy battles -- bosses, scripted fights and the
    beq .normal_battle          ; Archipelago death-link battle keep their own formation
    brl .done                   ; (brl, not bra: the routine body is longer than a byte reaches)
.normal_battle:

    rep #$30
    ldy.w #$0000                ; live member count
    lda.w #$0000
    pha                         ; $01,s = running sum of party levels
    %add_slot(0)
    %add_slot(1)
    %add_slot(2)
    %add_slot(3)

    cpy.w #$0000                ; paranoia: Maxim is always in the party, so this cannot happen,
    bne .have_party             ; but a zero divisor would hang the divide unit
    pla
    brl .done
.have_party:
    ; Dead members deliberately still count towards the average: reading status bytes to exclude
    ; them buys little and reintroduces the zero-divisor case. Capsules are not in these slots.
    pla
    sta.l $004204               ; WRDIVL/H = sum of levels
    sep #$20
    tya
    sta.l $004206               ; WRDIVB = live member count -- starts the divide
    nop                         ; the divide needs 16 cycles
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    rep #$30
    lda.l $004214               ; RDDIVL/H = average party level
    pha                         ; $01,s = running target level

    sep #$20
    lda.l !range_byte
    sta.l $004202               ; WRMPYA = size of the offset band
    jsl $8082C7                 ; A = next PRNG byte
    sta.l $004203               ; WRMPYB -- starts random * range
    nop
    nop
    nop
    nop
    lda.l $004217               ; RDMPYH = (random * range) >> 8 = offset in [0, range)
    rep #$30
    and.w #$00FF
    clc
    adc $01,s
    sta $01,s

    sep #$20
    lda.l !low_byte             ; the band's low end, two's complement
    rep #$30
    and.w #$00FF
    bit.w #$0080                ; sign-extend it to 16 bits
    beq .low_positive
    ora.w #$FF00
.low_positive:
    clc
    adc $01,s
    sta $01,s
    pla                         ; A = average + low + roll

    bmi .too_low                ; the sum is signed and a big negative LOW can undershoot zero
    cmp.w #!min_level
    bcs .check_high
.too_low:
    lda.w #!min_level
    bra .lookup
.check_high:
    cmp.w #!max_level+1
    bcc .lookup
    lda.w #!max_level
.lookup:
    dec                         ; the table is indexed by level-1, so 1..99 can never run off it
    tax
    sep #$20
    lda.l !table,x
    sta.l $7FF8A4               ; swap the pending formation for the level-appropriate one

.done:
    rep #$30
    ply
    plx
    plp
    rtl

assert pc() <= $D0EE10          ; do not spill past the region reserved in constants.py

org $DFFFFF                     ; pad the ROM out to 3MB so the region above always exists
    db $00
