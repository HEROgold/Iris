; Test-only harness for blue_chests.lua (Iris-Dev#21), assembled into the check ROM by build_blue_chests_rom.py; never
; part of a real build. The field main loop's JSL (rx.asm's MainLoop) goes through TestLoop first. When Lua sets the
; trigger byte $7F:E300 to 1, TestLoop runs one request from the field main loop, with NMI on, as RX does:
;   op ($7F:E301) 0: open a chest: $7F:E302 (u16) into $7FD4EF, $7F:E304 into $7FD4EE, then the chest routine $8E:C1DE
;                    (animation, then the hooked $8E:C1EB). $09CF/$09D0 afterwards go to $7F:E310.
;   op 1: SaveRX with save slot $7F:E305 (writes the slot and the counters).
;   op 2: LoadRX with save slot $7F:E305.
; and then sets the trigger to 2.
; Defines: !code / !code_end, !main_loop (rx.asm's MainLoop), !save_rx, !load_rx.

lorom

org $83BC16
    jsl TestLoop            ; overwrites JSL MainLoop

org !code

TestLoop:
    php
    sep #$20
    rep #$10
    lda.l $7FE300
    cmp.b #$01
    bne .done
    lda.l $7FE301
    beq .chest
    cmp.b #$01
    beq .save
    rep #$20
    lda.l $7FE305
    and.w #$00FF
    sep #$20
    jsl !load_rx
    bra .finish
.save:
    rep #$20
    lda.l $7FE305
    and.w #$00FF
    sep #$20
    jsl !save_rx
    bra .finish
.chest:
    rep #$20
    lda.l $7FE302
    sta.l $7FD4EF
    sep #$20
    lda.l $7FE304
    sta.l $7FD4EE
    jsl $8EC1DE
    rep #$20
    lda.l $7E09CF
    sta.l $7FE310
.finish:
    sep #$20
    lda.b #$02
    sta.l $7FE300
.done:
    plp
    jml !main_loop          ; MainLoop's RTL returns to $83:BC1A
