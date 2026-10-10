; Iris: the new-game hook. Everything Iris sets up for a fresh save runs here, in one routine, because asar can
; only hook these bytes once.
;
; Hook: the prologue-end / new-game handoff does `LDA #$FF : STA $099D : JMP $B18E` at $03:ADC2 (headerless file
; 0x1ADC2, a few bytes after the operands set_spawn_location edits). Both new-game paths (with and without the
; $0B51 bit-2 branch at $03:AD80) end here. $03:B18E itself is also reached from load-game paths, so it can't be
; hooked instead. A is 8-bit here (the surrounding code uses 8-bit immediates).
;
; !unlock_warps   Unlock every Warp-spell destination. Destinations are a byte array in save RAM
;                 ($7E:097B..$7E:0996): 0x00 = locked, 0xFF = unlocked. This bakes in the UNLOCK_WARP Game Genie codes.
; !skip_tutorial  Leave the Secret Skills Cave (map 5) as vanilla leaves it after the tutorial: set the tutorial's
;                 event flags and have Maxim learn Reset. See new_game.py for what each flag does.
; !start_items    Put items in the inventory through the game's add-item routine $82:E80C (item in $09CF, quantity
;                 in $09CD), as the Archipelago Ancient Cave patch's StartInventory does.

lorom

!unlock_warps ?= 1
!skip_tutorial ?= 0
!start_item_count ?= 0      ; number of (item, quantity) pairs in !start_items
!start_items ?= 0           ; "item,quantity,item,quantity,..." as dw values

; Event flag n is bit n % 8 (low bit first) of $7E:077E + n / 8, as the game's own helper at $80:BE30 computes it.
macro set_event_flag(n)
    lda.l $7E077E+(<n>>>3)
    ora.b #1<<(<n>&7)
    sta.l $7E077E+(<n>>>3)
endmacro

org $03ADC2                 ; file 0x1ADC2: was  A9 FF 8D 9D 09 4C 8E B1  (LDA #$FF/STA $099D/JMP $B18E)
    jml new_game_hook       ; 4 bytes
    db $EA,$EA,$EA,$EA      ; pad the remaining 4 replaced bytes with NOP

freecode
new_game_hook:
if !unlock_warps
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
endif
if !skip_tutorial
    ; Keep this list in sync with new_game.TUTORIAL_FLAGS (tests/test_new_game.py checks the assembled bytes).
    %set_event_flag($15)    ; FINISHED_TUTORIAL: the cave's exit door (05) opens on trigger 4, Tia's Elcid scene skips
    %set_event_flag($77)    ; Tia's "I'll wait at the cave" scene (03-C-02) has run
    %set_event_flag($AC)    ; the Reset lesson (LOAD_MAP 05-A-01) is done
    %set_event_flag($9E)    ; trigger-tile lessons 05-C-01 .. C-08 are done
    %set_event_flag($9F)
    %set_event_flag($A0)
    %set_event_flag($A1)
    %set_event_flag($A2)
    %set_event_flag($A3)
    %set_event_flag($AB)
    ; Maxim learns Reset the way event opcode 23 (handler $80:A489) does it: spell in $0A0B, character in A,
    ; JSL $82:FD3D. $0A0B is read through the data bank, so point DBR at a bank that mirrors WRAM.
    php
    phb
    sep #$20
    rep #$10
    lda #$80
    pha
    plb
    lda #$26                ; Reset
    sta $0A0B
    lda #$00                ; Maxim
    jsl $82FD3D
    plb
    plp
endif
if !start_item_count
    ; $82:E80C reads $09CD/$09CF through the data bank and can return with A 8-bit, so save everything around it.
    php
    phb
    sep #$20
    lda #$80
    pha
    plb
    rep #$30
    ldx #$0000
.next_item:
    lda.l start_items,x
    sta $09CF               ; item index
    lda.l start_items+2,x
    sta $09CD               ; quantity
    phx
    jsl $82E80C
    rep #$30
    plx
    inx #4
    cpx.w #!start_item_count*4
    bcc .next_item
    plb
    plp
endif
if !skip_tutorial || !unlock_warps == 0 || !start_item_count
    lda #$FF                ; A is still $FF after the warp stores unless something since changed it
endif
    sta.l $7E099D           ; the original displaced write (LDA #$FF : STA $099D)
    jml $03B18E             ; continue exactly where the vanilla JMP $B18E went

if !start_item_count
start_items:
    dw !start_items
endif
