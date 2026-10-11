return function(Q)
 local checks=0
 local function check(v,message) assert(v,message);checks+=1 end
 local function frames(s,dt,n) for _=1,n do Q.sample(s,dt) end end
 local LOW,LEAN,BALANCED,FULL=1,2,3,4
 check(#Q.Profiles==FULL)
 check(not Q.Profiles[LOW].shadows and Q.Profiles[LEAN].shadows,'shadows are the last thing Auto drops')
 check(Q.Profiles[LEAN].effects==Q.Profiles[LOW].effects and not Q.Profiles[LEAN].post and Q.Profiles[BALANCED].post)
 local s=Q.new()
 check(s.level==LOW)
 frames(s,1/30,120);check(s.level==LOW) -- startup grace stays inexpensive
 frames(s,1/30,270);check(s.level==LOW) -- weak device stays Low
 frames(s,1/60,600);check(s.level==LOW) -- no rapid oscillation
 frames(s,1/60,1300);check(s.level==BALANCED) -- slow recovery
 frames(s,1/60,960);check(s.level==FULL)
 frames(s,1/30,210);check(s.level==LEAN,'busy scenes cut effects first; shadows stay') -- 7 s: Full->Balanced->Lean
 frames(s,1/30,90);check(s.level==LEAN,'removing shadows needs five slow seconds')
 frames(s,1/30,210);check(s.level==LOW)
 frames(s,1/60,60*120);check(s.level==LOW,'a downgrade is sticky for the session')
 s=Q.new();s.warmup=0
 frames(s,1/60,120);Q.sample(s,2);check(s.level==LOW);check(s.fast==0)
 Q.sample(s,0/0);Q.sample(s,-1);check(s.level==LOW)
 frames(s,1/45,600);check(s.level==LOW) -- deadband
 s=Q.new();frames(s,1/60,19*60);check(s.level==LOW) -- no early upgrade
 frames(s,1/60,3*60);check(s.level==LEAN) -- first measured upgrade
 frames(s,1/60,16*60);check(s.level==BALANCED)
 frames(s,1/60,16*60);check(s.level==FULL)
 -- Luke's report: 60 s shop above 55 FPS, then a 30 s wave. Before this change Auto
 -- climbed back every shop and fell every wave, so shadows flickered on and off each wave.
 local function waves(waveDt)
  local q=Q.new();local shadows=Q.Profiles[q.level].shadows;local ons,offs,inWave=0,0,0
  local function run(seconds,dtFor)
   local changes,t=0,0
   while t<seconds do
    local dt=dtFor(q.level);Q.sample(q,dt);t+=dt
    local now=Q.Profiles[q.level].shadows
    if now~=shadows then changes+=1;shadows=now;if now then ons+=1 else offs+=1 end end
   end
   return changes
  end
  for _=1,6 do
   run(60,function() return 1/60 end)
   inWave=math.max(inWave,run(30,waveDt))
  end
  return q,ons,offs,inWave
 end
 -- Shadows themselves are the cost: only Low holds 40 FPS. Shadows appear once (first
 -- shop), go once and stay gone; before this change: on and off again every wave.
 local q,ons,offs,inWave=waves(function(level) return level>LOW and 1/30 or 1/45 end)
 check(q.level==LOW and q.ceiling==LOW);check(ons==1 and offs==1);check(inWave<=1)
 -- Effects are the cost: Lean holds 45 FPS with shadows, so shadows are never removed.
 q,ons,offs,inWave=waves(function(level) return level>LEAN and 1/30 or 1/45 end)
 check(q.level==LEAN and Q.Profiles[q.level].shadows);check(ons==1 and offs==0);check(inWave==0)
 for _,p in Q.Profiles do check(p.effects>0 and p.effects<=1);check(p.shardHz>=20) end
 return checks
end
