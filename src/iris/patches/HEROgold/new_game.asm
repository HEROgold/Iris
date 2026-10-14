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
; !skip_intro     Debug runs: set the flags the Elcid intro (Tia's shop, dinner, "Bad news") would have set. The new
;                 game also starts at Elcid entrance 3 (set_spawn_location) so the opening scene never loads.
; !start_items    Put items in the inventory through the game's add-item routine $82:E80C (item in $09CF, quantity
;                 in $09CD), as the Archipelago Ancient Cave patch's StartInventory does.
; !start_mermaid_jade, !start_engine
;                 Standalone Iris (Iris-Dev#16, #24): start with the Mermaid jade (448) and/or the Engine (449) and
;                 the ship they make: type $09DF 1 (submarine) with the jade alone, 2 (submarine + airship) with the
;                 Engine (vanilla has no airship that can't dive), placed at Elcid's dock $C8 the first time the world
;                 map loads ($09E0 = 0 on the map, $09EE = the pending dock, placed by $86:A2AE). No story flag is set
;                 (86/98/99/127/145 gate story scenes and NPCs). Two hooks keep the ship usable: event opcode 7C (set
;                 ship type, $80:BD6C) never lowers $09DF, so the Treadool scene's 7C(00) and the submarine scene's
;                 7C(01) can't take the vehicle back, and Warp arrival keeps the ship at the destination's dock before
;                 the Auralio water gate opens instead of sending it to Treadool ($86:9C31 BNE -> BRA).
; !ap_start_vehicles
;                 Archipelago (overworld): read the config block's start bytes once, at new game, and set the item
;                 bits: Start with Mermaid Jade = Ship 454 + Submarine 455, Start with Engine = Ship 454 + Engine 449.
;                 key_items.asm builds the ship from them and places it at the nearest dock.

lorom

!unlock_warps ?= 1
!skip_tutorial ?= 0
!skip_intro ?= 0
!start_item_count ?= 0      ; number of (item, quantity) pairs in !start_items
!start_items ?= 0           ; "item,quantity,item,quantity,..." as dw values
!clear_ap_rx ?= 0           ; zero the Archipelago RX counters and the blue-chest counter (archipelago/overworld/rx.asm)
!ap_blue_chests ?= $F027D0  ; constants.AP_SRAM_BLUE_CHESTS
!start_mermaid_jade ?= 0
!start_engine ?= 0
!ap_start_vehicles ?= 0
!ap_opt_start_mermaid_jade ?= $EC8042   ; constants.AP_OPT_START_MERMAID_JADE
!ap_opt_start_engine ?= $EC8043         ; constants.AP_OPT_START_ENGINE

!SCENARIO_0920 = $7E0920    ; 448 Mermaid jade bit $10, 449 Engine bit $20
!SCENARIO_0921 = $7E0921    ; 454 Ship bit $04, 455 Submarine bit $08
!ELCID_DOCK = $C8

; Event flag n is bit n % 8 (low bit first) of $7E:077E + n / 8, as the game's own helper at $80:BE30 computes it.
macro set_event_flag(n)
    lda.l $7E077E+(<n>>>3)
    ora.b #1<<(<n>&7)
    sta.l $7E077E+(<n>>>3)
endmacro

org $03ADC2                 ; file 0x1ADC2: was  A9 FF 8D 9D 09 4C 8E B1  (LDA #$FF/STA $099D/JMP $B18E)
    jml new_game_hook       ; 4 bytes
    db $EA,$EA,$EA,$EA      ; pad the remaining 4 replaced bytes with NOP

if !start_mermaid_jade || !start_engine
org $80BD6F                 ; event opcode 7C: was  8D DF 09 82 8B DF  (STA $09DF : BRL $9D00), A = the operand
    jml ship_upgrade
    nop
    nop

org $869C31                 ; Warp arrival: was  D0 3C  (BNE $9C6F on flag 149, the Auralio water gate)
    db $80                  ; BRA: the ship always goes to the destination's dock
endif

; NEW_GAME_CODE_REGION (apply_asm_patch's code_region), not freecode: asar's freespace finder lands in vanilla tile data.
org !code
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
if !skip_intro
    ; Keep this list in sync with new_game.INTRO_FLAGS (tests/test_new_game.py checks the assembled bytes).
    %set_event_flag($01)    ; MAXIM_IN_PARTY, set at the end of Tia's shop scene (04-A-01)
    %set_event_flag($0A)    ; NEW_GAME_STARTED, set by 03-A-02 before it walks Maxim into Tia's shop
    %set_event_flag($16)    ; Tia's dinner scene (04-C-01) has run
    %set_event_flag($96)    ; the "Bad news" scene (03-C-01) has run; the cave guard (06-B-50) lets you in
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
if !clear_ap_rx
    php
    rep #$20
    lda.w #$0000
    sta.l $F02800           ; received
    sta.l $F02802           ; processed
    sta.l !ap_blue_chests   ; Ancient Cave blue chests counted (blue_chests.asm)
    plp
endif
if !start_mermaid_jade || !start_engine
    lda.l !SCENARIO_0920
    ora.b #(!start_mermaid_jade*$10)|(!start_engine*$20)
    sta.l !SCENARIO_0920
    lda #$00
    sta.l $7E09E0           ; the ship is on the world map
    lda #!ELCID_DOCK
    sta.l $7E09EE           ; at Elcid's dock, once the world map loads
    lda #1+!start_engine
    sta.l $7E09DF           ; 1 submarine, 2 submarine + airship
endif
if !ap_start_vehicles
    lda.l !ap_opt_start_mermaid_jade
    beq .no_start_jade
    lda.l !SCENARIO_0921
    ora #$0C                ; Ship + Submarine
    sta.l !SCENARIO_0921
.no_start_jade:
    lda.l !ap_opt_start_engine
    beq .no_start_engine
    lda.l !SCENARIO_0921
    ora #$04                ; Ship
    sta.l !SCENARIO_0921
    lda.l !SCENARIO_0920
    ora #$20                ; Engine
    sta.l !SCENARIO_0920
.no_start_engine:
endif
if !skip_tutorial || !skip_intro || !unlock_warps == 0 || !start_item_count || !clear_ap_rx || !start_mermaid_jade || !start_engine || !ap_start_vehicles
    lda #$FF                ; A is still $FF after the warp stores unless something since changed it
endif
    sta.l $7E099D           ; the original displaced write (LDA #$FF : STA $099D)
    jml $03B18E             ; continue exactly where the vanilla JMP $B18E went

if !start_item_count
start_items:
    dw !start_items
endif

if !start_mermaid_jade || !start_engine
; Event opcode 7C, m=1, DB = the script's bank. The story only raises the ship type, except the Treadool scene's 7C(00);
; with a vehicle from the start, neither may take it back.
ship_upgrade:
    cmp.l $7E09DF
    bcc .keep
    sta.l $7E09DF
.keep:
    jml $809D00
endif

warnpc !code_end
