-- TrailerCam (TRAILER_CAM.md): smooth camera moves for trailer and ad footage. Developer
-- accounts only (AdminConfig), in Studio and in the published game. F6 turns it on and off.
-- Lives in StarterPlayerScripts with its TrailerCamPath module as a child.
--
-- Modes:
--  FLY    WASD + E/Q, right mouse to look. Everything is smoothed, so a plain keyboard move
--         already glides. Scroll = speed, Z/X = zoom. Your character stands still.
--  PATH   1 adds a key where the camera is, 2 removes the last, 3 clears them. G plays a smooth
--         curve through the keys at an even speed ([ and ] change its length). L loops it.
--  ORBIT  O circles the target nearest the middle of the screen (Tab: next target). Scroll =
--         radius, Shift+scroll = height, [ and ] = speed, R = reverse.
--  FOLLOW F chases the target from behind with a lazy turn. On yourself, you keep playing
--         (WASD moves your character) while the camera trails you.
-- U hides or shows the game's screen UI (hidden by default), B the floating labels and damage
-- numbers, H this panel. The panel and key markers never show while a move plays.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local Input=game:GetService('UserInputService')
local CAS=game:GetService('ContextActionService')
local StarterGui=game:GetService('StarterGui')
local Tags=game:GetService('CollectionService')

local player=Players.LocalPlayer
local Admin=require(RS:WaitForChild('RogueliteCombat'):WaitForChild('AdminConfig'))
if not Admin.isAdmin(player) then return end
local Path=require(script:WaitForChild('TrailerCamPath'))

local cam=workspace.CurrentCamera
workspace:GetPropertyChangedSignal('CurrentCamera'):Connect(function() cam=workspace.CurrentCamera end)

local S={
 on=false,mode='Fly',keys={},duration=8,loop=false,hideUI=true,hideBillboards=false,showPanel=true,
 speed=24,fov=70,targetFov=70,
 -- fly state
 pos=Vector3.zero,vel=Vector3.zero,yaw=0,pitch=0,tYaw=0,tPitch=0,
 -- path playback
 path=nil,t=0,
 -- orbit / follow
 target=nil,angle=0,radius=30,height=12,orbitSpeed=.22,dir=1,centre=nil,
 followYaw=0,followEye=nil,followLook=nil,followDist=22,followHeight=9,
}
local saved -- camera and UI state from before TrailerCam took over
local HOLD=.8 -- seconds the camera rests on the first and last key, for clean edit points

local function shift() return Input:IsKeyDown(Enum.KeyCode.LeftShift) or Input:IsKeyDown(Enum.KeyCode.RightShift) end

---------------------------------------------------------------------------------------------
-- Panel
local gui=Instance.new('ScreenGui');gui.Name='TrailerCamPanel';gui.ResetOnSpawn=false
gui.DisplayOrder=1000;gui.IgnoreGuiInset=true;gui.Enabled=false;gui.Parent=player:WaitForChild('PlayerGui')
local box=Instance.new('TextLabel');box.Name='Info';box.Position=UDim2.fromOffset(16,16);box.Size=UDim2.fromOffset(330,0)
box.AutomaticSize=Enum.AutomaticSize.Y;box.BackgroundColor3=Color3.fromRGB(20,26,38);box.BackgroundTransparency=.2
box.TextColor3=Color3.fromRGB(235,240,250);box.Font=Enum.Font.SourceSansBold;box.TextSize=17;box.RichText=true
box.TextXAlignment=Enum.TextXAlignment.Left;box.TextYAlignment=Enum.TextYAlignment.Top;box.TextWrapped=true;box.Parent=gui
local pad=Instance.new('UIPadding');for _,k in {'PaddingLeft','PaddingRight','PaddingTop','PaddingBottom'} do pad[k]=UDim.new(0,10) end;pad.Parent=box
Instance.new('UICorner',box).CornerRadius=UDim.new(0,8)

local markers=Instance.new('Folder');markers.Name='TrailerCamMarkers'

local function targetName()
 local t=S.target
 if not t or not t.Parent then return 'none' end
 local p=Players:GetPlayerFromCharacter(t)
 return p and p.DisplayName or t.Name
end

local playing -- true while a move is running and the panel must stay out of the shot
local function refresh()
 playing=(S.mode=='Path' and S.path~=nil) or S.mode=='Orbit' or S.mode=='Follow'
 gui.Enabled=S.on and S.showPanel and not playing
 markers.Parent=(S.on and not playing and S.showPanel) and cam or nil
 local lines={
  '<font size="20">TRAILER CAM</font>  <font color="#9fb3d1">F6 off · H hide</font>',
  string.format('Mode <b>%s</b> · speed %d · FOV %d',S.mode:upper(),S.speed,math.floor(S.targetFov+.5)),
  string.format('Keys %d · path %ds%s · <font color="#9fb3d1">1 add, 2 undo, 3 clear, G play, [ ] length, L loop</font>',
   #S.keys,S.duration,S.loop and ' · LOOP' or ''),
  string.format('Target %s · <font color="#9fb3d1">O orbit, F follow, Tab next</font>',targetName()),
  string.format('UI %s · labels %s · <font color="#9fb3d1">U, B</font>',S.hideUI and 'hidden' or 'shown',S.hideBillboards and 'hidden' or 'shown'),
 }
 box.Text=table.concat(lines,'\n')
end

local function drawMarkers()
 markers:ClearAllChildren()
 local function dot(p,size,color)
  local b=Instance.new('Part');b.Anchored=true;b.CanCollide=false;b.CanQuery=false;b.CanTouch=false;b.CastShadow=false
  b.Shape=Enum.PartType.Ball;b.Material=Enum.Material.Neon;b.Color=color;b.Size=Vector3.one*size;b.Position=p;b.Parent=markers
 end
 for i,k in S.keys do dot(k.cf.Position,1.2,i==1 and Color3.fromRGB(120,255,160) or Color3.fromRGB(255,200,90)) end
 local path=Path.build(S.keys)
 if path then for i=0,40 do dot((Path.sample(path,i/40)).Position,.35,Color3.fromRGB(150,200,255)) end end
end

---------------------------------------------------------------------------------------------
-- Hiding the game's UI while filming, and putting back exactly what was there.
local hidden,billboards,watch={},{},nil
local function hideGui(g)
 if g~=gui and g:IsA('ScreenGui') and g.Enabled then hidden[g]=true;g.Enabled=false end
end
local function setUI()
 local pg=player:FindFirstChildOfClass('PlayerGui')
 if S.on and S.hideUI then
  if pg then for _,g in pg:GetChildren() do hideGui(g) end end
  if pg and not watch then
   -- Screens that open mid-shot (level-up cards, toasts) stay hidden too.
   watch=pg.ChildAdded:Connect(function(g) task.defer(function() if S.on and S.hideUI and g.Parent then hideGui(g) end end) end)
  end
  pcall(StarterGui.SetCoreGuiEnabled,StarterGui,Enum.CoreGuiType.All,false)
 else
  if watch then watch:Disconnect();watch=nil end
  for g in hidden do if g.Parent then g.Enabled=true end end
  table.clear(hidden)
  if saved and saved.core then
   for kind,was in saved.core do pcall(StarterGui.SetCoreGuiEnabled,StarterGui,kind,was) end
  end
 end
end
-- Game screens can switch themselves back on mid-shot (the lobby HUD follows a server flag),
-- so while UI is hidden the frame loop sweeps PlayerGui a few times a second.
local sweep=0
local function sweepUI(dt)
 sweep+=dt
 if sweep<.2 or not (S.on and S.hideUI) then return end
 sweep=0
 local pg=player:FindFirstChildOfClass('PlayerGui')
 if pg then for _,g in pg:GetChildren() do hideGui(g) end end
end
local billboardWatch={}
local function hideBillboard(d)
 if d:IsA('BillboardGui') and d.Enabled then billboards[d]=true;d.Enabled=false end
end
local function setBillboards()
 for _,c in billboardWatch do c:Disconnect() end
 table.clear(billboardWatch)
 if S.on and S.hideBillboards then
  for _,d in workspace:GetDescendants() do hideBillboard(d) end
  local pg=player:FindFirstChildOfClass('PlayerGui')
  if pg then for _,d in pg:GetDescendants() do hideBillboard(d) end end
  -- Damage numbers and labels made after this point.
  local function watchIn(root) table.insert(billboardWatch,root.DescendantAdded:Connect(function(d) task.defer(function() if d.Parent then hideBillboard(d) end end) end)) end
  watchIn(workspace);if pg then watchIn(pg) end
 else
  for d in billboards do if d.Parent then d.Enabled=true end end
  table.clear(billboards)
 end
end

---------------------------------------------------------------------------------------------
-- Targets: map bosses first, then players, then regular enemies, nearest the screen middle.
local function rootOf(m)
 if not m or not m.Parent then return nil end
 if m:IsA('Model') then return m.PrimaryPart or m:FindFirstChild('HumanoidRootPart') or m:FindFirstChildWhichIsA('BasePart') end
 return m:IsA('BasePart') and m or nil
end
local function candidates()
 local list,seen={},{}
 local function add(m,rank)
  if seen[m] then return end
  local r=rootOf(m);if not r then return end
  seen[m]=true
  local v=r.Position-cam.CFrame.Position
  local ahead=v.Magnitude>1e-3 and v.Unit:Dot(cam.CFrame.LookVector) or 1
  table.insert(list,{m=m,rank=rank,score=ahead-(v.Magnitude/2000)})
 end
 for _,m in Tags:GetTagged('MapBoss') do add(m,1) end
 for _,p in Players:GetPlayers() do if p.Character then add(p.Character,2) end end
 for _,m in Tags:GetTagged('RogueliteZombie') do add(m,3) end
 table.sort(list,function(a,b) if a.score>.85 and b.score>.85 and a.rank~=b.rank then return a.rank<b.rank end return a.score>b.score end)
 return list
end
local function pickTarget(next)
 local list=candidates()
 if #list==0 then S.target=nil return end
 if next and S.target then
  for i,c in list do if c.m==S.target then S.target=list[i%#list+1].m return end end
 end
 S.target=list[1].m
end

---------------------------------------------------------------------------------------------
-- Modes
local function startFly()
 S.mode='Fly';S.path=nil
 local cf=cam.CFrame
 S.pos=cf.Position;S.vel=Vector3.zero
 local x,y=cf:ToEulerAnglesYXZ()
 S.pitch,S.yaw=x,y;S.tPitch,S.tYaw=x,y
end
local function startPath()
 if #S.keys<2 then return end
 S.path=Path.build(S.keys);S.t=-HOLD;S.mode='Path'
end
local function startOrbit()
 pickTarget(false)
 local r=rootOf(S.target);if not r then return end
 local c=r.Position
 local v=cam.CFrame.Position-c
 S.radius=math.clamp(Vector3.new(v.X,0,v.Z).Magnitude,8,250);S.height=math.clamp(v.Y,2,120)
 S.angle=math.atan2(v.Z,v.X);S.centre=c;S.mode='Orbit'
end
local function startFollow()
 if not S.target then S.target=player.Character end
 local r=rootOf(S.target);if not r then return end
 local _,y=r.CFrame:ToEulerAnglesYXZ()
 S.followYaw=y;S.followEye=cam.CFrame.Position;S.followLook=r.Position;S.mode='Follow'
end

-- Movement keys only belong to the camera in FLY; in the other modes you can still play.
local SINK='TrailerCamSink'
local MOVE={Enum.KeyCode.W,Enum.KeyCode.A,Enum.KeyCode.S,Enum.KeyCode.D,Enum.KeyCode.Q,Enum.KeyCode.E,Enum.KeyCode.Space}
local OWN={Enum.KeyCode.One,Enum.KeyCode.Two,Enum.KeyCode.Three,Enum.KeyCode.G,Enum.KeyCode.L,Enum.KeyCode.O,Enum.KeyCode.F,
 Enum.KeyCode.Tab,Enum.KeyCode.LeftBracket,Enum.KeyCode.RightBracket,Enum.KeyCode.Z,Enum.KeyCode.X,Enum.KeyCode.H,
 Enum.KeyCode.U,Enum.KeyCode.B,Enum.KeyCode.R}
local function bindSink()
 CAS:UnbindAction(SINK)
 if not S.on then return end
 local keys=table.clone(OWN)
 if S.mode=='Fly' then for _,k in MOVE do table.insert(keys,k) end end
 CAS:BindActionAtPriority(SINK,function() return Enum.ContextActionResult.Sink end,false,Enum.ContextActionPriority.High.Value+100,table.unpack(keys))
end

local function setMode(fn)
 fn();bindSink();refresh()
end

---------------------------------------------------------------------------------------------
-- Frame update
local function step(dt)
 dt=math.min(dt,1/20)
 sweepUI(dt)
 S.fov+=(S.targetFov-S.fov)*Path.alpha(6,dt)
 if S.mode=='Fly' then
  local move=Vector3.zero
  if not Input:GetFocusedTextBox() then
   if Input:IsKeyDown(Enum.KeyCode.W) then move+=Vector3.new(0,0,-1) end
   if Input:IsKeyDown(Enum.KeyCode.S) then move+=Vector3.new(0,0,1) end
   if Input:IsKeyDown(Enum.KeyCode.A) then move+=Vector3.new(-1,0,0) end
   if Input:IsKeyDown(Enum.KeyCode.D) then move+=Vector3.new(1,0,0) end
   if Input:IsKeyDown(Enum.KeyCode.E) then move+=Vector3.new(0,1,0) end
   if Input:IsKeyDown(Enum.KeyCode.Q) then move+=Vector3.new(0,-1,0) end
  end
  local rot=CFrame.fromEulerAnglesYXZ(S.pitch,S.yaw,0)
  local want=(move.Magnitude>0 and rot:VectorToWorldSpace(move.Unit) or Vector3.zero)*S.speed*(shift() and 3 or 1)
  S.vel=S.vel:Lerp(want,Path.alpha(3.5,dt))
  S.pos+=S.vel*dt
  S.yaw+=(S.tYaw-S.yaw)*Path.alpha(9,dt);S.pitch+=(S.tPitch-S.pitch)*Path.alpha(9,dt)
  cam.CFrame=CFrame.new(S.pos)*CFrame.fromEulerAnglesYXZ(S.pitch,S.yaw,0)
  cam.FieldOfView=S.fov
 elseif S.mode=='Path' and S.path then
  S.t+=dt
  local u=math.clamp(S.t/S.duration,0,1)
  local cf,fov=Path.sample(S.path,Path.ease(u,1))
  cam.CFrame=cf;cam.FieldOfView=fov
  if S.t>=S.duration+HOLD then
   if S.loop then S.t=-HOLD else
    -- Stay on the last key in FLY, so the next move starts from here.
    S.targetFov=fov;S.fov=fov;setMode(startFly)
   end
  end
 elseif S.mode=='Orbit' then
  local r=rootOf(S.target)
  if r then S.centre=S.centre:Lerp(r.Position,Path.alpha(2.5,dt)) end
  S.angle+=S.orbitSpeed*S.dir*dt
  cam.CFrame=Path.orbit(S.centre+Vector3.new(0,2,0),S.radius,S.height,S.angle)
  cam.FieldOfView=S.fov
 elseif S.mode=='Follow' then
  local r=rootOf(S.target)
  if r then
   local _,y=r.CFrame:ToEulerAnglesYXZ()
   -- Turn the long way never: wrap the gap to -pi..pi, then ease toward it slowly.
   local gap=(y-S.followYaw+math.pi)%(2*math.pi)-math.pi
   S.followYaw+=gap*Path.alpha(1.2,dt)
   local back=CFrame.fromEulerAnglesYXZ(0,S.followYaw,0):VectorToWorldSpace(Vector3.new(0,0,S.followDist))
   local eye=r.Position+back+Vector3.new(0,S.followHeight,0)
   S.followEye=S.followEye:Lerp(eye,Path.alpha(3,dt))
   S.followLook=S.followLook:Lerp(r.Position+Vector3.new(0,2,0),Path.alpha(5,dt))
  end
  cam.CFrame=CFrame.lookAt(S.followEye,S.followLook)
  cam.FieldOfView=S.fov
 end
end

---------------------------------------------------------------------------------------------
-- On / off
local function turnOn()
 S.on=true
 saved={type=cam.CameraType,cf=cam.CFrame,fov=cam.FieldOfView,subject=cam.CameraSubject,core={}}
 for _,kind in Enum.CoreGuiType:GetEnumItems() do
  if kind~=Enum.CoreGuiType.All then local ok,v=pcall(StarterGui.GetCoreGuiEnabled,StarterGui,kind);if ok then saved.core[kind]=v end end
 end
 S.fov=cam.FieldOfView;S.targetFov=S.fov
 cam.CameraType=Enum.CameraType.Scriptable
 startFly();bindSink();setUI();setBillboards();drawMarkers();refresh()
 -- Above the default camera, so the game's own camera scripts can't fight it.
 RunService:BindToRenderStep('TrailerCam',Enum.RenderPriority.Camera.Value+5,step)
end
local function turnOff()
 S.on=false
 RunService:UnbindFromRenderStep('TrailerCam')
 CAS:UnbindAction(SINK)
 Input.MouseBehavior=Enum.MouseBehavior.Default
 setUI();setBillboards();refresh()
 if saved then
  cam.CameraType=saved.type==Enum.CameraType.Scriptable and Enum.CameraType.Custom or saved.type
  cam.FieldOfView=saved.fov
  if saved.subject and saved.subject.Parent then cam.CameraSubject=saved.subject end
 end
 saved=nil
end

---------------------------------------------------------------------------------------------
-- Input
local looking=false
Input.InputBegan:Connect(function(io,processed)
 if io.KeyCode==Enum.KeyCode.F6 and not Input:GetFocusedTextBox() then
  if S.on then turnOff() else turnOn() end
  return
 end
 if not S.on or Input:GetFocusedTextBox() then return end
 local k=io.KeyCode
 if io.UserInputType==Enum.UserInputType.MouseButton2 and S.mode=='Fly' then
  looking=true;Input.MouseBehavior=Enum.MouseBehavior.LockCurrentPosition
 elseif k==Enum.KeyCode.One then
  table.insert(S.keys,{cf=cam.CFrame,fov=S.targetFov});drawMarkers()
 elseif k==Enum.KeyCode.Two then
  table.remove(S.keys);drawMarkers()
 elseif k==Enum.KeyCode.Three then
  table.clear(S.keys);drawMarkers()
 elseif k==Enum.KeyCode.G then
  setMode(S.mode=='Path' and startFly or startPath)
 elseif k==Enum.KeyCode.L then
  S.loop=not S.loop
 elseif k==Enum.KeyCode.LeftBracket or k==Enum.KeyCode.RightBracket then
  local d=k==Enum.KeyCode.RightBracket and 1 or -1
  if S.mode=='Orbit' then S.orbitSpeed=math.clamp(S.orbitSpeed*(d>0 and 1.25 or .8),.03,2)
  else S.duration=math.clamp(S.duration+d,2,60) end
 elseif k==Enum.KeyCode.O then
  setMode(S.mode=='Orbit' and startFly or startOrbit)
 elseif k==Enum.KeyCode.F then
  setMode(S.mode=='Follow' and startFly or startFollow)
 elseif k==Enum.KeyCode.Tab then
  pickTarget(true)
  if S.mode=='Orbit' then local r=rootOf(S.target);if r then S.centre=S.centre or r.Position end end
 elseif k==Enum.KeyCode.R then
  S.dir=-S.dir
 elseif k==Enum.KeyCode.H then
  S.showPanel=not S.showPanel
 elseif k==Enum.KeyCode.U then
  S.hideUI=not S.hideUI;setUI()
 elseif k==Enum.KeyCode.B then
  S.hideBillboards=not S.hideBillboards;setBillboards()
 end
 refresh()
end)
Input.InputEnded:Connect(function(io)
 if io.UserInputType==Enum.UserInputType.MouseButton2 and looking then
  looking=false;Input.MouseBehavior=Enum.MouseBehavior.Default
 end
end)
Input.InputChanged:Connect(function(io)
 if not S.on then return end
 if io.UserInputType==Enum.UserInputType.MouseMovement and looking then
  local d=io.Delta
  S.tYaw-=d.X*.0032;S.tPitch=math.clamp(S.tPitch-d.Y*.0032,-1.45,1.45)
 elseif io.UserInputType==Enum.UserInputType.MouseWheel then
  local z=io.Position.Z
  if S.mode=='Orbit' then
   if shift() then S.height=math.clamp(S.height+z*2,-10,150) else S.radius=math.clamp(S.radius*(z>0 and .9 or 1.1),6,300) end
  elseif S.mode=='Follow' then
   S.followDist=math.clamp(S.followDist*(z>0 and .9 or 1.1),6,120);S.followHeight=S.followDist*.4
  else
   S.speed=math.clamp(math.floor(S.speed*(z>0 and 1.25 or .8)+.5),2,400)
  end
  refresh()
 end
end)
-- Z/X zoom while held (smoothed through S.fov).
RunService.RenderStepped:Connect(function(dt)
 if not S.on or Input:GetFocusedTextBox() then return end
 local z=(Input:IsKeyDown(Enum.KeyCode.X) and 1 or 0)-(Input:IsKeyDown(Enum.KeyCode.Z) and 1 or 0)
 if z~=0 then S.targetFov=math.clamp(S.targetFov+z*25*dt,10,100);refresh() end
end)

player.CharacterAdded:Connect(function()
 -- A respawn resets the camera subject; keep filming from where we are.
 if S.on then task.defer(function() cam.CameraType=Enum.CameraType.Scriptable end) end
end)
