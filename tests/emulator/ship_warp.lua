-- Iris-Dev#51: a ship from an item follows Warp to the destination's dock. Mesen 2 headless:
--   Mesen.exe --testRunner <rom> ship_warp.lua > out.txt
-- Build the ROM with build_ship_warp_rom.py (debug + AP base patch, Elcid start, Warp known, Progressive Ship held).
-- Walks out of Elcid onto the world map, then casts Warp through the menu and checks where the ship lands:
--   A  Ship item, flag 127 clear:   Alunze, Treadool, Elcid  -> each town's dock (the fix: flag 149 is clear too)
--   B  story ship only (127 set):   Alunze                   -> Treadool's dock (vanilla before the Auralio water gate)
--   C  story ship + Submarine item: Alunze                   -> Alunze's dock, as a submarine
--   D  + Ship item + Engine:        Elcid                    -> Elcid's dock, as the airship
--   E  story ship, gate open (149): Alunze                   -> Alunze's dock (vanilla)
-- Prints PASS/FAIL per check and stops with 0 when every check passed.
print("LOADED")
local W = emu.memType.snesWorkRam
local frame, failures = 0, 0
local function rd(a) return emu.read(a, W) end
local function wr(a, v) emu.write(a, v, W) end
local function flag(n) return (rd(0x077E + (n >> 3)) >> (n & 7)) & 1 end

-- Warp list entries (from Elcid's start: every destination unlocked) and the docks they lead to ($09CC).
local ELCID, ALUNZE, TREADOOL = 0, 2, 13
local DOCK = { [ELCID] = {0xC8, 43, 217}, [ALUNZE] = {0xCB, 30, 152}, [TREADOOL] = {0xD6, 175, 47} }

for _, a in ipairs({0x09EE, 0x09E0, 0x09E3, 0x09E4}) do
  emu.addMemoryCallback(function(addr, value)
    local s = emu.getState()
    print(string.format("f=%d write %04X=%02X (pc after %02X:%04X)", frame, addr & 0xFFFF, value, s["cpu.k"], s["cpu.pc"]))
  end, emu.callbackType.write, a, a, emu.cpuType.snes, W)
end

local function state(tag)
  print(string.format("%s map=%02X 09E0=%02X 09EE=%02X 09DF=%02X ship=%d,%d 09CC=%02X 0920=%02X 0921=%02X f127=%d f149=%d",
    tag, rd(0x05AC), rd(0x09E0), rd(0x09EE), rd(0x09DF), rd(0x09E3), rd(0x09E4), rd(0x09CC), rd(0x0920), rd(0x0921),
    flag(127), flag(149)))
end
local function check(name, ok)
  print((ok and "PASS " or "FAIL ") .. name)
  if not ok then failures = failures + 1 end
end

-- Steps: {wait, buttons, hold=, gap=, act=}. Buttons go down `wait` frames after the previous step, for `hold` frames.
local STEPS = {}
local function add(s) STEPS[#STEPS + 1] = s end
local function act(fn) add({1, {}, gap = 30, act = fn}) end
local first = true
local function warp(entry, tag, dock_tag, ship_type)
  add({60, {}})
  add({10, {x = true}})                       -- menu
  if first then add({10, {down = true}}) end  -- ITEM -> SPELL (remembered afterwards)
  first = false
  add({10, {a = true}}); add({10, {a = true}}); add({10, {a = true}}); add({10, {a = true}})  -- Spell, Maxim, Warp, use
  for _ = 1, entry do add({2, {down = true}, gap = 10}) end
  add({10, {a = true}})                       -- destination
  add({10, {a = true}, gap = 460})            -- arrive on the world map
  act(function()
    local d = DOCK[dock_tag]
    state(tag)
    check(string.format("%s: $09CC is dock %02X", tag, DOCK[entry][1]), rd(0x09CC) == DOCK[entry][1])
    check(string.format("%s: ship at dock %02X (%d,%d)", tag, d[1], d[2], d[3]), rd(0x09E3) == d[2] and rd(0x09E4) == d[3])
    check(tag .. ": ship on the map ($09E0 = 0), $09EE consumed", rd(0x09E0) == 0 and rd(0x09EE) == 0)
    if ship_type then check(string.format("%s: ship type %d", tag, ship_type), rd(0x09DF) == ship_type) end
  end)
end

-- A: the Progressive Ship from the new-game hook became the Ship; flag 127 stays clear.
act(function()
  state("A start")
  check("A: Progressive Ship became the Ship (bit 454)", rd(0x0921) & 0x14 == 0x04)
  -- The Ship arrived in Elcid, so it's at Elcid's dock, the nearest one (Iris-Dev#67; ship_dock.lua).
  check("A: ship placed at Elcid's dock", rd(0x09E3) == 43 and rd(0x09E4) == 217 and rd(0x09E0) == 0)
  check("A: flags 127 and 149 clear", flag(127) == 0 and flag(149) == 0)
end)
warp(ALUNZE, "A Alunze", ALUNZE, 0)
warp(TREADOOL, "A Treadool", TREADOOL, 0)
warp(ELCID, "A Elcid", ELCID, 0)
act(function() check("A: flag 127 still clear", flag(127) == 0) end)
-- B: the story ship alone (as the Treadool scene leaves it), gate closed: vanilla keeps it at Treadool.
act(function() wr(0x0921, rd(0x0921) & ~0x0C); wr(0x078D, rd(0x078D) | 0x80) end)
warp(ALUNZE, "B Alunze", TREADOOL, 0)
-- C: a Submarine item on top of the story ship. key_items.asm sets the type in the field loop, which doesn't run on the
-- world map, so it's set here as ShipState would.
act(function() wr(0x0921, rd(0x0921) | 0x08); wr(0x09DF, 1) end)
warp(ALUNZE, "C Alunze", ALUNZE, 1)
-- D: the Ship item and the Engine as well: the airship (type 2).
act(function() wr(0x0921, rd(0x0921) | 0x04); wr(0x0920, rd(0x0920) | 0x20); wr(0x09DF, 2) end)
warp(ELCID, "D Elcid", ELCID, 2)
-- E: story ship only, the Auralio water gate open (flag 149): vanilla lets it follow.
act(function() wr(0x0921, rd(0x0921) & ~0x0C); wr(0x0920, rd(0x0920) & ~0x20); wr(0x0790, rd(0x0790) | 0x20); wr(0x09DF, 0) end)
warp(ALUNZE, "E Alunze", ALUNZE, 0)

-- Walking out of Elcid: a greedy walk to the south exit (map 03, 17..27 x 39), as .local/emu/route.lua.
local TX, TY = 22, 40
local phase, t0, si, hold = "boot", 0, 1, {}
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
      if map ~= 0x03 then print(string.format("FAIL not in Elcid (map %02X)", map)); emu.stop(1) end
      phase = "walk"; t0 = frame
    end
    if phase == "walk" then
      local d = frame - t0
      if d == 1 then
        local x, y = rd(0x008F), rd(0x0091)
        if map == 0x00 then print("on the world map"); phase = "settle"; hold = {}; t0 = frame; return end
        if from and x == from[1] and y == from[2] then blocked[key(x, y) .. "," .. from[3]] = true end
        local function H(a, b) return h[key(a, b)] or (math.abs(a - TX) + math.abs(b - TY)) end
        local best, bestv = nil, 1e9
        for _, name in ipairs(order) do
          if not blocked[key(x, y) .. "," .. name] then
            local v = 1 + H(x + dirs[name][1], y + dirs[name][2])
            if v < bestv then best, bestv = name, v end
          end
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
    if phase == "settle" and frame - t0 == 120 then phase = "run"; t0 = frame end
    if phase == "run" then
      local st = STEPS[si]
      if st == nil then
        print(failures == 0 and "ALL PASS" or string.format("%d FAILED", failures))
        emu.stop(failures == 0 and 0 or 1); return
      end
      local d = frame - t0
      if d == st[1] then hold = st[2] end
      if d == st[1] + (st.hold or 4) then hold = {} end
      if d == st[1] + (st.gap or 40) then
        if st.act then st.act() end
        si = si + 1; t0 = frame
      end
    end
    if frame > 60000 then print("FAIL timeout"); emu.stop(1) end
  end)
  if not ok then print("ERR " .. tostring(err)); emu.stop(2) end
end, emu.eventType.endFrame)
