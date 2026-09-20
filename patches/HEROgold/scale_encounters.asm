; Iris: scale normal enemy encounters to the party's average level.
;
; Companion to scale_encounters.py, which bakes the data this routine reads:
;   $E2:8000  99 bytes  level 1..99 -> best-matching formation id
;   $E2:8063  1 byte    LOW  end of the offset band, two's complement
;   $E2:8064  1 byte    RANGE, i.e. HIGH - LOW + 1
;   $E2:8065  this code
; The block is reserved in constants.py (SCALE_ENCOUNTERS_*) and claimed with an explicit `org` --
; never `freecode`, which would let asar's freespace scanner hand these bytes to another patch.
;
; It sits at headerless 0x310000, past the end of the original ROM. The base cart is a full 3MB
; with only ~1.2KB of blank space anywhere in it (constants.EMPTY_BYTES is NOT usable freespace --
; its first range starts inside real game data), so this patch expands the ROM to the 4MB a LoROM
; map can address and lives in the space that creates.
;
; ---------------------------------------------------------------------------------------------
; THE HOOK
;
; A store to the pending-formation byte $7F:F8A4 appears in exactly four places in the ROM
; (found by scanning for 8F A4 F8 7F / 8D A4 F8 / 9D A4 F8 / 99 A4 F8 -- there are no others):
;
;   $80:B919  event-script battle. The interpreter does
;               LDA $0BBB : STA.l $7FD4F7 : LDA #$FF : STA.l $7FF8A3 : JSR $C0B7 : STA.l $7FF8A4
;             where $80:C0B7 is the script-byte fetcher (LDA $0000,y : INY), so the formation id
;             comes straight out of the script stream. This is the scripted/boss path -- LEAVE IT.
;   $86:9CE6  Ancient Cave, and already level-scaled by the game itself:
;               LDA $0BBB : SEC : SBC #$1E : ... : LSR : CLC : ADC $00 : TAX : LDA $9DC7,X
;             LEAVE IT -- the cave picks its own difficulty curve.
;   $86:9D5D  Ancient Cave, table-driven from $97:C493. LEAVE IT.
;   $83:B9EC  the roaming map monster you walk into:
;               LDA $65 : TAX : LDA $05FA,X : SEC : SBC #$50 : STA.l $7FF8A4 : JSL $8383EB
;             i.e. NPC index -> NPC type byte -> formation id, then "force battle". THIS is the
;             normal-encounter path and the one we hook.
;
; Because we hook that one site rather than a shared routine, no battle-type test is needed --
; bosses, event battles, the Ancient Cave and the Archipelago death-link battle all reach
; $7FF8A4 through a different store and never run this code. (Note that a `$7FF8A3 == #$FE`
; guard would have been actively wrong here: this path writes $7FF8A3 via TDC, i.e. 0.)
;
; The vanilla instruction at $83:B9EC is `STA.l $7FF8A4` -- 4 bytes, exactly the size of a JSL,
; so the hook needs no NOP padding. On entry A is 8-bit and holds the vanilla formation id, and
; X/Y are 16-bit (REP #$10 at $83:B9DC). We replay the displaced store first, then overwrite it.
;
; PARTY LEVELS
;
; Statblocks are $BE apart: the Archipelago basepatch kills Maxim..Lexis by writing their status
; bytes at $0BBC/$0C7A/$0D38/$0DF6/$0EB4/$0F72/$1030, so status(i) = $0BBC + i*$BE. The level sits
; one byte below that, at $0BBB + i*$BE: both $80:B909 and $86:9CCE read $0BBB, the latter to
; derive the Ancient Cave's difficulty tier -- so that byte is the level the game itself uses to
; scale encounters, which is exactly what we want. ($0BBB is only ever read, never written, by
; those sites; structures/character.py documents the matching template order level(1),status(1).)
;
; $7E:0A7B..$7E:0A7E are the four active party slots, each holding a character index. They are
; copied as a block at $81:807A (LDA $0A7A : STA $153C : LDX #3 : LDA $0A7B,X : STA $153D,X ...).
; Rather than test for one particular empty-slot sentinel, a slot is treated as live only when it
; holds a real character index (0..6) -- that is correct whatever the game fills unused slots with,
; and it also rejects anything unexpected instead of dereferencing it.
; ---------------------------------------------------------------------------------------------

lorom

!table          = $E28000
!low_byte       = $E28063
!range_byte     = $E28064

!party_slots    = $7E0A7B       ; four bytes, one character index per active slot
!party_size     = 7             ; Maxim, Selan, Guy, Arty, Tia, Dekar, Lexis -- indexes 0..6
!stat_stride    = $BE           ; bytes between two characters' statblocks
!level_0        = $0BBB         ; level byte of character index 0 (Maxim)
!min_level      = 1
!max_level      = 99

; Add one party slot's level to the running sum at $01,s and bump the live-member count in Y.
; Entry/exit: 16-bit A and X/Y. Uses long addressing throughout so DBR does not matter.
macro add_slot(slot)
    sep #$20
    lda.l !party_slots+<slot>
    cmp.b #!party_size
    bcs ?empty                  ; not a character index -> unused slot
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

org $83B9EC                     ; was 8F A4 F8 7F (STA.l $7FF8A4) -- same length as a JSL
    jsl scale_encounter

org $FFFFFF                     ; grow the ROM to the full 4MB, so $E2:8000 exists at all
    db $00

org $E28065
scale_encounter:
    php
    sep #$20
    sta.l $7FF8A4               ; displaced instruction: the vanilla formation for this monster
    rep #$30
    phx
    phy

    ldy.w #$0000                ; Y = number of live party slots
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
    sta.l $7FF8A4               ; swap in the level-appropriate formation

.done:
    rep #$30
    ply
    plx
    plp
    rtl

assert pc() <= $E28400          ; do not spill past the region reserved in constants.py
