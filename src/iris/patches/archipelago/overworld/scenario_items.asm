; Iris: the scenario-item removal mode, chosen per seed by the config block (Iris-Dev#26, docs/ap/scenario_items.md).
;
; The story takes a scenario item (ids 428-461, one "held" bit each in $7E:091E-$0925) away only through event
; opcode 0x25 ("Remove item"): $80:A4B1 stores the item in $09CF and the quantity in $09CD and JSLs $82:FA57. That
; routine first tries the scenario bitfield through its worker $82:FA77:
;
;   82FA77  LDA $09CF : JSR $FB51     ; A=0 held / 1 scenario but not held / 2 not a scenario item; X = mask index,
;   82FA7D  CMP #$0002 : BEQ ...      ;   Y = word offset into $091E
;   82FA82  CMP #$0001 : BEQ ...
;   82FA87  LDA $8ED8C3,X             ; <-- hooked: the held bit's mask
;   82FA8B  EOR $091E,Y               ; clear the held bit
;   82FA8E  STA $091E,Y
;   82FA91  LDA #$0000 : CLC : RTS    ; "done, it was a scenario item"
;
; The hook replaces the 4-byte LDA long with a JSL of the same size. Mode 0 loads the mask as before, so the bit is
; cleared exactly as in vanilla. Mode 1 loads 0 instead: the EOR leaves the bitfield as it was, and the routine still
; returns A=0 ("done, scenario item"), so the item never falls through to the normal inventory. Items that aren't
; scenario items return from $FA7D before the hook and leave the normal inventory as before.
;
; Entry: m=0, x=0 (the worker uses 16-bit immediates). DBR doesn't matter: every access is long.
; Defines: !code / !code_end (apply_asm_patch's code_region), !mode_byte (SNES address of AP_OPT_SCENARIO_ITEM_MODE).

lorom

org $82FA87
    jsl ScenarioMask        ; overwrites LDA $8ED8C3,X

org !code

ScenarioMask:
    lda.l !mode_byte
    and.w #$00FF            ; the byte after the mode is another option
    bne .keep
    lda.l $8ED8C3,x         ; (overwritten instruction) mode 0: the mask, so the bit is cleared
    rtl
.keep:
    lda.w #$0000            ; mode 1: EOR 0 keeps the bit
    rtl

warnpc !code_end
