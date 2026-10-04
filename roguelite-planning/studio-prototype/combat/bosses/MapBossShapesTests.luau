-- MapBossShapesTests: run with fresh(require) in Edit; returns PASS/FAIL lines.
local S=require(game.ReplicatedStorage.RogueliteCombat.MapBossShapes)
local r={};local function add(ok,m) table.insert(r,(ok and 'PASS ' or 'FAIL ')..m) end
local F=Vector3.new(0,0,-1)
add(S.contains({kind='circle',center=Vector3.zero,radius=5},Vector3.new(4.9,0,0)),'circle inside edge')
add(not S.contains({kind='circle',center=Vector3.zero,radius=5},Vector3.new(5.1,0,0)),'circle outside edge')
add(S.contains({kind='line',origin=Vector3.zero,direction=F,length=20,width=4},Vector3.new(1.9,0,-19)),'line inside far corner')
add(not S.contains({kind='line',origin=Vector3.zero,direction=F,length=20,width=4},Vector3.new(0,0,1)),'line excludes behind origin')
add(S.contains({kind='cone',origin=Vector3.zero,direction=F,halfAngle=math.rad(25),length=18},Vector3.new(-3,0,-10)),'cone inside')
add(not S.contains({kind='cone',origin=Vector3.zero,direction=F,halfAngle=math.rad(25),length=18},Vector3.new(-8,0,-8)),'cone excludes 45 degrees')
add(math.abs(S.yaw(F,Vector3.new(-1,0,0))-math.pi/2)<1e-6,'yaw +90 is the left (-X)')
add(S.contains({kind='arc',pivot=Vector3.zero,forward=Vector3.new(0,0,1),from=math.rad(-100),to=math.rad(100),inner=4,outer=18},Vector3.new(0,0,10)),'arc behind boss inside')
add(not S.contains({kind='arc',pivot=Vector3.zero,forward=Vector3.new(0,0,1),from=math.rad(-100),to=math.rad(100),inner=4,outer=18},Vector3.new(0,0,-10)),'arc excludes the front')
add(S.contains({kind='circle',center=Vector3.zero,radius=5},Vector3.new(0,3.9,0)),'height band inside')
add(not S.contains({kind='circle',center=Vector3.zero,radius=5},Vector3.new(0,6,0)),'height band excludes a jumper above 5.5')
-- A circle's own height (the Hammer's Slam: 6) raises the top of the band: a plain jump doesn't clear it.
add(S.contains({kind='circle',center=Vector3.zero,radius=5,height=6},Vector3.new(0,5,0)) and S.contains({kind='circle',center=Vector3.zero,radius=5,height=6},Vector3.new(0,5.8,0)),'circle height 6 hits 5 and 5.8 above (the default band stops at 5.5)')
add(not S.contains({kind='circle',center=Vector3.zero,radius=5,height=6},Vector3.new(0,7,0)),'circle height 6 misses 7 above')
add(not S.contains({kind='circle',center=Vector3.zero,radius=5,height=6},Vector3.new(0,-2.5,0)),'circle height leaves the band below alone (2)')
local segs=S.outline({kind='cone',origin=Vector3.zero,direction=F,halfAngle=math.rad(25),length=18},24)
add(#segs>=24,'cone outline has segments')
add(S.contains({kind='capsule',a=Vector3.zero,b=Vector3.new(10,0,0),radius=2},Vector3.new(5,3,1.5)),'capsule inside (height band uses a)')
local track={{0,0,0,0},{1,10,0,0},{2,10,0,-10}}
add((S.sample(track,.5)-Vector3.new(5,0,0)).Magnitude<1e-6 and (S.sample(track,5)-Vector3.new(10,0,-10)).Magnitude<1e-6,'sample interpolates and clamps')
local p=S.shot(Vector3.new(0,8,0),math.pi/2,10,3,1)
add((p-Vector3.new(-10,3,0)).Magnitude<1e-6,'shot flies along its yaw and settles to hit height')
local back=S.decode(S.encode({kind='line',origin=Vector3.new(1,2,3),direction=F,length=4,width=2}))
add(back.origin==Vector3.new(1,2,3) and back.direction==F and back.length==4,'encode/decode round trip')
local ends=S.shotEnds({serial=7,ends={['1']=12.5}},7)
add(ends and ends['1']==12.5,'shot ends apply to their own volley')
add(S.shotEnds({serial=6,ends={['1']=12.5}},7)==nil,'shot ends from the last volley stop nothing')
add(S.shotEnds({['1']=12.5},7)==nil and S.shotEnds(nil,7)==nil,'unserialed or missing shot ends stop nothing')
-- Timing shared by MapBossService and MapBossPresentation (Hammer Brute review, 2026-10-03).
local lane={clips={'A','B','C'},rate=1.25,speed=32,length=40,shape='lane'}
local LT={clips={A=.5,B=.53,C=1},attacks={C={impact=.5},Slam={impact=.7}}}
local w=S.window(lane,LT,20)
add(math.abs(w.impact-.4)<1e-9 and math.abs(w.activeEnd-(.4+20/32))<1e-9 and math.abs(w.duration-(.4+20/32+.8))<1e-9 and w.warnStart==0 and math.abs(S.window(lane,LT).activeEnd-(.4+40/32))<1e-9,
 'lane window: start clip / rate, travel length / speed (default def.length), end clip / rate')
add(S.window(lane,{clips={A=.5}},20)==nil and S.window(lane,{},20)==nil and S.laneTimes(lane,{},20)==nil and S.window({clip='Slam'},LT)==LT.attacks.Slam,
 'window: nil without both lane clips (or any clip timing); a clip attack is its timing')
local finishing=table.clone(lane);finishing.finish={shape='circle'}
local fin=S.laneTimes(finishing,LT,20)
add(math.abs(fin.finishStart-w.activeEnd)<1e-9 and math.abs(fin.finishImpact-(w.activeEnd+.5))<1e-9 and math.abs(fin.duration-math.max(w.duration,w.activeEnd+.55))<1e-9 and fin.finishAt==LT.attacks.C
 and S.laneTimes(lane,LT,20).finishImpact==nil and S.laneTimes(lane,LT,20).duration==w.duration,'lane times: the finish starts where the run ends, and the duration covers its impact; none without def.finish')
local m=S.merged({clip='X',damage=1,phases={{}},finish={}},{damage=2,shape='circle'})
add(m.damage==2 and m.shape=='circle' and m.clip=='X' and m.phases==nil and m.finish==nil and S.isCharge({shape='lane',facing='forward'}) and S.isCharge({shape='lane',contact=4}) and not S.isCharge(lane) and not S.isCharge({shape='circle',contact=4}),
 'merged puts the part on top without phases or finish; isCharge: a forward or contact lane only')
local passed=0;for _,line in r do if line:sub(1,4)=='PASS' then passed+=1 end end
table.insert(r,('%d PASS, %d FAIL'):format(passed,#r-passed))
return table.concat(r,'\n')
