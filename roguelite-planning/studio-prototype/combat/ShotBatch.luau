-- Lossless, bounded batching of the existing 16-argument Shot protocol.
-- Dense arrays avoid RemoteEvent's sparse-table serialization ambiguity.
local B = { Marker = 'ShotBatchV1', Limit = 32 }
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
function B.writer(remote)
 local pending = {}
 local writer = {}
 function writer:flush()
  local count = #pending
  if count == 0 then return end
  local batch = pending
  pending = {}
  -- Keep the original wire format when there is nothing to batch.
  if count == 1 then remote:FireAllClients(B.unpack(batch[1]))
  else remote:FireAllClients(B.Marker, batch) end
 end
 function writer:push(...)
  pending[#pending + 1] = B.pack(...)
  if #pending >= B.Limit then self:flush() end
 end
 return writer
end
return B
