-- Egg pedestal stage: the big egg on its nest pedestal next to the egg merchant
-- (Workspace.RogueliteLobby.EggMerchant.Egg, placed by lobby/InstallEggMerchant.luau), its
-- always-on aura, the camera for the egg screen, and the hatch: two wobbles that crack it, then the
-- top bursts off and the pet pops out. Client-only: the aura, camera, wobbles, flying shell pieces
-- and the pet clone exist only on this client; the egg parts are moved locally and put back.
--
-- Egg parts carry `Kind`: base (pedestal, nest), shell (the bottom cup, stays), shard (top pieces,
-- with `Outward` = fling direction in pivot space), crack (with `Stage` 1|2; Neon, hidden at rest),
-- inner (Neon glow inside the cup, seen when open). Model attributes (pivot space): `Hinge`
-- (CFrame at the break line, used by ChestFX for the seam light and the burst), `EggBase`
-- (Vector3, where the egg sits in the nest; it rocks about this point) and `EggCentre`.
--
-- Camera flow (same as ChestStage): Show() flies from the player's view to the egg and settles on
-- the 'select' shot (egg right of centre, list on the left), Focus() pushes in for hatching,
-- Hide() flies back.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local Eggs=require(RS:WaitForChild('RogueliteCombat'):WaitForChild('EggConfig'))
local FX=require(RS:WaitForChild('ChestFX'))
local Merchant=require(RS:WaitForChild('EggMerchant'))
local T=require(RS:WaitForChild('UITheme'))
local S={}

local player=Players.LocalPlayer
local egg,aura,pivot0
local restRel={} -- egg piece -> CFrame in pivot space
local pieces={shell={},shard={},crack={},inner={}}
local base,centre,breakY=Vector3.zero,Vector3.new(0,4,0),3.5

S.Shot={
 select={dist=1.85,height=.55,shift=.34,lookUp=.12,fov=50},
 focus={dist=1.5,height=.38,shift=0,lookUp=.1,fov=44},
}

local function find()
 local lobby=workspace:FindFirstChild('RogueliteLobby')
 local root=lobby and lobby:FindFirstChild('EggMerchant')
 local m=root and root:FindFirstChild('Egg')
 if m and m:IsA('Model') and m.PrimaryPart and m:FindFirstChild('Egg_Bottom') then return m end
 return nil
end

local function hideGlow(p) p.Transparency=1 end

-- Sets up the egg once it has streamed in.
function S.Prepare()
 if egg and egg.Parent then return true end
 local m=find();if not m then return false end
 egg=m;pivot0=m:GetPivot()
 table.clear(restRel);for _,l in pieces do table.clear(l) end
 for _,p in m:GetDescendants() do
  if p:IsA('BasePart') then
   local kind=p:GetAttribute('Kind')
   if pieces[kind] then table.insert(pieces[kind],p);restRel[p]=pivot0:ToObjectSpace(p.CFrame) end
   if kind=='crack' or kind=='inner' then p.Material=Enum.Material.Neon;p.Color=Eggs.Glow;hideGlow(p) end
  end
 end
 table.sort(pieces.crack,function(a,b) return (a:GetAttribute('Stage') or 1)<(b:GetAttribute('Stage') or 1) end)
 base=m:GetAttribute('EggBase') or Vector3.new(0,1.7,0)
 centre=m:GetAttribute('EggCentre') or base+Vector3.new(0,2.3,0)
 local hinge=m:GetAttribute('Hinge');breakY=hinge and hinge.Y or centre.Y
 aura=FX.aura(m,{aura=Eggs.Aura,glow=Eggs.Glow})
 return true
end
function S.Watch(onReady)
 task.spawn(function()
  for _=1,480 do
   if S.Prepare() then if onReady then onReady() end;return end
   task.wait(.5)
  end
 end)
end
function S.Available() return S.Prepare() end
function S.Model() return egg end
function S.Aura() return aura end

-- Egg pieces --------------------------------------------------------------------------------------
-- Pose every egg piece (not the pedestal) rocked by `rock` about the egg's seat in the nest.
local function poseEgg(rock)
 local at=pivot0*CFrame.new(base)*rock*CFrame.new(-base)
 for p,rel in restRel do if p.Parent then p.CFrame=at*rel end end
end
local wobbleToken
-- A decaying rock and hop: strength 1 (first tap) .. 1.8 (second tap).
local function wobble(strength,duration)
 local mine={};wobbleToken=mine
 local start=os.clock()
 local conn;conn=RunService.RenderStepped:Connect(function()
  local t=os.clock()-start
  if wobbleToken~=mine then conn:Disconnect();return end
  if t>=duration then conn:Disconnect();poseEgg(CFrame.identity);return end
  local decay=(1-t/duration)^1.5
  local hop=math.max(0,math.sin(math.min(t/.2,1)*math.pi))*.28*strength
  poseEgg(CFrame.new(0,hop,0)*CFrame.Angles(math.rad(math.sin(t*23)*4*strength*decay),0,math.rad(math.sin(t*31)*7*strength*decay)))
 end)
end
local function fade(p,to,time)
 TweenService:Create(p,TweenInfo.new(time,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Transparency=to}):Play()
end

-- Camera ----------------------------------------------------------------------------------------
local camConn,saved -- saved: the player's own view to fly back to (UITheme keeps it once for all stages)
local eye,look,fov
local tEye,tLook,tFov
local rate=4
local shakeAmp,shakeT=0,0

local function shotFor(kind)
 if not egg then return end
 local cf,size=egg:GetBoundingBox()
 local big=math.max(size.X,size.Y,size.Z)
 local sh=S.Shot[kind]
 local front=pivot0.LookVector;local right=pivot0.RightVector
 local c=cf.Position
 local d=big*sh.dist+3
 local e=c+front*d+Vector3.new(0,big*sh.height,0)+right*(d*sh.shift*.35)
 local l=c+right*(d*sh.shift)+Vector3.new(0,size.Y*sh.lookUp,0)
 return e,l,sh.fov
end
local function overview()
 local c=pivot0.Position
 return c+pivot0.LookVector*30+Vector3.new(0,16,0),c+Vector3.new(0,3,0),55
end
local function drive(dt)
 if T.cameraOwner()~='Eggs' then return end -- the chest stage opened on top during our fly-back
 local cam=workspace.CurrentCamera
 local k=1-math.exp(-dt*rate)
 eye=eye:Lerp(tEye,k);look=look:Lerp(tLook,k);fov+=(tFov-fov)*k
 local offset=Vector3.zero
 if shakeAmp>0 then
  shakeT+=dt
  offset=Vector3.new(math.noise(shakeT*22,1),math.noise(shakeT*22,2),math.noise(shakeT*22,3))*shakeAmp
  shakeAmp=math.max(0,shakeAmp-dt*shakeAmp*5-dt*.05)
 end
 cam.CameraType=Enum.CameraType.Scriptable
 cam.CFrame=CFrame.lookAt(eye+offset,look+offset*.5)
 cam.FieldOfView=fov
end
-- Movement keys do nothing while the egg screen is up (same sink as the chest screen).
local CAS=game:GetService('ContextActionService')
local SINK='EggScreenBlockMovement'
local function setControls(on)
 if on then CAS:UnbindAction(SINK)
 else
  CAS:BindActionAtPriority(SINK,function() return Enum.ContextActionResult.Sink end,false,Enum.ContextActionPriority.High.Value+50,
   Enum.KeyCode.W,Enum.KeyCode.A,Enum.KeyCode.S,Enum.KeyCode.D,Enum.KeyCode.Up,Enum.KeyCode.Down,Enum.KeyCode.Left,Enum.KeyCode.Right,
   Enum.KeyCode.Thumbstick1,Enum.PlayerActions.CharacterForward,Enum.PlayerActions.CharacterBackward,Enum.PlayerActions.CharacterLeft,
   Enum.PlayerActions.CharacterRight,Enum.PlayerActions.CharacterJump)
 end
end

function S.Show()
 if not S.Prepare() then return false end
 local cam=workspace.CurrentCamera
 -- No FOV is saved: Hide always goes back to the regular 70 (2026-10-03, see UITheme.cameraTake).
 saved=T.cameraTake('Eggs',S.IsShown)
 eye=cam.CFrame.Position;look=cam.CFrame.Position+cam.CFrame.LookVector*20;fov=cam.FieldOfView
 tEye,tLook,tFov=overview();rate=2.6
 if camConn then camConn:Disconnect() end
 camConn=RunService.RenderStepped:Connect(drive)
 setControls(false)
 local mine=camConn
 task.delay(.6,function() if camConn==mine then S.Select() end end)
 return true
end
function S.Select(instant)
 local e,l,f=shotFor('select');if not e then return end
 tEye,tLook,tFov=e,l,f;rate=3.2
 if instant then eye,look,fov=e,l,f end
end
function S.Focus()
 local e,l,f=shotFor('focus');if not e then return end
 tEye,tLook,tFov=e,l,f;rate=3.6
end
function S.Shake(amount) shakeAmp=math.max(shakeAmp,amount) end
-- Where the egg's break line is on screen (UI cards fly out of it).
function S.MouthScreen()
 if not egg then return nil end
 local p,on=workspace.CurrentCamera:WorldToViewportPoint(pivot0*Vector3.new(0,breakY,0))
 return Vector2.new(p.X,p.Y),on
end
function S.Hide()
 if not camConn then return end
 local back=saved;saved=nil
 -- Release hands back the regular camera (Custom, your Humanoid, FOV 70) unless another stage holds it.
 local function release() camConn:Disconnect();camConn=nil;T.cameraRelease('Eggs');setControls(true) end
 if back then
  tEye=back.Position;tLook=back.Position+back.LookVector*20;tFov=T.CAMERA_FOV;rate=4.5
  local conn=camConn
  task.delay(.55,function()
   if camConn~=conn then return end
   release()
  end)
 else release() end
end
function S.IsShown() return camConn~=nil end

-- Hatching --------------------------------------------------------------------------------------
-- Taps 1 and 2: a wobble, and that stage's cracks light up. `hint` = best rarity colour inside.
function S.Charge(stage,hint)
 if not egg then return end
 wobble(stage==1 and 1 or 1.8,.5+stage*.1)
 for _,c in pieces.crack do
  if (c:GetAttribute('Stage') or 1)<=stage then c.Color=stage==2 and hint and Eggs.Glow:Lerp(hint,.4) or Eggs.Glow;fade(c,.05,.12) end
 end
 aura:SetLevel(stage)
 aura:Pulse(stage==1 and .8 or 1.3)
 if stage==2 and hint then aura:SetColor(aura.Color:Lerp(hint,.45),Eggs.Glow:Lerp(hint,.3)) end
 S.Shake(.12*stage)
 FX.play(stage==1 and FX.Sounds.GoldShake1 or FX.Sounds.GoldShake2,.75,stage==1 and 1.15 or 1.25)
 if stage==2 then FX.play(FX.Sounds.Charge,.35,1.15) end
end

local flying={} -- shard -> true while in the air
local petClone,petConn
local function clearPet()
 if petConn then petConn:Disconnect();petConn=nil end
 if petClone then petClone:Destroy();petClone=nil end
end
-- The pet pops out of the cup, grows, then hovers and sways facing the camera until Settle().
local function popPet(id,color)
 clearPet()
 local template=RS:FindFirstChild('PetModels') and RS.PetModels:FindFirstChild(id)
 if not template then return end
 local m=template:Clone()
 for _,p in m:GetDescendants() do
  if p:IsA('BasePart') then p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false
  elseif p:IsA('Script') or p:IsA('LocalScript') then p:Destroy() end
 end
 local full=1.55
 m:ScaleTo(.35)
 m.Parent=FX.folder()
 petClone=m
 local rim=pivot0*Vector3.new(base.X,breakY-.35,base.Z)
 local start=os.clock()
 local light=Instance.new('PointLight');light.Color=color or Eggs.Glow;light.Brightness=1.2;light.Range=9
 light.Parent=m.PrimaryPart or m:FindFirstChildWhichIsA('BasePart')
 petConn=RunService.RenderStepped:Connect(function()
  if not m.Parent then return end
  local t=os.clock()-start
  local grow=TweenService:GetValue(math.clamp(t/.5,0,1),Enum.EasingStyle.Back,Enum.EasingDirection.Out)
  local s=.35+(full-.35)*grow
  if math.abs(m:GetScale()-s)>.005 then m:ScaleTo(s) end
  local rise=math.clamp(t/.4,0,1)
  local bob=t>.5 and math.sin((t-.5)*2.4)*.14 or 0
  local cam=workspace.CurrentCamera.CFrame.Position
  local pos=rim+Vector3.new(0,-1.2+1.6*TweenService:GetValue(rise,Enum.EasingStyle.Quad,Enum.EasingDirection.Out)+bob,0)
  local face=Vector3.new(cam.X,pos.Y,cam.Z)
  local sway=math.sin(t*1.3)*.18
  m:PivotTo(CFrame.lookAt(pos,face)*CFrame.Angles(0,sway,0))
 end)
end

-- Tap 3: the top shards fly off, the inside glows, the pet pops out. scale: 1 / 1.6 / 2.4 (×1/×3/×10).
function S.Burst(scale,hint,petId)
 if not egg then return end
 wobbleToken=nil;poseEgg(CFrame.identity)
 aura:SetLevel(3)
 if hint then aura:SetColor(hint) end
 for _,c in pieces.crack do fade(c,1,.15) end
 for _,p in pieces.inner do p.Color=hint and Eggs.Glow:Lerp(hint,.5) or Eggs.Glow;fade(p,.1,.2) end
 -- Shards: outward and up with spin and gravity; fade at the end of the flight.
 local up=pivot0.UpVector
 for i,s in pieces.shard do
  flying[s]=true
  local out=s:GetAttribute('Outward');out=out and pivot0:VectorToWorldSpace(out) or (s.Position-pivot0*centre).Unit
  local v=out*(13+math.random()*6)*math.sqrt(scale)+up*(14+math.random()*6)
  local axis=out:Cross(up);axis=axis.Magnitude>.01 and axis.Unit or Vector3.xAxis
  local spin=(5+math.random()*5)*(i%2==0 and 1 or -1)
  local p0,r0=s.Position,s.CFrame.Rotation
  local start=os.clock()
  local conn;conn=RunService.RenderStepped:Connect(function()
   local t=os.clock()-start
   if not flying[s] then conn:Disconnect();return end
   if t>1.3 then conn:Disconnect();s.Transparency=1;return end
   s.CFrame=CFrame.new(p0+v*t+Vector3.new(0,-55,0)*t*t*.5)*CFrame.fromAxisAngle(axis,spin*t)*r0
   if t>.8 then s.Transparency=math.clamp((t-.8)/.5,0,1) end
  end)
 end
 FX.burst(aura,scale,hint)
 S.Shake(.35+.1*math.min(scale,5))
 FX.play(FX.Sounds.GoldShake2,.8,.8)
 FX.play(FX.Sounds.Burst,.6,1.05)
 if petId then task.delay(.12,function() popPet(petId,hint) end) end
 -- Once the pet is out, calm the glow so it doesn't wash the pet out (full blast hid the Frog).
 task.delay(1.1,function() if petClone and aura then aura:SetLevel(1) end end)
end

-- Put the egg back together (CLAIM, hatch again, or leaving mid-way): the pet goes, the shards
-- reappear in place with a quick fade, cracks and glow go dark, the aura calms down.
function S.Settle()
 if not egg then return end
 clearPet()
 wobbleToken=nil
 table.clear(flying)
 poseEgg(CFrame.identity)
 for _,s in pieces.shard do s.Transparency=1;fade(s,0,.35) end
 for _,c in pieces.crack do hideGlow(c) end
 for _,p in pieces.inner do fade(p,1,.3) end
 aura:SetColor(Eggs.Aura,Eggs.Glow);aura:SetLevel(0)
end

-- The merchant comes to life with the stage (the lobby UI requires this module).
Merchant.Start()

return S
