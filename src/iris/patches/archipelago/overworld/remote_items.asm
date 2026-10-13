; Iris: chests and grants holding the AP item (KEY30) say who the item is for and give nothing (Iris-Dev#19).
;
; A chest or grant that holds another player's item (or this world's character, capsule or maiden) holds the AP item.
;
; Chests. $8E:C1DE opens a red chest: $81:F1C5 loads the item's record, $8E:B5FB writes "Found " + its name into the
; text buffer at $7E:E000, which is shown; then $8E:C2CA..$8E:C2E2 hands the item over through the item-get menu
; ($82:E746, menu 4, which adds $09CF to the inventory). The caller ($8E:C199) sets the chest's opened bit when $09CF/$09D0
; come back zero. For the AP item:
;   - after the vanilla text is built, the chest's entry in the remote-text table (config bank) replaces it, if the
;     apworld wrote one;
;   - the item-get menu is skipped through $8E:C2DC, which zeroes $09CF/$09D0, so the opened bit is still set (the
;     Ancient Cave patch skips the same way).
; Received items (rx.asm) enter at $8E:C1EF and are never the AP item.
;
; Grants. Opcodes 20/21 store the item in $7FD4EF/$7FD4F0 and the count in $7FD4F1 ($80:A42B), then give it through
; the same item-get menu. For the AP item the menu is skipped; the script's own text and flags run as before.
;
; Defines: !code / !code_end (apply_asm_patch's code_region), !ap_item, !table (SNES address of the remote chest
; texts), !entry_size, !chest_count.

lorom

; chest: the text
org $8EC225
    jsl ChestText           ; overwrites JSL $8EB5FB

; chest: the item
org $8EC2CA
    jml ChestGive           ; overwrites REP #$10 : LDA $7FD4EF (first half); ChestGive returns to $8EC2D0

; grant: the item
org $80A435
    ; DB=$8E, x=0, m=1
    jml GrantGive           ; overwrites STA $7FD4F1

org !code

; m=1, x=0, X = $0B77 (the item record)
ChestText:
    jsl $8EB5FB             ; (overwritten instruction) "Found " + the item's name into $7E:E000
    php
    rep #$30
    lda $7FD4EF
    and.w #$81FF            ; bit 15: gold
    cmp.w #!ap_item
    bne .done
    lda $7FD4F1             ; the chest index: misc2, then 1 for misc1 bit 7
    cmp.w #!chest_count
    bcs .done
    asl                     ; index * 48
    asl
    asl
    asl
    pha
    asl
    clc
    adc $01,s
    tax
    pla
    sep #$20
    lda.l !table,x
    beq .done               ; no entry: keep "Found AP item"
    phb
    lda #$7E
    pha
    plb
    ldy #$0000
.copy:
    lda.l !table,x
    sta $E000,y
    beq .copied
    inx
    iny
    cpy.w #!entry_size-1
    bne .copy
    lda #$00
    sta $E000,y
.copied:
    plb
.done:
    plp
    rtl

; m=1, x=?
ChestGive:
    rep #$30
    lda $7FD4EF
    and.w #$81FF
    cmp.w #!ap_item
    sep #$20                ; Z stays
    beq .skip
    lda $7FD4EF             ; (overwritten instruction)
    jml $8EC2D0
.skip:
    jml $8EC2DC             ; no item-get menu; $09CF/$09D0 = 0, so the caller sets the opened bit

; m=1, x=0
GrantGive:
    sta $7FD4F1             ; (overwritten instruction)
    rep #$20
    lda $7FD4EF
    cmp.w #!ap_item
    sep #$20
    beq .skip
    jml $80A439             ; continue item get process
.skip:
    lda #$80                ; as the grant's end does
    tsb $099B
    jml $80A47F             ; RTS: no item-get menu

warnpc !code_end
