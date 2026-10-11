-- Molotov fire zone shape (2026-10-10 rework): pure checks on SpecialMotion's shared radius math,
-- which both the server ticks (SpecialWeapons) and the client pool (ThrownVisuals.fireZone) read.
-- Run: python run_fire_zone_tests.py path/to/luau.exe  (Luau CLI; SpecialMotion needs no Roblox).
return function(Motion)
 local checks=0
 local function check(ok,message) checks+=1;if not ok then error('FireZoneTests: '..message,2) end end
 local function near(a,b,message,eps) check(math.abs(a-b)<=(eps or 1e-6),message..' (got '..tostring(a)..', want '..tostring(b)..')') end
 local F,P=Motion.Fire,Motion.Poison

 -- Tuning as documented (WEAPON_BALANCE.md, Molotov rework).
 near(F.base,4.5,'fire base is the old flat radius');near(F.start,1.6,'fire starts at 1.6x');near(F.finish,.8,'fire ends at 0.8x')
 near(F.factor,.45,'fire ticks 45%');near(F.ignite,1,'ignition 100%');near(F.tick,.4,'fire tick 0.4 s');check(F.cap==4,'fire cap 4')
 near(P.factor,.4,'poison still ticks 40%');near(P.ignite,.4,'poison has no ignition');check(P.cap==3,'poison cap still 3')

 -- Radii from Area Size.
 local r0,r1=Motion.zoneRadii('Fire',1);near(r0,7.2,'fire start, no Area Size');near(r1,3.6,'fire end, no Area Size')
 r0,r1=Motion.fireRadii(1.5);near(r0,10.8,'+50% Area Size start');near(r1,5.4,'+50% Area Size end')
 r0,r1=Motion.fireRadii(3);near(r0,16,'start capped at 16 (base 12)');near(r1,9.6,'end follows the clamped base')
 r0,r1=Motion.fireRadii(.1);near(r0,3.2,'tiny base clamps to 2: start');near(r1,1.6,'tiny base clamps to 2: end')
 r0,r1=Motion.zoneRadii('Poison',1);near(r0,5.5,'poison unchanged');near(r1,5.5,'poison stays one size')
 r0,r1=Motion.zoneRadii('Poison',1.5);near(r0,8.25,'poison still grows with Area Size');near(r1,8.25,'poison flat')

 -- Hold.
 near(Motion.zoneHold('Fire',4),.4,'fire holds 0.4 s');near(Motion.zoneHold('Fire',1),.25,'hold is at most a quarter of a short life')
 near(Motion.zoneHold('Poison',5),0,'poison never holds')

 -- The curve: the design sheet's frames (0, 0.4, 2.2, 3.8 s) and its ends.
 near(Motion.zoneRadius(7.2,3.6,0,4,.4),7.2,'0 s: start radius')
 near(Motion.zoneRadius(7.2,3.6,.4,4,.4),7.2,'0.4 s: still full (hold)')
 near(Motion.zoneRadius(7.2,3.6,2.2,4,.4),5.4,'2.2 s: halfway, 5.4')
 near(Motion.zoneRadius(7.2,3.6,3.8,4,.4),3.6+3.6*(1-(3.4/3.6)^2*(3-2*3.4/3.6)),'3.8 s',1e-9)
 near(Motion.zoneRadius(7.2,3.6,4,4,.4),3.6,'4 s: end radius')
 near(Motion.zoneRadius(7.2,3.6,9,4,.4),3.6,'past the end stays at the end radius')
 near(Motion.zoneRadius(7.2,3.6,-1,4,.4),7.2,'before birth (clock skew) stays at the start radius')
 near(Motion.zoneRadius(5.5,nil,3,5,0),5.5,'no end radius: flat')
 near(Motion.zoneRadius(7.2,3.6,1,0,0),3.6,'zero duration cannot divide by zero')
 -- Monotonic and smooth: never grows, never jumps more than a tick's worth.
 local last=math.huge;local worst=0
 for i=0,400 do
  local r=Motion.zoneRadius(7.2,3.6,i/100,4,.4)
  check(r<=last+1e-12,'never grows at '..i/100);if last<math.huge then worst=math.max(worst,last-r) end;last=r
 end
 check(worst<.03,'smooth: largest 0.01 s step '..worst)
 -- Scales: a +50% Area Size fire is the same curve x1.5 at every moment.
 for _,age in {0,.4,1,2,3,4} do near(Motion.zoneRadius(10.8,5.4,age,4,.4),1.5*Motion.zoneRadius(7.2,3.6,age,4,.4),'x1.5 at '..age,1e-9) end

 -- Server tick schedule (SpecialWeapons): ticks at 0, 0.4 ... 3.6 s, the first is the ignition.
 local function throw(damage,tuning,a0,a1,hold,duration)
  local ticks,total,area=0,0,0
  local age=0
  while age<duration-1e-9 do
   local r=Motion.zoneRadius(a0,a1,age,duration,hold)
   local f=ticks==0 and tuning.ignite or tuning.factor
   ticks+=1;total+=damage*f;area+=damage*f*math.pi*r*r
   age+=tuning.tick
  end
  return ticks,total,area
 end
 local ticks,total,area=throw(3,F,7.2,3.6,.4,4)
 check(ticks==10,'10 ticks in 4 s');near(total,3*(1+9*.45),'Tier I: an enemy in the fire all 4 s takes 15.15',1e-9)
 local oldTicks,oldTotal,oldArea=throw(3,{tick=.4,factor=.4,ignite=.4},4.5,4.5,0,4)
 near(oldTotal,12,'old Tier I: 10 x 1.2')
 local ratio=area/oldArea
 check(ratio>2.2 and ratio<2.6,'damage x area per throw rises about 2.3x (got '..ratio..')')
 -- Ground x time the fire covers: x1.62 (the design sheet's "x1.6").
 local cover,oldCover=0,math.pi*4.5^2*4
 for i=0,3999 do local r=Motion.zoneRadius(7.2,3.6,(i+.5)/1000,4,.4);cover+=math.pi*r*r/1000 end
 near(cover/oldCover,1.62,'ground x time x1.62',.01)

 -- Worked example: a zombie standing 6 studs from the centre.
 local function inside(age) return 6<=Motion.zoneRadius(7.2,3.6,age,4,.4) end
 check(inside(0) and inside(.4) and inside(1.2),'6 studs out: burning early (old 4.5 never reached it)')
 check(not inside(2.8) and not inside(3.6),'6 studs out: clear once the fire burns down')

 -- Per-tier crowd output stays under Pandora's Box (the AoE leader) at every tier. Molotov Tier I-IV
 -- damage 3/5/7/10 every 1.727 s x 1/.9/.8/.7; Pandora 26/36/51/71, 7-stud blast every 2.229 s x the same.
 local mol,pan={3,5,7,10},{26,36,51,71};local cd={1,.9,.8,.7}
 for t=1,4 do
  local _,_,a=throw(mol[t],F,7.2,3.6,.4,4)
  local live=math.min(F.cap,4/(1.727*cd[t]))
  local crowd=a/4*live -- damage x stud^2 per second while `live` fires burn
  local pandora=pan[t]*math.pi*49/(2.229*cd[t])
  check(crowd<pandora,'Tier '..t..' Molotov crowd '..math.round(crowd)..' under Pandora '..math.round(pandora))
 end
 return checks
end
