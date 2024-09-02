import logging
from typing import TYPE_CHECKING, TypedDict
from helpers.files import read_file, restore_pointer, write_file
from logger import iris

if TYPE_CHECKING:
    from structures.monster import ScriptType
    from structures import Monster


class OpCode(TypedDict):
    params: int
    comment: str


op_codes: dict[int, OpCode] = {
    0x0: {"params": 0, "comment": "END"},
    0x1: {"params": 0, "comment": "Execute (don't exit) > I.E. For multiple actions"},
    0x2: {"params": 0, "comment": "Reset's game."},
    0x3: {"params": 2, "comment": "GoTo"}, # first 2 params > GoTo
    0x4: {"params": 2, "comment": "On Failure GoTo"}, # first 1 params > EQ Value, last 2 > GoTo
    0x5: {"params": 3, "comment": "On Chance GoTo"}, # first 1 params > EQ Value, last 2 > GoTo
    0x6: {"params": 5, "comment": "If Equal GoTo"}, # first 2 params > EQ Value, last 2 > GoTo
    0x7: {"params": 5, "comment": "If Not Equal GoTo"}, # first 2 params > EQ Value, last 2 > GoTo
    0x8: {"params": 5, "comment": "If Greater GoTo"}, # first 2 params > EQ Value, last 2 > GoTo
    0x9: {"params": 5, "comment": "If Less GoTo"}, # first 2 params > EQ Value, last 2 > GoTo
    0xA: {"params": 5, "comment": "If Greater or Equal GoTo"}, # first 2 params > EQ Value, last 2 > GoTo
    0xB: {"params": 5, "comment": "If Less or Equal GoTo"}, # first 2 params > EQ Value, last 2 > GoTo
    0xC: {"params": 3, "comment": "Register Set"}, # first 1 params > Register, last 2 > Value
    #  LOAD reg($XX), $YY YY
    #              Load $YY YY in "register" $XX

    #   $XX YY YY: $4E 00 00 => protection against Poison
    #              $50 00 00 => protection against Silence
    #              $52 00 00 => protection against Instant Death
    #              $54 00 00 => protection against Paralysis
    #              $56 00 00 => protection against Confusion
    #              $58 00 00 => protection against Sleep

    #              ! if bit 7 of the last byte is set 
    #                (generally: $0C XX YY 80)
    #                => LOAD reg($XX), reg($YY)
    #                   Load the value "register" $YY in "register" $XX

    0xD: {"params": 3, "comment": "Register ADD +"}, # first 1 params > Register, last 2 > Value
    0xE: {"params": 3, "comment": "Register SUB -"}, # first 1 params > Register, last 2 > Value
    0xF: {"params": 3, "comment": "Register MUL *"}, # first 1 params > Register, last 2 > Value
    0x10: {"params": 3, "comment": "Register DIV /"}, # first 1 params > Register, last 2 > Value
    0x11: {"params": 2, "comment": "Register Rand"}, # if N is the value stored in register $XX, store new value in range [0, N[(0 included, N excluded).
    0x12: {"params": 2, "comment": "Unknown"},
    0x13: {"params": 2, "comment": "Register Set Stat"},
    # LOAD reg($XX), stat_reg($YY)
            #      Load ??? in "register" $XX
            # $YY: ???
            #      $00 => current HP
            #      $01 => current MP
            #      $02 => max HP
            #      $03 => max MP
            #      $04 => ATP
            #      $05 => DFP

            #      $08 => INT (?)

            #      Note: target first! (ex.: 32 06, 32 01)
    0x14: {"params": 2, "comment": "Stat Set Register"},
    # LOAD stat_reg($YY), reg($XX)
    #         $YY: stat_reg($YY)
    #              $00 => current HP
    #              $01 => current MP
    #              $02 => max HP
    #              $03 => max MP
    #              $04 => ATP
    #              $05 => DFP
    #              $06 => STR
    #              $07 => AGL
    #              $08 => INT
    #              $09 => GUT
    #              $0A => MGR
    #              $0B => IP
    #              $0C => Level
    #              $0D => temp ATP+
    #              $0E => temp DFP+
    #              $0F => temp STR+
    #              $10 => temp AGL+
    #              $11 => temp INT+
    #              $12 => temp GUT+
    #              $13 => temp MGR+
    #              $14 => Status (+ the byte that follows it)

    #              Note: target first! (ex.: 32 06)

    #              Ex.: last attack of the Master (monster):
    #                   32 06 
    #                         Target self
    #                   14 01 00 
    #                         LOAD stat_reg(HP), reg($01)
    #                   28
    #                         Physical attack
    #                   (reg($01) = $0000 (probably)
    #                    => Master reduces his HP to 0 before attacking self)
    0x15: {"params": 2, "comment": "Register Set Stat Self"},
    # LOAD reg($XX), SELF_stat_reg($YY)
    #              same as:
    #              32 06
    #              13 XX YY
    0x16: {"params": 3, "comment": "Register AND"}, # AND reg($XX), $YY YY
    0x17: {"params": 3, "comment": "Register OR"}, # OR reg($XX), $YY YY
    0x1727: {"params": 3, "comment": "Add Element"},
    #     Add elemental power to attack
    #                  (weapon effect of some rings) 
    #          $XX XX: element
    #                  $00 01 => vs Dragons ('Dragon ring')
    #                  $00 20 => vs Sea enemies ('Sea ring')
    #                  $10 00 => (Light) vs Undead enemies ('Undead ring')
    0x18: {"params": 3, "comment": "Register XOR"}, # EOR reg($XX), $YY YY
    0x19: {"params": 1, "comment": "Unknown"},
    0x1A: {"params": 1, "comment": "Register NEG"}, # NEG reg($XX)
    #     $1A XX         : NEG reg($XX)
    #                  If the value stored in reg($XX) is n, store -n in reg($XX)
    #                  Ex.:
    #                  reg($87): $0003 (3)
    #                  NEG reg($87) => reg($87): $FFFD (-3)

    #                  ...
    #                  $FFFD -> -3
    #                  $FFFE -> -2
    #                  $FFFF -> -1
    #                  $0000 ->  0
    #                  $0001 ->  1
    #                  $0002 ->  2
    #                  ...
    0x1B: {"params": 1, "comment": "Unknown"},
    # $1B XX         : ???
    0x1C: {"params": 1, "comment": "Unknown"},
    # $1C XX         : ???
    0x1D: {"params": 1, "comment": "Cancel and continue?"},
    # $1D            : "Cancel and continue"?
    #                  (clean L2BASM reg $22 to $63)
    0x1E: {"params": 1, "comment": "Display Attack Name"},
    # $1E XX         : Display a monster attack name
    #             $XX: name number
    #                  ...
    #                  $7C => Devastation wave
    #                  $7D => Eerie light
    #                  $7E => Dark fry
    #                  ...
    #                  Effect on registers:
    #                  - load $00XX in reg($25)
    0x1F: {"params": 2, "comment": "Add Element"},
    # $1F XX XX      : Add elemental power to attack
    #                  (for some weapons and monster attacks) 
    #          $XX XX: element
    #                  $00 00 => Neutral
    #                  $00 01 => Effective against Dragons
    #                  $00 02 => Effective against Insects
    #                  $00 04 => Ice
    #                  $00 08 => Thunder
    #                  $00 10 => Earth
    #                  $00 20 => Effective against Sea enemies
    #                  $01 00 => Wind (CM: 'Hard Hat', 'Bluebird', 'Winged Horse')
    #                  $02 00 => Fire
    #                  $04 00 => Water
    #                  $08 00 => Soil (CM: 'Giant', 'Raddisher', 'Centaur')
    #                  $10 00 => Light
    #                  $20 00 => Shadow (Dark)
    #                  $40 00 => Effective against Hard enemies
    #                  $80 00 => Effective against Flying enemies

    #                  Effect on registers:
    #                  - load $XXXX in reg($27)
    0x20: {"params": 2, "comment": "Critical Hit Chance"},
    # $20 XX YY      : Enhanced critical hit rate
    #             $XX: % chances of critical hit
    #             $YY: damage multiplier for critical hits??? 
    #                  (real DMG = DMG * $YY / $10)???
    #                  Effect on registers:
    #                  - load $00XX in reg($28)
    #                  - load $00YY in reg($29)
    0x21: {"params": 5, "comment": "Physical Damage"},
    # $21 XX XX YY YY ZZ
    #                : Physical damage
    #                  (for items (boomerangs, some balls), monster attacks, ...)
    #          $XX XX: element
    #          $YY YY: base damage
    #             $ZZ: ???
    #                  Effect on registers:
    #                  - load $0005 in reg($23)
    #                  - load $0020 in reg($26)
    #                  - load element in reg($27)
    #                  - load ($10000 - base damage) in reg($2A)
    #                  - load $0020 in reg($2B)
    0x22: {"params": 5, "comment": "Magical Damage"},
    # $22 XX XX YY YY ZZ
    #                : Magical damage 
    #                  (for spells)
    #          $XX XX: element
    #          $YY YY: base damage
    #             $ZZ: ???
    #                  Effect on registers:
    #                  - load $000A in reg($23)
    #                  - load $01DC in reg($26)
    #                  - load element in reg($27)
    #                  - load ($10000 - (base damage + INT)) in reg($2A)
    #                  - load $0020 in reg($2B)

    # Hypothesis: 21 => not reflected by Mirror
    #                   damage dependent of row
    #             22 => reflected by Mirror
    #                   damage independent of row
    0x23: {"params": 2, "comment": "Bunny Sword"},
    # $23 78 00      : Weapon effect of the Bunny sword
    #                  Effect on registers:
    #                  - load $0020 in reg($26)
    #                  - load ($10000 - base damage) in reg($2A)
    #                  - load $0020 in reg($2B)
    0x24: {"params": 4, "comment": "Restore Stat"},
    # $24 XX YY YY ZZ: Restoring effect
    #             $XX: type
    #                  $00 => HP recovery
    #                  $01 => MP recovery
    #                  $04 => ATP modifier
    #                  $05 => DFP modifier
    #                  $06 => STR modifier
    #                  $07 => AGL modifier
    #                  $08 => INT modifier
    #                  $09 => GUT modifier
    #                  $0A => MGR modifier
    #             $YY YY: base value
    #             $ZZ: max fluctuation

    #             restored HP/MP/...  = base value + fluctuation
    #             with fluctuation = pseudo-randomly generated integer 
    #                                in range [0, max fluctuation[
    #                                (0 included, max fluctuation not included)

    #                  Effect on registers:
    #                  $XX = $00 =>
    #                  - load $YYYY in reg($2A)
    #                  - load $00ZZ in reg($2B)
    #                  $XX = $01 =>
    #                  - load $YYYY in reg($2D)
    #                  - load $00ZZ in reg($2E)
    0x25: {"params": 2, "comment": "Intensify Stat"},
    # $25 XX YY      : Statistics up/down effect
    #             $XX: type (affected stat)
    #                  $04 => ATP
    #                  $05 => DFP
    #                  $07 => AGL
    #                  $08 => INT
    #                  $09 => GUT
    #                  $0A => MGR
    #             $YY: % "intensity" of the effect

    #                  Effect on registers:
    #                  - $XX = 00 => load $YY in reg($2C)
    #                  - $XX = 01 => load $YY in reg($2F)
    #                  - $XX = 02 => load $YY in reg($32)
    #                  - $XX = 03 => load $YY in reg($35)
    #                  - $XX = 04 => load $YY in reg($38)
    #                  - $XX = 05 => load $YY in reg($3B)
    #                  - $XX = 06 => load $YY in reg($3E)
    0x26: {"params": 2, "comment": "Recover From Status"},
    # $26 XX YY      : Status recovering effect
    #             $XX: type
    #                  $00 => recover from Poisoning ('Antidote', 'Poison')
    #                  $01 => recover from Silence
    #                  $02 => recover from Death     ('Regain', ...)
    #                  $03 => recover from Paralysis ('Mystery pin', 'Release')
    #                  $04 => recover from Confusion ('Shriek')
    #                  $05 => recover from Sleep     ('Waken')
    #                  $07 => removes Mirror         (Erim's "Eerie light")
    #                         (verified by hacking the Antidote item 
    #                          (-> $26 07 64) and using one on a mirrored Selan)
    #             $YY: success probability ($64 = 100%)

    #                  Effect on registers:
    #                  - $XX = 03 => load $YY in reg($55)
    0x27: {"params": 2, "comment": "Apply Status Effect"},
    # $27 XX YY      : Status altering effect
    #             $XX: type
    #                  $00 => Poisoning
    #                  $01 => Silence ('Deflect')
    #                  $02 => Instant death
    #                  $03 => Paralysis
    #                  $04 => Confusion
    #                  $05 => Sleep
    #                  $06 => Status 6
    #                  $07 => Mirror
    #             $YY: success probability
    #                  $0A => 10%
    #                  $14 => 20%
    #                  $19 => 25%
    #                  $50 => 80%
    #                  $64 => 100%

    #                  Effect on registers:
    #                  - $XX = 03 => load $YY in reg($54)
    0x28: {"params": 0,"comment": "Physical Attack"},
    # $28            : Physical attack
    #                  (for monsters; like $37 for characters???) 
    #                  Effect on registers:
    #                  - load $0001 in reg($23)
    0x29: {"params": 0,"comment": "Defend"},
    # $29            : "Defends" (Offensive effect)
    #                  (for monsters / CM)
    #                  Effect on registers:
    #                  - load $0004 in reg($23)
    0x2A: {"params": 0,"comment": "Flee"},
    # $2A            : "Escapes" (flees) (Offensive effect)
    #                  (for monsters / CM)
    #                  Effect on registers:
    #                  - load $0006 in reg($23)
    0x2B: {"params": 2, "comment": "Use Item"},
    # $2B XX XX      : Use an item
    #          $XX XX: item number (see Item Compendium)
    #                  Ex.: 32 06 2B 01 00 => monster uses Charred newt on self
    0x2C : {"params": 1, "comment": "Monster Cast Spell"},
    # $2C XX         : Cast spell
    #                  (for monsters) 
    #             $XX: spell number (see Spell Compendium)
    #                  Effect on registers:
    #                  - load $0012 in reg($23)
    #                  - load $00XX in reg($24)
    0x2D: {"params": 1, "comment": "Call Companions"},
    # $2D XX         : "Calls companions"
    #                  (for monsters)
    #             $XX: monster number (see Monster Compendium)
    #                  $18 => Hound
    #                  $19 => Doben

    #                  Effect on registers:
    #                  *If the monster can call companions:
    #                  - load $0007 in reg($23)
    #                  - load $00XX in reg($24)
    #                  *Else:
    #                  - load $0002 in reg($10)
    0x2E: {"params": 1, "comment": "Unknown"},
    # $2E            : ???
    #                  Effect on registers:
    #                  - load $000D in reg($23)
    0x2F: {"params": 1, "comment": "Unknown"},
    # $2F XX         : ???
    # Hypothesis:
    # $2F XX
    # counts the number of dead in the hero party (CM included?) 
    # then stores that value in L2BASM reg($XX) (TO VERIFY!!!)

    0x30: {"params": 1,"comment": "Unknown"},
    # $30 XX         : ???
    0x31: {"params": 0,"comment": "Unknown"},
    # $31            : Reset the game (BRK)
    0x32: {"params": 1, "comment": "Target"},
    # $32 XX         : Target
    #                  (for some weapons and items, for monster attacks)
    #                  $32 01       => target one random foe
    #                  $32 01 32 05 => target all foes
    #                  $32 06       => target self
    #                  $32 06 32 05 => target all allies
    #                  ...
    0x33: {"params": 0, "comment": "Reset game"},
    # $33            : Reset the game (BRK)
    0x34: {"params": 0, "comment": "Reset game"},
    # $34            : Reset the game (BRK)
    0x35: {"params": 1,  "comment": "Special Item"},
    # $35 XX         : ???
    #             $XX: type
    #                  $01 => 'Warp' (spell and item)
    #                  $02 => 'Escape' (spell and item), 'Providence'
    #                  $03 => HP recovery? (see Potion) 
    #                  $22 => 'Smoke ball' (escape from battle)
    #                  $25 => 'Curselifter'
    0x36: {"params": 0, "comment": "Unknown"},
    # $36 XX         : ???
    0x37: {"params": 0, "comment": "Weapon Physical Attack"},
    # $37            : Physical attack(?)
    #                  (for weapons)
    #                  (execute Weapon effect code?)
    0x38: {"params": 0, "comment": "Reset game"},
    # $38            : Reset the game (BRK)
    0x39: {"params": 0, "comment": "Reset game"},
    # $39            : Reset the game (BRK)
    0x3A: {"params": 0, "comment": "Reset game"},
    # $3A            : Reset the game (BRK)
    0x3B: {"params": 0, "comment": "Reset game"},
    # $3B            : Reset the game (BRK)
    0x3C: {"params": 0, "comment": "Add INT to Damage"},
    # $3C            : "Add" INT to damage

    #                  - if DMG > 0 ("healing DMG") => DMG = DMG + INT
    #                    Ex.: if DMG = 100 and INT = 200
    #                         => DMG = 100 + 200 = 300

    #                  - if DMG = 0 => DMG = 0

    #                  - if DMG < 0 ("hurting DMG") => DMG = DMG - INT
    #                    Ex.: if DMG = -100 and INT = 200
    #                         => DMG = -100 - 200 = -300
    0x3E: {"params": 1, "comment": "Display CM Attack Name"},
    # $3E XX         : Display a Capsule Monster attack name???
    #             $XX: name number???
    #                  ...
    #                  $21 => Fish kick
    #                  ...
    #                  $2A => Bubble blast
    #                  ...
    0x3F: {"params": 3, "comment": "Learnable Attack"},
    # $3F XX YY YY   : If Capsule Monster has learned its learnable 
    #                  attack number $XX (in range [1, 3])
    #                  => jump to +$YYYY
    0x40: {"params": 0, "comment": "Unknown"},
    # $40 XX         : ???
    0x41: {"params": 0, "comment": "Wait > Checking Situation"},
    # $41            : "Checking situation."
    #                  (for monsters)
    #                  (see Master)
    #                  Effect on registers:
    #                  - load $000C in reg($23)
    0x42: {"params": 2, "comment": "Subroutine"},
    # $42 XX 00      : Call a L2BASM subroutine
    #             $XX: $00 => Weakness against Fire
    #             $XX: $01 => Weakness against Thunder
    #             $XX: $02 => Weakness against Water
    #             $XX: $03 => Weakness against Ice
    #             $XX: $04 => Weakness against "Eff. against Flying" attacks
    #                         + impervious to Earth
    #             $XX: $05 => Weakness against Light
    #             $XX: $06 => Protection against Fire
    #             $XX: $07 => Protection against Thunder
    #             $XX: $08 => Protection against Water
    #             $XX: $09 => Protection against Ice
    #             $XX: $0A => Protection against Light
    #             $XX: $0B => Protection against "neutral elemental" attacks?
    #             $XX: $0C => Weakness against "Eff. against Dragons" attacks
    #             $XX: $0D => Weakness against Shadow
    #             $XX: $0E => Protection against Shadow
    #             $XX: $0F => makes you a "Hard enemy"? (to check...)
    #             $XX: $10 => makes you an "insect"? (to check...)
    #             $XX: $11 => Full protection against 
    #                              Poisoning, 
    #                              Silence, 
    #                              Paralysis, 
    #                              Confusion 
    #                              and Sleep
    #                          Not protection against 
    #                              Instant Death, 
    #                              Effect 6 
    #                              and Mirror
    #                         (For a lot of monsters (bosses...), 
    #                          'Seethru cape', 'Seethru silk')
    #             $XX: $12 => Full protection against Instant Death but 
    #                         HP recovery spells inflict damage! (i.e.: you're
    #                         undead)
    #                         (Not used for items. Common for monsters)
    #             $XX: $13 => ??? (For Core monsters only. Not used for items)
    #                         (greatly reduce all magic DMG?)
    #             $XX: $14 => (For Gorem monsters only. Not used for items)
    #                         Protection against all attacks except "neutral 
    #                         elemental" attacks?
    #             $XX: $15 => ???
    #             $XX: $16 => (Not used for items/monster/caps.monsters)
    #             $XX: $17 => Protection against "hard" attacks?
    #                         (Not used for items. Used for Demise and Leech 
    #                          (monsters))
    #             $XX: $18 => Good protection against a certain elemental 
    #                         damage.
    #                         0C 81 02 00 42 18 00 
    #                          => Fire DMG greatly reduced (by 50 % ?)
    #                         (Gold gloves, Gold shield, Holy shield, 
    #                         Plati gloves, Plati shield, Rune gloves (IP effect))
    #                         (not used for monsters)
    #             $XX: $19 => Full protection against a certain elemental 
    #                         damage.
    #                         Ex.:
    #                         (Apron shield, Bolt shield, Cryst shield, 
    #                         0C 81 02 00 42 19 00 
    #                          => Fire attacks miss
    #                         Dark mirror, Flame shield, Water gaunt (IP effect))
    #                         (not used for monsters)
    #             $XX: $1A => "elemental mirror"
    #                         0C 81 02 00 42 1A 00 
    #                          => Fire attacks bounce back at attacker 
    #                             (like with Mirror)
    #                         (Agony helm, Aqua helm, Boom turban, 
    #                         Brill helm, Hairpin, Ice hairband (IP effect))
    #                         (not used for monsters)
    #             $XX: $1B => ??? (not used for items / monsters)
    #                  ...
    #             $XX: $23 => ???
    #             $XX: $24 => 'Miracle care' IP effect (Pearl shield):
    #                         FULL PROTECTION AGAINST ALL DAMAGE!
    0x43: {"params": 0, "comment": "Return from Subroutine"},
    # $43            : Return from a L2BASM subroutine
    0x44: {"params": 2, "comment": "Unknown"},
    # $44 XX YY      : ???
    0x477800_FF_54014F: {"params": 0, "comment": "Cast IP Spell"},
    #  _FF_ > Variable
    # $47 78 00     54 XX     01     4F: 
    #                  Cast spell
    #                  (for IPs. Doesn't consume MPs) 
    #             $XX: spell number (see Spell Compendium)
    0x47: {"params": 2, "comment": "Unknown"},
    # $47 ?? ??      : ???
    0x49: {"params": 0, "comment": "Unknown"},
    # $49            : ???
    0x4D: {"params": 0, "comment": "Unknown"},
    # $4D            : ???
    0x4E: {"params": 2, "comment": "Load Register > Stat Register"},
    # $4E XX YY      : LOAD reg($XX), TARGET_stat_reg($YY)
    #                  used in subroutine $42 28 00 (for some CM reaction scripts)
    0x4F: {"params": 0, "comment": "Exit without executing effect code"},
    # $4F            : Exit without executing "effect code"???
    #                  (see Gold Dragon)
    0x50: {"params": 0, "comment": "No Re-targetting Spells"},
    # $50            : A spell or attack where this instruction is used 
    #                  will not be retargetted if it targets a dead party 
    #                  member.
    #                  Is used for Rally and Valor (since those are the 2 
    #                  spells that affect dead characters). 
    #                  Could be used in other spells or attacks
    #                  (ex.: weapon effect of a sword: $50 37
    #                        => this sword would allow to hit a dead party 
    #                           member (the attack wouldn't be retargetted))
    0x51: {"params": 0, "comment": "Dark Reflector Effect"},
    # $51            : Dark reflector effect
    #                  Effect on registers:
    #                  - load $0002 in reg($61)???
    #                  - ???
    0x52: {"params": 0, "comment": "Reflector?"},
    # $52            : ??? (some kind of reflector?)
    0x53: {"params": 1, "comment": "Unknown"},
    # $53 XX         : ???
    0x54: {"params": 1, "comment": "Cast IP Spell?"},
    # $54 XX         : (cast spell?)
    #                  (for IPs)
    #             $XX: spell number
    #                  Effect on registers:
    #                  - load $0019 in reg($23)
    #                  - load $00XX in reg($24)
    0x55: {"params": 3, "comment": "Unsigned Division?"},
    # $55 XX YY YY   : "unsigned" division? (opcode $10 = "signed" division?)
    0x56: {"params": 2, "comment": "Attack Name Duration"},
    # $56 XX XX      : used to specify how long the attack name must be 
    #                  displayed.
    #                  Min: $0001
    #                  Max: the duration of the attack (animation) is the limit.
    #                  Note: $56 00 00 => the attack name is diplayed until 
    #                                     a new message must be displayed
    #                                     (=> until the end of the attack).
    0x57: {"params": 3, "comment": "Item Effectiveness > Spell"},
    # $57 XX XX YY   : For spells: effectiveness is increased by an item
    #                  (ex.: the 'Thunder ring' for the 'Thunder' spell)
    #          $XX XX: number of the item in the item list.
    #             $YY: increasment???
    0x58: {"params": 0, "comment": "Empty temp stat registers. (Eerie Light Effect)"},
    # $58            : Empty all "temp" stat_reg of all the heroes (CM included)
    #                  (special effect of Erim's Eerie light).
    0x59: {"params": 0, "comment": "Empty temp stat registers. (Enemies)"},
    # $59            : Empty all "temp" stat_reg of all enemies.
    0x5A: {"params": 1, "comment": "Call Battle Animation"},
    # $5A XX         : Call a battle animation (used for monster attacks/spells)
    #             $XX: animation number
    #                  ...
    #                  $12 => Flash spell
    #                  ...
    #                  $6B => Eerie light
    #                  ...
    #                  $90 => Dark fry
    #                  ...
    #                  $98 => Devastation wave
    #                  ...
    #                  $9B => Dark reflector
    #                  ...
    0x5B: {"params": 0, "comment": "Lose on Master Suicide"},
    # $5B            : Used in the final attack of the Master.
    #                  Effect: makes you lose if the Master kills himself 
    #                  (without this opcode, you would win).
    0x5C: {"params": 0, "comment": "Hide damage dealt"}
    # $5C            : Don't show the value of inflicted DMG 
    #                  (but the DMG is inflicted nonetheless!)
}
subroutines = {
    0x00:   " => Weak Vs Fire",
    0x01:   " => Weak Vs Thunder",
    0x02:   " => Weak Vs Water",
    0x03:   " => Weak Vs Ice",
    0x04:   " => Eff. against Flying attacks + impervious to Earth",
    0x05:   " => Weakness against Light",
    0x06:   " => Protection against Fire",
    0x07:   " => Protection against Thunder",
    0x08:   " => Protection against Water",
    0x09:   " => Protection against Ice",
    0x0A:   " => Protection against Light",
    0x0B:   " => Protection against neutral elemental attacks?",
    0x0C:   " => Weakness against Eff. against Dragons attacks",
    0x0D:   " => Weakness against Shadow",
    0x0E:   " => Protection against Shadow",
    0x0F:   " => makes you a Hard enemy? (to check...)",
    0x10:   " => makes you an insect? (to check...)",
    0x11:   " => Full protection against"
            " Poisoning, Silence, Paralysis, Confusion and Sleep."
            "Not protection against Instant Death, Effect 6 and Mirror."
            "(For a lot of monsters (bosses...),  'Seethru cape', 'Seethru silk'", 
    0x12:   " => Full protection against Instant Death but "
            "HP recovery spells inflict damage! (i.e.: you're undead)"
            "(Not used for items. Common for monsters)",
    0x13:   " => ??? (For Core monsters only. Not used for items), (greatly reduce all magic DMG?)",
    0x14:   " => (For Gorem monsters only. Not used for items),"
            "Protection against all attacks except neutral elemental attacks?",
    0x15:   " => ???",
    0x16:   " => (Not used for items/monster/caps.monsters)",
    0x17:   " => Protection against hard attacks?"
            "(Not used for items. Used for Demise and Leech",
    0x18:   " => Good protection against a certain elemental damage."
            "(Gold gloves, Gold shield, Holy shield, "
            " Plati gloves, Plati shield, Rune gloves (IP effect))"
            "(not used for monsters)",
    0x19:   " => Full protection against a certain elemental "
            " damage."
            " Ex.:"
            " (Apron shield, Bolt shield, Cryst shield, "
            " 0C 81 02 00 42 19 00 "
            "  => Fire attacks miss"
            " Dark mirror, Flame shield, Water gaunt (IP effect))"
            " (not used for monsters)",
    0x1A:   " => elemental mirror"
            " 0C 81 02 00 42 1A 00 "
            "  => Fire attacks bounce back at attacker "
            "     (like with Mirror)"
            " (Agony helm, Aqua helm, Boom turban, "
            " Brill helm, Hairpin, Ice hairband (IP effect))"
            " (not used for monsters)",
    0x1B:   " => ??? (not used for items / monsters)",
    0x22:   " => ??? (Nosferatu)",
    0x23:   " => ???",
    0x24:   " => 'Miracle care' IP effect (Pearl shield):"
            "FULL PROTECTION AGAINST ALL DAMAGE!",
}

def calc_offset(offset: bytes):
    """Calculate the offset of the jump, using signed bytes."""
    return

class SubRoutine:
    def __init__(self, index: int) -> None:
        self.index = index

    # TODO: implement reading and writing of subroutines.


# TODO: implement parent child relationship for scripts.
# Where jump to or GOTO locations are children. (Same as structures\events.py)
class BattleScript:
    pointer: int
    _script: list[tuple[int, bytes, bytes | None]]
    _pretty_script: list[tuple[str, str]]
    _visited: list[int]
    crash_codes = [0x02, 0x31, 0x33, 0x34, 0x38, 0x39, 0x3A, 0x3B]

    def __init__(self, monster: "Monster", pointer: int, type: "ScriptType") -> None:
        self.logger = logging.getLogger(f"{iris.name}.{monster.name}.Script.{type.name.title()}")
        self.monster = monster
        self.pointer = pointer
        self.type = type
        self._script = []
        self._pretty_script = []
        self._visited = []

    def get_arguments(self, opcode: int) -> int:
        return op_codes[opcode]["params"]

    @property
    def end(self):
        return self.pointer + len(self._script)

    def write(self):
        # FIXME: Sometimes overwrites (parts) of the script.
        for pointer, op_code, args in self._script:
            write_file.seek(pointer)
            write_file.write(op_code)
            if args:
                write_file.write(args)

    @restore_pointer
    def read(self, offset: int=0):
        restore_stack: list[int] = [self.pointer]
        read_file.seek(self.pointer + offset)

        while True:
            tell = read_file.tell()

            if tell in self._visited:
                if len(restore_stack) == 0:
                    break
                self.logger.debug(f"{tell} already visited. (continue...)")
                read_file.seek(restore_stack.pop())
                continue

            self._visited.append(tell)

            if tell == self.monster.pointer:
                self.logger.debug(f"{tell} reached monster pointer. (continue...)")
                read_file.seek(restore_stack.pop())
                continue

            byte = read_file.read(1)
            op_code = byte[0]
            nr_args = self.get_arguments(op_code)

            offset += 1
            if nr_args > 0:
                offset += nr_args
                args = read_file.read(nr_args)
                self._script.append((tell, byte, args))
            else:
                args = b""
                self._script.append((tell, byte, None))

            self._pretty_script.append((hex(op_code), f"Code -->> {op_codes[op_code]["comment"]}"))

            if op_code == 0x0:
                read_file.seek(restore_stack.pop())
                continue
            elif op_code == 0x1:
                # Execute effect code
                pass
            elif op_code in self.crash_codes:
                # Crashes game.
                self.logger.critical(f"Crash code {hex(op_code)} found.")
            elif op_code == 0x3:
                assert nr_args == 2 and args
                jump_offset = int.from_bytes(args[0:2], "little")
                self._pretty_script.append((hex(jump_offset), "0 -> Jump Offset"))
                restore_stack.append(self.monster.pointer + jump_offset)
            elif op_code == 0x4: # On Failure GoTo > If previous command failed
                assert nr_args == 2 and args
                jump_offset = int.from_bytes(args, "little")
                self._pretty_script.append((hex(jump_offset), "0 -> Jump Offset"))
                restore_stack.append(self.monster.pointer + jump_offset)
            elif op_code == 0x5: # Chance GoTo
                assert nr_args == 3 and args
                chance = args[0]
                bytes_offset = args[1:3]
                jump_offset = int.from_bytes(bytes_offset, "little", signed=True)
                self._pretty_script.append((hex(chance), f"0: Chance ({chance/255*100}%)"))
                self._pretty_script.append((hex(jump_offset), "1 -> Jump Offset"))
                restore_stack.append(self.monster.pointer + jump_offset)
            elif op_code == 0x6:
                assert nr_args == 5 and args
                compare_value = int.from_bytes(args[0:2], "little")
                compare_against = int.from_bytes(args[2:4], "little")
                jump_offset = int.from_bytes(args[4:6], "little")
                self._pretty_script.append((hex(compare_value), "1 -> Compare == (Reg)"))
                self._pretty_script.append((hex(compare_against), "2 -> Comparison (Value)"))
                self._pretty_script.append((hex(jump_offset), "3 -> Jump Offset"))
                restore_stack.append(self.monster.pointer + jump_offset)
            elif op_code == 0x7:
                assert nr_args == 5 and args
                compare_value = int.from_bytes(args[0:2], "little")
                compare_against = int.from_bytes(args[2:4], "little")
                jump_offset = int.from_bytes(args[4:6], "little")
                self._pretty_script.append((hex(compare_value), "1 -> Compare != (Reg)"))
                self._pretty_script.append((hex(compare_against), "2 -> Comparison (Value)"))
                self._pretty_script.append((hex(jump_offset), "3 -> Jump Offset"))
                restore_stack.append(self.monster.pointer + jump_offset)
            elif op_code == 0x8:
                assert nr_args == 5 and args
                compare_value = int.from_bytes(args[0:2], "little")
                compare_against = int.from_bytes(args[2:4], "little")
                jump_offset = int.from_bytes(args[4:6], "little")
                self._pretty_script.append((hex(compare_value), "1 -> Compare > (Reg)"))
                self._pretty_script.append((hex(compare_against), "2 -> Comparison (Value)"))
                self._pretty_script.append((hex(jump_offset), "3 -> Jump Offset"))
                restore_stack.append(self.monster.pointer + jump_offset)
            elif op_code == 0x9:
                assert nr_args == 5 and args
                compare_value = int.from_bytes(args[0:2], "little")
                compare_against = int.from_bytes(args[2:4], "little")
                jump_offset = int.from_bytes(args[4:6], "little")
                self._pretty_script.append((hex(compare_value), "1 -> Compare < (Reg)"))
                self._pretty_script.append((hex(compare_against), "2 -> Comparison (Value)"))
                self._pretty_script.append((hex(jump_offset), "3 -> Jump Offset"))
                restore_stack.append(self.monster.pointer + jump_offset)
            elif op_code == 0xA:
                assert nr_args == 5 and args
                compare_value = int.from_bytes(args[0:2], "little")
                compare_against = int.from_bytes(args[2:4], "little")
                jump_offset = int.from_bytes(args[4:6], "little")
                self._pretty_script.append((hex(compare_value), "1 -> Compare >= (Reg)"))
                self._pretty_script.append((hex(compare_against), "2 -> Comparison (Value)"))
                self._pretty_script.append((hex(jump_offset), "3 -> Jump Offset"))
                restore_stack.append(self.monster.pointer + jump_offset)
            elif op_code == 0xB:
                assert nr_args == 5 and args
                compare_value = int.from_bytes(args[0:2], "little")
                compare_against = int.from_bytes(args[2:4], "little")
                jump_offset = int.from_bytes(args[4:6], "little")
                self._pretty_script.append((hex(compare_value), "1 -> Compare <= (Reg)"))
                self._pretty_script.append((hex(compare_against), "2 -> Comparison (Value)"))
                self._pretty_script.append((hex(jump_offset), "3 -> Jump Offset"))
                restore_stack.append(self.monster.pointer + jump_offset)
            elif op_code in [0xC, 0xD, 0xE, 0xF, 0x10, 0x16, 0x17, 0x18]:
                assert nr_args == 3 and args
                reg = args[0]
                value = int.from_bytes(args[1:3], "little")
                self._pretty_script.append((hex(reg), "0 -> Register"))
                self._pretty_script.append((hex(value), "1 -> Value"))
            elif op_code in [0x11, 0x12, 0x13, 0x14, 0x15]:
                assert nr_args == 2 and args
                reg = args[0]
                value = int.from_bytes(args[1:2], "little")
                self._pretty_script.append((hex(reg), "0 -> Register"))
                self._pretty_script.append((hex(value), "1 -> Value"))
            elif op_code == 0x1A:
                assert nr_args == 1 and args
                reg = args[0]
                self._pretty_script.append((hex(reg), "0 -> Register"))
            elif op_code == 0x32:
                # TODO: investigate cases for target all foes/allies/self (more args?)
                assert nr_args == 1 and args
                target = args[0]
                self._pretty_script.append((hex(target), "0 -> Target"))
            elif op_code == 0x37:
                # Physical Attack, Execute Weapon effect?
                pass
            elif op_code == 0x42: # Subroutine
                assert nr_args == 2 and args and args[1:2] == b"\x00"
                self._pretty_script.append((hex(args[0]), f"0 -> {subroutines[args[0]]}"))
                self._pretty_script.append((hex(args[1]), "1 -> Empty Byte"))
                # TODO: read subroutines. (So we could edit it later) (Separate class?)
            elif op_code == 0x43:
                # Return from Subroutine
                continue
            else:
                for arg in args:
                    self._pretty_script.append((hex(arg), f"{args.index(arg)} -> Argument"))

        assert len(restore_stack) == 0, f"Script restore stack not empty: {restore_stack}"
        s = "\n"
        for i in self._pretty_script:
            s += f"    {i[0]}: {i[1]}\n"
        self.logger.debug(s)

