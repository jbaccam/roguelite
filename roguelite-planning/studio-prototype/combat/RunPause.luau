-- Run pause bookkeeping (plans/2026-10-02-L-pause.md): who has pressed pause, and whether the run
-- is frozen. A run freezes only when every living member has paused (solo: the one player); one
-- living member resuming unfreezes it for everyone. Downed players don't count. Pure logic on plain
-- values, so RunPauseTests runs it with stand-in players; RogueliteMeta applies the freeze.
local R={}

function R.new() return {paused={},frozen=false,frozenAt=nil,lastPause={}} end

-- Requests (RunAction SetPaused, 2026-10-03): a pause at most once every RATE seconds per player,
-- so spamming P can't flicker the freeze; a resume always goes through. The old shared limit
-- dropped a resume sent within 0.25 s of the pause (P tapped twice), leaving a solo run frozen with
-- the menu closed. Example: pause at 10.0, resume at 10.1 -> both apply; pause again at 10.2 ->
-- dropped (the menu re-sends it, PauseUI).
R.RATE=.25
function R.allow(st,p,on,now)
 if on~=true then return true end
 if now-(st.lastPause[p] or -math.huge)<R.RATE then return false end
 st.lastPause[p]=now
 return true
end
-- Leave Run (2026-10-03): may this player leave right now? Returns true, or false and the reason
-- the menu shows. s = {member, down, alive, withParty, leader}. Any time from the death screen, the
-- shop or the pause menu, mid-wave included: the server used to refuse an alive player mid-wave
-- without a word while the pause menu closed itself, which left the run frozen. LEAVE WITH PARTY
-- is the private party's leader's alone (leader=true, MatchService).
function R.canLeave(s)
 if s.withParty and not s.leader then return false,'Only the party leader can end the run for the party' end
 if s.down then return true end
 if not s.member then return false,'You are not in a run' end
 if not s.alive then return false,'Wait until you are back on your feet' end
 return true
end

-- Mark p paused (true) or playing. Returns true when it changed anything.
function R.set(st,p,on)
 on=on==true
 if (st.paused[p]==true)==on then return false end
 st.paused[p]=on or nil
 return true
end
function R.isPaused(st,p) return st.paused[p]==true end
-- Left the run or the server.
function R.forget(st,p) st.paused[p]=nil;st.lastPause[p]=nil end
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
