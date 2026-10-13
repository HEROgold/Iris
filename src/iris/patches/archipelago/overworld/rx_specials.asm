; Iris: received items that aren't game items (open world, Iris-Dev#43). Included by rx.asm.
;
; Item ids from $0200 up go here instead of the chest routine:
;   $0200 + c   character c (0 Maxim .. 6 Lexis): its FOUND flag (220 + c, for Elcid's party toggle) is set; if it
;               isn't in the party and one of the four slots is free, it joins as event opcode 2B does
;               ($80:A5C8: JSL $81F723, which fills a free slot of $0A7B and counts it in $0A7A; add it to the order list at
;               $0926; JSL $848204, the party/tool object refresh) and its party flag is set.
;   $0210 + s   capsule species s (0 Foomy .. 6 Armor Dog): owned, at its start level, under its default name, with
;               its story flag set; with no capsule in the party it also becomes the active one, the way
;               start_capsule.asm gives one (see there for each step).
;   $0220 + m   maiden m (0 Lisa, 1 Marie, 2 Clare): her flag (0x1A + m), which the Portravia lab
;               dock that flies to Doom Island reads (open_world/base.txt, A2-D-0A).
;
; Defines (rx_specials.py): !capsule_names, 35 bytes: each species' 5-byte default name.
; On entry: A 16-bit holding the id, X 16-bit; returns with A 8-bit.

!flags          = $077E         ; absolute: the main loop runs with DBR $83, whose $0000-$1FFF is low WRAM
!slots          = $0A7B         ; the four active party slots
!order          = $0926         ; the party order list event opcode 2B fills (5 entries, negative = empty)
!party_size     = 7

ReceiveSpecial:
    cmp.w #$0220
    bcs .maiden
    cmp.w #$0210
    bcs .capsule
    and.w #$000F
    tax
    sep #$20
    jmp ReceiveCharacter
.capsule:
    and.w #$000F
    tax
    sep #$20
    jmp ReceiveCapsule
.maiden:
    and.w #$000F
    tax
    sep #$20
    lda !flags+3
    ora.l MaidenMask,x
    sta !flags+3
    rts

; X = character index (16-bit), A 8-bit.
ReceiveCharacter:
    lda.l FoundOffset,x
    rep #$20
    and.w #$00FF
    tay
    sep #$20
    lda !flags,y
    ora.l FoundMask,x
    sta !flags,y                ; FOUND: Elcid's party toggle offers it from now on
    txa
    ldy.w #$0000
.in_party:
    cmp !slots,y
    beq .done
    iny
    cpy.w #$0004
    bne .in_party
    ldy.w #$0000
.room:
    lda !slots,y
    cmp.b #!party_size
    bcs .join                   ; a free slot
    iny
    cpy.w #$0004
    bne .room
    rts                         ; party full
.join:
    lda !flags
    ora.l PartyMask,x
    sta !flags                  ; its party flag
    txa
    pha
    jsl $81F723                 ; what event opcode 2B calls
    pla
    ldy.w #$0000
.order_seen:
    cmp !order,y
    beq .refresh
    iny
    cpy.w #$0005
    bne .order_seen
    ldy.w #$0000
.order_free:
    xba                         ; keep the character in B
    lda !order,y
    bmi .order_store
    xba
    iny
    cpy.w #$0005
    bne .order_free
    ldy.w #$0000                ; all taken: 2B overwrites the first entry, so this does too
    xba
.order_store:
    xba
    sta !order,y
.refresh:
    jsl $848204
.done:
    rts

; X = species (16-bit), A 8-bit.
ReceiveCapsule:
    lda.l CapsuleFlagOffset,x
    rep #$20
    and.w #$00FF
    tay
    sep #$20
    lda !flags,y
    ora.l CapsuleFlagMask,x
    sta !flags,y                ; its story flag: the join scene won't give it again
    lda.b #$01
    sta.l $7E11BB,x             ; owned
    lda.l $8EE4C4,x
    sta.l $7FF1A3,x             ; start level
    phx
    rep #$20
    txa
    asl
    asl
    clc
    adc $01,s
    tax                         ; X = species * 5
    sep #$20
    ldy.w #$0005
.name:
    lda.l CapsuleNames,x
    sta.l $7FF180,x             ; the species' name
    inx
    dey
    bne .name
    plx
    lda.l $7E0A7F
    cmp.b #$07
    beq .owned_only             ; a capsule is in the party already
    txa
    sta.l $7E11A3               ; active species
    lda.b #$01
    sta.l $7E11A4               ; first form
    lda.b #$07
    sta.l $7E0A7F               ; party slot 5 = member 7
    phx
    jsl $82C515
    jsl $82C261
    plx
    txa
    phk                         ; a fake JSL $82:E7DB plus its PHA (start_capsule.asm explains)
    pea.w .back-1
    pha
    jml $82E7DB
.back:
.owned_only:
    rts

PartyMask:          db $02,$04,$08,$10,$40,$20,$80     ; party flags 1,2,3,4,6,5,7: Tia and Dekar are swapped
FoundOffset:        db 27,27,27,27,28,28,28            ; FOUND flags 220-226 (EventFlag.FOUND_*)
FoundMask:          db $10,$20,$40,$80,$01,$02,$04
CapsuleFlagOffset:  db 1,1,1,1,1,1,2                   ; story flags 08,09,0C,0D,0E,0F,10
CapsuleFlagMask:    db $01,$02,$10,$20,$40,$80,$01
MaidenMask:         db $04,$08,$10                     ; flags 1A,1B,1C
CapsuleNames:       db !capsule_names
