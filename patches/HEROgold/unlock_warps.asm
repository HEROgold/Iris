; Iris: unlock every Warp-spell destination from the start of the game.
;
; Warp destinations are stored as a per-location byte array in save RAM ($7E:097B..$7E:0996):
; 0x00 = not yet visited (locked), 0xFF = unlocked. Vanilla only sets $099D at new game, so a
; fresh save can cast Warp but has no destinations. The "UNLOCK_WARP" Game Genie codes force the
; 22 real destination bytes to 0xFF at runtime; this patch bakes that into the ROM instead.
;
; Hook: the prologue-end / new-game handoff already does `LDA #$FF : STA $099D : JMP $B18E` at
; $03:ADC2 (headerless file 0x1ADC2 -- the same routine set_spawn_location edits a few bytes above).
; A is 8-bit here (the surrounding code uses 8-bit immediates), so we don't touch the P register.
; We replace those 8 bytes with a JML to our routine, which sets the destination bytes (using long
; stores so it is DBR-independent), replays the original `STA $099D`, and jumps to the original
; continuation at $03:B18E exactly as vanilla would.

lorom

org $03ADC2                 ; file 0x1ADC2: was  A9 FF 8D 9D 09 4C 8E B1  (LDA #$FF/STA $099D/JMP $B18E)
    jml unlock_warp_hook    ; 4 bytes
    db $EA,$EA,$EA,$EA      ; pad the remaining 4 replaced bytes with NOP

freecode
unlock_warp_hook:
    lda #$FF                ; A stays 8-bit (M flag already set by surrounding code)
    ; The 22 real warp-destination flags (skips reserved 0984/0985/0987/0993/0994/0995).
    sta.l $7E097B
    sta.l $7E097C
    sta.l $7E097D
    sta.l $7E097E
    sta.l $7E097F
    sta.l $7E0980
    sta.l $7E0981
    sta.l $7E0982
    sta.l $7E0983
    sta.l $7E0986
    sta.l $7E0988
    sta.l $7E0989
    sta.l $7E098A
    sta.l $7E098B
    sta.l $7E098C
    sta.l $7E098D
    sta.l $7E098E
    sta.l $7E098F
    sta.l $7E0990
    sta.l $7E0991
    sta.l $7E0992
    sta.l $7E0996
    sta.l $7E099D           ; original displaced write (LDA #$FF : STA $099D)
    jml $03B18E             ; continue exactly where the vanilla JMP $B18E went
