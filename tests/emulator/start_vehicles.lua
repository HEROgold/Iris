-- Iris-Dev#16, #24: a new game with the Mermaid jade and/or the Engine has the vehicle at Elcid's dock. Mesen 2 headless:
--   Mesen.exe --testRunner <rom> start_vehicles.lua > out.txt
-- Build the ROM with build_start_vehicles_rom.py (jade, engine, both, or ap: the AP base patch with both start bytes).
-- What the ROM gives is read from the scenario-item bits at the start:
--   standalone: Mermaid jade (448, $0920 bit $10) and/or Engine (449, $0920 bit $20); the ship type is 1 with the jade
--               alone and 2 with the Engine. The new-game hook places the ship ($09E0 = 0, $09EE = C8).
--   ap:         Ship + Submarine (454/455, $0921 bits $04/$08), Ship + Engine (449); key_items.asm builds the type:
--               1 submarine, 2 both, 3 airship only, and places the ship at the nearest dock, Elcid's.
-- Walks out of Elcid (map 03) onto the world map and checks the ship is at Elcid's dock C8 (43,217) with that type.
-- Prints PASS/FAIL per check and stops with 0 when every check passed.
print("LOADED")
local W = emu.memType.snesWorkRam
local frame, failures = 0, 0
local function rd(a) return emu.read(a, W) end
local function flag(n) return (rd(0x077E + (n >> 3)) >> (n & 7)) & 1 end
local DOCK = {0xC8, 43, 217}
local POS = {0x008F, 0x0091, 1}  -- Elcid: the leader's tile
local TARGET = {22, 40}          -- Elcid's exit
local expected, ap

local function state(tag)
  print(string.format("%s map=%02X 09DF=%02X 09E0=%02X 09EE=%02X ship=%d,%d 0920=%02X 0921=%02X flags 86=%d 98=%d 99=%d 127=%d 145=%d",
    tag, rd(0x05AC), rd(0x09DF), rd(0x09E0), rd(0x09EE), rd(0x09E3), rd(0x09E4), rd(0x0920), rd(0x0921),
    flag(86), flag(98), flag(99), flag(127), flag(145)))
end
local function check(name, ok)
  print((ok and "PASS " or "FAIL ") .. name)
  if not ok then failures = failures + 1 end
end

local phase, t0, hold = "boot", 0, {}
local h, blocked, from, steps = {}, {}, nil, 0
local dirs = { right = {1, 0}, left = {-1, 0}, down = {0, 1}, up = {0, -1} }
local order = {"right", "left", "down", "up"}
local function key(x, y) return x .. "," .. y end

emu.addEventCallback(function()
  local ok, err = pcall(function()
    if phase == "boot" then
      local f = frame % 40
      if f < 3 then emu.setInput({start = true}, 0) elseif f >= 20 and f < 23 then emu.setInput({a = true}, 0) end
    else emu.setInput(hold, 0) end
  end)
  if not ok then print("ERR " .. tostring(err)) end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
  frame = frame + 1
  local ok, err = pcall(function()
    local map = rd(0x05AC)
    if phase == "boot" and frame > 1500 then
      if map ~= 0x03 then print(string.format("FAIL not in Elcid (map %02X)", map)); emu.stop(1); return end
      state("start")
      local s20, s21 = rd(0x0920), rd(0x0921)
      ap = s21 & 0x04 ~= 0
      if ap then
        local sub, air = s21 & 0x08 ~= 0, s20 & 0x20 ~= 0
        expected = (air and sub) and 2 or (air and 3 or 1)
        print(string.format("AP: Ship%s%s -> type %d", sub and " + Submarine" or "", air and " + Engine" or "", expected))
      else
        local jade, engine = s20 & 0x10 ~= 0, s20 & 0x20 ~= 0
        check("standalone: the Mermaid jade or the Engine is held", jade or engine)
        expected = engine and 2 or 1
        print(string.format("standalone:%s%s -> type %d", jade and " Mermaid jade" or "", engine and " Engine" or "", expected))
      end
      check(string.format("ship type $09DF = %d", expected), rd(0x09DF) == expected)
      check("ship pending at Elcid's dock C8", rd(0x09E0) == 0 and rd(0x09EE) == DOCK[1])
      check("no story vehicle flag set (86, 98, 99, 127, 145)",
        flag(86) + flag(98) + flag(99) + flag(127) + flag(145) == 0)
      phase = "walk"; t0 = frame
    end
    if phase == "walk" then
      local d = frame - t0
      if d == 1 then
        if map == 0x00 then phase = "settle"; hold = {}; t0 = frame; return end
        local x, y, unit = rd(POS[1]), rd(POS[2]), POS[3]
        if from and x == from[1] and y == from[2] then blocked[key(x, y) .. "," .. from[3]] = true end
        local function H(a, b) return h[key(a, b)] or (math.abs(a - TARGET[1]) + math.abs(b - TARGET[2])) end
        local best, bestv = nil, 1e9
        for _, name in ipairs(order) do
          if not blocked[key(x, y) .. "," .. name] then
            local v = unit + H(x + unit * dirs[name][1], y + unit * dirs[name][2])
            if v < bestv then best, bestv = name, v end
          end
        end
        if best == nil then
          blocked, h, from = {}, {}, nil
          hold = {a = true}; steps = steps + 1
          return
        end
        h[key(x, y)] = math.max(H(x, y), bestv)
        from = {x, y, best}
        hold = {[best] = true}
        steps = steps + 1
        if steps > 3000 then print("FAIL gave up walking"); emu.stop(3) end
      end
      if d == 9 then hold = {} end
      if d >= 24 then t0 = frame end
    end
    if phase == "settle" and frame - t0 == 120 then
      state("world map")
      check(string.format("ship at Elcid's dock C8 (%d,%d)", DOCK[2], DOCK[3]), rd(0x09E3) == DOCK[2] and rd(0x09E4) == DOCK[3])
      check("ship on the map ($09E0 = 0), $09EE consumed", rd(0x09E0) == 0 and rd(0x09EE) == 0)
      check(string.format("ship type still %d", expected), rd(0x09DF) == expected)
      print(failures == 0 and "ALL PASS" or string.format("%d FAILED", failures))
      emu.stop(failures == 0 and 0 or 1)
    end
    if frame > 60000 then print("FAIL timeout"); emu.stop(1) end
  end)
  if not ok then print("ERR " .. tostring(err)); emu.stop(2) end
end, emu.eventType.endFrame)
