-- Session lock for saved profiles (LOBBY_AND_MATCH_SERVERS.md §6). The saved record carries
-- lock={job=<server id>,at=os.time()}, and only the server holding it may write, so two servers
-- (a quick rejoin, or a lobby -> match hop) can never overwrite each other's progress.
-- Pure: it takes any store with UpdateAsync(key, transform), so the rules run against a fake store.
local L={}
L.WAIT=15 -- another server's lock: keep retrying this long (its leaving save is usually in flight), then take over
L.RETRY=3
L.ATTEMPTS=3 -- store errors before a load gives up

local function lockOf(record) return type(record)=='table' and type(record.lock)=='table' and record.lock or nil end
L.lockOf=lockOf

-- Loads key and locks it for job. Returns the record (lock set) and 'takeover' when another
-- server's lock was overridden, or nil plus 'error' / 'cancelled'.
-- opts: fresh() for a new account; optional wait, sleep(s), clock(), now(), and stillWanted()
-- (false stops waiting, e.g. the player already left).
function L.claim(store,key,job,opts)
 local sleep,clock,now=opts.sleep or task.wait,opts.clock or os.clock,opts.now or os.time
 local takeoverAt=clock()+(opts.wait or L.WAIT)
 local errors=0
 while true do
  local takeover=clock()>=takeoverAt
  local taken,record,overrode=false,nil,false
  local ok,err=pcall(store.UpdateAsync,store,key,function(old)
   local lock=lockOf(old)
   if lock and lock.job~=job and not takeover then taken=false;return nil end -- cancels the write
   overrode=lock~=nil and lock.job~=job
   record=type(old)=='table' and old or opts.fresh()
   record.lock={job=job,at=now()}
   taken=true
   return record
  end)
  if ok and taken then return record,overrode and 'takeover' or nil end
  if not ok then
   errors+=1;warn('ProfileLock: load failed',key,err)
   if errors>=L.ATTEMPTS then return nil,'error' end
  end
  if opts.stillWanted and not opts.stillWanted() then return nil,'cancelled' end
  sleep(ok and L.RETRY or errors)
 end
end

-- Writes data under job's lock; release=true clears the lock (leaving, teleporting). Returns
-- ok, lost, err. lost: another server holds the lock, nothing was written, and this server must
-- stop saving its out-of-date copy.
function L.write(store,key,job,data,release,now)
 local lost=false
 local ok,err=pcall(store.UpdateAsync,store,key,function(old)
  local lock=lockOf(old)
  lost=lock~=nil and lock.job~=job
  if lost then return nil end
  data.lock=not release and {job=job,at=(now or os.time)()} or nil
  return data
 end)
 if not ok then return false,false,err end
 return not lost,lost,nil
end

return L
