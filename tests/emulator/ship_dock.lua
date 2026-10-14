-- Iris-Dev#67: a Ship received before the Treadool scene appears at the dock nearest the player. Mesen 2 headless:
--   Mesen.exe --testRunner <rom> ship_dock.lua > out.txt
-- Build the ROM with build_ship_dock_rom.py (debug + AP base patch, no ship), starting in Elcid or in Treadool.
-- Receives the Ship (item 454) the way the client does (the RX list in SRAM), checks the pending dock, walks out onto
-- the world map and checks where the ship is (ship_warp.lua covers the Warp side of #51):
--   Elcid    (map 03, world 40,218) -> Elcid's dock    C8 (43,217), far from Treadool
--   Treadool (map 7A, world 176,46) -> Treadool's dock D6 (175,47)
-- Prints PASS/FAIL per check and stops with 0 when every check passed.
print("LOADED")
local W, S = emu.memType.snesWorkRam, emu.memType.snesSaveRam
local frame, failures = 0, 0
local function rd(a) return emu.read(a, W) end
local function flag(n) return (rd(0x077E + (n >> 3)) >> (n & 7)) & 1 end
local SHIP = 454
-- map -> expected dock {id, x, y}, where the player's position is (x, y addresses, units per tile) and a spot of the
-- exit to walk to, in those units. $8F/$91 hold the tile in Elcid (as ship_warp.lua) but not in Treadool, where
-- $06BA/$06E2 follow the leader in half tiles (found by tracing). Treadool's exit is the west edge.
local TOWNS = {
  [0x03] = {name = "Elcid", dock = {0xC8, 43, 217}, pos = {0x008F, 0x0091, 1}, target = {22, 40}},
  [0x7A] = {name = "Treadool", dock = {0xD6, 175, 47}, pos = {0x06BA, 0x06E2, 2}, target = {0, 17}},
}
local town

local function state(tag)
  print(string.format("%s map=%02X 09E0=%02X 09EE=%02X 09DF=%02X ship=%d,%d 0921=%02X f127=%d", tag, rd(0x05AC),
    rd(0x09E0), rd(0x09EE), rd(0x09DF), rd(0x09E3), rd(0x09E4), rd(0x0921), flag(127)))
end
local function check(name, ok)
  print((ok and "PASS " or "FAIL ") .. name)
  if not ok then failures = failures + 1 end
end

-- The client's write: item id at $F0:2804 + 2(n-1), then the received counter n at $F0:2800.
local function receive(item)
  local n = (emu.read(0x2800, S) | (emu.read(0x2801, S) << 8)) + 1
  emu.write(0x2802 + 2 * n, item & 0xFF, S); emu.write(0x2803 + 2 * n, item >> 8, S)
  emu.write(0x2800, n & 0xFF, S); emu.write(0x2801, n >> 8, S)
end

-- Walking: a greedy walk to the town's exit, as ship_warp.lua.
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
      town = TOWNS[map]
      if town == nil then print(string.format("FAIL not in a known town (map %02X)", map)); emu.stop(1); return end
      state("start " .. town.name)
      check("no ship yet ($09E0 = FF)", rd(0x09E0) == 0xFF and rd(0x0921) & 0x04 == 0)
      receive(SHIP)
      phase = "receive"; t0 = frame
    end
    if phase == "receive" then  -- the "found" message waits for A; the field loop goes on once it closes
      local d = frame - t0
      if rd(0x0921) & 0x04 == 0 then
        if d % 60 == 40 then hold = {a = true} elseif d % 60 == 44 then hold = {} end
        if d > 1200 then print("FAIL the Ship never arrived"); emu.stop(1) end
      else
        hold = {}; phase = "received"; t0 = frame
      end
    end
    if phase == "received" and frame - t0 == 60 then
      local d = town.dock
      state("received")
      check("the Ship item is held (bit 454)", rd(0x0921) & 0x04 == 0x04)
      check(string.format("%s: ship pending at dock %02X", town.name, d[1]), rd(0x09E0) == 0 and rd(0x09EE) == d[1])
      check("flag 127 clear", flag(127) == 0)
      phase = "walk"; t0 = frame
    end
    if phase == "walk" then
      local d = frame - t0
      if d == 1 then
        if map == 0x00 then phase = "settle"; hold = {}; t0 = frame; return end
        local x, y, unit = rd(town.pos[1]), rd(town.pos[2]), town.pos[3]
        if from and x == from[1] and y == from[2] then blocked[key(x, y) .. "," .. from[3]] = true end
        local function H(a, b) return h[key(a, b)] or (math.abs(a - town.target[1]) + math.abs(b - town.target[2])) end
        local best, bestv = nil, 1e9
        for _, name in ipairs(order) do
          if not blocked[key(x, y) .. "," .. name] then
            local v = unit + H(x + unit * dirs[name][1], y + unit * dirs[name][2])
            if v < bestv then best, bestv = name, v end
          end
        end
        if best == nil then  -- boxed in: a message still open, most likely; close it and start over
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
      local d = town.dock
      state("world map")
      check(string.format("%s: ship at dock %02X (%d,%d)", town.name, d[1], d[2], d[3]),
        rd(0x09E3) == d[2] and rd(0x09E4) == d[3])
      check("ship on the map ($09E0 = 0), $09EE consumed", rd(0x09E0) == 0 and rd(0x09EE) == 0)
      check("flag 127 still clear", flag(127) == 0)
      print(failures == 0 and "ALL PASS" or string.format("%d FAILED", failures))
      emu.stop(failures == 0 and 0 or 1)
    end
    if frame > 60000 then print("FAIL timeout"); emu.stop(1) end
  end)
  if not ok then print("ERR " .. tostring(err)); emu.stop(2) end
end, emu.eventType.endFrame)
