; Iris: receive Archipelago items in the overworld game (Iris-Dev#20). Ported from the lufia2ac base patch's RX.
; The main loop also runs key_items.asm (progressive items, ship type), included at the end. Item ids from $0200 are
; characters, capsules and maidens (rx_specials.asm).
;
; The SNI client appends received items to a list in expanded SRAM and bumps the "received" counter; the field main
; loop gives one item per frame through the chest routine (the "found X" message, without the chest animation) until
; "processed" catches up. Both counters, and blue_chests.asm's blue-chest counter, are saved and loaded with the save
; slot. The new-game hook clears them (new_game.asm, !clear_ap_rx). $F0:2000-$27BF is free (vanilla saves end at
; $F0:1FFF); the per-slot areas serve up to 8 save slots.
;
; Defines: !blue_chests / !blue_chests_saved (AP_SRAM_BLUE_CHESTS / _SAVED), !blue_chest_count
; (AP_OPT_BLUE_CHEST_COUNT, u16).
;
; SRAM (bank $F0 = $70):
;   $F0:27C0  u16 per save slot: saved blue-chest counter (AP_SRAM_BLUE_CHESTS_SAVED)
;   $F0:27D0  u16 blue-chest counter: Ancient Cave blue chests opened as checks (blue_chests.asm, AP_SRAM_BLUE_CHESTS;
;             read by the client)
;   $F0:27E0  4 bytes per save slot: saved received / processed counters
;   $F0:2800  u16 received counter (written by the client)
;   $F0:2802  u16 processed counter (written by the game)
;   $F0:2804  u16 item ids, one per received item, in order

lorom

MAX_RECEIVED = $0800        ; list room up to the end of the 32KB SRAM: ($F08000 - $F02804) / 2 = $15FE, kept lower

org $80FFD8
    db $05                  ; SRAM size: 32KB (vanilla $03, 8KB); the RX area lives above the vanilla saves

; Copy protection: at boot the game writes $00 and then $FF to $70:0000 and checks that $70:2000 reads the same, which
; only holds while 8KB of SRAM mirrors every 8KB. With 32KB it doesn't, and the game resets right after the logos.
; $71:0000 still mirrors $70:0000 (32KB fills one bank), so compare against that instead, as lufia2ac does.
org $80809A
    cmp $710000             ; overwrites CMP $702000
org $8080A6
    cmp $710000             ; overwrites CMP $702000

; main loop
org $83BC16
    ; DB=$83, x=0, m=1
    jsl MainLoop            ; overwrites LDA $09A7 : BIT.b #$01
    nop

; store the counters with the save slot
org $82EB61
    ; A = save slot
    jsl SaveRX              ; overwrites JSL $8090C9

; restore the counters with the save slot
org $82EAD5
    ; A = save slot
    jsl LoadRX              ; overwrites JSL $809099

; RX_CODE_REGION (apply_asm_patch's code_region), not freecode: asar's freespace finder lands in vanilla tile data.
org !code

MainLoop:
    jsr RX
    jsl KeyItems            ; key_items.asm
    lda $09A7               ; (overwritten instruction)
    bit.b #$01              ; (overwritten instruction)
    rtl

RX:
    rep #$20
    lda $F02802             ; processed
    cmp $F02800             ; received
    bpl +
    inc
    sta $F02802
    asl
    tax
    lda $F02802,x           ; item n is at $F02802 + 2n, n counted from 1
    cmp.w #$0200
    bcc .item
    jsr ReceiveSpecial      ; a character, capsule or maiden (rx_specials.asm)
    bra +
.item:
    sta $7FD4EF             ; give it as a chest's item
    sep #$20
    jsl $8EC1EF             ; chest routine, without the chest animation
    stz $A7                 ; cleanup, as lufia2ac does
    jsl $83AB4F
+:  sep #$20
    rts

SaveRX:
    jsl $8090C9             ; (overwritten instruction) write save slot A to SRAM
    sep #$10
    rep #$20
    asl
    tax                     ; slot * 2
    lda !blue_chests
    sta !blue_chests_saved,x
    txa
    asl
    tax                     ; slot * 4
    lda $F02800
    sta $F027E0,x
    lda $F02802
    sta $F027E2,x
    sep #$20
    rep #$10
    rtl

LoadRX:
    jsl $809099             ; (overwritten instruction) load save slot A from SRAM
    sep #$10
    rep #$20
    asl
    tax                     ; slot * 2
    lda !blue_chests_saved,x
    cmp !blue_chest_count   ; above this seed's N: blank SRAM or garbage
    bcc +
    beq +
    lda.w #$0000
+:  sta !blue_chests
    txa
    asl
    tax                     ; slot * 4
    lda $F027E2,x
    cmp $F027E0,x           ; processed > received: a save from before this patch, or blank SRAM
    beq +
    bcs ++
+:  lda $F027E0,x
    cmp.w #MAX_RECEIVED     ; more items than the list can hold: garbage too
    bcs ++
    sta $F02800
    lda $F027E2,x
    sta $F02802
    bra +++
++: lda.w #$0000            ; start this save's list from scratch
    sta $F02800
    sta $F02802
+++:
    sep #$20
    rep #$10
    rtl

incsrc "rx_specials.asm"
incsrc "key_items.asm"

warnpc !code_end
