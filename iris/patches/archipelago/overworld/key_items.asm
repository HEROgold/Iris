; Iris: the Ship, Submarine and progressive key items of the overworld Archipelago game (Iris-Dev#33).
; Included by rx.asm; KeyItems runs once per field frame, after RX.
;
; Items (free scenario-item slots, named by key_items.py):
;   454 Ship        the boat; while the Treadool scene hasn't given it yet, it is placed at the Treadool dock
;   455 Submarine
;   456 Prog. ship  token: becomes the first one missing of Ship, Submarine, Engine (airship)
;   457 Prog. arrow token: becomes the first tool missing of Arrow, Fire arrow
; The story still gives the ship (flag 127), the submarine (flag 86) and the airship (flag 99) as in vanilla; the items
; only add to it. The ship type $09DF follows from what you hold: 0 boat, 1 submarine, 2 submarine and airship, and
; 3 airship only (terrorwave's patch_no_submarine, ported below: 3 flies but can't dive).
;
; Scenario-item bits: item i (428+) is bit (i-428)&7 of $091E+((i-428)>>3). Event flag n: bit n&7 of $077E+(n>>3).
; Tool list: $0926-$092A hold tool ids (0 Arrow, 1 Bomb, 2 Hook, 3 Fire arrow, 4 Hammer; table $83:C433), $FF = empty.

!ENGINE_BYTE = $0920
!ENGINE_BIT = $20               ; 449 Engine
!KEYS_BYTE = $0921
!SHIP_BIT = $04                 ; 454
!SUBMARINE_BIT = $08            ; 455
!PROGRESSIVE_SHIP_BIT = $10     ; 456
!PROGRESSIVE_ARROW_BIT = $20    ; 457
!GOT_SUBMARINE_BYTE = $0788     ; flag 86
!GOT_SUBMARINE_BIT = $40
!GOT_AIRSHIP_BYTE = $078A       ; flag 99
!GOT_AIRSHIP_BIT = $08
!GOT_SHIP_BYTE = $078D          ; flag 127, set by the Treadool scene that gives the ship
!GOT_SHIP_BIT = $80
!TREADOOL_DOCK = $01            ; ship location of the Treadool scene, 7D(01)
!ARROW = $00
!FIRE_ARROW = $03

; Airship only (3) can't dive: the R-button dive used to go for any ship type but the boat.
org $8697FA
    jml DiveCheck               ; overwrites LDA $09DF : BNE $9829
    nop

; Boarding: 3 takes off like 2 (vanilla: 0 nothing, 1 dive, 2 ask).
org $86981A
    jml ShipKind                ; overwrites BEQ $9841 : DEC : BEQ $9829; A = $09DF

freecode

DiveCheck:
    lda $09DF
    beq .no
    cmp #$03
    beq .no
    jml $869829
.no:
    jml $8697FF

ShipKind:
    cmp #$03
    beq .airship
    cmp #$02
    beq .both
    cmp #$01
    beq .submarine
    jml $869841
.submarine:
    jml $869829
.both:
    jml $86981F
.airship:
    jml $86982C

; m=1, x=0. DB mirrors WRAM $0000-$1FFF. Called with JSL from rx.asm's main loop (another freecode block).
KeyItems:
    jsr ProgressiveShip
    jsr ProgressiveArrow
    jsr ShipState
    rtl

ProgressiveShip:
    lda !KEYS_BYTE
    bit #!PROGRESSIVE_SHIP_BIT
    beq .done
    and #$FF-!PROGRESSIVE_SHIP_BIT
    sta !KEYS_BYTE
    jsr HasShip
    bcs .submarine
    lda !KEYS_BYTE
    ora #!SHIP_BIT
    sta !KEYS_BYTE
    rts
.submarine:
    jsr HasSubmarine
    bcs .airship
    lda !KEYS_BYTE
    ora #!SUBMARINE_BIT
    sta !KEYS_BYTE
    rts
.airship:
    lda !ENGINE_BYTE
    ora #!ENGINE_BIT
    sta !ENGINE_BYTE
.done:
    rts

ProgressiveArrow:
    lda !KEYS_BYTE
    bit #!PROGRESSIVE_ARROW_BIT
    beq .done
    and #$FF-!PROGRESSIVE_ARROW_BIT
    sta !KEYS_BYTE
    lda #!ARROW
    jsr HasTool
    bcc GiveTool
    lda #!FIRE_ARROW
    jsr HasTool
    bcc GiveTool
.done:
    rts

; A = tool id. Into the first empty slot, then refresh the tools as the add-tool event opcode does ($80:A5C8).
GiveTool:
    ldx #$0000
.find:
    pha
    lda $0926,x
    bmi .free
    pla
    inx
    cpx #$0005
    bne .find
    rts
.free:
    pla
    sta $0926,x
    jsl $848204
    rts

; A = tool id, kept. Carry set when it is in the tool list.
HasTool:
    ldx #$0004
.next:
    cmp $0926,x
    beq .yes
    dex
    bpl .next
    clc
    rts
.yes:
    sec
    rts

; Carry set when held, from the item or from the story.
HasShip:
    lda !KEYS_BYTE
    bit #!SHIP_BIT
    bne .yes
    lda !GOT_SHIP_BYTE
    bit #!GOT_SHIP_BIT
    bne .yes
    clc
    rts
.yes:
    sec
    rts

HasSubmarine:
    lda !KEYS_BYTE
    bit #!SUBMARINE_BIT
    bne .yes
    lda !GOT_SUBMARINE_BYTE
    bit #!GOT_SUBMARINE_BIT
    bne .yes
    clc
    rts
.yes:
    sec
    rts

HasAirship:
    lda !ENGINE_BYTE
    bit #!ENGINE_BIT
    bne .yes
    lda !GOT_AIRSHIP_BYTE
    bit #!GOT_AIRSHIP_BIT
    bne .yes
    clc
    rts
.yes:
    sec
    rts

ShipState:
    jsr HasShip
    bcc .done
    lda !GOT_SHIP_BYTE          ; a Ship item before the Treadool scene: put the ship at the Treadool dock, once
    bit #!GOT_SHIP_BIT
    bne .type
    lda $09E0
    cmp #$FF
    bne .type
    stz $09E0                   ; as 7E(00)
    lda #!TREADOOL_DOCK
    sta $09EE                   ; as 7D(01)
.type:
    jsr HasAirship
    bcc .no_airship
    jsr HasSubmarine
    lda #$02
    bcs .store
    lda #$03
    bra .store
.no_airship:
    jsr HasSubmarine
    lda #$00
    bcc .store
    lda #$01
.store:
    sta $09DF
.done:
    rts
