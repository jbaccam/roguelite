-- BossVfxHammerTests: the Hammer's rubble wave helpers (BossVfx/Hammer, RW, 2026-10-09). Run in Edit
-- through tools/RepoRequire.luau only: R.run('BossVfxHammerTests'). In Edit the effects module returns
-- just its pure helpers ({rubble=RW}) before Common loads, so nothing is built or written to Studio.
-- The timing checks use the server's own wave test (MapBossService X.waveHit): a burst rises exactly
-- when the server's front reaches its distance. The last two read the real Hammer def and the client's
-- line decoding (MapBossPresentation P.lines, which the `wave` hook's unit.lines come from).
local RW=require({Name='BossVfxHammer'}).rubble
local X=require({Name='MapBossService'})._shapes
local S=require({Name='MapBossShapes'})
local Defs=require({Name='MapBossDefs'})
local P=require({Name='MapBossPresentation'})
local r={};local function add(ok,m) table.insert(r,(ok and 'PASS ' or 'FAIL ')..m) end
-- Protected: a check returns true, or a string saying what went wrong.
local function check(m,f)
 local ok,v=pcall(f)
 add(ok and v==true,m..(not ok and ' (error: '..tostring(v)..')' or v~=true and ' ('..tostring(v)..')' or ''))
end
local function near(a,b,eps) return math.abs(a-b)<(eps or 1e-9) end
local F=Vector3.new(0,0,-1)
local LINE={kind='line',origin=Vector3.new(10,4,20),direction=F,length=85,width=9}

check('one 85-stud line: 15-20 bursts, 4-6 studs apart, from near the hammer to the far end',function()
 local list=RW.schedule(85,55,0,false,7)
 if #list<15 or #list>20 then return #list..' bursts' end
 if list[1].d>4 or list[#list].d<80 or list[#list].d>85 then return 'ends '..list[1].d..', '..list[#list].d end
 for i=2,#list do local g=list[i].d-list[i-1].d;if g<4 or g>6 then return 'gap '..g..' at '..i end end
 return true
end)
check('enraged fan: each of 3 lines gets 15-20 bursts, 4-6 studs apart',function()
 for li=1,3 do
  local list=RW.schedule(85,55,0,true,li*31)
  if #list<15 or #list>20 then return #list..' bursts' end
  for i=2,#list do local g=list[i].d-list[i-1].d;if g<4 or g>6 then return 'gap '..g end end
 end
 return true
end)
check('heights build from knee-high by the hammer (1.5-2 studs) to tall heaps at 85 (7-9)',function()
 for seed=1,20 do
  local list=RW.schedule(85,55,0,false,seed)
  local a,z=list[1].h,list[#list].h
  if a<1.5 or a>2 or z<7 or z>9 then return string.format('seed %d: %.2f .. %.2f',seed,a,z) end
  for _,b in list do if math.abs(b.h/RW.height(b.d,85)-1)>.051 then return 'jitter past 5% at '..b.d end end
 end
 local last=0
 for d=0,85,.5 do local h=RW.height(d,85);if h<=last then return 'height falls at '..d end;last=h end
 return true
end)
check('a shorter line still builds from knee-high to tall at its own end',function()
 local list=RW.schedule(40,55,0,false,3)
 return list[1].h<2.1 and list[#list].h>7 and #list>=6 or (list[1].h..' .. '..list[#list].h)
end)
check('each burst rises exactly when the server\'s front reaches it (impact + d/travel, X.waveHit)',function()
 local impact=1.7;local side=F:Cross(Vector3.yAxis)
 for _,fan in {false,true} do
  for _,b in RW.schedule(85,55,impact,fan,11) do
   if not near(b.at,impact+b.d/55) then return 'at '..b.at..' for d '..b.d end
   local p=LINE.origin+F*b.d+side*RW.offset(b,LINE.width/2)
   if not X.waveHit({travel=55},{impact=impact},LINE,p,b.at-1e-6,b.at+1e-6) then return 'server front misses d '..b.d end
   if X.waveHit({travel=55},{impact=impact},LINE,p,b.at+1e-6,b.at+5) then return 'server front reaches d '..b.d..' late' end
  end
 end
 return true
end)
check('pose: buried before it rises, overshoots in the pop, holds at rest, cracks and is gone after 1-1.35 s',function()
 for _,f in {0,.5,1} do
  local hold,gone=RW.times(f)
  if gone<1 or gone>1.35 or hold<.5 or hold>.75 then return string.format('f %.1f: hold %.2f gone %.2f',f,hold,gone) end
  local l0=RW.pose(-.01,f);local lp=RW.pose(RW.RISE-1e-4,f);local lh,sh=RW.pose((RW.SETTLE+hold)/2,f)
  local lg,_,_,pg=RW.pose(gone+.01,f);local _,_,c,pc=RW.pose(hold+RW.CRACK/2,f)
  if l0~=0 or lp<1.08 or lh~=1 or sh~=1 or lg~=0 or pg~='gone' or pc~='crack' or c<=0 then return 'f '..f end
  if RW.pose(.005,f)>.15 then return 'not buried as it starts' end
 end
 return true
end)
check('pose is continuous through each change of phase (no pops)',function()
 for _,f in {0,1} do
  local hold,gone=RW.times(f)
  for _,t in {RW.RISE,RW.SETTLE,hold,hold+RW.CRACK,gone} do
   local a,sa=RW.pose(t-1e-6,f);local b,sb=RW.pose(t+1e-6,f)
   if math.abs(a-b)>.01 or math.abs(sa-sb)>.01 then return string.format('jump at %.3f: lift %.3f -> %.3f',t,a,b) end
  end
 end
 return true
end)
-- Every chunk of a heap: its foot below the ground, its sideways reach (with the burst's offset)
-- inside the lane; the tallest reaching the burst height.
local function heapOk(h,halfW,cap,seed,side)
 local list=RW.layout(h,halfW-math.abs(side),cap,Random.new(seed))
 if #list<3 or #list>cap then return #list..' chunks (cap '..cap..')' end
 local top=0;for _,c in list do top=math.max(top,c.top) end
 local lift=.1*(top*1.12+.3) -- the pop's overshoot raises the heap by 10% of its depth (Hammer spawn)
 for _,c in list do
  if c.bottom+lift>-.05 then return string.format('h %.1f: a chunk floats at the overshoot (bottom %.2f)',h,c.bottom) end
  if math.abs(side)+math.abs(c.pos.X)+c.hx>halfW+1e-6 then return string.format('h %.1f: a chunk leaves the lane (%.2f)',h,math.abs(side)+math.abs(c.pos.X)+c.hx) end
  if c.top>h*1.1 then return 'too tall '..c.top end
 end
 if top<h*.97 then return string.format('h %.1f: tallest only %.2f',h,top) end
 return true
end
check('heaps: every chunk sunk at its foot (through the pop\'s overshoot), inside the 9-stud lane, the tallest at the burst height',function()
 for _,fan in {false,true} do
  for _,q in {.35,.65,1} do
   local cap=RW.chunkCap(fan,q)
   for seed=1,12 do
    for _,b in RW.schedule(85,55,0,fan,seed) do
     local ok=heapOk(b.h,4.5,cap,b.seed,RW.offset(b,4.5));if ok~=true then return ok end
    end
   end
  end
 end
 return true
end)
check('heaps: the same seed builds the same heap; bigger heaps get more chunks, up to the cap',function()
 local a,b=RW.layout(5,4.5,6,Random.new(9)),RW.layout(5,4.5,6,Random.new(9))
 if #a~=#b then return 'counts differ' end
 for i=1,#a do if a[i].name~=b[i].name or a[i].size~=b[i].size or a[i].pos~=b[i].pos or a[i].color~=b[i].color then return 'chunk '..i..' differs' end end
 local n=0
 for h=1.6,8.6,.5 do local k=#RW.layout(h,4.5,6,Random.new(3));if k<n then return 'fewer chunks at '..h end;n=k end
 if #RW.layout(1.8,4.5,6,Random.new(1))~=3 or #RW.layout(8,4.5,6,Random.new(1))~=6 or #RW.layout(8,4.5,3,Random.new(1))~=3 then return 'counts at the ends' end
 return true
end)
check('heaps: kit rock meshes only, in flat dirt-brown and rock-grey tones',function()
 local names={};for _,list in RW.MESHES do for _,n in list do names[n]=true end end
 local tones={[RW.DARK]=true};for _,c in RW.DIRT do tones[c]=true end;for _,c in RW.ROCK do tones[c]=true end
 for seed=1,30 do
  for _,c in RW.layout(2+seed%7,4.5,6,Random.new(seed)) do
   if not names[c.name] or not (c.name:match('^MoltenRock_') or c.name:match('^SandstoneRubble_') or c.name:match('^ShellChip_')) then return 'mesh '..c.name end
   if not tones[c.color] then return 'colour '..tostring(c.color) end
  end
 end
 return true
end)
check('phone budget: the enraged fan stays under 200 chunks a wave at Full and 140 at Low, debris capped',function()
 for _,q in {.35,1} do
  local total,bits=0,0
  for li=1,3 do
   for _,b in RW.schedule(85,55,0,true,li) do
    total+=#RW.layout(b.h,4.5,RW.chunkCap(true,q),Random.new(b.seed))
    local p,c=RW.bits(b.h,true,li==2,q);bits+=p+c
   end
  end
  if total>(q<.5 and 140 or 200) then return q..': '..total..' chunks' end
  if bits>(q<.5 and 12 or 30) then return q..': '..bits..' bits' end
 end
 return true
end)
check('the Hammer\'s real waves (MapBossDefs: Slam, SpinSlam, the Charge finish) are the 85 x 9 at 55 studs/s these are built for',function()
 local H=Defs.get('Hammer');if not H then return 'no Hammer def' end
 local found=0
 for _,list in {H.attacks.Slam.phases,H.attacks.SpinSlam.phases,H.attacks.Charge.finish} do
  for _,part in list or {} do
   if part.shape=='wave' then
    found+=1
    if part.length~=RW.LENGTH or part.width~=RW.WIDTH or part.travel~=RW.TRAVEL then return 'wave '..tostring(part.length)..' x '..tostring(part.width)..' at '..tostring(part.travel) end
    local n=#RW.schedule(part.length,part.travel,0,false,1);if n<15 or n>20 then return n..' bursts' end
   end
  end
 end
 if found~=3 then return found..' waves' end
 if #(H.enrage.fan or {})~=3 then return 'fan of '..#(H.enrage.fan or {}) end
 return true
end)
check('a wave unit\'s fan as the presentation decodes it (P.lines): every burst inside its own line and on the server\'s front',function()
 local list={}
 for _,deg in {-25,0,25} do local l=table.clone(LINE);l.direction=CFrame.Angles(0,math.rad(deg),0):VectorToWorldSpace(F);table.insert(list,S.encode(l)) end
 local lines=P.lines({lines=list});if not lines or #lines~=3 then return 'decoded '..tostring(lines and #lines) end
 for li,line in lines do
  if typeof(line.origin)~='Vector3' or not near(line.direction.Magnitude,1,1e-6) or line.length~=85 or line.width~=9 then return 'line '..li end
  local side=line.direction:Cross(Vector3.yAxis) -- as the controller offsets a burst
  for _,b in RW.schedule(line.length,55,2,true,li) do
   local pos=line.origin+line.direction*b.d+side*RW.offset(b,line.width/2)
   if not X.waveHit({travel=55},{impact=2},line,pos,b.at-1e-6,b.at+1e-6) then return 'line '..li..' misses d '..b.d end
  end
 end
 return true
end)
return table.concat(r,'\n')
