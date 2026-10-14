-- Iris-Dev#26: the AP base patch's scenario-item removal mode, switched by the config block ($EC:8047). Mesen 2 headless:
--   Mesen.exe --testRunner <rom> scenario_items.lua > out.txt
-- Build the ROM with build_scenario_items_rom.py (mode 0 or 1).
-- A "Remove item" event is hard to reach, so this calls its routine the way the opcode handler $80:A4B1 does: item in
-- $09CF, quantity in $09CD, JSL $82FA57. Once the new game stands in Elcid, Lua gives the party the Crown (459: bit 7 of
-- $0921) and Potion x10 in inventory slot 0 ($0A8D = $1402, id | quantity << 9), then the CPU jumps to a stub in WRAM
-- ($7F:E000) that turns NMI off, removes 1 Crown and then 1 Potion, keeping A, P and $09CF after each call at
-- $7F:E100.., and sets $7F:E300.
--   mode 0: the Crown's bit is cleared. mode 1: it stays. Both: the call returns A=0, C=0 and zeroes $09CF ("done,
--   scenario item"), and the Potion leaves the normal inventory (x9).
-- Prints PASS/FAIL per check and stops with 0 when every check passed.
print("LOADED")
local W, S = emu.memType.snesWorkRam, emu.memType.snesMemory
local frame, failures = 0, 0
local function rd(a) return emu.read(a, W) end
local function rd16(a) return rd(a) + rd(a + 1) * 256 end
local function check(name, ok)
  print((ok and "PASS " or "FAIL ") .. name)
  if not ok then failures = failures + 1 end
end

local HOOK_SITE = 0x82FA87
local STUB, RESULT, DONE = 0x1E000, 0x1E100, 0x1E300  -- $7F:E000.. in WRAM
local CROWN_BYTE, CROWN_BIT = 0x0921, 0x80
local INVENTORY, POTIONS_10, POTIONS_9 = 0x0A8D, 0x1402, 0x1202
local phase, t0, mode = "boot", 0, 0

local function remove(item)  -- 16-bit A/X/Y, DBR $7E
  return {
    0xA9, item % 256, item // 256,  -- LDA #item
    0x8D, 0xCF, 0x09,               -- STA $09CF
    0xA9, 0x01, 0x00,               -- LDA #1
    0x8D, 0xCD, 0x09,               -- STA $09CD
    0x22, 0x57, 0xFA, 0x82,         -- JSL $82FA57
  }
end
local function keep(at)  -- A (16-bit) at $7FE1at, P at +2, $09CF at +4
  return {
    0x08,                           -- PHP
    0x8F, at, 0xE1, 0x7F,           -- STA.l $7FE1at
    0xE2, 0x20,                     -- SEP #$20
    0x68,                           -- PLA (P)
    0x8F, at + 2, 0xE1, 0x7F,       -- STA.l $7FE1at+2
    0xC2, 0x30,                     -- REP #$30
    0xAD, 0xCF, 0x09,               -- LDA $09CF
    0x8F, at + 4, 0xE1, 0x7F,       -- STA.l $7FE1at+4
  }
end

local STUB_CODE = {}
local function emit(bytes) for _, b in ipairs(bytes) do STUB_CODE[#STUB_CODE + 1] = b end end
emit({
  0x78,                          -- SEI
  0xE2, 0x20,                    -- SEP #$20
  0xA9, 0x00,                    -- LDA #0
  0x8F, 0x00, 0x42, 0x00,        -- STA.l $004200: no NMI, whose handler would leave the stub
  0xA9, 0x7E, 0x48, 0xAB,        -- LDA #$7E : PHA : PLB (the routine reads $09CF and $091E through DBR)
  0xC2, 0x30,                    -- REP #$30
})
emit(remove(459)); emit(keep(0x00))
emit(remove(2)); emit(keep(0x10))
emit({
  0xE2, 0x20,                    -- SEP #$20
  0xA9, 0x01,                    -- LDA #1
  0x8F, 0x00, 0xE3, 0x7F,        -- STA.l $7FE300
  0x80, 0xFE,                    -- BRA *
})

emu.addEventCallback(function()
  if phase == "boot" then
    local f = frame % 40
    if f < 3 then emu.setInput({start = true}, 0) elseif f >= 20 and f < 23 then emu.setInput({a = true}, 0) end
  else emu.setInput({}, 0) end
end, emu.eventType.inputPolled)

local function jump_to_stub()
  local st = emu.getState()
  st["cpu.k"] = 0x7F; st["cpu.pc"] = 0xE000; st["cpu.d"] = 0
  -- endFrame is a line before vblank: the stub would take the NMI before it turns NMI off.
  st["internalRegisters.enableNmi"] = false; st["internalRegisters.nmiFlag"] = false
  st["cpu.needNmi"] = false; st["cpu.nmiFlagCounter"] = 0
  emu.setState(st)
end

emu.addEventCallback(function()
  frame = frame + 1
  local ok, err = pcall(function()
    if phase == "boot" and frame > 1500 then
      local map = rd(0x05AC)
      if map ~= 0x03 then print(string.format("FAIL not in Elcid (map %02X)", map)); emu.stop(1); return end
      check("the remove worker is hooked (JSL $E89A00)",
        emu.read(HOOK_SITE, S) == 0x22 and emu.read(HOOK_SITE + 1, S) == 0x00 and emu.read(HOOK_SITE + 2, S) == 0x9A
        and emu.read(HOOK_SITE + 3, S) == 0xE8)
      check("the held? lookup is vanilla (no NO_SCENARIO_ITEMS)", emu.read(0x82FB80, S) == 0x39)
      mode = emu.read(0xEC8047, S)
      print(string.format("config: scenario-item mode %d", mode))
      emu.write(CROWN_BYTE, rd(CROWN_BYTE) | CROWN_BIT, W)
      emu.write(INVENTORY, POTIONS_10 % 256, W); emu.write(INVENTORY + 1, POTIONS_10 // 256, W)
      print(string.format("before: $0921=%02X $0A8D=%04X", rd(CROWN_BYTE), rd16(INVENTORY)))
      for i, b in ipairs(STUB_CODE) do emu.write(STUB + i - 1, b, W) end
      emu.write(DONE, 0, W)
      phase = "run"; t0 = frame
      jump_to_stub()
      return
    end
    if phase == "run" then
      if rd(DONE) ~= 1 then
        if frame - t0 > 600 then
          local st = emu.getState()
          print(string.format("FAIL the stub never finished (pc %02X:%04X)", st["cpu.k"], st["cpu.pc"])); emu.stop(3)
        end
        return
      end
      local crown_a, crown_p, crown_arg = rd16(RESULT), rd(RESULT + 2), rd16(RESULT + 4)
      local potion_p, potion_arg = rd(RESULT + 0x12), rd16(RESULT + 0x14)
      print(string.format("Crown: A=%04X P=%02X $09CF=%04X; Potion: P=%02X $09CF=%04X", crown_a, crown_p, crown_arg,
        potion_p, potion_arg))
      print(string.format("after: $0921=%02X $0A8D=%04X", rd(CROWN_BYTE), rd16(INVENTORY)))
      local held = rd(CROWN_BYTE) & CROWN_BIT ~= 0
      if mode == 0 then
        check("mode 0: removing the Crown clears its held bit", not held)
      else
        check("mode 1: removing the Crown leaves its held bit", held)
      end
      check("the Crown's removal returns done, scenario item (A=0, C=0, $09CF zeroed)",
        crown_a == 0 and crown_p & 1 == 0 and crown_arg == 0)
      check("a Potion still leaves the normal inventory (x10 -> x9, C=0, $09CF zeroed)",
        rd16(INVENTORY) == POTIONS_9 and potion_p & 1 == 0 and potion_arg == 0)
      print(failures == 0 and "ALL PASS" or string.format("%d FAILED", failures))
      emu.stop(failures == 0 and 0 or 1)
      return
    end
    if frame > 60000 then print("FAIL timeout"); emu.stop(1) end
  end)
  if not ok then print("ERR " .. tostring(err)); emu.stop(2) end
end, emu.eventType.endFrame)
