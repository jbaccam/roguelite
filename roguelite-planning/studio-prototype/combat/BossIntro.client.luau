-- A wave boss's super-jump entrance, client side (plans/2026-10-03-tutorial-design.md). BossService
-- times it with attributes on the boss:
--   BossIntroStart  rumble; a dark shadow grows where he will land; the camera turns to the spot
--   BossIntroLand   he falls the last FALL seconds and lands hammer-first (BossPresentation plays his
--                   Slam clip timed to the landing, with its dust and boom); shockwave ring and shake
--   BossIntroUntil  a camera orbit with his name card, then the camera eases back to the player
-- Presentation only: the server holds him (anchored where he lands, can't be hurt), the players and
-- the enemies until BossIntroUntil. The falling body is this client moving the anchored root
-- locally; it is put back on the server's spot at the landing. The camera is always handed back.
-- Map bosses with a def.intro (MapBossService; the Hammer Brute) set the same attributes and
-- BossIntroName, and MapBossPresentation plays their intro clip (IntroLand) timed to the landing.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local TweenService=game:GetService('TweenService')
local SoundService=game:GetService('SoundService')
local RS=game:GetService('ReplicatedStorage')
local T=require(RS:WaitForChild('UITheme'))
local player=Players.LocalPlayer
local FALL=.65 -- BossService.INTRO.fall
local HEIGHT=110 -- studs he falls from
local NAMES={HammerBoss='HAMMER BRUTE'}
local DUST=Color3.fromRGB(255,236,206)
local playing=false

local function smooth(x) x=math.clamp(x,0,1);return x*x*(3-2*x) end
local function flat(parent,name,size,cf,color,transparency,material)
 local p=Instance.new('Part');p.Name=name;p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false
 p.Size=size;p.CFrame=cf;p.Color=color;p.Transparency=transparency;p.Material=material or Enum.Material.SmoothPlastic;p.Parent=parent
 return p
end
-- A flat disc lying on the ground (a cylinder turned on its side).
local function disc(parent,name,center,diameter,color,transparency)
 local p=flat(parent,name,Vector3.new(.06,diameter,diameter),CFrame.new(center)*CFrame.Angles(0,0,math.pi/2),color,transparency)
 p.Shape=Enum.PartType.Cylinder
 return p
end
-- Shockwave: a ring of short flat neon segments that spreads out and fades (no shaded mesh).
local function shockwave(parent,center,from,to,seconds,width)
 local ring=Instance.new('Folder');ring.Name='Shockwave';ring.Parent=parent
 local segments={}
 for i=1,32 do
  segments[i]=flat(ring,'Segment',Vector3.new(width,.05,1),CFrame.new(center),DUST,.15,Enum.Material.Neon)
 end
 local t0=os.clock()
 local conn
 conn=RunService.RenderStepped:Connect(function()
  local k=math.clamp((os.clock()-t0)/seconds,0,1);local e=1-(1-k)^3
  local r=from+(to-from)*e
  for i,s in segments do
   local a=i*math.pi/16
   s.Size=Vector3.new(width*(1-k*.6),.05,r*math.pi/16+.1)
   s.CFrame=CFrame.new(center+Vector3.new(math.sin(a)*r,.04,math.cos(a)*r))*CFrame.Angles(0,a+math.pi/2,0)
   s.Transparency=.15+.85*k
  end
  if k>=1 then conn:Disconnect();ring:Destroy() end
 end)
end
local function boom(parent)
 local s=Instance.new('Sound');s.SoundId='rbxasset://sounds/impact_explosion_03.mp3';s.Volume=.9;s.PlaybackSpeed=.42
 s.SoundGroup=SoundService:FindFirstChild('RogueliteSFX');s.Parent=parent;s:Play() -- the Settings SFX slider
end
-- Letterbox bars and the boss's name card.
local function overlay(name)
 local gui=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='BossIntro',ResetOnSpawn=false,DisplayOrder=90,IgnoreGuiInset=true,ZIndexBehavior=Enum.ZIndexBehavior.Sibling})
 local bars={}
 for i,anchor in {0,1} do
  local b=T.make('Frame',gui,{Name=i==1 and 'TopBar' or 'BottomBar',AnchorPoint=Vector2.new(0,anchor),Position=UDim2.fromScale(0,anchor),Size=UDim2.new(1,0,0,0),BackgroundColor3=Color3.new(0,0,0),BorderSizePixel=0})
  bars[i]=b
 end
 local holder=T.make('Frame',gui,{Name='Card',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.74),Size=UDim2.fromOffset(640,130),BackgroundTransparency=1,Visible=false})
 local scale=T.make('UIScale',holder,{Scale=1})
 local plate=T.panel(holder,'Plate',0,18,640,96,'panel');T.caps(plate,56)
 local title=T.label(plate,'Name',name,40,8,560,62,54,T.Color.gold);title.TextStrokeTransparency=0
 local sub=T.label(holder,'Sub','WAVE BOSS',220,0,200,34,24,T.Color.negative);sub.TextStrokeTransparency=0
 local function fit()
  local v=gui.AbsoluteSize;scale.Scale=math.clamp(math.min(v.X/1280,v.Y/760),.5,1.2)
 end
 gui:GetPropertyChangedSignal('AbsoluteSize'):Connect(fit);fit()
 local o={gui=gui}
 function o.bars(on)
  for _,b in bars do TweenService:Create(b,TweenInfo.new(.45,Enum.EasingStyle.Quad),{Size=UDim2.new(1,0,on and .1 or 0,0)}):Play() end
 end
 function o.card(on)
  holder.Visible=on
  if on then scale.Scale*=1.35;local v=gui.AbsoluteSize;local s=math.clamp(math.min(v.X/1280,v.Y/760),.5,1.2)
   TweenService:Create(scale,TweenInfo.new(.4,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=s}):Play() end
 end
 return o
end

-- Unique entrances (MapBossDefs def.intro.style, round 10 spec: every boss its own intro). Each
-- style owns the body before the landing (local root moves on the server-anchored boss), the camera
-- before the landing and the effects; the orbit with the name card and the ease home are shared.
-- The health bar slides in only after BossIntroUntil (RogueliteHUD), so it never covers the shot.
--   skydrop   (the Hammer Brute; nil) the super jump: shadow, fall, crater, shockwaves (as before).
--   surface   (Giant King Crab) sand churns, the claws break the surface first, he hauls himself up.
--   sandrise  (The Pharaoh) a sand spiral and a glyph circle; he rises through it, staff first.
--   footsteps (Frost Cyclops) three heavy thuds from his feet, the camera climbs to the club.
--   descent   (Inferno Dragon) his shadow sweeps the arena; he glides down and lands.
--   event     (round 10 leaders) nothing here: Round10Events films them inside the event's intro.
local Common
local function vfx()
 if Common==nil then local ok,m=pcall(function() return require(RS:WaitForChild('RogueliteCombat'):WaitForChild('BossVfx'):WaitForChild('Common')) end);Common=ok and m or false end
 return Common or nil
end
local up=Vector3.yAxis
local STYLE={}
STYLE.skydrop=function(c)
 local shadow=disc(c.fx,'Shadow',c.spot+up*.06,3,Color3.new(0,0,0),.9)
 local crater
 return {
  body=function(t)
   if t<c.land-FALL then c.root.CFrame=c.frame+up*400
   elseif t<c.land then local k=(t-(c.land-FALL))/FALL;c.root.CFrame=c.frame+up*HEIGHT*(1-k*k) end
  end,
  pre=function(t,g,landed)
   shadow.Size=Vector3.new(.06,3+c.radius*.6*g,3+c.radius*.6*g);shadow.Transparency=landed and 1 or .9-.55*g
   if crater then crater.Transparency=.25+.75*smooth((t-c.land)/(c.done-c.land)) end
  end,
  landed=function()
   shockwave(c.fx,c.spot,3,c.radius*1.1,.6,1.1)
   task.delay(.12,function() if c.fx.Parent then shockwave(c.fx,c.spot,2,c.radius*.75,.55,.8) end end)
   crater=disc(c.fx,'Crater',c.spot+up*.05,c.radius*.55,Color3.fromRGB(58,44,34),.25)
   boom(c.fx)
  end,
 }
end
-- Rising from below the ground: depth studs down until `from`, up to the spot by `to` (eased), with
-- an optional pitch (claws first) that levels out as it rises.
local function riser(c,depth,from,to,pitch)
 return function(t)
  local k=smooth((t-from)/math.max(.1,to-from))
  c.root.CFrame=c.frame*CFrame.new(0,-depth*(1-k),0)*CFrame.Angles((pitch or 0)*(1-k),0,0)
 end
end
local function lowWatch(c,height,dist)
 return CFrame.lookAt(c.spot+c.side*(c.radius*(dist or 1.35))+up*c.radius*(height or .35),c.spot+up*c.size.Y*.42)
end
STYLE.surface=function(c)
 local V=vfx();local depth=c.size.Y+2;local riseFrom=c.start+.55
 local watch=lowWatch(c,.3,1.3)
 local churn
 return {
  body=riser(c,depth,riseFrom,c.land-.12,-.45),
  camera=function(t) return c.from:Lerp(watch,smooth((t-c.start)/.7)) end,
  rumble=function(t,g) return .1+.35*g end,
  pre=function(t)
   if V and not churn and t>=c.start+.1 then
    churn=V.host(c.spot+up*.4,math.max(.5,c.land-t)+.6,up)
    V.fx(churn,'SandSpray',{Rate=40,Speed={8,16},SpreadAngle=60,Lifetime={.7,1.1},Size=V.ns({0,2},{1,5}),Color=Color3.fromRGB(226,206,160),Transparency=V.ns({0,.15},{1,1}),Drag=2,LightInfluence=.8,Rotation={0,360},EmissionDirection=Enum.NormalId.Top})
    V.fx(churn,'WaterSplash',{Rate=14,Speed={10,18},SpreadAngle=45,Lifetime={.6,.9},Size=V.ns({0,2},{1,4}),Color=Color3.fromRGB(220,240,255),Transparency=V.ns({0,.2},{1,1}),Drag=2,Rotation={0,360},EmissionDirection=Enum.NormalId.Top})
    V.cue('crab_scuttle',c.spot,.6,.7)
   end
  end,
  landed=function()
   if V then V.dustRing(c.spot,c.radius*.3,14,Color3.fromRGB(226,206,160),20,4.5);V.ring(c.spot+up*.08,'ShockwaveRing',4,c.radius*1.8,.6,Color3.fromRGB(255,236,206),.15) end
   boom(c.fx)
  end,
 }
end
STYLE.sandrise=function(c)
 local V=vfx();local depth=c.size.Y+1.5;local watch=lowWatch(c,.32,1.4)
 local spun,plate,setPlate
 return {
  body=riser(c,depth,c.start+.6,c.land-.35,0),
  camera=function(t) return c.from:Lerp(watch,smooth((t-c.start)/.75)) end,
  rumble=function(t,g) return .06+.18*g end,
  pre=function(t,g)
   if V and not spun then
    spun=true
    plate,setPlate=V.plate(c.spot+up*.06,'HieroglyphCircle',c.radius*.9,Color3.fromRGB(255,214,110),0,1.6)
    -- The spiral: emitters circling the spot until the landing.
    local host=V.host(c.spot+up*.5,(c.land-t)+.8,up)
    V.fx(host,'SandSpray',{Rate=60,Speed={6,12},SpreadAngle=25,Lifetime={1,1.5},Size=V.ns({0,2},{1,6}),Color=Color3.fromRGB(230,200,140),Transparency=V.ns({0,.2},{1,1}),Drag=1.2,LightInfluence=.7,Rotation={0,360},RotSpeed={-120,120},EmissionDirection=Enum.NormalId.Top,Acceleration=Vector3.new(0,6,0)})
    V.fx(host,'Hieroglyphs',{Rate=10,Speed={4,8},SpreadAngle=40,Lifetime={1,1.6},Size=V.ns({0,1.2},{1,1.8}),Color=Color3.fromRGB(255,214,110),LightEmission=.8,Transparency=V.ns({0,.1},{1,1}),EmissionDirection=Enum.NormalId.Top})
    V.cue('pharaoh_charge',c.spot,.6,.9)
   end
   if setPlate then setPlate(1-.85*g,nil,nil,(t*60)%360) end
  end,
  landed=function()
   if V then V.cue('sand_burst',c.spot,.8,.8);V.dustRing(c.spot,c.radius*.25,12,Color3.fromRGB(230,200,140),16,4) end
   if plate then task.delay(1.2,function() if plate.Parent then plate:Destroy() end end) end
  end,
 }
end
STYLE.footsteps=function(c)
 local V=vfx()
 local beats={c.start+.35,c.start+.95,c.start+1.55}
 local fired={}
 local low=CFrame.lookAt(c.spot+c.side*(c.radius*.75)+up*1.6,c.spot+up*c.size.Y*.2)
 local high=CFrame.lookAt(c.spot+c.side*(c.radius*1.25)+up*c.size.Y*.5,c.spot+up*c.size.Y*.75)
 return {
  camera=function(t)
   if t<beats[3]+.2 then return c.from:Lerp(low,smooth((t-c.start)/.5)) end
   return low:Lerp(high,smooth((t-beats[3]-.2)/math.max(.2,c.land-beats[3]-.2)))
  end,
  rumble=function(t) for _,b in beats do if t>=b and t<b+.35 then return .9*(1-(t-b)/.35) end end;return 0 end,
  pre=function(t)
   for i,b in beats do
    if not fired[i] and t>=b then
     fired[i]=true
     if V then V.cue('ice_wave',c.spot,.7,.65+i*.05);V.dustRing(c.spot,c.size.X*.3,8,Color3.fromRGB(220,235,245),10,3) end
    end
   end
  end,
  landed=function() if V then V.ring(c.spot+up*.08,'FrostRing',4,c.radius*1.9,.7,Color3.fromRGB(190,235,255),.1,1.2) end;boom(c.fx) end,
 }
end
STYLE.descent=function(c)
 local V=vfx()
 local back=-Vector3.new(c.frame.LookVector.X,0,c.frame.LookVector.Z).Unit
 local glideFrom=c.start+.6
 local shadow=disc(c.fx,'Shadow',c.spot+up*.06,c.radius*.9,Color3.new(0,0,0),1)
 return {
  body=function(t)
   local k=smooth((t-glideFrom)/math.max(.2,c.land-glideFrom))
   if t<glideFrom then c.root.CFrame=c.frame+up*400;return end
   -- An arc down from behind and above, nose easing level for the landing.
   local offset=back*(70*(1-k))+up*(48*(1-k)^1.6)
   c.root.CFrame=(c.frame+offset)*CFrame.Angles(math.rad(14)*(1-k),0,0)
  end,
  camera=function(t)
   local watch=CFrame.lookAt(c.spot+c.side*(c.radius*1.7)+up*c.radius*.55,c.root.Position)
   return c.from:Lerp(watch,smooth((t-c.start)/.6))
  end,
  rumble=function(t,g) return .05+.15*g end,
  pre=function(t,g)
   -- The shadow sweeps in across the arena ahead of him, darkening as he nears.
   local k=smooth((t-c.start)/math.max(.2,c.land-c.start))
   local p=c.spot+back*(80*(1-k))+up*.06
   shadow.CFrame=CFrame.new(p)*CFrame.Angles(0,0,math.pi/2);shadow.Transparency=1-.5*k
   if V and not c.flapped and t>=glideFrom then c.flapped=true;V.cue('wing_flap',c.spot,.8,.8);V.cue('dragon_windup',c.spot,.6,.9) end
  end,
  landed=function() shadow.Transparency=1;if V then V.dustRing(c.spot,c.radius*.35,14,Color3.fromRGB(150,120,100),20,5) end;boom(c.fx) end,
 }
end
local function play(npc)
 local start,land,done=npc:GetAttribute('BossIntroStart'),npc:GetAttribute('BossIntroLand'),npc:GetAttribute('BossIntroUntil')
 if playing or type(land)~='number' or type(done)~='number' then return end
 local styleName=npc:GetAttribute('BossIntroStyle') or 'skydrop'
 if styleName=='event' then return end -- a round 10 leader: Round10Events films it
 if workspace:GetServerTimeNow()>=done-.3 then return end
 local root=npc.PrimaryPart or npc:WaitForChild('HumanoidRootPart',3)
 local frame=npc:GetAttribute('BossFrame')
 if not root or typeof(frame)~='CFrame' then return end
 playing=true
 start=type(start)=='number' and start or land-1.8
 local camera=workspace.CurrentCamera
 local spot=Vector3.new(frame.X,npc:GetAttribute('BossGroundY') or frame.Y-6,frame.Z)
 local size=npc:GetExtentsSize()
 local chest=spot+Vector3.yAxis*math.max(6,size.Y*.55)
 local radius=math.max(20,size.Y*1.7)
 local fx=Instance.new('Folder');fx.Name='BossIntroFX';fx.Parent=workspace
 -- The card: the old Hammer's name, else the map boss's BossIntroName (MapBossDefs introName), else
 -- its BossName in capitals.
 local ui=overlay(NAMES[npc.Name] or npc:GetAttribute('BossIntroName') or string.upper(npc:GetAttribute('BossName') or npc.Name))
 ui.bars(true)
 local shake=T.setting('ScreenShake')~=false and 1 or 0
 -- Camera: where it was (to come back to), relative to the player so a nudge doesn't matter.
 local hrp=player.Character and player.Character:FindFirstChild('HumanoidRootPart')
 local homeOffset=hrp and camera.CFrame.Position-hrp.Position or Vector3.new(0,12,20)
 local homeLook=camera.CFrame.LookVector
 local from=camera.CFrame
 local side=hrp and Vector3.new(hrp.Position.X-spot.X,0,hrp.Position.Z-spot.Z) or Vector3.new(0,0,1)
 side=side.Magnitude>1 and side.Unit or Vector3.new(0,0,1)
 local watch=CFrame.lookAt(spot+side*(radius*1.9)+Vector3.yAxis*radius*.8,chest+Vector3.yAxis*4)
 local angle0=math.atan2(side.X,side.Z)
 local ctx={npc=npc,root=root,frame=frame,spot=spot,size=size,chest=chest,radius=radius,fx=fx,side=side,start=start,land=land,done=done,from=from,watch=watch}
 local plan=(STYLE[styleName] or STYLE.skydrop)(ctx)
 T.cameraTake('BossIntro',function() return playing end)
 camera.CameraType=Enum.CameraType.Scriptable
 local landed,carded,uncarded,conn=false,false,false,nil
 local orbitEnd
 local function finish()
  if conn then conn:Disconnect();conn=nil end
  fx:Destroy();ui.gui:Destroy()
  if root.Parent then root.CFrame=frame end
  playing=false
  -- The regular camera: Custom, your Humanoid (or the teammate you spectate), FOV 70 (UITheme).
  T.cameraRelease('BossIntro')
 end
 local function step()
  local t=workspace:GetServerTimeNow()
  if not npc.Parent or t>=done then finish();return end
  -- The body before the landing (each style's own), then on the server's spot.
  if t<land then if plan.body then plan.body(t) end
  elseif not landed then
   landed=true;root.CFrame=frame
   if plan.landed then plan.landed() end
  end
  local g=smooth((t-start)/(land-start))
  if plan.pre then plan.pre(t,g,landed) end
  -- Camera: the style's shot until just after the landing, then the orbit, then ease back home.
  local cf
  if t<land+.35 then
   cf=plan.camera and plan.camera(t) or from:Lerp(watch,smooth((t-start)/math.max(.2,math.min(.7,land-start))))
   orbitEnd=nil
  elseif t<done-.7 then
   local u=smooth((t-land-.35)/math.max(.1,done-.7-land-.35))
   local a=angle0+math.rad(115)*u
   local r=radius*(1.35-.25*u)
   cf=CFrame.lookAt(spot+Vector3.new(math.sin(a)*r,0,math.cos(a)*r)+Vector3.yAxis*(size.Y*.45+2),chest)
   orbitEnd=cf
  else
   local home=hrp and hrp.Parent and CFrame.lookAt(hrp.Position+homeOffset,hrp.Position+homeOffset+homeLook) or from
   cf=(orbitEnd or watch):Lerp(home,smooth((t-(done-.7))/.7))
  end
  -- Shake: the style's rumble before the landing (the sky drop's builds with the shadow), a hard
  -- jolt on it.
  local amount=0
  if t<land then amount=plan.rumble and plan.rumble(t,g) or .08+.25*g elseif t<land+.8 then amount=1.6*(1-(t-land)/.8)^2 end
  amount*=shake
  if amount>0 then cf*=CFrame.new((math.random()-.5)*amount,(math.random()-.5)*amount,0)*CFrame.Angles(0,0,(math.random()-.5)*amount*.02) end
  camera.CFrame=cf
  if not carded and t>=land+.5 then carded=true;ui.card(true) end
  if carded and not uncarded and t>=done-.7 then uncarded=true;ui.card(false);ui.bars(false) end
 end
 conn=RunService.RenderStepped:Connect(function()
  local ok,err=pcall(step)
  if not ok then warn('BossIntro failed:',err);finish() end
 end)
end

local function watchBoss(npc) task.spawn(play,npc) end
Tags:GetInstanceAddedSignal('HammerBoss'):Connect(watchBoss)
for _,npc in Tags:GetTagged('HammerBoss') do watchBoss(npc) end
-- Map bosses play it when they have an entrance (BossIntroStart; its style, BossIntroStyle). The tag
-- can land a moment before the intro attributes, so a boss without them yet is given 2 s for them.
local function watchMapBoss(npc)
 if npc:GetAttribute('BossIntroStart')~=nil then watchBoss(npc);return end
 local c;c=npc:GetAttributeChangedSignal('BossIntroStart'):Connect(function() c:Disconnect();watchBoss(npc) end)
 task.delay(2,function() if c.Connected then c:Disconnect() end end)
end
Tags:GetInstanceAddedSignal('MapBoss'):Connect(watchMapBoss)
for _,npc in Tags:GetTagged('MapBoss') do watchMapBoss(npc) end

-- Self-heal to the regular camera (Custom, your Humanoid, FOV 70) on arrival and after every spawn,
-- unless a camera stage holds it (2026-10-03: players were left in a narrow "isometric" view). Here
-- because this script runs on every server role, lobby and match.
local function heal() task.defer(T.cameraHeal) end
player.CharacterAdded:Connect(function(character) character:WaitForChild('Humanoid',10);heal() end)
if player.Character then heal() end
