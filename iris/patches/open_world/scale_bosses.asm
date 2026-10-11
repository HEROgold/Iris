; Iris: scale scripted (boss) battles to the party's level (open world, --boss-strength party).
;
; THE HOOK
;
; The battle loads each monster into a $BE-byte record through the long pointer $B2 (bank $7E): the routine
; around $81:FC0B clears it, copies the monster's ROM record ($96:85C0 table), and ends with
;   $81:FCD8  A6 B2        LDX $B2
;   $81:FCDA  22 D5 F4 81  JSL $81F4D5     ; derives the battle stats from the base ones
;   $81:FCDE  E2 20 AB 6B  SEP #$20 : PLB : RTL
; The JSL is replaced with one to scale_boss, which jumps on to $81F4D5 itself (a tail call, so $81F4D5's RTL
; returns to $81:FCDE). On entry A and X/Y are 16-bit, X = the record pointer.
;
; Record fields (found by watching the Lizard Man's record at $7E:161B in Mesen): HP word +$11 (current), +$25
; (max), +$51; MP +$13, +$27, +$53; attack +$78, defense +$7A; agility, intelligence, guts and magic resistance as
; words +$7E..+$85; +$45 the address of the monster's ROM record, in bank !monster_bank (the loader's
; LDA #$96 : PHA : PLB). The loader doesn't copy the level; it's byte 13 of the ROM record (after the name).
;
; Only scripted battles are scaled: $80:B919, the event-script battle every boss NPC uses, stores #$FF in
; $7F:F8A3 (the roaming-monster path stores 0; see scale_encounters.asm).
;
; THE SCALE
;
; T = the live party members' average level, L = the monster's level. Each field v becomes
;   v / L * T + (v % L) * T / L      (hardware 16/8 divide and 8x8 multiply only), capped at $FFFF, at least 1.
; The level itself, which the battle reads from the ROM record, stays.

lorom

!party_slots    = $7E0A7B
!party_size     = 7
!stat_stride    = $BE
!level_0        = $0BBB
!scripted       = $FF
!monster_bank   ?= $96
!level_in_record = 13

; Add one party slot's level to the word at $01,s and count it in Y (16-bit A and X/Y in and out).
macro add_slot(slot)
    sep #$20
    lda.l !party_slots+<slot>
    cmp.b #!party_size
    bcs ?empty
    sta.l $004202
    lda.b #!stat_stride
    sta.l $004203
    nop
    nop
    nop
    nop
    rep #$30
    iny
    lda.l $004216
    clc
    adc.w #!level_0
    tax
    sep #$20
    lda.l $7E0000,x
    rep #$30
    and.w #$00FF
    clc
    adc $01,s
    sta $01,s
?empty:
    rep #$30
endmacro

; Scale the word at record offset <offset> (L and T are on the stack: see scale_field).
macro scale(offset)
    ldy.w #<offset>
    jsr scale_field
endmacro

org $81FCDA
    jsl scale_boss              ; was JSL $81F4D5

freecode
scale_boss:
    php
    rep #$30
    pha
    phx
    phy
    sep #$20
    lda.l $7FF8A3
    cmp.b #!scripted
    beq .scripted
    brl .done
.scripted:
    rep #$30
    ldy.w #$0000
    lda.w #$0000
    pha                         ; $01,s = sum of party levels
    %add_slot(0)
    %add_slot(1)
    %add_slot(2)
    %add_slot(3)
    pla
    cpy.w #$0000
    bne .have_party
    brl .done
.have_party:
    sta.l $004204
    sep #$20
    tya
    sta.l $004206               ; sum / members
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    rep #$30
    lda.l $004214               ; T
    pha                         ; $01,s = T (word)
    ldy.w #$0045
    lda [$B2],y                 ; the monster's ROM record
    tax
    sep #$20
    lda.l (!monster_bank<<16)+!level_in_record,x   ; L
    rep #$30
    and.w #$00FF
    bne .have_level
    pla
    brl .done
.have_level:
    pha                         ; $01,s = L, $03,s = T
    %scale($0011)
    %scale($0025)
    %scale($0051)
    %scale($0013)
    %scale($0027)
    %scale($0053)
    %scale($0078)
    %scale($007A)
    %scale($007E)
    %scale($0080)
    %scale($0082)
    %scale($0084)
    pla                         ; L
    pla                         ; T
.done:
    rep #$30
    ply
    plx
    pla
    plp
    jml $81F4D5

; v at record offset Y -> v / L * T + (v % L) * T / L, capped at $FFFF, at least 1 (0 stays 0). 16-bit A, X/Y.
; Stack on entry: $01,s return, $03,s L, $05,s T. Three scratch words below them: $01 q, $03 r, $05 v.
scale_field:
    lda [$B2],y
    bne .nonzero
    rts                         ; 0 stays 0 (no MP pool)
.nonzero:
    pha                         ; v
    pha                         ; r
    pha                         ; q    -> $01 q, $03 r, $05 v, $07 return, $09 L, $0B T
    lda $05,s
    sta.l $004204
    sep #$20
    lda $09,s
    sta.l $004206               ; v / L
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    rep #$20
    lda.l $004214
    sta $01,s                   ; q
    lda.l $004216
    sta $03,s                   ; r (< L <= 99)
    sep #$20
    lda $02,s                   ; qh
    sta.l $004202
    lda $0B,s                   ; T
    sta.l $004203
    nop
    nop
    nop
    nop
    lda.l $004217
    bne .overflow               ; qh * T >= $100: the result can't fit 16 bits
    lda.l $004216
    sta $06,s                   ; $05,s = (qh * T) << 8
    lda.b #$00
    sta $05,s
    lda $01,s                   ; ql
    sta.l $004202
    lda $0B,s
    sta.l $004203
    nop
    nop
    nop
    nop
    rep #$20
    lda.l $004216               ; ql * T
    clc
    adc $05,s
    bcs .overflow
    sta $05,s                   ; q * T
    sep #$20
    lda $03,s                   ; r
    sta.l $004202
    lda $0B,s
    sta.l $004203
    nop
    nop
    nop
    nop
    rep #$20
    lda.l $004216               ; r * T (< 9801)
    sta.l $004204
    sep #$20
    lda $09,s
    sta.l $004206               ; (r * T) / L
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    rep #$20
    lda.l $004214
    clc
    adc $05,s
    bcs .overflow
    bne .store
    lda.w #$0001                ; a stat never drops to 0
    bra .store
.overflow:
    rep #$20
    lda.w #$FFFF
.store:
    sta [$B2],y
    pla
    pla
    pla
    rts
