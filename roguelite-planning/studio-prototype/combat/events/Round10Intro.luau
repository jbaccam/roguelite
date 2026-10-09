-- Client only: each round 10 event's own short cinematic (ROUND_10_MASTER_SPEC.md "Cinematic").
-- Round10Service holds the fight (CinematicUntil) and publishes workspace.Round10Event: the arena
-- Center, the party's position (Players), the subject (Focus, FocusFrame), the leader/hero/tombs as
-- ObjectValues, and IntroStart/IntroUntil on the server clock. Every client films the same server
-- timeline, so a late frame never desyncs the shots from the leader's intro clip.
-- Shared controller: letterbox, title + objective card, camera ownership (UITheme cameraTake), shake
-- that obeys the Screen Shake setting, and a guaranteed restore on finish, error, removal or skip.
-- Per-event data: shots (camera CFrame over time) and moments (one-off effects). All effects are
-- presentation only; the server's hazards never run during the intro.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local Lighting=game:GetService('Lighting')
local RS=game:GetService('ReplicatedStorage')
local T=require(RS:WaitForChild('UITheme'))
local combat=RS:WaitForChild('RogueliteCombat')
local Common=require(combat:WaitForChild('BossVfx'):WaitForChild('Common'))
local K=Common.K
local player=Players.LocalPlayer
local I={}
-- Round10Defs, required on first use (it may replicate after this module loads).
local function Defs() return require(combat:WaitForChild('Round10Defs')) end
local up=Vector3.yAxis
local function smooth(x) x=math.clamp(x,0,1);return x*x*(3-2*x) end
local function flat(v) return Vector3.new(v.X,0,v.Z) end
local function unit(v,fallback) v=flat(v);return v.Magnitude>.05 and v.Unit or fallback or Vector3.new(0,0,-1) end
local function look(from,at) return CFrame.lookAt(from,at) end

-- Letterbox and the card: the event title in gold on the theme's panel with stone caps, the
-- objective on a pill under it. Scales with the screen like BossIntro's.
local function overlay(title,objective)
 local gui=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='Round10Intro',ResetOnSpawn=false,DisplayOrder=90,IgnoreGuiInset=true,ZIndexBehavior=Enum.ZIndexBehavior.Sibling})
 local bars={}
 for i,anchor in {0,1} do
  bars[i]=T.make('Frame',gui,{Name=i==1 and 'TopBar' or 'BottomBar',AnchorPoint=Vector2.new(0,anchor),Position=UDim2.fromScale(0,anchor),Size=UDim2.new(1,0,0,0),BackgroundColor3=Color3.new(0,0,0),BorderSizePixel=0})
 end
 local holder=T.make('Frame',gui,{Name='Card',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.72),Size=UDim2.fromOffset(720,150),BackgroundTransparency=1,Visible=false})
 local scale=T.make('UIScale',holder,{Scale=1})
 local plate=T.panel(holder,'Plate',20,0,680,92,'panel');T.caps(plate,56)
 local name=T.label(plate,'Title',title,40,6,600,72,52,T.Color.gold);name.TextStrokeTransparency=0
 local pill=T.panel(holder,'Objective',110,92,500,48,'inset')
 local sub=T.label(pill,'Text',objective,14,4,472,40,24,T.Color.white);sub.TextStrokeTransparency=0
 local function fit() local v=gui.AbsoluteSize;scale.Scale=math.clamp(math.min(v.X/1280,v.Y/760),.45,1.15) end
 gui:GetPropertyChangedSignal('AbsoluteSize'):Connect(fit);fit()
 local o={gui=gui}
 function o.bars(on) for _,b in bars do TweenService:Create(b,TweenInfo.new(.4,Enum.EasingStyle.Quad),{Size=UDim2.new(1,0,on and .09 or 0,0)}):Play() end end
 function o.card(on)
  holder.Visible=on
  if on then local s=scale.Scale;scale.Scale=s*1.3;TweenService:Create(scale,TweenInfo.new(.38,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=s}):Play() end
 end
 return o
end

-- The anchors as values (nil when missing).
local function anchors(folder)
 local a={folder=folder,center=folder:GetAttribute('Center'),players=folder:GetAttribute('Players'),focus=folder:GetAttribute('Focus'),
  frame=folder:GetAttribute('FocusFrame'),start=folder:GetAttribute('IntroStart'),untilAt=folder:GetAttribute('IntroUntil'),swarm=folder:GetAttribute('Swarm')}
 local function value(name) local v=folder:FindFirstChild(name);return v and v:IsA('ObjectValue') and v.Value or nil end
 a.leader=value('Leader');a.hero=value('Hero')
 a.tombs={};for _,l in {'A','B','C'} do local m=value('Tomb'..l);if m then table.insert(a.tombs,m) end end
 a.vents={};local vf=folder:FindFirstChild('Vents');if vf then for _,v in vf:GetChildren() do table.insert(a.vents,v) end end
 table.sort(a.vents,function(x,y) return x.Name<y.Name end)
 return a
end
local function rootOf(m) return m and (m.PrimaryPart or m:FindFirstChild('HumanoidRootPart')) or nil end

-- Local-only part offsets (coffins rising, lids falling): every part of a model moved by `offset`
-- (a CFrame applied in world space about `pivot`), restored to its replicated CFrame afterwards.
local function holdModel(model)
 local list={}
 for _,p in model:GetDescendants() do if p:IsA('BasePart') then list[p]=p.CFrame end end
 return list
end
local function placeModel(list,transform) for p,cf in list do if p.Parent then p.CFrame=transform*cf end end end
local function hideModel(model,hidden)
 for _,p in model:GetDescendants() do if p:IsA('BasePart') or p:IsA('Decal') then p.LocalTransparencyModifier=hidden and 1 or 0 end end
end

-- ── Per-event shot lists ─────────────────────────────────────────────────────────────────────────
-- Each builder returns {title, objective, card (s), shots={{to, cf(k,t)}...}, moments={{at, fn}}, tick(t), cleanup()}.
-- Shots run in order; shot i lasts until `to` seconds from the intro start and is blended into from
-- the previous shot's end over BLEND seconds. The last 0.65 s always ease home to the player.
local BUILD={}
local BLEND=.35

BUILD.PopGoesTheZombie=function(a,def)
 local focus=a.focus or a.center;local dir=unit(focus-(a.players or focus+Vector3.new(0,0,10)))
 local side=up:Cross(dir)
 local hero=a.hero;local chest=focus+up*3.2
 local function heroPos() local r=rootOf(hero);return r and r.Position or chest end
 local swell -- the hero's harmless intro swell (its UpperTorso, locally)
 return {title=def.title,objective=def.objective..' '..Defs().clock(def.duration),card=2.6,
  shots={
   {to=1.7,cf=function(k) local from=focus-dir*13+side*3+up*1.8;local to=focus-dir*8.5+side*2+up*2.4;return look(from:Lerp(to,smooth(k)),heroPos()+up*1.2) end},
   {to=2.8,cf=function(k) local p=heroPos();return look(p-dir*5.6+side*1.6+up*(2.6+k*.4),p+up*1.7) end},
   {to=3.55,cf=function(k) local p=heroPos();local from=p-dir*5.6+side*1.6+up*3;local to=p-dir*24+side*6+up*15;return look(from:Lerp(to,smooth(k)),p+up*.5) end},
  },
  moments={
   {at=1.9,fn=function() Common.cue('zombie_roar',heroPos(),.55,.7) end},
   {at=2.0,fn=function()
    -- Belly swells and cheeks tense: a local pulse on the hero's UpperTorso/Head (no blast).
    local m=hero;local torso=m and m:FindFirstChild('UpperTorso');local head=m and m:FindFirstChild('Head')
    if not torso then return end
    local t0,h0=torso.Size,head and head.Size
    swell=function(k) torso.Size=t0*(1+.22*k);if head then head.Size=h0*(1+.06*k) end end
    K.animate(1.4,function(t) if not torso.Parent then return true end;local k=math.sin(math.clamp(t/.55,0,1)*math.pi/2)*(1-smooth((t-.7)/.3));swell(k) end,function() if torso.Parent then torso.Size=t0;if head then head.Size=h0 end end end,'r10Swell',4)
    Common.light(heroPos()+up*3,Color3.fromRGB(255,214,60),14,3,1.2)
   end},
  },
 }
end

BUILD.CrabRave=function(a,def)
 local cf=a.frame or CFrame.lookAt(a.focus or a.center,a.players or a.center)
 local function at(x,y,z) return (cf*CFrame.new(x,y,z)).Position end
 return {title=def.title,objective=def.objective,card=2.3,
  shots={
   -- Close on the rear speakers powering up (behind the DJ, low, looking forward into them).
   {to=1.3,cf=function(k) return look(at(1.4,3.4,7.5-k*1.6),at(0,3.6,.8)) end},
   -- Arc round to the eyes and pincers; the claws snap at 2.0 on the music's accent.
   {to=2.3,cf=function(k) local ang=math.rad(180-160*smooth(k));local r=8.5-1.2*k;return look(at(math.sin(ang)*r,2.6+.8*k,math.cos(ang)*r*-1),at(0,2.4,-1.2)) end},
   -- Pull back and up: the crab reinforcements gathered round it.
   {to=4.15,cf=function(k) local from=at(4,4,-9);local to=at(6,12,-26);return look(from:Lerp(to,smooth(k)),at(0,1.6,0)) end},
  },
  moments={
   {at=.35,fn=function() Common.cue('crab_windup',at(0,3,1),.5,.8) end},
   {at=2.0,fn=function()
    Common.light(at(0,3,-1),Color3.fromRGB(80,255,230),22,4,.6);Common.star(at(1.6,2.6,-2.6),Color3.fromRGB(120,255,235),5,.25);Common.star(at(-1.6,2.6,-2.6),Color3.fromRGB(255,120,180),5,.25)
    Common.shake(at(0,0,0),.6,.35);Common.cue('crab_slam',at(0,0,0),.8,1.15)
   end},
  },
 }
end

BUILD.TombOpens=function(a,def)
 local tombs=a.tombs;local A=tombs[1];local cfA=a.frame or (A and A:GetPivot()) or CFrame.new(a.center)
 local center=a.center;local players=a.players or center+Vector3.new(0,0,30)
 local held={} -- model -> part frames (rise and lids, locally)
 local lids={}
 for i,m in tombs do
  held[m]=holdModel(m)
  -- Each lid swings about its hinge (HingeFrame, Round10Service) from closed to lying open.
  local lid=m:FindFirstChild('Sarcophagus_Lid',true)
  local closed,hinge=lid and lid:GetAttribute('ClosedFrame'),lid and lid:GetAttribute('HingeFrame')
  if typeof(closed)=='CFrame' and typeof(hinge)=='CFrame' then lids[i]={part=lid,hinge=hinge,rel=hinge:ToObjectSpace(closed)} end
 end
 local height=(A and A:GetExtentsSize().Y or 10)+1
 local function riseK(i,t) return smooth((t-.12*(i-1))/1.4) end
 local LID={1.6,2.05,2.35}
 local dirA=unit(cfA.Position-players)
 return {title=def.title,objective=def.objective,card=3.9,
  shots={
   {to=1.6,cf=function(k) local from=players+dirA*4+up*2.2;local to=players+dirA*14+up*3.4;return look(from:Lerp(to,smooth(k)),cfA.Position+up*3) end},
   {to=3.9,cf=function(k) return look((cfA*CFrame.new(5.5-k,4.6,-12+k*1.5)).Position,(cfA*CFrame.new(0,3.6,-3)).Position) end},
   {to=4.4,cf=function(k) local back=unit(players-center);return look(center+back*(34+4*k)+up*(24+2*k),center+up*2) end},
  },
  tick=function(t)
   for i,m in tombs do
    local list=held[m];if list then
     local k=riseK(i,t)
     local drop=-height*(1-k)+(k<1 and math.sin(t*38)*.06*(1-k) or 0)
     -- Lid i: closed (rising with the body) until LID[i], then swings down onto the sand.
     local L=lids[i]
     for p,cf in list do
      if p.Parent then
       if L and p==L.part then
        local swing=math.clamp((t-LID[i])/.42,0,1);swing=swing*swing -- falls, speeding up
        p.CFrame=CFrame.new(0,drop,0)*L.hinge*CFrame.Angles(-math.rad(90)*swing,0,0)*L.rel
       else p.CFrame=CFrame.new(0,drop,0)*cf end
      end
     end
    end
   end
  end,
  moments={
   {at=0,fn=function() Common.cue('stone_rumble',center,.7,.9);for _,m in tombs do local r=rootOf(m);if r then Common.emit(Vector3.new(r.Position.X,cfA.Y+.4,r.Position.Z),up,'SandBurst',{emit=10,Speed={6,12},SpreadAngle=55,Lifetime={.8,1.3},Size=Common.ns({0,2},{1,5}),Color=Color3.fromRGB(226,196,150),Transparency=Common.ns({0,.15},{1,1}),Drag=2,LightInfluence=.8,Rotation={0,360}}) end end end},
   {at=.2,fn=function() Common.shake(center,.35,1.4) end},
   {at=1.95,fn=function() Common.cue('sand_burst',cfA.Position,.8,1);Common.dustRing((cfA*CFrame.new(0,0,-3.5)).Position,1.5,10,Color3.fromRGB(226,200,160),12,3) end},
   {at=3.7,fn=function() local p=(cfA*CFrame.new(0,0,-5)).Position;Common.shake(p,.8,.4);Common.cue('ice_slam',p,.7,.75);Common.dustRing(p,2,12,Color3.fromRGB(226,200,160),16,3.5) end},
  },
  cleanup=function() for _,list in held do placeModel(list,CFrame.new()) end end,
 }
end

BUILD.BloodMoonHunt=function(a,def)
 local cf=a.frame or CFrame.lookAt(a.focus or a.center,a.players or a.center)
 local players=a.players or a.center
 local moonDir=(unit(cf.Position-players)*1+up*.55).Unit
 local function at(x,y,z) return (cf*CFrame.new(x,y,z)).Position end
 return {title=def.title,objective=def.objective,card=2.6,
  shots={
   -- Moon reveal: from the party, up toward the red moon over the alpha's rim.
   {to=1.0,cf=function(k) local p=players+up*(4+k);return look(p,p+moonDir*40) end},
   -- Low in front of the alpha: its silhouette against the sky as it howls (peak at 2.0).
   {to=2.75,cf=function(k) return look(at(3.5-k,1.6,-11+k*1.8),at(0,5.5,0)) end},
   -- Over its shoulder toward the arena and the party.
   {to=3.8,cf=function(k) local from=at(3,7,6);local to=at(2.4,8.5,9);return look(from:Lerp(to,smooth(k)),players+up*2) end},
  },
  moments={
   {at=1.9,fn=function() Common.cue('dragon_windup',at(0,5,0),.7,1.35) end},
   {at=2.25,fn=function() Common.cue('dragon_windup',players+moonDir*30,.35,1.6) end},
   {at=2.05,fn=function() Common.ring(Vector3.new(cf.X,cf.Y-2.5,cf.Z),'ShockwaveRing',4,30,.9,Color3.fromRGB(255,80,80),.35,1.4);Common.shake(at(0,0,0),.4,.5) end},
  },
  moonDir=moonDir,
 }
end

BUILD.Eruption=function(a,def)
 local vents=a.vents;local v1=vents[1];local c1=v1 and v1:GetAttribute('Center') or a.focus or a.center
 local players=a.players or a.center;local away=unit(c1-players)
 local swarm=a.swarm or (a.center)
 local glows={}
 for i,v in vents do for _,p in v:GetDescendants() do if p:IsA('BasePart') and p.Name:find('Glow') then table.insert(glows,{part=p,i=i,color=p.Color}) end end end
 return {title=def.title,objective=def.objective..' '..Defs().clock(def.duration),card=2.2,
  shots={
   {to=1.8,cf=function(k) local from=c1-away*11+up*1.6;local to=c1-away*8+up*2.2;return look(from:Lerp(to,smooth(k)),c1+up*1.2) end},
   {to=3.35,cf=function(k) local from=c1-away*8+up*2.2;local to=swarm-unit(swarm-players)*20+up*16;return look(from:Lerp(to,smooth(k)),(c1:Lerp(swarm,smooth(k)))+up*1) end},
  },
  tick=function(t)
   -- Vent seams brighten in sequence through the rumble, then settle back (the server's cycle starts after).
   for _,g in glows do
    if g.part.Parent then
     local k=smooth((t-.25*(g.i-1))/.5)*(1-smooth((t-3)/.6))
     g.part.Color=g.color:Lerp(Color3.fromRGB(255,214,120),k)
    end
   end
  end,
  moments={
   {at=0,fn=function() Common.cue('ground_quake',c1,.7,.8);Common.shake(c1,.45,1.6) end},
   {at=1.6,fn=function()
    -- The harmless preview geyser on the first vent.
    Common.emit(c1+up*.6,up,'Flame',{emit=26,Speed={34,48},SpreadAngle=9,Lifetime={.7,1.1},Size=Common.ns({0,3},{1,6}),Color=Color3.fromRGB(255,170,60),Transparency=Common.ns({0,.05},{.7,.3},{1,1}),LightEmission=.6,Drag=1.5,Rotation={0,360}})
    Common.emit(c1+up*1,up,'SmokePuff',{emit=10,Speed={16,26},SpreadAngle=14,Lifetime={1.2,1.8},Size=Common.ns({0,3},{1,8}),Color=Color3.fromRGB(70,58,58),Transparency=Common.ns({0,.2},{1,1}),Drag=1.2,Rotation={0,360}})
    Common.cue('lava_hiss',c1,.8,1);Common.light(c1+up*4,Color3.fromRGB(255,140,50),26,4,1)
   end},
  },
  cleanup=function() for _,g in glows do if g.part.Parent then g.part.Color=g.color end end end,
 }
end


-- ── The controller ──────────────────────────────────────────────────────────────────────────────
local playing
function I.playing() return playing~=nil end
-- Plays the event intro for `folder` (workspace.Round10Event). Returns immediately; the camera is
-- always handed back (finish runs on the end, any error, the folder's removal or the event ending).
function I.play(folder)
 if playing then return end
 local id=folder:GetAttribute('EventId');local def=Defs().byId(id);local builder=BUILD[id]
 if not def or not builder then return end
 local start,untilAt=folder:GetAttribute('IntroStart'),folder:GetAttribute('IntroUntil')
 if type(start)~='number' or type(untilAt)~='number' or workspace:GetServerTimeNow()>=untilAt-.3 then return end
 -- Give the server's actors a moment to replicate (the ObjectValues come right after the folder).
 task.wait(.15)
 if not folder.Parent then return end
 local a=anchors(folder)
 local ok,spec=pcall(builder,a,def);if not ok or not spec then warn('Round10Intro: '..tostring(id)..' failed: '..tostring(spec));return end
 local state={}
 playing=state
 local camera=workspace.CurrentCamera
 local ui=overlay(spec.title,spec.objective);ui.bars(true)
 local hrp=player.Character and player.Character:FindFirstChild('HumanoidRootPart')
 local homeOffset=hrp and camera.CFrame.Position-hrp.Position or Vector3.new(0,12,20)
 local homeLook=camera.CFrame.LookVector
 local from=camera.CFrame
 T.cameraTake('Round10Intro',function() return playing==state end)
 camera.CameraType=Enum.CameraType.Scriptable
 local duration=untilAt-start
 local fired={}
 -- A hidden leader (the Warden inside his coffin) shows from its intro clip's start (BossStart).
 local hidden=a.leader and (a.leader:GetAttribute('BossStart') or 0)>workspace:GetServerTimeNow()+.05
 if hidden then hideModel(a.leader,true) end
 local conn,carded,uncarded
 local function finish()
  if playing~=state then return end
  if conn then conn:Disconnect();conn=nil end
  if spec.cleanup then pcall(spec.cleanup) end
  if a.leader then hideModel(a.leader,false) end
  ui.gui:Destroy()
  playing=nil
  T.cameraRelease('Round10Intro')
 end
 state.finish=finish
 local function shotAt(t)
  local prevEnd=0
  for i,s in spec.shots do
   if t<s.to then
    local k=math.clamp((t-prevEnd)/math.max(.05,s.to-prevEnd),0,1)
    local cf=s.cf(k,t)
    -- Blend in from the previous shot's last frame.
    if i>1 and t-prevEnd<BLEND then local before=spec.shots[i-1].cf(1,prevEnd);cf=before:Lerp(cf,smooth((t-prevEnd)/BLEND)) end
    return cf,s.to
   end
   prevEnd=s.to
  end
  return spec.shots[#spec.shots].cf(1,duration),prevEnd
 end
 local function step()
  local now=workspace:GetServerTimeNow();local t=now-start
  if not folder.Parent or t>=duration then finish();return end
  if hidden and now>=(a.leader:GetAttribute('BossStart') or 0) then hidden=false;hideModel(a.leader,false) end
  for i,m in spec.moments or {} do if not fired[i] and t>=m.at then fired[i]=true;task.spawn(pcall,m.fn) end end
  if spec.tick then spec.tick(t) end
  local cf
  local lastStart=spec.shots[#spec.shots].to
  if t<lastStart then cf=shotAt(t)
  else
   -- Ease from the last shot back to the player's own view (behind them, as it was).
   local home=hrp and hrp.Parent and CFrame.lookAt(hrp.Position+homeOffset,hrp.Position+homeOffset+homeLook) or from
   local last=spec.shots[#spec.shots].cf(1,lastStart)
   cf=last:Lerp(home,smooth((t-lastStart)/math.max(.1,duration-lastStart)))
  end
  if not carded and t>=(spec.card or 2) then carded=true;ui.card(true);T.sound('ui_upgrade') end
  if carded and not uncarded and t>=duration-.55 then uncarded=true;ui.card(false);ui.bars(false) end
  camera.CFrame=cf -- Common.shake adds its offset after this (and obeys the Screen Shake setting)
 end
 conn=RunService.RenderStepped:Connect(function()
  local okStep,err=pcall(step)
  if not okStep then warn('Round10Intro failed: '..tostring(err));finish() end
 end)
 folder.Destroying:Connect(finish)
end
function I.stop() if playing and playing.finish then playing.finish() end end
return I
