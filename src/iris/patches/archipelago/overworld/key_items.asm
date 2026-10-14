; Iris: the Ship, Submarine and progressive key items of the overworld Archipelago game (Iris-Dev#33).
; Included by rx.asm; KeyItems runs once per field frame, after RX.
;
; Items (free scenario-item slots, named by key_items.py):
;   454 Ship        the boat; while the Treadool scene hasn't given it yet, it is placed at the Treadool dock
;   455 Submarine
;   456 Prog. ship  token: becomes the first one missing of Ship, Submarine, Engine (airship)
;   457 Prog. arrow token: becomes the Fire arrow (Maxim always starts with the Arrow)
; The story still gives the ship (flag 127), the submarine (flag 86) and the airship (flag 99) as in vanilla; the items
; only add to it. The ship type $09DF follows from what you hold: 0 boat, 1 submarine, 2 submarine and airship, and
; 3 airship only (terrorwave's patch_no_submarine, ported below: 3 flies but can't dive).
;
; Scenario-item bits: item i (428+) is bit (i-428)&7 of $091E+((i-428)>>3). Event flag n: bit n&7 of $077E+(n>>3).

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
!FIRE_ARROW_ITEM = 426

; The code continues rx.asm's block (RX_CODE_REGION); the hooks step out of it and back.
pushpc

; Airship only (3) can't dive: the R-button dive used to go for any ship type but the boat.
org $8697FA
    jml DiveCheck               ; overwrites LDA $09DF : BNE $9829
    nop

; Boarding: 3 takes off like 2 (vanilla: 0 nothing, 1 dive, 2 ask).
org $86981A
    jml ShipKind                ; overwrites BEQ $9841 : DEC : BEQ $9829; A = $09DF

; Warp arrival on the world map ($86:9BCA, $09C9 == 1): the ship goes to the destination's dock, $09EE = $09CC (the
; high byte of the Warp list entry). Until the Auralio water gate opens (flag 149) vanilla keeps it at Treadool: a
; dock below $D6 (the towns before Treadool) becomes $D6, Treadool's. A Ship or Submarine item may come before the
; gate, so with either one held the ship follows to every dock (Iris-Dev#51). Flag 127 stays the Treadool check.
org $869C2B
    jml WarpDockGate            ; overwrites LDA #$95 : JSL $80BE1A, then BNE $9C6F (gate open: keep the dock)
    nop
    nop

pullpc

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

; m=1. Long reads: DB is the warp code's caller's.
WarpDockGate:
    lda.l $7E0000+!KEYS_BYTE
    and #!SHIP_BIT|!SUBMARINE_BIT
    bne .follow
    lda #$95                    ; flag 149, Auralio water gate open
    jsl $80BE1A
    jml $869C31                 ; BNE $9C6F on the flag
.follow:
    jml $869C6F

; m=1, x=0. DB mirrors WRAM $0000-$1FFF. Called with JSL from rx.asm's main loop.
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

; The pool's only Progressive Arrow is the Fire arrow (the apworld always starts Maxim with the Arrow), so the token
; gives item 426 through the chest routine, as a received item is given (rx.asm). $0926-$092A is the party's walking
; order (event opcodes 2B/2C add and remove characters there), not a tool list: writing a tool id into it added a
; walker instead of a tool.
ProgressiveArrow:
    lda !KEYS_BYTE
    bit #!PROGRESSIVE_ARROW_BIT
    beq .done
    and #$FF-!PROGRESSIVE_ARROW_BIT
    sta !KEYS_BYTE
    rep #$20
    lda.w #!FIRE_ARROW_ITEM
    sta $7FD4EF
    sep #$20
    jsl $8EC1EF                 ; chest routine, without the chest animation
    stz $A7
    jsl $83AB4F
.done:
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
