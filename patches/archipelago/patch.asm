lorom

; TODO: move this file outside this directory. (one above)


; archipelago item
org $96F9AD  ; properties
    DB $00,$00,$00,$E4,$00,$00,$00,$00,$00,$00,$00,$00,$00
org $9EDD60  ; name
    DB "AP item     "       ; overwrites "Key30       "; TODO change to an unused overworld item
org $9FA900  ; sprite
    incbin "ap_logo.bin"
    warnpc $9FA980
