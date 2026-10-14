; Iris: Ancient Cave blue chests as count-based Archipelago checks (Iris-Dev#21). Ported from the blue-chest part of
; the lufia2ac base patch's TX (ancient_cave/basepatch.asm).
;
; $8E:C1DE opens a chest: the item is in $7FD4EF/$7FD4F0, and a blue chest has bit 14 ($4000) set until $8E:C1F4
; masks the high byte. $8E:C1EB plays the chest animation (JSL $83F559), then $8E:C1EF goes on to the item get. The hook
; replaces that JSL: after the animation, a blue chest with the option on and the counter below N bumps the counter and
; skips the item get through $8E:C2DC, which zeroes $09CF/$09D0 so the chest counts as emptied (remote_items.asm skips
; the same way). Anything else continues at $8E:C1EF as in vanilla, so the red-chest hooks at $8E:C225/$8E:C2CA run
; after this one. Received items (rx.asm, key_items.asm) enter at $8E:C1EF and never get here.
;
; The client reports location #k for every k <= the counter. rx.asm saves and loads the counter with the save slot; the
; new-game hook zeroes it (new_game.asm, !clear_ap_rx).
;
; Entry: m=1, x=0. Every access is long.
; Defines: !code / !code_end (apply_asm_patch's code_region), !enabled (AP_OPT_BLUE_CHESTS_ENABLED), !count
; (AP_OPT_BLUE_CHEST_COUNT, u16), !counter (AP_SRAM_BLUE_CHESTS, SRAM).

lorom

org $8EC1EB
    jml BlueChest           ; overwrites JSL $83F559

org !code

BlueChest:
    jsl $83F559             ; (overwritten instruction) the chest animation
    php
    rep #$20
    lda.l $7FD4EF
    and.w #$4000            ; a blue chest
    beq .give
    lda.l !enabled
    and.w #$00FF            ; the byte after is the count
    beq .give
    lda.l !counter
    cmp.l !count
    bcs .give               ; N blue chests counted already: normal loot
    inc
    sta.l !counter
    plp
    sep #$20
    rep #$10
    jml $8EC2DC             ; no item get; $09CF/$09D0 = 0, so the chest counts as emptied
.give:
    plp
    jml $8EC1EF             ; the item get, as in vanilla

warnpc !code_end
