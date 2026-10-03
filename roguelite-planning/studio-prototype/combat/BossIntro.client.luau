-- A wave boss's super-jump entrance, client side (plans/2026-10-03-tutorial-design.md). BossService
-- times it with attributes on the boss:
--   BossIntroStart  rumble; a dark shadow grows where he will land; the camera turns to the spot
--   BossIntroLand   he falls the last FALL seconds and lands hammer-first (BossPresentation plays his
--                   Slam clip timed to the landing, with its dust and boom); shockwave ring and shake
--   BossIntroUntil  a camera orbit with his name card, then the camera eases back to the player
-- Presentation only: the server holds him (anchored where he lands, can't be hurt), the players and
-- the enemies until BossIntroUntil. The falling body is this client moving the anchored root
-- locally; it is put back on the server's spot at the landing. The camera is always handed back.
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
local NAMES={HammerBoss='HAMMER ZOMBIE BOSS'}
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

local function play(npc)
 local start,land,done=npc:GetAttribute('BossIntroStart'),npc:GetAttribute('BossIntroLand'),npc:GetAttribute('BossIntroUntil')
 if playing or type(land)~='number' or type(done)~='number' then return end
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
 local shadow=disc(fx,'Shadow',spot+Vector3.yAxis*.06,3,Color3.new(0,0,0),.9)
 local crater
 local ui=overlay(NAMES[npc:GetAttribute('ZombieType')] or string.upper(npc.Name))
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
 camera.CameraType=Enum.CameraType.Scriptable
 local landed,carded,uncarded,conn=false,false,false,nil
 local orbitEnd
 local function finish()
  if conn then conn:Disconnect();conn=nil end
  fx:Destroy();ui.gui:Destroy()
  if root.Parent then root.CFrame=frame end
  local h=player.Character and player.Character:FindFirstChildOfClass('Humanoid')
  camera.CameraType=Enum.CameraType.Custom
  if h then camera.CameraSubject=h end
  playing=false
 end
 local function step()
  local t=workspace:GetServerTimeNow()
  if not npc.Parent or t>=done then finish();return end
  -- The body: hidden high above, then the fall (speeding up), then on the server's spot.
  if t<land-FALL then root.CFrame=frame+Vector3.yAxis*400
  elseif t<land then local k=(t-(land-FALL))/FALL;root.CFrame=frame+Vector3.yAxis*HEIGHT*(1-k*k)
  elseif not landed then
   landed=true;root.CFrame=frame
   shockwave(fx,spot,3,radius*1.1,.6,1.1)
   task.delay(.12,function() if fx.Parent then shockwave(fx,spot,2,radius*.75,.55,.8) end end)
   crater=disc(fx,'Crater',spot+Vector3.yAxis*.05,radius*.55,Color3.fromRGB(58,44,34),.25)
   boom(fx)
  end
  -- Shadow grows until he lands, then the crater fades.
  local g=smooth((t-start)/(land-start))
  shadow.Size=Vector3.new(.06,3+radius*.6*g,3+radius*.6*g);shadow.Transparency=landed and 1 or .9-.55*g
  if crater then crater.Transparency=.25+.75*smooth((t-land)/(done-land)) end
  -- Camera: ease to a view of the spot, hold through the fall, orbit him, then ease back home.
  local cf
  if t<land+.35 then
   cf=from:Lerp(watch,smooth((t-start)/math.max(.2,math.min(.7,land-start))))
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
  -- Shake: a low rumble before the landing, a hard jolt on it.
  local amount=0
  if t<land then amount=.08+.25*g elseif t<land+.8 then amount=1.6*(1-(t-land)/.8)^2 end
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
