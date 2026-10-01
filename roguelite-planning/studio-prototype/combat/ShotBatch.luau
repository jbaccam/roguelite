-- Lossless, bounded batching of the existing 16-argument Shot protocol.
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
return B
