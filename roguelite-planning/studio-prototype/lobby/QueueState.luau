-- Independent, server-owned queue membership and launch countdown. No rewards or combat state.
-- Time is passed in (server clock), so the rules can be tested without waiting.
-- Phases: Idle (empty) -> Choosing (first player is host, picking the map) -> Counting (host
-- pressed START) -> launch (locked until finish).
local QueueState={}
QueueState.__index=QueueState
QueueState.COUNTDOWN=10 -- seconds after the host presses START
QueueState.FULL_COUNTDOWN=3 -- a full pad (or a solo run) launches sooner
QueueState.CHOOSING_LIMIT=60 -- a host who never presses START gives the pad up
local function reset(q) q.members={};q.locked=false;q.launchAt=nil;q.host=nil;q.phase='Idle';q.since=nil;q.solo=false;q.map=nil;q.difficulty=nil end
function QueueState.new(count,capacity)
 local self=setmetatable({queues={},membership={},capacity=capacity},QueueState)
 for i=1,count do self.queues[i]={};reset(self.queues[i]) end
 return self
end
function QueueState:capacityOf(q) return q.solo and 1 or self.capacity end
function QueueState:leave(id,now)
 local index=self.membership[id]
 if not index then return false end
 local q=self.queues[index]
 if q.locked then return false end
 for i,v in q.members do if v==id then table.remove(q.members,i);break end end
 self.membership[id]=nil
 if #q.members==0 then reset(q)
 elseif q.host==id then q.host=q.members[1];if q.phase=='Choosing' then q.since=now end end
 return true
end
function QueueState:join(id,index,now)
 local q=self.queues[index]
 if not q or q.locked or self.membership[id] or #q.members>=self:capacityOf(q) then return false end
 table.insert(q.members,id);self.membership[id]=index
 if #q.members==1 then q.host=id;q.phase='Choosing';q.since=now end
 if q.phase=='Counting' and #q.members>=self:capacityOf(q) then q.launchAt=math.min(q.launchAt,now+QueueState.FULL_COUNTDOWN) end
 return true
end
-- An empty pad for a player who pressed PLAY away from the pads, or nil when all are in use.
function QueueState:freePad()
 for index,q in self.queues do if q.phase=='Idle' and not q.locked and #q.members==0 then return index end end
end
-- Host confirms the map and difficulty. Solo is refused once someone else is already on the pad.
function QueueState:start(id,index,now,map,solo,difficulty)
 local q=self.queues[index]
 if not q or q.locked or q.host~=id or q.phase~='Choosing' then return false end
 if solo and #q.members>1 then return false end
 q.phase='Counting';q.map=map;q.solo=solo==true;q.difficulty=difficulty or 'Normal'
 local full=#q.members>=self:capacityOf(q)
 q.launchAt=now+(full and QueueState.FULL_COUNTDOWN or QueueState.COUNTDOWN)
 return true
end
-- Hosts who have been choosing longer than the limit; the caller removes them.
function QueueState:stale(now)
 local out={}
 for _,q in self.queues do if q.phase=='Choosing' and q.since and now-q.since>QueueState.CHOOSING_LIMIT then table.insert(out,q.host) end end
 return out
end
-- Locks and returns the indices of queues whose countdown finished. Members stay listed
-- (and cannot leave) until `finish` clears the queue after departure.
function QueueState:due(now)
 local out={}
 for index,q in self.queues do
  if not q.locked and q.phase=='Counting' and now>=q.launchAt and #q.members>0 then q.locked=true;table.insert(out,index) end
 end
 return out
end
function QueueState:finish(index)
 local q=self.queues[index]
 for _,id in q.members do self.membership[id]=nil end
 reset(q)
end
return QueueState
