-- Handyman turret, client (HANDYMAN_TURRET.md, 2026-10-03). StarterPlayerScripts.HandymanTurret, a
-- LocalScript (unsandboxed, like PetVisuals). Presentation and requests only; the server
-- (HandymanTurretService) decides where a turret stands, what it shoots and whether BUILD works.
--  * Every Folder in workspace.RogueliteTurrets gets a local copy of its tier's model
--    (RogueliteCombat.HandymanTurrets.T1-T4) on its Position and Yaw. Anchored, no collision.
--  * The head turns toward the replicated Aim (a slow look around when it is idle) and snaps to each
--    nail it fires: the first 'Fly' row of each of its projectiles (id 'Turret') on the Shot remote.
--    The barrel kicks back, a flat Neon flash shows at the muzzle, and Tier IV's barrel cluster spins
--    up while it fires. Turrets past 250 studs from the camera aren't posed.
--  * A build or move (BuiltAt) drops it in with a flat lime ground ring and dust; a tier up swaps the
--    model with the same ring.
--  * BUILD for a Handyman in a wave: B, gamepad R1, or the on-screen button (bottom right, left of
--    the melee DASH; on touch screens just above the jump button). It shows the turret, the key and
--    the 8 s cooldown (ReadyAt).
-- Nothing shows until the turret models are installed.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local RS=game:GetService('ReplicatedStorage')
local Input=game:GetService('UserInputService')
local TweenService=game:GetService('TweenService')
local combat=RS:WaitForChild('RogueliteCombat')
local H=require(combat:WaitForChild('HandymanTurret'))
local K=require(combat:WaitForChild('VfxKit'))
local Wire=require(combat:WaitForChild('ShotBatch'))
local T=require(RS:WaitForChild('UITheme'))
local player=Players.LocalPlayer
local DRAW_RANGE=250
local LIME=T.Color.lime
local FLASH=Color3.fromRGB(255,236,150)
local TURN=10 -- radians a second the head turns toward its aim

local holder=Instance.new('Folder');holder.Name='RogueliteTurretsLocal';holder.Parent=workspace
local shown={} -- server Folder -> v
local byOwner={} -- owner UserId -> v

local function template(tier) local f=H.templates(combat);return f and f:FindFirstChild('T'..tier) end
local function clear(v) if v.model then v.model:Destroy();v.model=nil end end
-- A local copy of the tier's model, and where its moving parts sit: the head pivot in the base's
-- space, the head part from its pivot, the barrel pivot (its spin axis) from the head pivot, the
-- barrel part from that, and the optional Glow from whichever it follows.
local function make(v)
 clear(v)
 local src=template(v.tier);if not src then return end
 local m=src:Clone()
 for _,d in m:GetDescendants() do if d:IsA('BasePart') then d.Anchored=true;d.CanCollide=false;d.CanTouch=false;d.CanQuery=false end end
 local pivot=m:GetPivot()
 local head,barrel,glow=m:FindFirstChild('Head'),m:FindFirstChild('Barrel'),m:FindFirstChild('Glow')
 local hp,bp=head:GetPivot(),barrel:GetPivot()
 local rel=pivot:ToObjectSpace(hp)
 v.headRel,v.headRot=rel.Position,rel.Rotation
 v.headPart=hp:ToObjectSpace(head.CFrame)
 v.barrelRel=hp:ToObjectSpace(bp)
 v.barrelPart=bp:ToObjectSpace(barrel.CFrame)
 v.glow=glow and glow:IsA('BasePart') and glow or nil
 if v.glow then
  v.glowFollows=v.glow:GetAttribute('Follows')=='Head' and 'Head' or 'Barrel'
  v.glowRel=(v.glowFollows=='Head' and hp or bp):ToObjectSpace(v.glow.CFrame)
 end
 v.muzzles={}
 for i=1,12 do local a=barrel:FindFirstChild('Muzzle'..i);if not (a and a:IsA('Attachment')) then break end;table.insert(v.muzzles,a) end
 v.spins=m:GetAttribute('Spin')==true
 -- Tier IV's barrels spin: it flashes from their centre (MuzzleCentre, in the Barrel's frame).
 local centre=barrel:GetAttribute('MuzzleCentre')
 v.muzzleCentre=v.spins and typeof(centre)=='Vector3' and centre or nil
 v.model,v.head,v.barrel=m,head,barrel
 if v.base then m:PivotTo(v.base) end
 m.Parent=holder
end
local function pose(v,now,lift)
 local base=v.base
 if lift>0 then base=base+Vector3.yAxis*lift;v.model:PivotTo(base);v.lifted=true
 elseif v.lifted then v.model:PivotTo(base);v.lifted=false end
 local headCF=base*CFrame.new(v.headRel)*CFrame.Angles(0,v.yaw-v.baseYaw,0)*v.headRot
 v.head.CFrame=headCF*v.headPart
 local age=now-(v.kick or -1)
 local kick=age<.12 and (v.spins and .08 or .22)*(1-age/.12)^2 or 0
 -- The barrel pitches on its trunnion, recoils along +Z and (Tier IV) spins about its Z.
 local barrelCF=headCF*v.barrelRel*CFrame.Angles(v.pitch,0,0)*CFrame.new(0,0,kick)*CFrame.Angles(0,0,v.spin)
 v.barrel.CFrame=barrelCF*v.barrelPart
 v.barrelCF=barrelCF
 if v.glow then v.glow.CFrame=(v.glowFollows=='Head' and headCF or barrelCF)*v.glowRel end
end
-- Build pop: a flat lime ring on the ground and a puff of dust bits.
local function ring(position)
 if not K.near(position,160) then return end
 K.ring(holder,CFrame.new(position+Vector3.yAxis*.08),{radius0=.6,radius1=3.4,width=.5,color=LIME,duration=.45,segments=18,bodyAlpha=.3})
 K.shards(holder,position+Vector3.yAxis*.3,K.Dust,8,8,.45,.16,Enum.Material.SmoothPlastic,.7)
end
-- Muzzle flash: three short Neon slivers from the muzzle that fired, gone in 0.07 s.
local function flash(v)
 if (#v.muzzles==0 and not v.muzzleCentre) or not v.barrelCF or not K.near(v.base.Position,160) then return end
 local at=v.muzzleCentre and v.barrelCF:PointToWorldSpace(v.muzzleCentre) or v.muzzles[(v.shots-1)%#v.muzzles+1].WorldPosition
 local frame=CFrame.lookAt(at,at+v.barrelCF.LookVector)
 local roll=math.random()*math.pi*2
 local parts={}
 for i=1,3 do parts[i]=K.part(holder,'TurretFlash',Vector3.new(.08,.08,.5),FLASH,0,Enum.Material.Neon) end
 K.animate(.07,function(t)
  for i,p in parts do
   local length=(i==1 and .6 or .4)*(1-t*.5)
   p.Size=Vector3.new(.08*(1-t*.6),.08*(1-t*.6),length)
   p.CFrame=frame*CFrame.Angles(0,0,roll+i*2.09)*CFrame.Angles(i==1 and 0 or math.rad(30),0,0)*CFrame.new(0,0,-length/2)
   p.Transparency=t
  end
 end,function() for _,p in parts do p:Destroy() end end,'turretFlash',24)
end

local function attach(f)
 if shown[f] or not f:IsA('Folder') then return end
 local v={folder=f,owner=f:GetAttribute('OwnerUserId') or tonumber(f.Name),tier=H.tier(f:GetAttribute('Tier')),spin=0,spinVel=0,shots=0,yaw=0,baseYaw=0,pitch=0}
 shown[f]=v
 if v.owner then byOwner[v.owner]=v end
 local function place(pop)
  local position=f:GetAttribute('Position');if typeof(position)~='Vector3' then return end
  v.baseYaw=f:GetAttribute('Yaw') or 0;v.yaw=v.baseYaw
  v.base=CFrame.new(position)*CFrame.Angles(0,v.baseYaw,0)
  if not v.model then make(v) elseif not v.lifted then v.model:PivotTo(v.base) end
  if pop then v.popAt=os.clock();ring(position) end
 end
 f:GetAttributeChangedSignal('BuiltAt'):Connect(function() place(true) end)
 f:GetAttributeChangedSignal('Tier'):Connect(function()
  local tier=H.tier(f:GetAttribute('Tier'));if tier==v.tier then return end
  v.tier=tier;make(v)
  if v.base then v.popAt=os.clock();ring(v.base.Position) end
 end)
 -- A new turret arrives with BuiltAt already set: drop it in if it was just built.
 local built=f:GetAttribute('BuiltAt')
 place(type(built)=='number' and workspace:GetServerTimeNow()-built<1)
end
local function detach(f)
 local v=shown[f];if not v then return end
 shown[f]=nil
 if v.owner and byOwner[v.owner]==v then byOwner[v.owner]=nil end
 clear(v)
end
local function hook(folder)
 for _,f in folder:GetChildren() do attach(f) end
 folder.ChildAdded:Connect(attach)
 folder.ChildRemoved:Connect(detach)
end
local existing=workspace:FindFirstChild('RogueliteTurrets')
if existing then hook(existing) end
workspace.ChildAdded:Connect(function(c) if c.Name=='RogueliteTurrets' and c:IsA('Folder') then hook(c) end end)

-- Each turret nail: the first Fly row of each projectile key. Snap the head to it, kick, flash.
local seen,prunedAt={},os.clock()
local function row(origin,finish,kind,id,_,_,_,_,ownerId,_,_,_,_,key)
 if kind~='Fly' or id~=H.Id or key==nil or seen[key] then return end
 seen[key]=os.clock()
 local v=byOwner[ownerId];if not v or not v.base then return end
 if typeof(origin)=='Vector3' and typeof(finish)=='Vector3' then
  local d=finish-origin
  local flat=Vector3.new(d.X,0,d.Z).Magnitude
  if flat>.05 then v.shotYaw=H.yaw(d);v.yaw=v.shotYaw;v.shotPitch=math.clamp(math.atan2(d.Y,flat),-.45,.45);v.pitch=v.shotPitch end
 end
 v.kick=os.clock();v.shots+=1;v.flash=true
end
combat:WaitForChild('Shot').OnClientEvent:Connect(function(a,b,...)
 if a==Wire.Marker then for _,r in ipairs(b) do row(Wire.unpack(r)) end else row(a,b,...) end
 local now=os.clock()
 if now-prunedAt>2 then prunedAt=now;for k,t in seen do if now-t>2 then seen[k]=nil end end end
end)

RunService.RenderStepped:Connect(function(dt)
 local now=os.clock()
 -- A paused run (RunPaused) freezes the turrets as they are: no turning, spin or idle look-around.
 if combat:GetAttribute('RunPaused')==true then return end
 local camera=workspace.CurrentCamera;local eye=camera and camera.CFrame.Position
 for f,v in shown do
  if not v.model or not v.base then continue end
  if eye and (eye-v.base.Position).Magnitude>DRAW_RANGE then continue end
  -- Head: hold a fired nail's heading a moment, else follow Aim; idle, a slow look around.
  -- The barrel pitches toward its target (up to 26 degrees), level when idle.
  local target,pitch=nil,0
  if v.shotYaw and now-(v.kick or -1)<.15 then target,pitch=v.shotYaw,v.shotPitch or 0
  else
   local aim=f:GetAttribute('Aim')
   if typeof(aim)=='Vector3' then
    local d=aim-v.base:PointToWorldSpace(v.headRel)
    local flat=Vector3.new(d.X,0,d.Z).Magnitude
    if flat>.05 then target=H.yaw(d);pitch=math.clamp(math.atan2(d.Y-1,flat),-.45,.45) end
   end
   target=target or v.baseYaw+math.sin(now*.7)*.45
  end
  local diff=(target-v.yaw+math.pi)%(2*math.pi)-math.pi
  v.yaw+=math.clamp(diff,-TURN*dt,TURN*dt)
  v.pitch+=math.clamp(pitch-v.pitch,-3*dt,3*dt)
  -- Tier IV: the barrel cluster spins up while it fires and winds down after.
  if v.spins then
   local want=now-(v.kick or -1)<.4 and 22 or 0
   v.spinVel+=(want-v.spinVel)*math.min(1,dt*4)
   v.spin=(v.spin+v.spinVel*dt)%(math.pi*2)
  end
  local lift=0
  if v.popAt then local t=(now-v.popAt)/.24;if t<1 then lift=2.4*(1-t)^2 else v.popAt=nil end end
  pose(v,now,lift)
  if v.flash then v.flash=false;flash(v) end
 end
end)

-- BUILD -------------------------------------------------------------------------------------------
local gui=Instance.new('ScreenGui');gui.Name='HandymanTurretHUD';gui.ResetOnSpawn=false;gui.DisplayOrder=6
gui.ZIndexBehavior=Enum.ZIndexBehavior.Sibling;gui.Parent=player:WaitForChild('PlayerGui')
local root=T.make('Frame',gui,{Name='Root',BackgroundTransparency=1,Size=UDim2.fromScale(1,1)})
local SIZE=96
local slot=T.frame(root,'BuildSlot',0,0,SIZE,SIZE);slot.Visible=false
local layoutScale=T.make('UIScale',slot,{Scale=1})
local request -- below
local button=T.button(slot,'BuildButton','',0,0,SIZE,SIZE,function() request() end)
button.Selectable=false -- gamepads use R1; menus' selection never lands here mid-wave
local bounce=T.make('UIScale',button,{Scale=1})
button.Caption.Text='BUILD';button.Caption.Size=UDim2.new(1,-10,0,24);button.Caption.Position=UDim2.new(0,5,1,-28);button.Caption.TextSize=20
local image=T.make('ImageLabel',button,{Name='IconImage',BackgroundTransparency=1,Position=UDim2.fromOffset(16,8),Size=UDim2.fromOffset(64,60),ScaleType=Enum.ScaleType.Fit,Visible=false})
local view=T.make('ViewportFrame',button,{Name='IconView',BackgroundTransparency=1,Position=UDim2.fromOffset(16,8),Size=UDim2.fromOffset(64,60),Ambient=Color3.fromRGB(190,190,190),LightColor=Color3.new(1,1,1),LightDirection=Vector3.new(-1,-2,-1),Visible=false})
local camera=T.make('Camera',view,{FieldOfView=30});view.CurrentCamera=camera
local shade=T.make('Frame',button,{Name='Cooldown',BackgroundColor3=Color3.new(0,0,0),BackgroundTransparency=.4,BorderSizePixel=0,AnchorPoint=Vector2.new(0,1),Position=UDim2.new(0,6,1,-6),Size=UDim2.new(1,-12,0,0),ZIndex=3})
T.make('UICorner',shade,{CornerRadius=UDim.new(0,10)})
local seconds=T.label(button,'Seconds','',0,0,SIZE,SIZE,34);seconds.Size=UDim2.fromScale(1,1);seconds.ZIndex=4
local hint=T.chip(slot,'KeyHint','B',-8,-8,T.Color.well,LIME);hint.ZIndex=5
for _,d in hint:GetDescendants() do if d:IsA('GuiObject') then d.ZIndex=5 end end
local pad=T.make('ImageLabel',hint,{Name='PadIcon',BackgroundTransparency=1,Size=UDim2.fromScale(1,1),ScaleType=Enum.ScaleType.Fit,Visible=false,ZIndex=6})

local iconTier
local function setIcon(tier)
 if tier==iconTier then return end
 local src=template(tier);if not src then return end
 iconTier=tier
 for _,c in view:GetChildren() do if c:IsA('Model') then c:Destroy() end end
 -- The uploaded icon (HandymanTurret.Icons, else the template's Icon attribute), else a live view.
 local icon=H.Icons[tier]
 if type(icon)~='string' or icon=='' then icon=src:GetAttribute('Icon') end
 if type(icon)=='string' and icon~='' then image.Image=icon;image.Visible=true;view.Visible=false;return end
 local m=src:Clone();m:PivotTo(CFrame.new());m.Parent=view
 local cf,size=m:GetBoundingBox()
 local distance=size.Magnitude*.5/math.tan(math.rad(15))*1.05
 camera.CFrame=CFrame.lookAt(cf.Position+Vector3.new(.9,.6,-1.3).Unit*distance,cf.Position)
 view.Visible=true;image.Visible=false
end
local function own() local f=workspace:FindFirstChild('RogueliteTurrets');return f and f:FindFirstChild(tostring(player.UserId)) end
-- A Handyman (or anyone with an ADMIN turret) alive in the run during a wave or the sandbox.
local function eligible()
 local run=RS:FindFirstChild('RogueliteRunState');local phase=run and run:GetAttribute('Phase')
 if phase~='Combat' and phase~='Practice' then return false end
 if not H.templates(combat) then return false end
 if player:GetAttribute('RunMember')~=true or player:GetAttribute('LobbyPreviewActive')==true then return false end
 local h=player.Character and player.Character:FindFirstChildOfClass('Humanoid')
 if not h or h.Health<=0 or player:GetAttribute('RunDown')~=nil then return false end
 local states=combat:FindFirstChild('PlayerStates');local state=states and states:FindFirstChild(tostring(player.UserId))
 return (state~=nil and state:GetAttribute('Class')==H.Class) or own()~=nil
end
local function remaining()
 local f=own();local readyAt=f and f:GetAttribute('ReadyAt')
 return type(readyAt)=='number' and math.max(0,readyAt-workspace:GetServerTimeNow()) or 0
end
local function pop(scale)
 bounce.Scale=scale
 TweenService:Create(bounce,TweenInfo.new(.25,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=1}):Play()
end
local lastPress=0
request=function()
 if not slot.Visible then return end
 local now=os.clock();if now-lastPress<.2 then return end;lastPress=now
 if remaining()>.1 then
  -- Still cooling down: a small shake, nothing sent.
  button.Position=UDim2.fromOffset(5,0)
  TweenService:Create(button,TweenInfo.new(.18,Enum.EasingStyle.Elastic,Enum.EasingDirection.Out),{Position=UDim2.fromOffset(0,0)}):Play()
  return
 end
 local remote=combat:FindFirstChild('RunAction')
 if remote then remote:FireServer('BuildTurret');pop(.86) end
end
Input.InputBegan:Connect(function(input,processed)
 if processed or Input:GetFocusedTextBox() then return end
 if input.KeyCode==H.Keys.Keyboard or input.KeyCode==H.Keys.Gamepad then request() end
end)

-- Layout: the HUD's scale (RogueliteUI: 1 on desktops, .55 on a phone, times the HUD size
-- setting). Keyboard and gamepad: the bottom-right corner. Touch: just above the jump button (the
-- melee DASH sits left of it). Then clear of the HUD's menu column and boss bar and of the DASH
-- button (RogueliteCombat.client): left of what sits on the right edge, above anything else.
-- Examples: on a 1920x1080 screen with DASH it sits left of DASH; an 844x390 phone gets scale .63,
-- a 60 px button 12 px above the jump button.
local function touchMode()
 local ok,yes=pcall(function() return Input.PreferredInput==Enum.PreferredInput.Touch end)
 if ok then return yes end
 return Input.TouchEnabled and (not Input.KeyboardEnabled or Input:GetLastInputType()==Enum.UserInputType.Touch)
end
local function rectOf(o) local p=o.AbsolutePosition-root.AbsolutePosition;return {p.X,p.Y,p.X+o.AbsoluteSize.X,p.Y+o.AbsoluteSize.Y} end
local function layout()
 local size=root.AbsoluteSize;local w,h=size.X,size.Y
 if w<2 or h<2 then return end
 local hud=T.setting('HudScale');if type(hud)~='number' then hud=1 end
 local s=math.clamp(math.min(w/1100,h/620),.55,1)*hud
 layoutScale.Scale=s
 local half=SIZE*s/2
 local touch=touchMode()
 local c
 if touch then
  local small=math.min(w,h)<=500
  local jump=small and {w-95,h-90,w-25,h-20} or {w-170,h-210,w-50,h-90}
  local touchGui=player.PlayerGui:FindFirstChild('TouchGui')
  local frame=touchGui and touchGui:FindFirstChild('TouchControlFrame')
  local jb=frame and frame:FindFirstChild('JumpButton')
  if jb and jb:IsA('GuiObject') and jb.Visible and jb.AbsoluteSize.X>0 then jump=rectOf(jb) end
  c=Vector2.new((jump[1]+jump[3])/2,jump[2]-12-half)
 else
  c=Vector2.new(w-24-half,h-24-half)
 end
 local list={}
 local hudGui=player.PlayerGui:FindFirstChild('RogueliteHUD');local area=hudGui and hudGui:FindFirstChild('SafeArea');area=area and area:FindFirstChild('HUD')
 for _,name in {'Menu','BossHealth'} do
  local o=area and area:FindFirstChild(name)
  if o and o:IsA('GuiObject') and o.Visible and o.AbsoluteSize.X>0 then table.insert(list,rectOf(o)) end
 end
 local dashGui=player.PlayerGui:FindFirstChild('RogueliteDash')
 local dash=dashGui and dashGui:IsA('ScreenGui') and dashGui.Enabled and dashGui:FindFirstChild('DashButton',true)
 if dash and dash:IsA('GuiObject') and dash.AbsoluteSize.X>0 then table.insert(list,rectOf(dash)) end
 local gap=half+8
 for _=1,4 do
  local hit
  for _,r in list do if c.X+gap>r[1] and c.X-gap<r[3] and c.Y+gap>r[2] and c.Y-gap<r[4] then hit=r;break end end
  if not hit then break end
  c=hit[3]>=w-40 and Vector2.new(hit[1]-gap,c.Y) or Vector2.new(c.X,hit[2]-gap)
 end
 slot.AnchorPoint=Vector2.new(.5,.5);slot.Position=UDim2.fromOffset(c.X,c.Y)
 -- The key on the hint chip: B, the gamepad's R1 glyph, or nothing on touch.
 local gamepad=Input:GetLastInputType().Name:find('^Gamepad')~=nil
 hint.Visible=not touch
 local text=hint:FindFirstChild('Text')
 if gamepad then
  local ok,glyph=pcall(Input.GetImageForKeyCode,Input,H.Keys.Gamepad)
  pad.Image=ok and glyph or '';pad.Visible=pad.Image~=''
  if text then text.Text=pad.Visible and '' or 'R1' end
 else
  pad.Visible=false
  if text then local ok,key=pcall(Input.GetStringForKeyCode,Input,H.Keys.Keyboard);text.Text=ok and key~='' and key or 'B' end
 end
end
root:GetPropertyChangedSignal('AbsoluteSize'):Connect(layout)
Input.LastInputTypeChanged:Connect(layout)
player:GetAttributeChangedSignal('Setting_HudScale'):Connect(layout)

local wasReady=true
local tick,layoutAt=0,0
RunService.Heartbeat:Connect(function(dt)
 tick+=dt;if tick<.1 then return end;tick=0
 local on=eligible()
 if on~=slot.Visible then slot.Visible=on;if on then layout();pop(.7) end end
 -- Turrets whose model wasn't there to clone yet (installed while running in Studio).
 for _,v in shown do if not v.model and v.base and template(v.tier) then make(v) end end
 if not on then return end
 local now=os.clock()
 if now-layoutAt>1 then layoutAt=now;layout() end -- the touch jump button arrives late
 local mine=own()
 setIcon(H.tier(mine and mine:GetAttribute('Tier') or 1))
 local left=remaining()
 shade.Size=UDim2.new(1,-12,math.clamp(left/H.BUILD_COOLDOWN,0,1),-12*math.clamp(left/H.BUILD_COOLDOWN,0,1))
 seconds.Text=left>0 and tostring(math.ceil(left)) or ''
 local readyNow=left<=0
 if readyNow and not wasReady then pop(1.15) end
 wasReady=readyNow
end)
