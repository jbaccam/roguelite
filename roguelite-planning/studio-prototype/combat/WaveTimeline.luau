-- Server-owned authored arrivals, pure clock/composition/cap policy. Counts are our 40s-wave
-- adaptation, not copied Brotato data. Deaths never advance this clock or request an arrival.
-- Boss adds average two arrivals/second, below late ordinary waves (4.5/s).
-- The existing boss population cap still leaves melee access when clearing falls behind.
local T={Duration=40,MaxAlive=100,BossInterval=3,BossAmount=6}
-- {seconds between arrivals, solo group size, fast every N, heavy every N (0 disables)}
T.Profiles={
 {6,6,0,0},{6,7,5,0},{6,8,4,0},{5,8,4,0},{5,9,4,0},
 {5,10,4,0},{5,11,4,0},{4,11,4,12},{4,12,4,12},{4,12,4,12},
 {4,13,4,11},{4,13,4,10},{4,14,4,10},{4,14,4,9},{4,15,4,9},
 {4,15,4,9},{4,16,4,8},{4,16,4,8},{4,17,4,8},{4,18,4,8},
}
function T.new(wave) return {wave=math.max(1,math.floor(wave or 1)),elapsed=0,next=0,serial=0,boss=nil} end
function T.players(players) return math.clamp(math.floor(tonumber(players) or 1),0,4) end
function T.participating(member,down,returning,health,hasRoot,practice)
 return hasRoot and (health or 0)>0 and not down and not returning and (member==true or practice==true)
end
function T.dispatchInterval(players) return .25/math.max(1,T.players(players)) end
function T.groupInterval(base,players) return base/math.max(1,T.players(players)) end
function T.nextRoot(cursor,count) return count>0 and cursor%count+1 or nil end
function T.queueLimit(players,boss) return math.min(T.MaxAlive,(boss and 20 or 36)*T.players(players)) end
function T.enqueue(queue,incoming,reserved,limit)
 local room=math.max(0,limit-reserved)
 -- Prefer recent composition to stale backlog, but never cancel already-issued warnings here.
 local keep=math.max(0,room-#incoming)
 while #queue>keep do table.remove(queue,1) end
 for _,id in incoming do if #queue>=room then break end;table.insert(queue,id) end
end
function T.step(s,dt,paused,boss,players)
 if s.boss~=nil and s.boss~=boss then s.next=s.elapsed+(boss and 0 or T.Profiles[math.min(s.wave,20)][1]) end
 s.boss=boss
 if paused or T.players(players)==0 then return end
 s.elapsed+=math.max(0,dt)
 if not boss and s.elapsed>=T.Duration then return end
 if s.elapsed<s.next then return end
 local p=T.Profiles[math.min(s.wave,20)]
 local interval=boss and T.BossInterval or p[1]
 -- At most one pulse per call; a hitch never delivers all missed groups in one burst.
 s.next=math.max(s.next+interval,s.elapsed+.25);s.serial+=1
 local multiplier=T.players(players)
 local count=math.floor((boss and T.BossAmount or p[2])*multiplier+.5)
 local roles={}
 for i=1,count do
  local ordinal=(s.serial-1)*count+i
  roles[i]=not boss and p[4]>0 and ordinal%p[4]==0 and 'Heavy' or p[3]>0 and ordinal%p[3]==0 and 'Fast' or 'Basic'
 end
 return {roles=roles,at=s.elapsed,boss=boss,serial=s.serial}
end
-- Map-local roster, server catalog only; absent roles fall back to its ordinary type.
function T.pickId(role,ordinal,roster,byId,legacy,wave)
 local pool={Basic={},Fast={},Heavy={}}
 local ids={}
 if type(roster)=='string' then for id in roster:gmatch('[^,%s]+') do if byId[id] then table.insert(ids,id) end end end
 if type(roster)=='string' and #ids==0 then return nil end -- invalid explicit map roster must never import Pine Valley mobs
 if #ids==0 then
  ids={legacy.Regular,legacy.Baby};if wave>=8 then table.insert(ids,legacy.Mutant) end
 end
 for _,id in ids do
  local d=byId[id]
  local bucket=d.behavior=='Heavy' and 'Heavy' or ((d.speed or 0)>=18 or d.legacy=='Baby') and 'Fast' or 'Basic'
  table.insert(pool[bucket],id)
 end
 local choices=#pool[role]>0 and pool[role] or #pool.Basic>0 and pool.Basic or ids
 return choices[(ordinal-1)%#choices+1]
end
function T.capacity(total,regular,pending,regularCap)
 return total+pending<T.MaxAlive and regular+pending<regularCap
end
function T.advanceWarning(elapsed,dt,paused)
 return elapsed+(paused and 0 or math.clamp(dt,0,.1))
end
function T.safeSpots(spots,roots,minimum,distance)
 for _,spot in spots do for _,root in roots do if distance(spot,root)<minimum then return false end end end
 return true
end
-- Candidates are ordinary living rigs only. Never turn retirement into a Humanoid death.
function T.retireCandidate(entries)
 local oldest
 for _,e in entries do
  if not e.protected and (not oldest or e.born<oldest.born or e.born==oldest.born and e.index<oldest.index) then oldest=e end
 end
 return oldest
end
return T
