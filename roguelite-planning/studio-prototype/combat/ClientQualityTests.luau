return function(Q)
 local checks=0
 local function check(v) assert(v);checks+=1 end
 local function frames(s,dt,n) for _=1,n do Q.sample(s,dt) end end
 local s=Q.new()
 check(s.level==1)
 frames(s,1/30,120);check(s.level==1) -- startup grace stays inexpensive
 frames(s,1/30,270);check(s.level==1) -- weak device stays Low
 frames(s,1/60,600);check(s.level==1) -- no rapid oscillation
 frames(s,1/60,1300);check(s.level==3) -- slow recovery
 frames(s,1/30,210);check(s.level==1) -- busy scenes downgrade again
 s=Q.new();s.warmup=0
 frames(s,1/60,120);Q.sample(s,2);check(s.level==1);check(s.fast==0)
 Q.sample(s,0/0);Q.sample(s,-1);check(s.level==1)
 frames(s,1/45,600);check(s.level==1) -- deadband
 s=Q.new();frames(s,1/60,19*60);check(s.level==1) -- no early upgrade
 frames(s,1/60,3*60);check(s.level==2) -- first measured upgrade
 frames(s,1/60,16*60);check(s.level==3)
 for _,p in Q.Profiles do check(p.effects>0 and p.effects<=1);check(p.shardHz>=20) end
 return checks
end
