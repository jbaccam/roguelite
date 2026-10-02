-- Run pause bookkeeping (plans/2026-10-02-L-pause.md): who has pressed pause, and whether the run
-- is frozen. A run freezes only when every living member has paused (solo: the one player); one
-- living member resuming unfreezes it for everyone. Downed players don't count. Pure logic on plain
-- values, so RunPauseTests runs it with stand-in players; RogueliteMeta applies the freeze.
local R={}

function R.new() return {paused={},frozen=false,frozenAt=nil} end

-- Mark p paused (true) or playing. Returns true when it changed anything.
function R.set(st,p,on)
 on=on==true
 if (st.paused[p]==true)==on then return false end
 st.paused[p]=on or nil
 return true
end
function R.isPaused(st,p) return st.paused[p]==true end
-- Left the run or the server.
function R.forget(st,p) st.paused[p]=nil end
-- A new run, a reset, results: nobody is paused and nothing is frozen.
function R.clear(st) table.clear(st.paused);st.frozen=false;st.frozenAt=nil end

-- living: the living run members. Returns whether the run should be frozen, how many of them have
-- paused, and how many there are.
function R.evaluate(st,living)
 local n,count=0,0
 for _,p in living do n+=1;if st.paused[p] then count+=1 end end
 return n>0 and count==n,count,n
end

-- Moves to `frozen` at time `now`. Returns 'freeze', or 'unfreeze' and how long the run was
-- frozen (deadlines move later by that), or nil when nothing changes.
function R.step(st,frozen,now)
 if frozen and not st.frozen then st.frozen=true;st.frozenAt=now;return 'freeze' end
 if not frozen and st.frozen then
  st.frozen=false;local by=math.max(0,now-(st.frozenAt or now));st.frozenAt=nil
  return 'unfreeze',by
 end
 return nil
end
return R
