-- Iris-Dev#21: Ancient Cave blue chests as count-based checks, switched by the config block ($EC:8048 on, $EC:8049 N).
-- Mesen 2 headless:
--   Mesen.exe --testRunner <rom> blue_chests.lua > out.txt
-- Build the ROM with build_blue_chests_rom.py (count 2, or 0 for off). Its test-only harness runs requests from the field
-- main loop, with NMI on, as RX does: Lua fills $7F:E301.. and sets $7F:E300 to 1, the harness sets it to 2 when done.
-- So nothing races the game: a request only runs once the field main loop picks it up.
-- Once the new game stands in Elcid, Lua opens chests through the chest routine $8E:C1DE (animation, then the hooked
-- $8E:C1EB) with a Potion (2): a blue chest is $4002, a red one $0002.
--   count 2: blue chests 1 and 2 bump the SRAM counter ($F0:27D0) and give nothing; blue chest 3 gives its Potion and
--            the counter stays 2; a red chest gives its Potion. Then SaveRX stores the counter with save slot 0
--            ($F0:27C0), Lua zeroes the live counter, and LoadRX brings it back.
--   count 0: a blue chest gives its Potion and the counter stays 0.
-- Prints PASS/FAIL per check and stops with 0 when every check passed.
print("LOADED")
local W, S, SRAM = emu.memType.snesWorkRam, emu.memType.snesMemory, emu.memType.snesSaveRam
local frame, failures = 0, 0
local function rd(a) return emu.read(a, W) end
local function rd16(a) return rd(a) + rd(a + 1) * 256 end
local function sram16(a) return emu.read(a, SRAM) + emu.read(a + 1, SRAM) * 256 end
local function check(name, ok)
  print((ok and "PASS " or "FAIL ") .. name)
  if not ok then failures = failures + 1 end
end

local TRIGGER, OP, ITEM, OBJECT, SLOT, RESULT = 0x1E300, 0x1E301, 0x1E302, 0x1E304, 0x1E305, 0x1E310
local COUNTER, SAVED = 0x27D0, 0x27C0
local INVENTORY, SLOTS, POTION = 0x0A8D, 96, 2
local HOOK_SITE = 0x8EC1EB

local function potions()
  local n = 0
  for i = 0, SLOTS - 1 do
    local entry = rd16(INVENTORY + 2 * i)
    if entry % 512 == POTION then n = n + entry // 512 end
  end
  return n
end

-- Requests, run one after the other: {op, item word, label}; check(before, after) runs once the harness is done.
local count
local requests = {}
local current, pending_since, before = 0, 0, nil

local function chest(item, label, expect)
  requests[#requests + 1] = {op = 0, item = item, label = label, expect = expect}
end

local function plan()
  if count == 0 then
    chest(0x4002, "off: a blue chest gives its Potion, the counter stays 0", function(b, a)
      return a.potions == b.potions + 1 and a.counter == 0 end)
    return
  end
  chest(0x4002, "blue chest 1 bumps the counter (0 -> 1) and gives nothing", function(b, a)
    return a.counter == 1 and a.potions == b.potions and a.result == 0 end)
  chest(0x4002, "blue chest 2 bumps the counter (1 -> 2) and gives nothing", function(b, a)
    return a.counter == 2 and a.potions == b.potions and a.result == 0 end)
  chest(0x4002, "blue chest 3 gives its Potion, the counter stays 2", function(b, a)
    return a.counter == 2 and a.potions == b.potions + 1 end)
  chest(0x0002, "a red chest gives its Potion, the counter stays 2", function(b, a)
    return a.counter == 2 and a.potions == b.potions + 1 end)
  requests[#requests + 1] = {op = 1, label = "SaveRX stores the counter with save slot 0", expect = function(b, a)
    return sram16(SAVED) == 2 end}
  requests[#requests + 1] = {op = 2, zero = true, label = "LoadRX restores the counter from save slot 0", expect =
    function(b, a) return b.counter == 0 and a.counter == 2 end}
end

local function snapshot()
  return {potions = potions(), counter = sram16(COUNTER), result = rd16(RESULT)}
end

local function start(request)
  if request.zero then emu.write(COUNTER, 0, SRAM); emu.write(COUNTER + 1, 0, SRAM) end
  emu.write(OP, request.op, W)
  emu.write(ITEM, (request.item or 0) % 256, W); emu.write(ITEM + 1, (request.item or 0) // 256, W)
  emu.write(OBJECT, 0, W); emu.write(SLOT, 0, W)
  emu.write(RESULT, 0xFF, W); emu.write(RESULT + 1, 0xFF, W)
  before = snapshot()
  emu.write(TRIGGER, 1, W)
  pending_since = frame
end

local phase = "boot"
emu.addEventCallback(function()
  if phase == "boot" then
    local f = frame % 40
    if f < 3 then emu.setInput({start = true}, 0) elseif f >= 20 and f < 23 then emu.setInput({a = true}, 0) end
  elseif phase == "run" and frame - pending_since > 30 and (frame - pending_since) % 20 < 3 then
    emu.setInput({a = true}, 0)  -- close a "Found" message if one waits for a button
  else emu.setInput({}, 0) end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
  frame = frame + 1
  local ok, err = pcall(function()
    if phase == "boot" and frame > 1500 then
      local map = rd(0x05AC)
      if map ~= 0x03 then print(string.format("FAIL not in Elcid (map %02X)", map)); emu.stop(1); return end
      check("the chest routine is hooked (JML $E89B00)",
        emu.read(HOOK_SITE, S) == 0x5C and emu.read(HOOK_SITE + 1, S) == 0x00 and emu.read(HOOK_SITE + 2, S) == 0x9B
        and emu.read(HOOK_SITE + 3, S) == 0xE8)
      count = emu.read(0xEC8049, S) + emu.read(0xEC804A, S) * 256
      print(string.format("config: enabled %d, count %d", emu.read(0xEC8048, S), count))
      check("a new game starts the counter at 0", sram16(COUNTER) == 0)
      plan()
      emu.write(TRIGGER, 0, W)
      phase = "run"; current = 1
      start(requests[current])
      return
    end
    if phase == "run" then
      if rd(TRIGGER) ~= 2 then
        if frame - pending_since > 900 then
          local st = emu.getState()
          print(string.format("FAIL request %d never finished (pc %02X:%04X)", current, st["cpu.k"], st["cpu.pc"]))
          emu.stop(3)
        end
        return
      end
      if frame - pending_since < 2 then return end
      local after = snapshot()
      local request = requests[current]
      print(string.format("  potions %d -> %d, counter %d -> %d, $09CF %04X", before.potions, after.potions,
        before.counter, after.counter, after.result))
      check(request.label, request.expect(before, after))
      emu.write(TRIGGER, 0, W)
      current = current + 1
      if current > #requests then
        print(failures == 0 and "ALL PASS" or string.format("%d FAILED", failures))
        emu.stop(failures == 0 and 0 or 1)
        return
      end
      start(requests[current])
      return
    end
    if frame > 60000 then print("FAIL timeout"); emu.stop(1) end
  end)
  if not ok then print("ERR " .. tostring(err)); emu.stop(2) end
end, emu.eventType.endFrame)
