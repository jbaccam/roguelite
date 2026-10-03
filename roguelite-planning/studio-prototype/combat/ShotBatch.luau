-- Combat network packing, shared by the server and clients:
--  * lossless, bounded batching of the 16-argument Shot protocol (writer, fire);
--  * the frame's non-lethal hits as one small message per player (hitWriter, readHits);
--  * one weapon attack's fields in one replicated attribute (packAttack, attackOf).
-- Dense arrays avoid RemoteEvent's sparse-table serialization ambiguity.
local Players = game:GetService('Players')
-- Radius: selective delivery (server only, below). Clients cull these effects at 160 studs; the
-- lobby is 900+ studs from the nearest arena (Pine Valley), so 400 keeps every arena event in
-- reach of everyone in that arena while lobby players stop receiving them.
local B = { Marker = 'ShotBatchV1', Limit = 32, Radius = 400 }
function B.pack(...)
 local row = table.pack(...)
 assert(row.n <= 16, 'Shot protocol exceeds 16 arguments')
 local nilMask = 0
 for i = 1, 16 do
  if row[i] == nil then
   row[i] = false
   nilMask = bit32.bor(nilMask, bit32.lshift(1, i - 1))
  end
 end
 row.n = nil
 row[17] = nilMask
 return row
end
function B.unpack(row)
 local values = table.clone(row)
 local nilMask = values[17]
 for i = 1, 16 do
  if bit32.band(nilMask, bit32.lshift(1, i - 1)) ~= 0 then values[i] = nil end
 end
 return table.unpack(values, 1, 16)
end
-- Where each player is, refreshed at most every 0.1 s (a few studs of movement against a 400-stud
-- radius). Hit events fire per damage, so this is not looked up per event.
local snapshot, snapshotAt = {}, -math.huge
local function listeners()
 local now = os.clock()
 if now - snapshotAt < .1 then return snapshot end
 snapshotAt = now
 snapshot = {}
 for _, p in Players:GetPlayers() do
  local character = p.Character
  local root = character and character:FindFirstChild('HumanoidRootPart')
  snapshot[#snapshot + 1] = { player = p, position = root and root.Position }
 end
 return snapshot
end
-- The owner always receives; so does a player with no body (unknown position), and everyone when
-- the event has no position.
local function receives(entry, origin, owner)
 return entry.player == owner or not entry.position or typeof(origin) ~= 'Vector3'
  or (entry.position - origin).Magnitude <= B.Radius
end
-- remote:FireAllClients(...) for the players near origin (plus owner). One FireAllClients when
-- that is everyone, as on a match server with one arena.
function B.fire(remote, origin, owner, ...)
 local list = listeners()
 local count = 0
 for _, e in list do if receives(e, origin, owner) then count += 1 end end
 if count == #list then remote:FireAllClients(...) return end
 for _, e in list do
  if e.player.Parent == Players and receives(e, origin, owner) then remote:FireClient(e.player, ...) end
 end
end
-- push(owner, ...shot): batched per recipient, in push order, so Shot-before-damage ordering holds
-- for each client when the caller flushes before dealing damage.
function B.writer(remote)
 local pending = {}
 local writer = {}
 function writer:flush()
  local count = #pending
  if count == 0 then return end
  local batch = pending
  pending = {}
  local list = listeners()
  local rows, everyone = {}, true
  for i, e in list do
   local mine = {}
   for _, item in batch do if receives(e, item.origin, item.owner) then mine[#mine + 1] = item.row end end
   rows[i] = mine
   if #mine < count then everyone = false end
  end
  if everyone then
   -- Keep the original wire format when there is nothing to batch.
   if count == 1 then remote:FireAllClients(B.unpack(batch[1].row))
   else
    local all = table.create(count)
    for i, item in batch do all[i] = item.row end
    remote:FireAllClients(B.Marker, all)
   end
   return
  end
  for i, e in list do
   local mine = rows[i]
   if #mine > 0 and e.player.Parent == Players then
    if #mine == 1 then remote:FireClient(e.player, B.unpack(mine[1]))
    else remote:FireClient(e.player, B.Marker, mine) end
   end
  end
 end
 function writer:push(owner, ...)
  pending[#pending + 1] = { row = B.pack(...), origin = (...), owner = owner }
  if #pending >= B.Limit then self:flush() end
 end
 return writer
end

-- Hit batches (CombatEffectsService). A hit used to be its own FireAllClients: 300-800 a second
-- late in a 4-player run. Now a frame's non-lethal hits go out together, one message per player
-- (players near the hit plus its owner, as above), over the HitFX UnreliableRemoteEvent. They
-- only draw numbers, splats and flashes and play splat sounds, so a lost packet loses a few of
-- those and nothing waits for a resend. Unreliable messages over ~900 bytes are dropped, so a
-- frame's hits are split into messages of at most HitBytes: each hit is 18 bytes plus its
-- weapon id in a buffer, and its enemy goes beside it as an argument (budgeted at 24 bytes).
-- Example: 30 hits in one frame, ids like '07', is 30*(20+24)+32 = 1,352 bytes, so two messages.
-- Kills stay on the reliable Hit remote (CombatEffectsService).
B.HitBytes = 760
local LETHAL, SECONDARY, DOT, MINE = 1, 2, 4, 8
-- One hit, ready to encode. dot: a burn/poison/zone tick (clients skip its splat and flash).
function B.hitItem(owner, position, damage, npc, lethal, secondary, dot, weaponId)
 local flags = (lethal and LETHAL or 0) + (secondary and SECONDARY or 0) + (dot and DOT or 0)
 local id = type(weaponId) == 'string' and string.sub(weaponId, 1, 255) or ''
 return { owner = owner, position = position, damage = damage, npc = npc, flags = flags, id = id }
end
-- How `items` split into messages: {first, last, buffer bytes} each, in order.
function B.splitHits(items)
 local out, first, bytes, budget = {}, 1, 0, 32
 for i, item in items do
  local size = 18 + #item.id
  if i > first and budget + size + 24 > B.HitBytes then
   out[#out + 1] = { first, i - 1, bytes }
   first, bytes, budget = i, 0, 32
  end
  bytes += size
  budget += size + 24
 end
 if first <= #items then out[#out + 1] = { first, #items, bytes } end
 return out
end
-- One message's buffer and enemies (hits first..last) as `player` gets it: `mine` is set per
-- player, which is why each player gets their own copy.
function B.encodeHits(items, first, last, bytes, player)
 local buf = buffer.create(bytes)
 local npcs = table.create(last - first + 1)
 local at = 0
 for i = first, last do
  local item = items[i]
  local p = item.position
  local amount = math.round(item.damage)
  if amount ~= amount then amount = 0 end
  buffer.writef32(buf, at, p.X)
  buffer.writef32(buf, at + 4, p.Y)
  buffer.writef32(buf, at + 8, p.Z)
  buffer.writeu32(buf, at + 12, math.clamp(amount, 0, 4294967295))
  buffer.writeu8(buf, at + 16, item.flags + (player ~= nil and item.owner == player and MINE or 0))
  buffer.writeu8(buf, at + 17, #item.id)
  buffer.writestring(buf, at + 18, item.id)
  at += 18 + #item.id
  npcs[i - first + 1] = item.npc
 end
 return buf, npcs
end
function B.hitWriter(remote)
 local pending = {}
 local writer = {}
 function writer:push(...)
  pending[#pending + 1] = B.hitItem(...)
 end
 function writer:flush()
  if #pending == 0 then return end
  local batch = pending
  pending = {}
  for _, e in listeners() do
   if e.player.Parent == Players then
    local mine = {}
    for _, item in batch do if receives(e, item.position, item.owner) then mine[#mine + 1] = item end end
    for _, part in B.splitHits(mine) do
     local buf, npcs = B.encodeHits(mine, part[1], part[2], part[3], e.player)
     -- Enemies as separate arguments: one the player can't see arrives as nil without
     -- shifting the others, which a table's holes could.
     remote:FireClient(e.player, buf, table.unpack(npcs, 1, part[2] - part[1] + 1))
    end
   end
  end
 end
 return writer
end
-- A HitFX message as hit records: position (the enemy's root when hit), damage (rounded), npc
-- (nil when this client can't see it), lethal, secondary, dot, mine, weaponId.
function B.readHits(buf, npcs)
 local out = {}
 if typeof(buf) ~= 'buffer' or type(npcs) ~= 'table' then return out end
 local size, at = buffer.len(buf), 0
 while at + 18 <= size do
  local n = buffer.readu8(buf, at + 17)
  if at + 18 + n > size then break end
  local flags = buffer.readu8(buf, at + 16)
  local id = buffer.readstring(buf, at + 18, n)
  local npc = npcs[#out + 1]
  out[#out + 1] = {
   position = Vector3.new(buffer.readf32(buf, at), buffer.readf32(buf, at + 4), buffer.readf32(buf, at + 8)),
   damage = buffer.readu32(buf, at + 12),
   npc = typeof(npc) == 'Instance' and npc or nil,
   lethal = bit32.btest(flags, LETHAL), secondary = bit32.btest(flags, SECONDARY),
   dot = bit32.btest(flags, DOT), mine = bit32.btest(flags, MINE),
   weaponId = id ~= '' and id or nil,
  }
  at += 18 + n
 end
 return out
end

-- One weapon attack in one replicated attribute, 'Attack' on the slot folder (RogueliteCombat).
-- Each attack used to write 12 attributes. Text, ';'-separated: start time, motion rate, kind,
-- style, side, hand, swing range, attack root (x,y,z, then its flat look x,z), attack aim, flat
-- attack direction (x,z), second aim (empty when none). Positions keep 0.01 studs, directions
-- 0.0001, the start time 1 ms. 120-160 characters (CombatWireTests).
function B.packAttack(a)
 local root, aim, direction, second = a.root, a.aim, a.direction, a.second
 local look = root.LookVector
 return string.format('%.3f;%.5g;%s;%s;%d;%d;%.5g;%.2f,%.2f,%.2f,%.4f,%.4f;%.2f,%.2f,%.2f;%.4f,%.4f;%s',
  a.start, a.rate, a.kind or '', a.style or '', a.side or 1, a.hand or 1, a.range,
  root.X, root.Y, root.Z, look.X, look.Z, aim.X, aim.Y, aim.Z, direction.X, direction.Z,
  second and string.format('%.2f,%.2f,%.2f', second.X, second.Y, second.Z) or '')
end
local NONE = table.freeze({})
local function numbers(text)
 local list = {}
 for i, v in string.split(text or '', ',') do list[i] = tonumber(v) end
 return list
end
-- The table packAttack was given (root, aim, direction, second rebuilt), or an empty table when
-- the slot has had no attack since its last reset. Read-only: callers share it.
function B.unpackAttack(raw)
 if type(raw) ~= 'string' then return NONE end
 local f = string.split(raw, ';')
 local r, a, d, s = numbers(f[8]), numbers(f[9]), numbers(f[10]), numbers(f[11])
 local out = {
  start = tonumber(f[1]), rate = tonumber(f[2]), kind = f[3] ~= '' and f[3] or nil, style = f[4] ~= '' and f[4] or nil,
  side = tonumber(f[5]), hand = tonumber(f[6]), range = tonumber(f[7]),
 }
 if #r == 5 then
  local position = Vector3.new(r[1], r[2], r[3])
  local look = Vector3.new(r[4], 0, r[5])
  out.root = CFrame.lookAt(position, position + (look.Magnitude > .001 and look.Unit or -Vector3.zAxis))
 end
 if #a == 3 then out.aim = Vector3.new(a[1], a[2], a[3]) end
 if #d == 2 then
  local flat = Vector3.new(d[1], 0, d[2])
  out.direction = flat.Magnitude > .001 and flat.Unit or nil
 end
 if #s == 3 then out.second = Vector3.new(s[1], s[2], s[3]) end
 return table.freeze(out)
end
-- A slot folder's current attack, parsed once per change (renderers read it every frame).
local parsed = setmetatable({}, { __mode = 'k' })
function B.attackOf(slot)
 local raw = slot:GetAttribute('Attack')
 local c = parsed[slot]
 if c and c.raw == raw then return c.attack end
 local attack = B.unpackAttack(raw)
 parsed[slot] = { raw = raw, attack = attack }
 return attack
end
return B
