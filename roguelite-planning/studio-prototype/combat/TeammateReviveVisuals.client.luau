-- Teammate revive spots (combat/TeammateRevive.luau) on this screen: a glowing ring on the floor where
-- a run member fell, their name over it, the hold filling the ring, and the revive prompt in the
-- green theme (a custom ProximityPrompt style: E, a held tap on phones, Y on a controller). The fill
-- reads the spot's Progress, ProgressAt (server time) and ProgressRate (it fills faster with more
-- revivers and drains slowly when nobody holds), so every screen shows the same progress, the downed
-- player's death screen included. The prompt shows only to living run members who aren't down: never
-- to the downed player, people outside the run, or anyone while the run is paused. Each reviver whose
-- hold counts (ReviveGuard) wears a lime bubble: they take 40% damage and enemy shots stop at it.
-- Presentation only: the server times each hold itself, guards the revivers and decides the revive.
-- Unsandboxed LocalScript in StarterPlayerScripts, like PetVisuals.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local UserInputService=game:GetService('UserInputService')
local PromptService=game:GetService('ProximityPromptService')
local TweenService=game:GetService('TweenService')
local RS=game:GetService('ReplicatedStorage')
local T=require(RS:WaitForChild('UITheme'))
local C=T.Color
local combat=RS:WaitForChild('RogueliteCombat')
local player=Players.LocalPlayer
local gui=player:WaitForChild('PlayerGui')
local FOLDER='RogueliteReviveSpots'
local SEGMENTS=32 -- ring pieces lighting up one by one: 32 in 2.5 s is one every 0.08 s
local SLICE=Rect.new(48,48,208,208) -- UITheme's nine-slice centre
local views={} -- spot model -> {ring,stroke,segments,plus,tag,down,prompt,shown,pressing,progress,reviver}
local bubbles={} -- guarded reviver (Player) -> their bubble Part (local to this screen)

-- May this player revive anyone right now? The server checks again; this only hides the prompt.
local function canHelp()
 if not player:GetAttribute('RunMember') or player:GetAttribute('RunDown') or combat:GetAttribute('RunPaused')==true then return false end
 local h=player.Character and player.Character:FindFirstChildOfClass('Humanoid')
 return h~=nil and h.Health>0
end
-- The ring on the top face of the spot's Pad (8x8 studs, 400x400 here): a dark disc so it reads on any floor, a
-- lime rim that pulses until someone holds, SEGMENTS pieces that light up with the hold, and a plus.
-- Unlit (LightInfluence 0), so it glows the same by day and night.
local function ring(pad)
 local g=T.make('SurfaceGui',gui,{Name='ReviveRing',Adornee=pad,Face=Enum.NormalId.Top,SizingMode=Enum.SurfaceGuiSizingMode.PixelsPerStud,PixelsPerStud=50,LightInfluence=0,Brightness=1.5,ResetOnSpawn=false,ZIndexBehavior=Enum.ZIndexBehavior.Sibling})
 local function circle(name,size,color,transparency)
  local f=T.make('Frame',g,{Name=name,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromScale(size,size),BackgroundColor3=color,BackgroundTransparency=transparency,BorderSizePixel=0})
  T.make('UICorner',f,{CornerRadius=UDim.new(1,0)})
  return f
 end
 circle('Disc',.86,C.shade,.45)
 local stroke=T.make('UIStroke',circle('Rim',.94,C.lime,1),{Color=C.lime,Thickness=10,Transparency=.2})
 local segments={}
 for i=1,SEGMENTS do
  local a=(i-.5)/SEGMENTS*2*math.pi-math.pi/2 -- clockwise from the top
  local s=T.make('Frame',g,{Name='Segment'..i,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5+math.cos(a)*.36,.5+math.sin(a)*.36),Size=UDim2.fromScale(.055,.03),Rotation=math.deg(a)+90,BackgroundColor3=C.white,BackgroundTransparency=.7,BorderSizePixel=0})
  T.make('UICorner',s,{CornerRadius=UDim.new(.5,0)})
  segments[i]=s
 end
 local plus={}
 for i,size in {Vector2.new(.2,.06),Vector2.new(.06,.2)} do
  local f=T.make('Frame',g,{Name='Plus'..i,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromScale(size.X,size.Y),BackgroundColor3=C.white,BackgroundTransparency=.1,BorderSizePixel=0})
  T.make('UICorner',f,{CornerRadius=UDim.new(0,6)})
  plus[i]=f
 end
 return g,stroke,segments,plus
end
-- Over the spot, seen through walls so teammates can find them: the name, DOWN or who is reviving,
-- the hold bar, and the prompt row once this player is close enough to revive. Phones draw it
-- smaller (70% at 560 px tall and below).
local function tag(spot,pad)
 local b=T.make('BillboardGui',gui,{Name='ReviveTag',Adornee=pad,Size=UDim2.fromOffset(260,130),StudsOffset=Vector3.new(0,5.5,0),AlwaysOnTop=true,MaxDistance=300,LightInfluence=0,ResetOnSpawn=false,Active=true,ZIndexBehavior=Enum.ZIndexBehavior.Sibling})
 local body=T.frame(b,'Body',0,0,260,130);body.AnchorPoint=Vector2.new(.5,.5);body.Position=UDim2.fromScale(.5,.5)
 local scale=T.make('UIScale',body,{Scale=1})
 T.label(body,'Name',spot:GetAttribute('DownName') or '',0,0,260,34,28,C.white)
 local status=T.label(body,'Status','DOWN',0,32,260,22,18,C.negative)
 local fill,track=T.bar(body,'Progress',50,60,160,12,C.lime);track.Visible=false
 local row=T.make('ImageButton',body,{Name='Prompt',BackgroundTransparency=1,Position=UDim2.fromOffset(20,80),Size=UDim2.fromOffset(220,48),Image=T.Asset.panel,ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=.5,AutoButtonColor=false,Selectable=false,Visible=false})
 local cap=T.make('Frame',row,{Name='Key',Position=UDim2.fromOffset(8,7),Size=UDim2.fromOffset(34,34),BackgroundColor3=C.lime,BorderSizePixel=0})
 T.make('UICorner',cap,{CornerRadius=UDim.new(0,8)});T.make('UIStroke',cap,{Color=C.ink,Thickness=2})
 local capScale=T.make('UIScale',cap,{Scale=1})
 local key=T.label(cap,'Text','E',0,0,34,34,20,C.ink);key.TextStrokeTransparency=1
 local pad=T.icon(cap,'Pad',3,3,28,'');pad.Visible=false
 local action=T.label(row,'Action','HOLD TO REVIVE',50,7,162,34,19,C.white);action.TextXAlignment=Enum.TextXAlignment.Left
 return {gui=b,scale=scale,status=status,fill=fill,track=track,row=row,capScale=capScale,key=key,pad=pad,action=action}
end
-- The key for how this player is playing: E (their keyboard layout's name for it), the controller's
-- own Y image, or a plus on phones, where the row itself is held.
local function showKey(v,prompt,inputType)
 local touch=inputType==Enum.ProximityPromptInputType.Touch
 local gamepad=inputType==Enum.ProximityPromptInputType.Gamepad
 local image=gamepad and UserInputService:GetImageForKeyCode(prompt.GamepadKeyCode) or ''
 local name=UserInputService:GetStringForKeyCode(prompt.KeyboardKeyCode)
 v.tag.pad.Image=image;v.tag.pad.Visible=image~=''
 v.tag.key.Text=touch and '+' or gamepad and (image=='' and 'Y' or '') or (name~='' and string.upper(name) or 'E')
 v.tag.action.Text=touch and 'HOLD HERE TO REVIVE' or 'HOLD TO REVIVE'
end
local function press(v,down) TweenService:Create(v.tag.capScale,TweenInfo.new(.08),{Scale=down and .88 or 1}):Play() end
-- A held tap or click on the row stands in for the key (custom prompts handle touch themselves).
local function release(v)
 local input=v.pressing;v.pressing=nil
 if input and v.shown then pcall(v.shown.InputHoldEnd,v.shown) end
end

-- A spot arrives whole (a Persistent model); the wait for its Pad is only a safety net.
local function track(spot)
 if views[spot] or not spot:IsA('Model') then return end
 local pad=spot:FindFirstChild('Pad') or spot:WaitForChild('Pad',10)
 if not pad or views[spot] or spot.Parent==nil then return end
 local g,stroke,segments,plus=ring(pad)
 local v={ring=g,stroke=stroke,segments=segments,plus=plus,tag=tag(spot,pad),down=spot:GetAttribute('DownUserId'),progress=0}
 v.tag.row.InputBegan:Connect(function(input)
  if v.pressing or not v.shown then return end
  if input.UserInputType==Enum.UserInputType.Touch or input.UserInputType==Enum.UserInputType.MouseButton1 then
   v.pressing=input;v.shown:InputHoldBegin()
  end
 end)
 v.tag.row.InputEnded:Connect(function(input) if input==v.pressing then release(v) end end)
 views[spot]=v
end
local function untrack(spot)
 local v=views[spot];if not v then return end
 views[spot]=nil;release(v)
 v.ring:Destroy();v.tag.gui:Destroy()
 -- A full hold ended in a revive: a cheer for the one who revived and the one revived.
 if v.progress>=.9 and (v.reviver==player.UserId or v.down==player.UserId) then T.sound('ui_upgrade') end
end
-- The finger or button lifted anywhere (it may have slid off the row): stop that hold.
UserInputService.InputEnded:Connect(function(input) for _,v in views do if v.pressing==input then release(v) end end end)
PromptService.PromptShown:Connect(function(prompt,inputType)
 if prompt.Name~='RevivePrompt' then return end
 local spot=prompt:FindFirstAncestorWhichIsA('Model');local v=spot and views[spot];if not v then return end
 v.prompt=prompt;v.shown=prompt;showKey(v,prompt,inputType)
 local hidden;hidden=prompt.PromptHidden:Connect(function()
  hidden:Disconnect()
  if v.shown==prompt then release(v);v.shown=nil;press(v,false) end
 end)
end)
-- The key cap dips while this player holds (keyboard, controller or the row).
local function capFor(prompt,who,down)
 if who~=player or prompt.Name~='RevivePrompt' then return end
 local spot=prompt:FindFirstAncestorWhichIsA('Model');local v=spot and views[spot];if v then press(v,down) end
end
PromptService.PromptButtonHoldBegan:Connect(function(prompt,who) capFor(prompt,who,true) end)
PromptService.PromptButtonHoldEnded:Connect(function(prompt,who) capFor(prompt,who,false) end)

RunService.RenderStepped:Connect(function()
 local now=workspace:GetServerTimeNow()
 local helper=canHelp()
 local member=player:GetAttribute('RunMember')==true
 local pulse=.25+.2*math.sin(os.clock()*4)
 local s=math.clamp(workspace.CurrentCamera.ViewportSize.Y/800,.7,1)
 for spot,v in views do
  local mine=v.down==player.UserId
  -- Only someone who may revive gets the prompt; this copy's Enabled is local, the server never sets it.
  v.prompt=v.prompt or spot:FindFirstChild('RevivePrompt',true)
  local want=helper and not mine
  if v.prompt and v.prompt.Enabled~=want then v.prompt.Enabled=want end
  local revivers=spot:GetAttribute('Revivers') or 0
  local held=revivers>0
  local p0,at=spot:GetAttribute('Progress'),spot:GetAttribute('ProgressAt')
  local progress=type(p0)=='number' and type(at)=='number' and math.clamp(p0+(spot:GetAttribute('ProgressRate') or 0)*(now-at),0,1) or 0
  v.progress=progress;v.reviver=held and spot:GetAttribute('ReviverUserId') or nil
  -- Each piece fades in from white to lime as the hold passes it.
  local lit=progress*SEGMENTS
  if lit~=v.lit then
   v.lit=lit
   for i,seg in v.segments do local f=math.clamp(lit-(i-1),0,1);seg.BackgroundColor3=C.white:Lerp(C.lime,f);seg.BackgroundTransparency=.7*(1-f) end
   for _,f in v.plus do f.BackgroundColor3=C.white:Lerp(C.lime,progress) end
  end
  v.stroke.Transparency=held and 0 or pulse
  local t=v.tag
  t.gui.Enabled=member or mine
  if t.scale.Scale~=s then t.scale.Scale=s;t.gui.Size=UDim2.fromOffset(260*s,130*s) end
  -- More than one holding: "BEN +1 ARE REVIVING" (the ring fills x1.5 with two, x2 with three).
  local who=string.upper(spot:GetAttribute('ReviverName') or 'A teammate')..(revivers>1 and ' +'..(revivers-1)..' ARE' or ' IS')
  t.status.Text=not held and 'DOWN' or v.reviver==player.UserId and (revivers>1 and 'REVIVING x'..revivers or 'REVIVING') or mine and who..' REVIVING YOU' or who..' REVIVING'
  t.status.TextColor3=held and C.lime or C.negative
  t.track.Visible=held or progress>0 -- a let-go ring drains slowly, so its bar stays up
  if t.track.Visible then T.setBar(t.fill,progress) end
  t.row.Visible=v.shown~=nil and want
 end
 -- The reviver bubbles: one per player the server guards (ReviveGuard), on their body.
 for q,b in bubbles do
  local r=q.Parent and q:GetAttribute('ReviveGuard') and q.Character and q.Character:FindFirstChild('HumanoidRootPart')
  if r then b.CFrame=r.CFrame else bubbles[q]=nil;b:Destroy() end
 end
 for _,q in Players:GetPlayers() do
  local r=not bubbles[q] and q:GetAttribute('ReviveGuard') and q.Character and q.Character:FindFirstChild('HumanoidRootPart')
  if r then
   local b=Instance.new('Part');b.Name='ReviveBubble';b.Shape=Enum.PartType.Ball;b.Size=Vector3.one*7
   b.Material=Enum.Material.ForceField;b.Color=C.lime;b.Anchored=true;b.CanCollide=false;b.CanQuery=false;b.CanTouch=false;b.CastShadow=false
   b.CFrame=r.CFrame;b.Parent=workspace;bubbles[q]=b
  end
 end
end)
task.spawn(function()
 local folder=workspace:FindFirstChild(FOLDER)
 while not folder do workspace.ChildAdded:Wait();folder=workspace:FindFirstChild(FOLDER) end
 folder.ChildAdded:Connect(function(spot) task.spawn(track,spot) end);folder.ChildRemoved:Connect(untrack)
 for _,spot in folder:GetChildren() do task.spawn(track,spot) end
end)
