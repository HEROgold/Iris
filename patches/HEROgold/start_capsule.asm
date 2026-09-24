; Iris: start a new game with a capsule monster, whatever the start map is.
;
; Defines (passed by start_capsule.py):
;   !species   capsule species 0-6 (capsule table index // 5: Foomy, Shaggy, Hard Hat, Red Fish,
;              Myconido, Raddisher, Armor Dog)
;   !n0..!n4   the capsule's name, 5 ASCII bytes (0 pads a shorter name)
;   !flag_address, !flag_mask   the species' story flag (byte and bit in the event flags at $7E:077E)
;   (no stub: bank $82 has no free space, see the tail call below)
;
; Hook: the new-game setup at $83:AD80 already checks whether to start with a capsule:
;     $83:AD80  LDA $0B51 : BIT #$02 : BEQ $ADAB     (7 bytes, file 0x1AD80)
;     $83:AD87  ... LDA #$07 : STA $0A7F : LDA #$01 : JSL $82:C352 ...  (special start, map $68)
;     $83:ADAB  normal start (start map / entrance; set_spawn_location edits these bytes)
; A is 8-bit and X is 16-bit here (the same state vanilla calls $82:C352 in). We replace the 7 bytes
; with a JML, replay the check, and on the normal path give the capsule before rejoining $83:ADAB.
;
; What giving a capsule means (mirrors the data part of the capsule-join routine $82:E7AA, which event
; opcode 81 uses, without its naming screen):
;   story flag of species s        the flag the join scene sets before "81 s" (Foomy 08, Shaggy 09,
;                                  Hard Hat 0C, Red Fish 0D, Myconido 0E, Raddisher 0F, Armor Dog 10),
;                                  so the scene treats the capsule as already given
;   $7E:11BB+s = 1                 owned flag for species s
;   $7F:F1A3+s = [$8E:E4C4+s]      the species' start level (vanilla table)
;   $7F:F180+s*5 = name            5-byte name per species
;   $7E:11A3 = s, $7E:11A4 = 1     active species and form (1 = first form, e.g. Foomy S)
;   $7E:0A7F = 7                   party slot 5 holds member 7 (the capsule)
;   JSL $82:C515                   per-species byte at $11A6+ (table $8E:E485)
;   JSL $82:C261                   build member 7 from those tables: name/level ($82:C3F8), stats
;                                  ($82:CE52, $82:D270), record pointer $1124 and script offsets
;                                  $1129/$112B from the capsule table at $97:DCB8
;   tail of $82:E7AA at $82:E7DB   EXP for the level ($82:CE23), save level/EXP/name back to the
;                                  per-species tables ($82:C443), TRB $0B50 #$80, then (because $0A7F
;                                  is already 7) PLA : STA $11A3 : JSR $C3F8 : JSR $CE52 : RTL.
;
; The tail ends in PLA : RTL (its entry pushed $11A3 after the JSL). CE23/C443/C3F8 end in RTS, so
; they only work from bank $82, and bank $82 has no free space for a stub. So we enter the tail with
; JML after pushing, by hand, what a JSL plus that PHA would have left on the stack: our bank (PHK),
; our return address - 1 (PEA), and the species byte (PHA), which PLA/STA $11A3 put back.
; See docs/reference/capsule-ram.md.

lorom

org $83AD80                     ; was AD 51 0B 89 02 F0 24
    jml start_capsule_hook      ; 4 bytes
    db $EA,$EA,$EA              ; pad the remaining 3 bytes with NOP

freecode
start_capsule_hook:
    lda $0B51                   ; replay the vanilla check (same DBR as the original code)
    bit.b #$02
    beq .give
    jml $83AD87                 ; bit set: vanilla's own special start, untouched
.give:
    lda.l !flag_address
    ora.b #!flag_mask
    sta.l !flag_address         ; story flag: the join scene won't give this capsule again
    ldx.w #!species
    lda.b #$01
    sta.l $7E11BB,x             ; owned
    lda.l $8EE4C4,x
    sta.l $7FF1A3,x             ; start level for this species
    lda.b #!n0
    sta.l $7FF180+(!species*5)
    lda.b #!n1
    sta.l $7FF180+(!species*5)+1
    lda.b #!n2
    sta.l $7FF180+(!species*5)+2
    lda.b #!n3
    sta.l $7FF180+(!species*5)+3
    lda.b #!n4
    sta.l $7FF180+(!species*5)+4
    lda.b #!species
    sta.l $7E11A3               ; active species
    lda.b #$01
    sta.l $7E11A4               ; active form: first form
    lda.b #$07
    sta.l $7E0A7F               ; party slot 5 = member 7 (capsule)
    jsl $82C515
    jsl $82C261                 ; build member 7 (EXP still 0)
    phk                         ; fake "JSL $82:E7DB" + the PHA its routine did before this point
    pea.w .back-1
    lda.b #!species
    pha
    jml $82E7DB                 ; EXP for the level, save to tables, reload member 7, RTL to .back
.back:
    jml $83ADAB                 ; continue with the normal new-game start
