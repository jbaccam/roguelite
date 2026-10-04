-- Chest island stage: the five chests on their pedestals (Workspace.RogueliteLobby.ChestIsland,
-- built by lobby/InstallChestIsland.luau), their always-on auras and name labels, and the camera
-- for the chest screen. Client-only: auras, labels, camera moves and the opening animation exist
-- only on this client; the chests are moved locally and put back afterwards.
--
-- Camera flow: Show() flies from the player's view to the island, Select(tier) pans between
-- chests (chest on the right, list on the left), Focus() pushes in for opening, Hide() flies back.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local Chests=require(RS:WaitForChild('RogueliteCombat'):WaitForChild('ChestConfig'))
local FX=require(RS:WaitForChild('ChestFX'))
local T=require(RS:WaitForChild('UITheme'))
local S={}

local player=Players.LocalPlayer
local island,chests,auras,labels={},{},{},{}
local ready=false

-- Camera shot tuning (studs, multiplied by the chest's largest side where noted).
S.Shot={
 select={dist=1.95,height=.75,shift=.34,lookUp=.1,fov=50},
 focus={dist=1.75,height=.5,shift=0,lookUp=-.12,fov=44},
 overview={fov=55},
}

local function root() return workspace:FindFirstChild('RogueliteLobby') and workspace.RogueliteLobby:FindFirstChild('ChestIsland') end

-- World labels above each chest: name in the chest colour, owned count underneath.
local function label(model,def)
 local cf,size=model:GetBoundingBox()
 local g=Instance.new('BillboardGui');g.Name='ChestLabel';g.Adornee=model.PrimaryPart or model:FindFirstChildWhichIsA('BasePart')
 g.Size=UDim2.fromScale(9,2.9);g.StudsOffsetWorldSpace=Vector3.new(0,size.Y*.55+2.4,0)+(cf.Position-g.Adornee.Position)*Vector3.new(1,0,1)
 g.LightInfluence=0;g.MaxDistance=220;g.AlwaysOnTop=false;g.ResetOnSpawn=false
 local name=Instance.new('TextLabel');name.Name='Name';name.BackgroundTransparency=1;name.Size=UDim2.fromScale(1,.55);name.Font=Enum.Font.FredokaOne
 name.Text=def.name;name.TextScaled=true;name.TextColor3=Color3.new(1,1,1);name.TextStrokeTransparency=.2;name.Parent=g
 local grad=Instance.new('UIGradient');grad.Color=ColorSequence.new(def.aura:Lerp(Color3.new(1,1,1),.55),def.aura:Lerp(Color3.new(1,1,1),.15));grad.Rotation=90;grad.Parent=name
 local line=Instance.new('Frame');line.Name='Underline';line.BorderSizePixel=0;line.BackgroundColor3=def.aura:Lerp(Color3.new(1,1,1),.4);line.AnchorPoint=Vector2.new(.5,0)
 line.Position=UDim2.fromScale(.5,.57);line.Size=UDim2.fromScale(.8,.035);line.Parent=g
 local lg=Instance.new('UIGradient');lg.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.5,0),NumberSequenceKeypoint.new(1,1)});lg.Parent=line
 local count=Instance.new('TextLabel');count.Name='Count';count.BackgroundTransparency=1;count.Position=UDim2.fromScale(0,.63);count.Size=UDim2.fromScale(1,.34)
 count.Font=Enum.Font.FredokaOne;count.TextScaled=true;count.TextColor3=Color3.fromRGB(210,255,161);count.TextStrokeTransparency=.3;count.Text='';count.Parent=g
 g.Parent=player:WaitForChild('PlayerGui')
 return g
end

-- Sets up every chest that has streamed in. Chests missing so far are picked up by S.Watch.
function S.Prepare()
 local r=root();if not r then return false end
 local folder=r:FindFirstChild('Chests');if not folder then return false end
 island=r
 for _,id in Chests.Order do
  local m=folder:FindFirstChild(id)
  if not chests[id] and m and m:IsA('Model') and m.PrimaryPart and #m:GetChildren()>=4 then
   chests[id]=m
   local def=Chests.ById[id]
   auras[id]=FX.aura(m,{aura=def.aura,glow=def.glow})
   labels[id]=label(m,def)
  end
 end
 ready=next(chests)~=nil
 return ready
end
-- The island is Persistent but still arrives a moment after the player: keep trying until
-- every chest is set up, calling onChange each time more chests appear.
function S.Watch(onChange)
 task.spawn(function()
  local have=0
  for _=1,240 do
   S.Prepare()
   local n=0;for _ in chests do n+=1 end
   if n~=have then have=n;if onChange then onChange() end end
   if n>=#Chests.Order then return end
   task.wait(.5)
  end
 end)
end
function S.Available() return S.Prepare() end
function S.Chest(id) return chests[id] end
function S.Aura(id) return auras[id] end

-- Owned counts on the world labels ('×3 READY' in lime, nothing when none).
function S.SetCounts(owned)
 for id,g in labels do
  local n=owned[id] or 0
  g.Count.Text=n>0 and ('×'..n..' READY') or ''
 end
end

-- Camera ----------------------------------------------------------------------------------------
local camConn,saved -- saved: the player's own view to fly back to (UITheme keeps it once for all stages)
local eye,look,fov
local tEye,tLook,tFov
local rate=4
local shakeAmp,shakeT=0,0
local current -- selected chest id

local function shotFor(id,kind)
 local m=chests[id];if not m then return end
 local cf,size=m:GetBoundingBox()
 local pivot=FX.rest(m).pivot
 local big=math.max(size.X,size.Y,size.Z)
 local sh=S.Shot[kind]
 local front=pivot.LookVector;local right=pivot.RightVector
 local centre=cf.Position
 local d=big*sh.dist+3
 local e=centre+front*d+Vector3.new(0,big*sh.height,0)+right*(d*sh.shift*.35)
 local l=centre+right*(d*sh.shift)+Vector3.new(0,size.Y*sh.lookUp,0)
 return e,l,sh.fov
end
local function overview()
 local sum,n=Vector3.zero,0
 for _,m in chests do sum+=m:GetPivot().Position;n+=1 end
 local c=sum/n
 local front=Vector3.zero
 for _,m in chests do front+=m:GetPivot().LookVector end
 front=(front*Vector3.new(1,0,1)).Unit
 return c+front*48+Vector3.new(0,20,0),c+Vector3.new(0,3,0),S.Shot.overview.fov
end

local function drive(dt)
 if T.cameraOwner()~='Chests' then return end -- the egg stage opened on top during our fly-back
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

-- Movement keys do nothing while the chest screen is up (sunk at high priority, so this works
-- with any control scripts; Escape/Space/Enter stay free for the screen).
local CAS=game:GetService('ContextActionService')
local SINK='ChestScreenBlockMovement'
local function setControls(on)
 if on then CAS:UnbindAction(SINK)
 else
  CAS:BindActionAtPriority(SINK,function() return Enum.ContextActionResult.Sink end,false,Enum.ContextActionPriority.High.Value+50,
   Enum.KeyCode.W,Enum.KeyCode.A,Enum.KeyCode.S,Enum.KeyCode.D,Enum.KeyCode.Up,Enum.KeyCode.Down,Enum.KeyCode.Left,Enum.KeyCode.Right,
   Enum.KeyCode.Thumbstick1,Enum.PlayerActions.CharacterForward,Enum.PlayerActions.CharacterBackward,Enum.PlayerActions.CharacterLeft,
   Enum.PlayerActions.CharacterRight,Enum.PlayerActions.CharacterJump)
 end
end

local function showLabels(on) for _,g in labels do g.Enabled=on end end
function S.Show(id)
 if not S.Prepare() then return false end
 showLabels(false) -- the screen names the chest itself; world labels would clutter it
 local cam=workspace.CurrentCamera
 -- No FOV is saved: Hide always goes back to the regular 70 (2026-10-03, see UITheme.cameraTake).
 saved=T.cameraTake('Chests',S.IsShown)
 eye=cam.CFrame.Position;look=cam.CFrame.Position+cam.CFrame.LookVector*20;fov=cam.FieldOfView
 -- Fly out over the island first, then settle on the chosen chest.
 tEye,tLook,tFov=overview();rate=2.6
 current=id
 if camConn then camConn:Disconnect() end
 camConn=RunService.RenderStepped:Connect(drive)
 setControls(false)
 task.delay(.75,function() if camConn and current==id then S.Select(id) end end)
 return true
end
function S.Select(id,instant)
 current=id
 local e,l,f=shotFor(id,'select');if not e then return end
 tEye,tLook,tFov=e,l,f;rate=3.2
 if instant then eye,look,fov=e,l,f end
end
function S.Focus(id)
 local e,l,f=shotFor(id or current,'focus');if not e then return end
 tEye,tLook,tFov=e,l,f;rate=3.6
end
function S.Shake(amount) shakeAmp=math.max(shakeAmp,amount) end
-- Where the chest mouth is on screen (for UI items flying out of it).
function S.MouthScreen(id)
 local m=chests[id or current];if not m then return nil end
 local cf,size=m:GetBoundingBox()
 local p,on=workspace.CurrentCamera:WorldToViewportPoint(cf.Position+Vector3.new(0,size.Y*.25,0))
 return Vector2.new(p.X,p.Y),on
end
function S.Hide()
 if not camConn then return end
 local back=saved
 saved=nil
 -- Release hands back the regular camera (Custom, your Humanoid, FOV 70) unless another stage holds it.
 local function done() camConn:Disconnect();camConn=nil;T.cameraRelease('Chests');setControls(true);showLabels(true) end
 if back then
  tEye=back.Position;tLook=back.Position+back.LookVector*20;tFov=T.CAMERA_FOV;rate=4.5
  local conn=camConn
  task.delay(.55,function()
   if camConn~=conn then return end
   done()
  end)
 else
  done()
 end
end
function S.IsShown() return camConn~=nil end

-- Opening --------------------------------------------------------------------------------------
-- Stage 1 and 2: shake and charge. Stage 3: burst the lid open. `hint` is the best rarity colour.
function S.Charge(id,stage,hint)
 local m,a=chests[id],auras[id];if not m then return end
 local strength=stage==1 and 1 or 1.7
 FX.shake(m,strength,.5+stage*.08)
 a:SetLevel(stage)
 a:Pulse(stage==1 and .8 or 1.3)
 if stage==2 and hint then a:SetColor(a.Color:Lerp(hint,.45)) end
 S.Shake(.12*stage)
 local taps=id=='Gold' and {FX.Sounds.GoldShake1,FX.Sounds.GoldShake2} or {FX.Sounds.Shake1,FX.Sounds.Shake2}
 FX.play(stage==1 and taps[1] or taps[2],.7,stage==1 and 1 or 1.08)
 if stage==2 then FX.play(FX.Sounds.Charge,.35,1.1) end
end
function S.Burst(id,scale,hint)
 local m,a=chests[id],auras[id];if not m then return end
 a:SetLevel(3)
 if hint then a:SetColor(hint) end
 FX.lid(m,(m:GetAttribute('OpenDeg') or 105)+12,.32,Enum.EasingStyle.Quad)
 task.delay(.32,function() FX.lid(m,m:GetAttribute('OpenDeg') or 105,.5,Enum.EasingStyle.Back) end)
 FX.burst(a,scale,hint)
 S.Shake(.35+.1*math.min(scale,5))
 FX.play(FX.Sounds.Open,.8,1)
 FX.play(FX.Sounds.Burst,.6,1)
end
-- Close the lid and calm the aura back down (CLAIM, or leaving mid-way).
function S.Settle(id)
 local m,a=chests[id],auras[id];if not m then return end
 local def=Chests.ById[id]
 FX.lid(m,0,.45,Enum.EasingStyle.Bounce)
 a:SetColor(def.aura,def.glow);a:SetLevel(0)
 task.delay(.5,function() if FX.lidAngle(m)<1 then FX.reset(m) end end)
end

return S
