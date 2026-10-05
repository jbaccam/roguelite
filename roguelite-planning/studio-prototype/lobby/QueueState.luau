-- Independent, server-owned queue membership and launch countdown. No rewards or combat state.
-- Time is passed in (server clock), so the rules can be tested without waiting.
-- Phases: Idle (empty) -> Choosing (first player is host, picking the map) -> Counting (host
-- pressed START) -> launch (locked until finish).
local QueueState={}
QueueState.__index=QueueState
QueueState.COUNTDOWN=10 -- seconds after the host presses START
QueueState.FULL_COUNTDOWN=3 -- a full pad (or a solo run) launches sooner
QueueState.CHOOSING_LIMIT=60 -- a host who never presses START gives the pad up
-- Readiness is explicit: an unready member holds the pad indefinitely. A timeout must never
-- launch someone who is still picking a class or has not agreed to this map and difficulty.
-- solo = a Private pad (user, 2026-10-03: "what if were in a group with 2 people that wanted it to
-- be private"): only the ids in q.allow (the host's party, the host included) may join, and it holds
-- that many. Without allow it is the old solo pad: the host alone. Example: Ana and Ben in a party,
-- Ana starts Private -> Ben may join (2 of 2, the short countdown), Cal stepping on is refused.
-- picked: ids that locked in a class on this pad (START, LOCK IN); joined: when each got on.
local function reset(q) q.members={};q.locked=false;q.launchAt=nil;q.host=nil;q.phase='Idle';q.since=nil;q.solo=false;q.map=nil;q.difficulty=nil;q.allow=nil;q.allowCount=nil;q.picked={};q.joined={};q.startedAt=nil;q.readyAt=nil;q.fullAt=nil end
function QueueState.new(count,capacity)
 local self=setmetatable({queues={},membership={},capacity=capacity},QueueState)
 for i=1,count do self.queues[i]={};reset(self.queues[i]) end
 return self
end
function QueueState:capacityOf(q) return q.solo and math.min(self.capacity,q.allowCount or 1) or self.capacity end
-- Joining or unreadying cancels the countdown. Once everybody explicitly readies, leave a
-- visible three-second countdown on full/private pads, ten seconds on an open partial pad.
local function retime(self,q,now)
 if q.phase~='Counting' or not q.startedAt then return end
 for _,m in q.members do
  if not q.picked[m] then
   q.launchAt=nil;q.readyAt=nil;q.fullAt=nil
   return
  end
 end
 q.readyAt=q.readyAt or now
 q.launchAt=q.readyAt+(#q.members>=self:capacityOf(q) and QueueState.FULL_COUNTDOWN or QueueState.COUNTDOWN)
end
function QueueState:leave(id,now)
 local index=self.membership[id]
 if not index then return false end
 local q=self.queues[index]
 if q.locked then return false end
 for i,v in q.members do if v==id then table.remove(q.members,i);break end end
 self.membership[id]=nil;q.picked[id]=nil;q.joined[id]=nil
 if #q.members==0 then reset(q)
 else
  if q.host==id then q.host=q.members[1];if q.phase=='Choosing' then q.since=now end end
  retime(self,q,now)
 end
 return true
end
function QueueState:join(id,index,now)
 local q=self.queues[index]
 if not q or q.locked or self.membership[id] or #q.members>=self:capacityOf(q) then return false end
 if q.solo and not (q.allow and q.allow[id]) then return false end -- a Private pad: its party only
 table.insert(q.members,id);self.membership[id]=index;q.joined[id]=now
 if #q.members==1 then q.host=id;q.phase='Choosing';q.since=now end
 retime(self,q,now)
 return true
end
-- id confirmed a class and starter on their pad (START, or LOCK IN on the class step): the
-- countdown stops waiting for them. False when they aren't on a pad or it is already leaving.
function QueueState:lockIn(id,now)
 local index=self.membership[id];local q=index and self.queues[index]
 if not q or q.locked or q.phase~='Counting' or not q.map then return false end
 q.picked[id]=true;retime(self,q,now)
 return true
end
function QueueState:unready(id,now)
 local index=self.membership[id];local q=index and self.queues[index]
 if not q or q.locked then return false end
 q.picked[id]=nil;retime(self,q,now)
 return true
end
-- A final server validation failed: keep the group together and require fresh confirmation.
function QueueState:cancelLaunch(index,now)
 local q=self.queues[index];if not q then return end
 q.locked=false;q.picked={};retime(self,q,now)
end
-- How many on pad `index` haven't locked in a class yet.
function QueueState:picking(index)
 local q=self.queues[index];local n=0
 for _,id in q and q.members or {} do if not q.picked[id] then n+=1 end end
 return n
end
-- A Private pad's party grew (an invite accepted after START): its new members may join it too,
-- and it holds that many more (2026-10-03). No effect on an Open pad.
function QueueState:allowParty(index,ids,now)
 local q=self.queues[index]
 if not q or q.locked or not q.solo or not q.allow then return end
 for _,id in ids do q.allow[id]=true end
 local n=0;for _ in q.allow do n+=1 end;q.allowCount=n
 retime(self,q,now)
end
-- An empty pad for a player who pressed PLAY away from the pads, or nil when all are in use.
function QueueState:freePad()
 for index,q in self.queues do if q.phase=='Idle' and not q.locked and #q.members==0 then return index end end
end
-- Host confirms the map and difficulty. Private (solo) takes allow, a set of user ids (the host's
-- party), and is refused while anyone outside it is on the pad.
function QueueState:start(id,index,now,map,solo,difficulty,allow)
 local q=self.queues[index]
 if not q or q.locked or q.host~=id or q.phase~='Choosing' then return false end
 if solo then
  for _,m in q.members do if m~=id and not (allow and allow[m]) then return false end end
  q.allow=table.clone(allow or {});q.allow[id]=true
  local n=0;for _ in q.allow do n+=1 end;q.allowCount=n
 end
 q.phase='Counting';q.map=map;q.solo=solo==true;q.difficulty=difficulty or 'Normal'
 -- START includes the host's class confirmation. Earlier picks cannot consent to a map that
 -- had not been selected yet; all other members must confirm after the map is published.
 q.startedAt=now;q.picked={[id]=true};q.readyAt=nil;q.fullAt=nil
 retime(self,q,now)
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
  if not q.locked and q.phase=='Counting' and q.launchAt and now>=q.launchAt and #q.members>0 and self:picking(index)==0 then q.locked=true;table.insert(out,index) end
 end
 return out
end
function QueueState:finish(index)
 local q=self.queues[index]
 for _,id in q.members do self.membership[id]=nil end
 reset(q)
end
return QueueState
