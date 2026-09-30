-- Frost Cyclops effects (plan F Task 13). Client-only; nothing here changes hits.
-- GroundSlam: frost mist gathers on the club; the slam throws frost shockwave rings, a crown of
-- ice, flung shards and snow, and leaves a frozen floor.
-- Stomp: a Todoroki-style ice wave. Frost creeps down the path during the leg raise; after the
-- stomp, glacier clusters erupt one after another along the server's wave line, each at
-- impact + d / travel (the instant the server hit-tests that distance), growing from IceSpike_A
-- at the foot to IceSpike_E at the far end. The wall holds, then shatters into shards and mist.
-- Enraged, the server fans the wave into several lines (MapBossAttackData.lines); each line gets
-- its own wall.
-- Aftershock (GroundSlam's follow-up): a glacier bursts out of each circle and shatters.
-- Sizes follow the scaled boss: def.radius / width / length are the server's final hit sizes.
local C=require(script.Parent:WaitForChild('Common'))
local K=C.K
local ns=C.ns
local up=Vector3.yAxis
local ICE,PALE,MIST,WHITE=Color3.fromRGB(165,222,255),Color3.fromRGB(222,246,255),Color3.fromRGB(228,246,255),Color3.new(1,1,1)
local SHARDS={'IceShard_A','IceShard_B','IceShard_C'}
local SPIKES={'IceSpike_A','IceSpike_B','IceSpike_C','IceSpike_D','IceSpike_E'}
-- Kit glacier sizes (width, height, depth in studs) and the share of each one's height authored
-- below the ground line (boss-vfx-kit manifest). The template's own Size wins when it exists.
local SIZE={IceSpike_A=Vector3.new(2.705,3.574,2.075),IceSpike_B=Vector3.new(4.075,5.952,3.765),IceSpike_C=Vector3.new(6.228,8.359,4.791),IceSpike_D=Vector3.new(9.031,11.931,7.941),IceSpike_E=Vector3.new(11.883,15.42,9.053)}
local BELOW={IceSpike_A=.161,IceSpike_B=.16,IceSpike_C=.163,IceSpike_D=.162,IceSpike_E=.157}
local ICE_BLOCK={ICE,Enum.Material.Ice}
local HOLD=1.1 -- each cluster stands this long after it has grown
local F={}

local function snow(pos,count,speed,spread)
 C.emit(pos,up,'SnowSparkle',{emit=count,Speed=speed,SpreadAngle=spread or 60,Lifetime={.5,.9},Size=ns({0,.55},{1,0}),Color=PALE,LightEmission=.9,LightInfluence=.2,Drag=1.4,Acceleration=Vector3.new(0,-26,0),Rotation={0,360},RotSpeed={-200,200}})
end
local function mist(pos,count,speed,size,spread)
 C.emit(pos,up,'FrostMist',{emit=count,Speed=speed,SpreadAngle=spread or 80,Lifetime={.8,1.15},Size=ns({0,size*.55},{1,size}),Color=MIST,Transparency=ns({0,.3},{.6,.45},{1,1}),Drag=3,LightInfluence=.5,LightEmission=.15,Rotation={0,360},RotSpeed={-30,30}})
end

-- Glacier clusters. A cluster's frame sits on its ground point (yaw and lean included) and the mesh
-- scales about that base, so it grows up out of the floor with its authored buried share hidden.
local function glacier(name,base,rot,size)
 local c={frame=CFrame.new(base)*rot,size=size,below=BELOW[name] or .16,base=base}
 c.part=C.mesh(name,c.frame,.2)
 if not c.part then c.size=size*Vector3.new(.45,1,.45);c.part=C.part('Glacier',c.size*.2,c.frame,ICE,.15);c.part.Material=Enum.Material.Ice end
 return c
end
-- Scale since eruption: 0.2 -> 1.08 in 0.12 s (the overshoot), settling to 1 by 0.2 s.
local function growth(t) if t<.12 then return .2+.88*(1-(1-t/.12)^3) end;return 1.08-.08*K.smooth((t-.12)/.08) end
local function stand(c,since,life)
 local s=growth(since);local sink=math.max(0,1-since/.12)*c.size.Y*.12
 if since>life-.1 then local k=math.clamp((since-life+.1)/.1,0,1);s*=1+.05*k;c.part.Transparency=.55*k end -- cracking
 c.part.Size=c.size*s;c.part.CFrame=c.frame*CFrame.new(0,c.size.Y*s*(.5-c.below)-sink,0)
end
local function shatter(c,groundY,scale,loud)
 if not c.part then return end
 local mid=c.base+up*c.size.Y*.35;c.part:Destroy();c.part=nil
 C.chunks(mid,groundY,SHARDS,{count=4,speed={9,15},up={6,14},scale={scale,scale*1.3},life=1.2,fallback=ICE_BLOCK})
 mist(mid,2,{2,4},2.5+scale*.6,90);snow(mid,8+math.floor(scale*2),{8,14},90)
 if loud then C.cue('ice_crack',mid,.4,1.3) end
end
-- Full size for a cluster, slimmed across the lane so the wall stays close to the 5-stud hit width
-- without losing height.
local function sized(name,s,width)
 local t=C.template(name);local b=(t and t.Size or SIZE[name])*s;local cap=(width or 5)*1.5
 return Vector3.new(b.X*math.min(1,cap/b.X),b.Y,b.Z*.9)
end

-- GroundSlam ------------------------------------------------------------------------------
local function slamWindup(ctx)
 local at,def=ctx.attack,ctx.def;local head=ctx.points(def.point,C.age(ctx));if not C.near(head) then return end
 C.cue('ice_windup',head,.75)
 local host=C.part('Host',Vector3.one*1.6,CFrame.new(head),K.White,1)
 C.fx(host,'FrostMist',{Rate=30,Shape=Enum.ParticleEmitterShape.Sphere,Speed={.5,1.5},SpreadAngle=180,Lifetime={.6,.9},Size=ns({0,1.1},{1,2.6}),Color=ICE,Transparency=ns({0,1},{.25,.45},{1,1}),LightInfluence=.5,LightEmission=.2,Rotation={0,360},RotSpeed={-40,40}})
 C.fx(host,'SnowSparkle',{Rate=16,Speed={.5,2},SpreadAngle=180,Lifetime={.35,.6},Size=ns({0,0},{.3,.45},{1,0}),Color=PALE,LightEmission=1,Rotation={0,360}})
 local light=Instance.new('PointLight');light.Color=ICE;light.Range=0;light.Brightness=0;light.Shadows=false;light.Parent=host
 C.follow(ctx,at.impact,function(age)
  host.CFrame=CFrame.new(ctx.points(def.point,age))
  local k=math.clamp((age-at.warnStart)/math.max(.1,at.impact-at.warnStart),0,1);light.Range=4+8*k;light.Brightness=.3+1.7*k*k
 end,function() C.retire({host},1) end)
end
-- A crown of small glaciers bursting out of the slam point, leaning outward, then shattering.
local function crown(g,groundY,s)
 local list={};local seed=math.random()*6.28;s=s or 1
 for i=1,6 do
  local a=seed+i/6*math.pi*2;local out=Vector3.new(math.cos(a),0,math.sin(a))
  list[i]=glacier('IceSpike_B',g+out*2.6*s,CFrame.lookAt(Vector3.zero,out).Rotation*CFrame.Angles(-math.rad(28+math.random()*14),0,0),sized('IceSpike_B',(.8+math.random()*.35)*s,99))
  stand(list[i],0,10)
 end
 local life=.7
 K.animate(life+.1,function(_,age)
  for _,c in list do if c.part then if age>=life then shatter(c,groundY,2.2,false) else stand(c,age,life) end end end
 end,function() for _,c in list do if c.part then c.part:Destroy() end end end,'bossWave',8)
end
local function slamImpact(ctx)
 local at,def=ctx.attack,ctx.def;local g=C.ground(ctx,ctx.points(def.point,at.impact));local r,s=def.radius or 11,ctx.scale
 C.shake(g,1.6,.55);if not C.near(g,r) then return end
 C.cue('ice_slam',g,.95)
 C.star(g+up*2.5,PALE,r*1.2,.24);C.light(g+up*3,PALE,r*2.6,3.4,.45);K.pop(C.folder(),g+up*1.2,PALE,r*.35,r*1.4,.26,.5)
 C.ring(g+up*.06,'ShockwaveRing',2,r*1.4,.24,PALE,0,true) -- crisp white snap
 C.ring(g+up*.08,'FrostRing',1,r*2,.5,WHITE,0,true) -- the frost shockwave, out to the hit radius
 C.ring(g+up*.1,'FrostRing',2,r*2.6,.95,ICE,.45,true) -- a slower, fainter second ring
 C.stain(g+up*.03,'FrostFloor',r*1.5,WHITE,.08,1.5,1.42,.05,.6) -- frozen floor, ~3 s
 crown(g,ctx.groundY,s)
 C.dustRing(g,r*.85,14,MIST,{16,24},4*s)
 C.chunks(g+up*1.2,ctx.groundY,SHARDS,{count=10,speed={14,22},up={14,22},scale={2.4*s,3.6*s},life=1.4,fallback=ICE_BLOCK})
 snow(g+up*.5,34,{16,28},80);mist(g+up*.6,18,{10,16},5*s,88)
end

-- Stomp: the ice wave ---------------------------------------------------------------------
-- One controller per attack, started from windup (or impact if the windup was missed). It owns the
-- creeping frost strip, the foot mist, the path glints and every glacier, all timed on the server
-- clock so each cluster rises exactly when the server's wave front reaches it.
local function wave(ctx,line,key)
 ctx.frostWave=ctx.frostWave or {};if ctx.frostWave[key] then return end;ctx.frostWave[key]=true
 local at,def=ctx.attack,ctx.def;local travel=def.travel or 40;local origin,dir,length
 if line and line.kind=='line' then origin,dir,length=line.origin,line.direction,line.length
 else
  origin=ctx.points(def.point,at.impact);dir=C.flat(ctx.dirAt(def.point,at.impact))
  if dir.Magnitude<.05 then dir=C.flat(ctx.cf.LookVector) end;dir=dir.Unit;length=def.length or 26
 end
 origin=Vector3.new(origin.X,ctx.groundY,origin.Z)
 local mid=origin+dir*length/2;if not C.near(mid,length/2) then return end
 local side=dir:Cross(up).Unit;local look=CFrame.lookAt(Vector3.zero,dir).Rotation;local groundY=ctx.groundY
 -- Frost creeps down the path during the leg raise, deepens as the wave passes, and is what the
 -- wall leaves behind.
 local strip={};local lead=math.max(.2,at.impact-at.warnStart)
 for i=0,6 do
  local d=2+i*(length-4)/6;local p,set=C.plate(origin+dir*d+side*(math.random()-.5)*.8+up*.02,'FrostFloor',6.5+math.random()*1.5,WHITE,nil,false)
  if p then table.insert(strip,{p=p,set=set,show=at.warnStart+lead*(.12+.7*i/6),freeze=at.impact+d/travel,gone=at.impact+d/travel+.2+HOLD}) end
 end
 -- Anticipation: cold mist on the raised foot; frost glints rise along the path just before the stomp.
 local foot=C.part('Host',Vector3.one*2,CFrame.new(ctx.points(def.point,math.max(C.age(ctx),at.warnStart))),K.White,1)
 C.fx(foot,'FrostMist',{Rate=14,Shape=Enum.ParticleEmitterShape.Sphere,Speed={.5,1.5},SpreadAngle=180,Lifetime={.6,.9},Size=ns({0,1},{1,2.4}),Color=ICE,Transparency=ns({0,1},{.25,.5},{1,1}),LightInfluence=.5,Rotation={0,360},RotSpeed={-40,40}})
 local lane=C.part('Host',Vector3.new(def.width or 5,.2,length),CFrame.lookAt(mid+up*.2,mid+up*.2+dir),K.White,1)
 local glints=C.fx(lane,'SnowSparkle',{Rate=0,Enabled=true,EmissionDirection=Enum.NormalId.Top,Speed={2,5},SpreadAngle=15,Lifetime={.4,.7},Size=ns({0,0},{.3,.5},{1,0}),Color=PALE,LightEmission=1,Rotation={0,360},RotSpeed={-120,120}})
 -- One cluster every 2.2 studs: A near the foot up to E at the far end, zig-zagging a little either
 -- side of the line and leaning outward and forward.
 local clusters={}
 local spacing=#(ctx.data.lines or {})>1 and 2.8 or 2.2
 for d=1.1,math.max(length,1.2),spacing do
  local n=#clusters+1;local f=math.min(d/length,.999);local band=math.clamp(math.floor(f*5)+1,1,5);local sgn=n%2==0 and 1 or -1
  local rot=look*CFrame.Angles(0,math.rad(math.random(-25,25)),0)*CFrame.Angles(-math.rad(3+math.random()*5),0,-sgn*math.rad(6+math.random()*7))
  clusters[n]={at=at.impact+d/travel,band=band,name=SPIKES[band],pos=origin+dir*d+side*sgn*(.3+math.random()*.5),rot=rot,size=sized(SPIKES[band],(.9+.2*((f*5)%1))*(.94+math.random()*.12),def.width),loud=n%3==1 and key==1}
 end
 local function erupt(c)
  c.g=glacier(c.name,c.pos,c.rot,c.size);stand(c.g,0,10)
  local p=c.pos+up*.4
  mist(p,1+math.ceil(c.band/2),{3,6},2+c.band*.8,70);snow(p+up*.3,5+c.band*2,{10,16+c.band*2},35)
  C.chunks(p+up*.8,groundY,SHARDS,{count=c.band>=4 and 3 or 2,speed={5,10},up={14,22},scale={1.4+c.band*.3,1.9+c.band*.35},life=1,fallback=ICE_BLOCK})
  C.ring(c.pos+up*.05,'ShockwaveRing',1,2.5+c.band*1.6,.22,PALE,.35,true)
  if c.loud then C.cue('ice_crack',p,.55) end -- one crack every 3 clusters
  C.shake(p,.22+c.band*.08,.16)
 end
 local last=clusters[#clusters].at+.2+HOLD;local deadAt,retired,rolling
 K.animate(math.max(1,last-C.age(ctx))+2.2,function()
  local age=C.age(ctx)
  if not deadAt and not C.live(ctx) then deadAt=age end -- boss died or reset: no more ice, the wall breaks now
  if age<at.impact and not deadAt then
   foot.CFrame=CFrame.new(ctx.points(def.point,age));if glints then glints.Rate=age>at.impact-.55 and 45 or 0 end
  elseif not retired then retired=true;C.retire({foot,lane},1) end
  if not rolling and not deadAt and age>=at.impact then rolling=true;if key==1 then C.cue('ice_wave',mid,.9) end end
  local busy=false
  for _,c in clusters do
   if not c.g and not c.done then if deadAt then c.done=true elseif age>=c.at then erupt(c) end end
   if c.g and c.g.part then
    local since=age-c.at
    if deadAt or since>=.2+HOLD then shatter(c.g,groundY,1.5+c.band*.35,c.loud);c.done=true else stand(c.g,since,.2+HOLD) end
   end
   busy=busy or not c.done
  end
  for _,s in strip do
   if s.p.Parent then
    local a
    if age<s.show then a=1
    elseif age<s.freeze then a=1-.7*math.min(1,(age-s.show)/.4)
    elseif age<s.gone then a=.3-.18*math.min(1,(age-s.freeze)/.15)
    else a=.12+.88*K.smooth((age-s.gone)/1.6) end
    if deadAt then a=math.max(a,K.smooth((age-deadAt)/.5)) end
    s.set(a);if a>=.999 and (deadAt or age>s.gone) then s.p:Destroy() else busy=true end
   end
  end
  return not busy
 end,function()
  for _,c in clusters do if c.g and c.g.part then c.g.part:Destroy() end end
  for _,s in strip do s.p:Destroy() end
  if not retired then foot:Destroy();lane:Destroy() end
 end,'bossWave',8)
end
-- Every wave line the server sent (one, or the enraged fan), else one from the sampled stomp.
local function waves(ctx)
 local lines=ctx.data.lines
 if type(lines)=='table' and #lines>0 then for i,l in lines do wave(ctx,C.Shapes.decode(l),i) end
 else wave(ctx,C.shape(ctx),1) end
end
local function stompImpact(ctx)
 local at,def=ctx.attack,ctx.def;local g=C.ground(ctx,ctx.points(def.point,at.impact))
 C.shake(g,1,.4);if not C.near(g) then return end
 C.cue('ice_slam',g,.55,1.15)
 local s=ctx.scale
 C.ring(g+up*.06,'FrostRing',1,10*s,.4,WHITE,0,true);C.ring(g+up*.08,'ShockwaveRing',1,7*s,.2,PALE,.15,true)
 C.star(g+up*1.5,PALE,7*s,.16)
 snow(g+up*.5,24,{10,20},75);mist(g+up*.4,6,{6,10},4*s,88)
end

function F.windup(ctx)
 if ctx.kind=='GroundSlam' then slamWindup(ctx)
 elseif ctx.kind=='Stomp' then C.cue('ice_windup',ctx.points(ctx.def.point,C.age(ctx)),.75);waves(ctx) end
end
function F.impact(ctx)
 if ctx.kind=='GroundSlam' then slamImpact(ctx)
 elseif ctx.kind=='Stomp' then stompImpact(ctx);waves(ctx) end
end
-- Aftershock: a big glacier bursts out of each circle, leaning out, and shatters 0.85 s later.
function F.aftershock(m)
 local s,r=m.scale or 1,m.radius or 6
 for i,p in m.points do
  if C.near(p,r) then
   local g=glacier('IceSpike_D',p,CFrame.Angles(0,math.random()*6.28,0)*CFrame.Angles(math.rad(math.random(-8,8)),0,math.rad(math.random(-8,8))),sized('IceSpike_D',r/5.5,r*1.4))
   stand(g,0,10)
   K.animate(1,function(_,age) if g.part then if age>=.85 then shatter(g,p.Y,2.4*s,i==1) else stand(g,age,.85) end end end,function() if g.part then g.part:Destroy() end end,'bossWave',8)
   C.ring(p+up*.06,'FrostRing',1,r*2.2,.4,WHITE,0,true);C.stain(p+up*.03,'FrostFloor',r*1.8,WHITE,.05,1,1.2,.05,.6)
   C.star(p+up*2,PALE,r*1.3,.2);snow(p+up*.5,18,{12,22},70);mist(p+up*.5,6,{6,10},r*.7,80)
   C.chunks(p+up*1,p.Y,SHARDS,{count=4,speed={8,14},up={14,22},scale={1.8*s,2.6*s},life=1.2,fallback=ICE_BLOCK})
   if i<=2 then C.cue('ice_slam',p,.5,1.2) end;C.shake(p,.7,.3)
  end
 end
end
-- Both attacks are instant at impact (activeEnd == impact); the wave runs on its own controller.
function F.active(ctx,age) end
return F
