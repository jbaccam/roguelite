-- Client only: the round 10 event's on-screen information, in the game's green UI theme (UITheme).
--   Objective panel: under the wave timer (and under the boss bar when that sits under the timer on
--     phones), the event title and its real clear condition. The Tomb event adds three compact
--     A / B / C entries with their own health and a WARDEN ALIVE / DEFEATED chip (EventStatus).
--   Banner: EVENT CLEARED when the server latches the clear (EventPhase Complete).
--   Cue: PACK EMPOWERED (EventCue) as a red toast.
--   Pointers: an arrow at the screen edge toward the leader and each standing tomb when they are off
--     screen (objectives only, never ordinary mobs).
--   Tomb bars: each coffin's own world-space bar (BillboardGui) with its letter: truthful health
--     from its Humanoid, never through walls (AlwaysOnTop off).
-- Text plus shape plus colour everywhere (never colour alone); sizes follow the HUD's own scale.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local Http=game:GetService('HttpService')
local RS=game:GetService('ReplicatedStorage')
local T=require(RS:WaitForChild('UITheme'))
local player=Players.LocalPlayer
local C=T.Color
local H={}
local mounted -- {panel, ...}
local RED=Color3.fromRGB(239,35,47)

local function hudRoot()
 local gui=player:WaitForChild('PlayerGui'):FindFirstChild('RogueliteHUD')
 local safe=gui and gui:FindFirstChild('SafeArea');return safe and safe:FindFirstChild('HUD')
end
local function decode(raw) local ok,t=pcall(Http.JSONDecode,Http,raw or '');return ok and type(t)=='table' and t or nil end

-- A thin health track like the HUD's (red fill over an orange trail), returns fill, trail.
local function track(parent,x,y,w,h)
 local t=T.make('Frame',parent,{Name='Track',Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),BackgroundColor3=C.track,BorderSizePixel=0,ClipsDescendants=true})
 T.make('UICorner',t,{CornerRadius=UDim.new(0,3)})
 local trail=T.make('Frame',t,{Name='Trail',Size=UDim2.fromScale(1,1),BackgroundColor3=Color3.fromRGB(248,172,104),BorderSizePixel=0})
 local fill=T.make('Frame',t,{Name='Fill',Size=UDim2.fromScale(1,1),BackgroundColor3=RED,BorderSizePixel=0})
 T.make('UIGradient',fill,{Rotation=90,Color=ColorSequence.new(Color3.fromRGB(255,109,103),Color3.fromRGB(165,16,27))})
 return fill,trail,t
end
local function setTrack(fill,trail,ratio,state)
 ratio=math.clamp(ratio,0,1)
 if state.last==nil or math.abs(state.last-ratio)>1e-3 then
  local down=state.last and ratio<state.last
  state.last=ratio;fill.Size=UDim2.fromScale(ratio,1)
  if down then TweenService:Create(trail,TweenInfo.new(.5,Enum.EasingStyle.Quad,Enum.EasingDirection.Out,0,false,.12),{Size=UDim2.fromScale(ratio,1)}):Play() else trail.Size=fill.Size end
 end
end

local PANEL_W=420
local function build(def)
 local hud=hudRoot();if not hud then return nil end
 local root=T.make('Frame',hud,{Name='Round10Objective',AnchorPoint=Vector2.new(.5,0),Position=UDim2.new(.5,0,0,130),Size=UDim2.fromOffset(PANEL_W,86),BackgroundTransparency=1})
 local scale=T.make('UIScale',root,{Scale=1})
 local plate=T.panel(root,'Plate',0,0,PANEL_W,86,'panel')
 local title=T.label(plate,'Title',def.title,16,6,PANEL_W-32,34,26,C.gold);title.TextStrokeTransparency=0
 local goal=T.label(plate,'Goal',def.objective,16,40,PANEL_W-32,30,18,C.white)
 local m={root=root,scale=scale,plate=plate,goal=goal,def=def,tombs={},height=86}
 if def.kind=='tombs' then
  -- Three entries A / B / C and the Warden chip under them.
  goal.Text='DESTROY THE TOMBS'
  local rows=T.make('Frame',plate,{Name='Tombs',BackgroundTransparency=1,Position=UDim2.fromOffset(16,72),Size=UDim2.fromOffset(PANEL_W-32,30)})
  for i,letter in {'A','B','C'} do
   local cell=T.panel(rows,'Tomb'..letter,(i-1)*((PANEL_W-32)/3),0,(PANEL_W-32)/3-6,30,'inset')
   local tag=T.label(cell,'Letter',letter,4,1,24,28,18,C.cream)
   local fill,trail,tr=track(cell,30,9,(PANEL_W-32)/3-44,12)
   local cross=T.label(cell,'Destroyed','DESTROYED',28,1,(PANEL_W-32)/3-40,28,13,C.muted);cross.Visible=false
   m.tombs[letter]={cell=cell,fill=fill,trail=trail,track=tr,cross=cross,state={}}
  end
  m.warden=T.label(plate,'Warden','WARDEN ALIVE',16,106,PANEL_W-32,24,17,C.negative)
  m.height=136
  plate.Size=UDim2.fromOffset(PANEL_W,m.height);root.Size=UDim2.fromOffset(PANEL_W,m.height)
 end
 return m
end
-- Under the timer, or under the boss bar when the HUD put that under the timer (phones).
local function place(m)
 local hud=m.root.Parent;if not hud then return end
 local timer=hud:FindFirstChild('Timer');local boss=hud:FindFirstChild('BossHealth')
 local s=1;local ts=timer and timer:FindFirstChildOfClass('UIScale');if ts then s=ts.Scale end
 local y=timer and (timer.AbsolutePosition.Y-hud.AbsolutePosition.Y+timer.AbsoluteSize.Y+8) or 130
 local test=timer and timer:FindFirstChild('TestRun');if test and test.Visible then y+=26*s end
 if boss and boss.Visible and boss.AnchorPoint.Y==0 then
  local by=boss.AbsolutePosition.Y-hud.AbsolutePosition.Y
  if by>=y-4 then y=by+boss.AbsoluteSize.Y+6 end
 end
 -- Never wider than the gap between the health block and the build strip.
 local w=hud.AbsoluteSize.X;local maxW=math.max(240,w-2*(12+384*s)-20)
 m.scale.Scale=math.min(s,maxW/PANEL_W)
 m.root.Position=UDim2.new(.5,0,0,y)
end

-- Tomb world bars: a letter badge and a bar over each coffin while it stands.
local function tombBar(model)
 local root=model:FindFirstChild('HumanoidRootPart');local h=model:FindFirstChildOfClass('Humanoid');if not root or not h then return nil end
 local size=model:GetExtentsSize()
 local gui=T.make('BillboardGui',root,{Name='Round10TombBar',Size=UDim2.fromOffset(180,46),StudsOffsetWorldSpace=Vector3.new(0,size.Y*.55+1.6,0),AlwaysOnTop=false,MaxDistance=180,LightInfluence=0,ResetOnSpawn=false})
 local badge=T.panel(gui,'Badge',0,0,46,46,'panel')
 T.label(badge,'Letter',model:GetAttribute('TombLetter') or '?',4,4,38,38,26,C.gold)
 local fill,trail=track(gui,48,14,128,18)
 local state={}
 local function update() setTrack(fill,trail,h.MaxHealth>0 and h.Health/h.MaxHealth or 0,state) end
 h.HealthChanged:Connect(update);update()
 h.Died:Connect(function() gui:Destroy() end)
 return gui
end

-- Off-screen pointers: one arrow per objective (leader, standing tombs).
local pointerGui
local pointers={}
local function pointer(key,label,color)
 local p=pointers[key];if p then return p end
 pointerGui=pointerGui or T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='Round10Pointers',ResetOnSpawn=false,DisplayOrder=21,IgnoreGuiInset=true})
 local f=T.make('Frame',pointerGui,{Name=key,AnchorPoint=Vector2.new(.5,.5),Size=UDim2.fromOffset(54,54),BackgroundTransparency=1,Visible=false})
 local disc=T.panel(f,'Disc',3,3,48,48,'panel')
 T.label(disc,'Label',label,4,4,40,40,label:len()>1 and 15 or 24,color)
 local arrow=T.make('Frame',f,{Name='Arrow',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromOffset(16,16),Rotation=45,BackgroundColor3=color,BorderSizePixel=0,ZIndex=0})
 p={frame=f,arrow=arrow};pointers[key]=p;return p
end
local function updatePointer(p,position)
 local camera=workspace.CurrentCamera;if not camera or not position then p.frame.Visible=false;return end
 local v,onScreen=camera:WorldToViewportPoint(position)
 local size=camera.ViewportSize
 if onScreen and v.X>40 and v.X<size.X-40 and v.Y>40 and v.Y<size.Y-40 then p.frame.Visible=false;return end
 local center=size/2;local d=Vector2.new(v.X,v.Y)-center
 if v.Z<0 then d=-d end
 if d.Magnitude<1 then d=Vector2.new(0,1) end
 local margin=48;local half=center-Vector2.new(margin,margin)
 local k=math.min(math.abs(half.X/(d.X~=0 and d.X or 1e-3)),math.abs(half.Y/(d.Y~=0 and d.Y or 1e-3)))
 local at=center+d*k
 p.frame.Visible=true;p.frame.Position=UDim2.fromOffset(at.X,at.Y)
 local dir=d.Unit;p.arrow.Position=UDim2.new(.5,dir.X*30,.5,dir.Y*30)
end
local function clearPointers() for _,p in pointers do p.frame:Destroy() end;table.clear(pointers) end

-- Shows the panel for `def` (Round10Defs entry); state reads RogueliteRunState each frame.
function H.show(def,folder)
 H.hide()
 local m=build(def);if not m then return end
 mounted=m
 m.bars={}
 local conn
 conn=RunService.Heartbeat:Connect(function()
  if mounted~=m or not m.root.Parent then conn:Disconnect();return end
  place(m)
  local run=RS:FindFirstChild('RogueliteRunState')
  local st=run and decode(run:GetAttribute('EventStatus'))
  if def.kind=='tombs' and st then
   local down=0
   for _,e in st.tombs or {} do
    local row=m.tombs[e.letter]
    if row then
     setTrack(row.fill,row.trail,(e.max or 1)>0 and (e.health or 0)/(e.max or 1) or 0,row.state)
     row.track.Visible=e.alive;row.cross.Visible=not e.alive
     row.cell.ImageTransparency=e.alive and 0 or .45
     if not e.alive then down+=1 end
    end
   end
   m.goal.Text=('DESTROY THE TOMBS  %d / %d'):format(down,#(st.tombs or {}))
   -- 2026-10-10: a party can face 2-3 Wardens (Round10Service); the chip counts them.
   local total=tonumber(st.wardenTotal) or 1;local left=tonumber(st.wardens) or (st.leaderAlive and 1 or 0)
   if total>1 then m.warden.Text=left>0 and ('WARDENS ALIVE  %d / %d'):format(left,total) or 'WARDENS DEFEATED'
   else m.warden.Text=st.leaderAlive and 'WARDEN ALIVE' or 'WARDEN DEFEATED' end
   m.warden.TextColor3=st.leaderAlive and C.negative or C.lime
  end
  -- Pointers: the leader and the standing tombs, off screen only.
  local seen={}
  if folder and folder.Parent then
   -- Leader, plus Leader2 / Leader3 (a party's extra Tomb Wardens, 2026-10-10).
   for _,key in {'Leader','Leader2','Leader3'} do
    local leader=folder:FindFirstChild(key);leader=leader and leader.Value
    local lh=leader and leader.Parent and leader:FindFirstChildOfClass('Humanoid')
    if lh and lh.Health>0 and (leader:GetAttribute('BossIntroUntil') or 0)<=workspace:GetServerTimeNow() then
     local id=key:lower();seen[id]=true;local r=leader.PrimaryPart;updatePointer(pointer(id,'BOSS',C.negative),r and r.Position)
    end
   end
   for _,l in {'A','B','C'} do
    local v=folder:FindFirstChild('Tomb'..l);local tomb=v and v.Value
    local th=tomb and tomb.Parent and tomb:FindFirstChildOfClass('Humanoid')
    if th and th.Health>0 then
     seen['tomb'..l]=true;local r=tomb:FindFirstChild('HumanoidRootPart');updatePointer(pointer('tomb'..l,l,C.gold),r and r.Position)
     if not m.bars[tomb] then m.bars[tomb]=tombBar(tomb) or false end
    end
   end
  end
  for key,p in pointers do if not seen[key] then p.frame.Visible=false end end
 end)
end
function H.hide()
 if mounted then mounted.root:Destroy();mounted=nil end
 clearPointers()
end
-- The EVENT CLEARED banner: pops in, holds, fades.
function H.cleared()
 local gui=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='Round10Cleared',ResetOnSpawn=false,DisplayOrder=40,IgnoreGuiInset=true})
 local holder=T.make('Frame',gui,{AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.3),Size=UDim2.fromOffset(560,110),BackgroundTransparency=1})
 local scale=T.make('UIScale',holder,{Scale=.6})
 local plate=T.panel(holder,'Plate',0,0,560,110,'panel');T.caps(plate,64)
 local l=T.label(plate,'Text','EVENT CLEARED',40,10,480,90,64,C.lime);l.TextStrokeTransparency=0
 local v=gui.AbsoluteSize;local s=math.clamp(math.min(v.X/1280,v.Y/760),.5,1.1)
 TweenService:Create(scale,TweenInfo.new(.35,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=s}):Play()
 T.sound('ui_upgrade')
 task.delay(2.4,function()
  if not gui.Parent then return end
  TweenService:Create(plate,TweenInfo.new(.35),{ImageTransparency=1}):Play()
  TweenService:Create(l,TweenInfo.new(.35),{TextTransparency=1,TextStrokeTransparency=1}):Play()
  task.delay(.4,function() gui:Destroy() end)
 end)
end
-- A short cue line (PACK EMPOWERED) in the HUD's toast slot.
function H.cue(text)
 local gui=player:WaitForChild('PlayerGui'):FindFirstChild('RogueliteHUD');if not gui then return end
 -- Not C.negative: that colour means a failed action and plays the error sound.
 T.toast(gui,text,Color3.fromRGB(255,96,88))
end
return H
