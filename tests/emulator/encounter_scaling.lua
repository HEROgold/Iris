-- Iris-Dev#25: the AP base patch's encounter scaling, switched by the config block ($EC:8044 on/off, $EC:8045 LOW,
-- $EC:8046 RANGE). Mesen 2 headless:
--   Mesen.exe --testRunner <rom> encounter_scaling.lua > out.txt
-- Build the ROM with build_encounter_scaling_rom.py (off, or on LOW HIGH).
-- Walking into a roaming monster is hard to script, so this calls the hook's routine the way $83:B9EC does. Once the
-- new game stands in Elcid, the CPU jumps to a stub in WRAM ($7F:E000) that turns NMI off and RUNS times loads a fake
-- vanilla formation id into A (8-bit A, 16-bit X/Y) and does JSL $E28065 (what the JSL at $83:B9EC calls), keeping
-- each run's A at $7F:E100+n and $7F:F8A4 at $7F:E200+n. Then it sets $7F:E300 and spins.
--   off: $7F:F8A4 and A stay the vanilla id every run.
--   on:  $7F:F8A4 is the table's formation ($E2:8000 + level - 1) for some level in the party's average + [LOW, HIGH],
--        clamped to 1..99; the party's levels are set to 30 first so the band doesn't clamp onto one entry.
-- Prints PASS/FAIL per check and stops with 0 when every check passed.
print("LOADED")
local W, S = emu.memType.snesWorkRam, emu.memType.snesMemory
local frame, failures = 0, 0
local function rd(a) return emu.read(a, W) end
local function check(name, ok)
  print((ok and "PASS " or "FAIL ") .. name)
  if not ok then failures = failures + 1 end
end

local HOOK_SITE, TABLE = 0x83B9EC, 0xE28000
local STUB, RESULT_A, RESULT_F, DONE = 0x1E000, 0x1E100, 0x1E200, 0x1E300  -- $7F:E000.. in WRAM
local VANILLA = 0xC0                 -- past the 192 formations: the table can't hold it
local RUNS, LEVEL = 64, 30
local phase, t0, allowed, enabled = "boot", 0, {}, 0

local STUB_CODE = {
  0x78,                          -- SEI
  0xE2, 0x20,                    -- SEP #$20
  0xA9, 0x00,                    -- LDA #0
  0x8F, 0x00, 0x42, 0x00,        -- STA.l $004200: no NMI, whose handler would leave the stub
  0xC2, 0x10,                    -- REP #$10
  0xA2, 0x00, 0x00,              -- LDX #0
  -- loop (offset 14):
  0xA9, VANILLA,                 -- LDA #VANILLA
  0x22, 0x65, 0x80, 0xE2,        -- JSL $E28065
  0xE2, 0x20,                    -- SEP #$20
  0x9F, 0x00, 0xE1, 0x7F,        -- STA.l $7FE100,x
  0xAF, 0xA4, 0xF8, 0x7F,        -- LDA.l $7FF8A4
  0x9F, 0x00, 0xE2, 0x7F,        -- STA.l $7FE200,x
  0xA9, 0x00,                    -- LDA #0
  0x8F, 0xA4, 0xF8, 0x7F,        -- STA.l $7FF8A4
  0xE8,                          -- INX
  0xE0, RUNS, 0x00,              -- CPX #RUNS
  0xD0, 0x100 - 32,              -- BNE loop
  0xA9, 0x01,                    -- LDA #1
  0x8F, 0x00, 0xE3, 0x7F,        -- STA.l $7FE300
  0x80, 0xFE,                    -- BRA *
}

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
      check("the roaming-monster store is hooked (JSL $E28065)",
        emu.read(HOOK_SITE, S) == 0x22 and emu.read(HOOK_SITE + 1, S) == 0x65 and emu.read(HOOK_SITE + 2, S) == 0x80
        and emu.read(HOOK_SITE + 3, S) == 0xE2)
      enabled = emu.read(0xEC8044, S)
      local low, range = emu.read(0xEC8045, S), emu.read(0xEC8046, S)
      if low >= 0x80 then low = low - 0x100 end
      print(string.format("config: enabled=%d low=%d range=%d", enabled, low, range))
      local sum, count = 0, 0
      for slot = 0, 3 do
        local c = rd(0x0A7B + slot)
        if c < 7 then
          emu.write(0x0BBB + c * 0xBE, LEVEL, W)
          sum = sum + LEVEL; count = count + 1
        end
      end
      local avg = sum // count
      print(string.format("party: %d members, levels set to %d, average %d", count, LEVEL, avg))
      local ids = {}
      for off = low, low + range - 1 do
        local lvl = math.min(99, math.max(1, avg + off))
        local id = emu.read(TABLE + lvl - 1, S)
        allowed[id] = true; ids[#ids + 1] = string.format("L%d:%02X", lvl, id)
      end
      print("band: " .. table.concat(ids, " "))
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
      local seen, list = {}, {}
      for n = 0, RUNS - 1 do
        local a, f = rd(RESULT_A + n), rd(RESULT_F + n)
        if enabled == 0 then
          if f ~= VANILLA or a ~= VANILLA then
            check(string.format("run %d: off keeps $7FF8A4 and A vanilla (got %02X, A %02X)", n, f, a), false)
          end
        elseif not allowed[f] then
          check(string.format("run %d: $7FF8A4 = %02X is from the band", n, f), false)
        end
        if not seen[f] then seen[f] = true; list[#list + 1] = string.format("%02X", f) end
      end
      print("formations seen: " .. table.concat(list, " "))
      if enabled == 0 then
        check(string.format("off: %d runs left $7FF8A4 (and A) at the vanilla %02X", RUNS, VANILLA), failures == 0)
      else
        check(string.format("on: %d runs each swapped in a formation from the band's table entries", RUNS), failures == 0)
        check("on: more than one formation over the runs (the roll varies)", #list > 1)
      end
      print(failures == 0 and "ALL PASS" or string.format("%d FAILED", failures))
      emu.stop(failures == 0 and 0 or 1)
      return
    end
    if frame > 60000 then print("FAIL timeout"); emu.stop(1) end
  end)
  if not ok then print("ERR " .. tostring(err)); emu.stop(2) end
end, emu.eventType.endFrame)
