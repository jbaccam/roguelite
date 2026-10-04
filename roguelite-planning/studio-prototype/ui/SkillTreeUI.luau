-- Full-screen Skill Tree (lobby), green theme (UITheme).
-- Opening: the nodes spring outward from the centre star in waves. No ripple circles.
-- Buying: the node squashes and pops lime with a flash and a few sparks, the links to its
-- children charge up, newly reachable skills flip over and the key counter ticks down.
-- Presentation and requests only: purchases go through ProfileAction('BuySkill', id) and are
-- validated by ProfileService with SkillTreeConfig. Owned skills come from the ProfileSkills attribute.
local RS=game:GetService('ReplicatedStorage')
local Lighting=game:GetService('Lighting')
local Input=game:GetService('UserInputService')
local TweenService=game:GetService('TweenService')
local SoundService=game:GetService('SoundService')
local TextService=game:GetService('TextService')
local RunService=game:GetService('RunService')
local GuiService=game:GetService('GuiService')
local CAS=game:GetService('ContextActionService')
local T=require(RS:WaitForChild('UITheme'))
local FX=require(RS:WaitForChild('StoreFX'))
local combat=RS:WaitForChild('RogueliteCombat')
local Skills=require(combat:WaitForChild('SkillTreeConfig'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local C=T.Color
local U={}

-- Laid out on a T.canvas like ArmoryUI (one scale: 1920x1080 on a 16:9 monitor, about 1500x740 on
-- a phone); see plan(). The board also zooms and pans.
local UNIT=150 -- board pixels between grid units
local SIZE={root=150,capstone=128,node=108}
local ZOOM_MIN,ZOOM_MAX=.5,1.25 -- manual zoom; the auto-fit may go lower to show the whole tree
local M,GAP=24,16 -- canvas margin, gap between pieces
local BONUS_W,PANEL_H,HINT_H=340,560,48
local INFO_W,INFO_H=872,170
local CLOSE_W,CLOSE_H=240,86
local BOARD_MIN=720 -- narrowest board band: a new player's first two rings at zoom 1 (tiles reach ±354)
local PAD_ACTION='SkillTreeGamepad'
local HINTS={
 KeyboardAndMouse='Drag to look around  ·  Scroll to zoom',
 Touch='Drag to look around  ·  Pinch to zoom',
 Gamepad='Right stick to look around  ·  LB / RB to zoom  ·  X to buy',
}
local SLICE=Rect.new(48,48,208,208)
local WHITE=Color3.new(1,1,1)
local LINK_IDLE=Color3.fromRGB(64,72,76)
-- Stats with no art of their own borrow the nearest icon.
local STAT_ICON={CritDamage='CritChance'}

local function tween(obj,time,props,style,dir,delay)
 local tw=TweenService:Create(obj,TweenInfo.new(time,style or Enum.EasingStyle.Quad,dir or Enum.EasingDirection.Out,0,false,delay or 0),props)
 tw:Play();return tw
end
local function fmt(n)
 n=math.floor(tonumber(n) or 0)
 if n>=1e6 then return string.format('%.1fM',n/1e6) elseif n>=1e4 then return string.format('%.1fK',n/1e3) end
 return tostring(n)
end
local function play(id,volume,pitch)
 if not id then return end
 local s=Instance.new('Sound');s.SoundId='rbxassetid://'..id;s.Volume=volume or .5;s.PlaybackSpeed=pitch or 1
 s.SoundGroup=SoundService:FindFirstChild('RogueliteSFX') -- Settings SFX slider
 s.Parent=SoundService;SoundService:PlayLocalSound(s)
 task.delay(5,function() s:Destroy() end)
end
local function textWidth(text,size) return TextService:GetTextSize(text,size,T.Font,Vector2.new(2000,200)).X end
local function centred(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
local function left(l) l.TextXAlignment=Enum.TextXAlignment.Left;return l end
-- 'KeyboardAndMouse' | 'Touch' | 'Gamepad': what the player is using right now.
local function inputKind()
 local ok,pref=pcall(function() return Input.PreferredInput end)
 if ok and typeof(pref)=='EnumItem' and HINTS[pref.Name] then return pref.Name end
 local t=Input:GetLastInputType()
 if t==Enum.UserInputType.Touch then return 'Touch' end
 if t.Name:find('^Gamepad') then return 'Gamepad' end
 return 'KeyboardAndMouse'
end

-- Title plate with stone caps (same as the Armory's).
local function plate(parent,text,x,y,size)
 size=size or 38
 local w=textWidth(text,size)+90
 local p=T.panel(parent,'TitlePlate',x,y,w,64,'panel')
 T.caps(p,44)
 local l=T.label(p,'Title',text,0,0,0,0,size);l.Size=UDim2.fromScale(1,1)
 return p,w
end

-- opts: profile() -> LobbyUI profile ({gems, connected}), onVisible(bool) to hide the lobby HUD,
-- request(action, ...) -> {ok, message} (defaults to the ProfileAction remote).
function U.new(player,opts)
 local self={}
 local request=opts.request or function(...) return combat:WaitForChild('ProfileAction'):InvokeServer(...) end
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='SkillTree',ResetOnSpawn=false,DisplayOrder=58,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,Enabled=false,
  -- Full screen minus phone notches and rounded corners; the shade reaches under them.
  ScreenInsets=Enum.ScreenInsets.DeviceSafeInsets,ClipToDeviceSafeArea=false})
 self.Screen=screen
 local root,blur,shade,board,boardScale,fxLayer
 local groups={} -- HUD frames on the canvas, rebuilt when the screen changes size
 local nodes,links={},{}
 local owned,gems={Root=true},0
 local lastState={}
 local selected=Skills.ROOT
 local zoom,pan=1,Vector2.zero -- pan: board centre offset from the free area's centre, canvas px
 local L,P,canvas -- canvas metrics (T.canvas) and the plan() for them
 local hudProfile -- last profile read, for the Studio / loading chip
 local boxMin,boxMax=Vector2.zero,Vector2.zero -- board px around every drawn skill
 local pending -- node id sent to the server, celebrated when ProfileSkills confirms it
 local shownGems=0
 local gemsValue,gemsPill,gemsCounter
 local info,bonusPanel,selection
 local conns={}

 local function readProfile()
  local p=opts.profile()
  gems=p.gems or 0
  owned=Skills.parse(player:GetAttribute('ProfileSkills'))
  hudProfile=p
  return p
 end

 -- Layout ----------------------------------------------------------------------
 -- P: where every piece goes on the current canvas (canvas px), recomputed when the screen
 -- changes size. 1920x1080: bonuses at x 24..364; title, board and info card centred on the screen
 -- (x 960); the board gets 388..1532 between the title (ends 154) and the info card (starts 890).
 -- 844x390 phone (canvas 1500x738 inside the safe area): title and emeralds share one row, the
 -- info card runs under the bonus column (which stops above it and scrolls) and the board keeps
 -- tiles tappable instead of fitting the whole tree (the player pans).
 local function plan(c)
  local p={s=c.s,w=c.w,h=c.h,top=c.top}
  local studio=RunService:IsStudio()
  local chip=studio or not (hudProfile and hudProfile.connected)
  p.compact=c.h<900
  p.x0,p.x1=M+BONUS_W+M,c.w-M
  -- Centred on the screen (2026-10-03: centred in the room right of the bonus column, the tree,
  -- title and card opened 180 px right of centre). The board band mirrors the column's edge; where
  -- that leaves under BOARD_MIN (small phones) it widens right instead of reaching under the
  -- column. Canvas 1500 (844x390 phone): band 388..1112, centre 750; 1334 (iPhone SE): 388..1108.
  p.fx0,p.fx1=p.x0,math.min(p.x1,math.max(c.w-p.x0,p.x0+BOARD_MIN))
  p.cx=(p.fx0+p.fx1)/2
  -- Short screens: a slightly smaller plate and pill side by side (544 px wide, fits between the
  -- top-bar buttons on an iPhone SE).
  p.plateSize,p.pillW=p.compact and 36 or 40,p.compact and 190 or 220
  p.plateW=textWidth('SKILL TREE',p.plateSize)+90
  if p.compact then p.topW,p.topH,p.topY=18+p.plateW+12+p.pillW+18,chip and 100 or 64,12
  else p.topW,p.topH,p.topY=600,chip and 164 or 136,18 end
  p.topX=p.cx-p.topW/2
  if p.compact then
   -- The row sits in the top-bar band: keep it between Roblox's corner buttons (about 260 screen
   -- px on the left, 120 on the right). iPhone SE: 542..1086 of a 1334 canvas.
   p.topX=math.max(260/c.s+8,math.min(p.topX,c.w-120/c.s-8-p.topW))
  end
  p.closeX,p.closeY=c.w-M-CLOSE_W,c.h-20-CLOSE_H
  p.infoY=c.h-20-INFO_H
  p.infoX=math.min(p.cx-INFO_W/2,p.closeX-GAP-INFO_W)
  -- Bonus column, below Roblox's top-bar buttons. When the info card reaches under it (narrow
  -- canvases) it stops above the card.
  local colTop=c.top+8
  local colBottom=p.infoX<p.x0 and p.infoY-GAP or c.h-M
  p.colExtra=8+HINT_H+(studio and 48 or 0)
  p.panelH=math.clamp(colBottom-colTop-p.colExtra,180,PANEL_H)
  p.colY=colTop+math.max(0,(colBottom-colTop-p.panelH-p.colExtra)/2)
  -- Board: that band, below the title (and the top bar), above the card.
  p.fy0=math.max(p.topY+p.topH,c.top)+8
  p.fy1=p.infoY-8
  p.fcx,p.fcy=(p.fx0+p.fx1)/2,(p.fy0+p.fy1)/2
  return p
 end
 -- slide: where the frame slides in from on open (canvas px from its place).
 local function group(name,x,y,w,h,slide)
  local f=T.frame(canvas,name,x,y,w,h);f.ZIndex=20
  f:SetAttribute('Slide',slide)
  table.insert(groups,f)
  return f
 end
 -- Board px around every skill drawn (owned, buyable, '?'), with room for names and prices.
 local function measure()
  local a,b=Vector2.new(math.huge,math.huge),Vector2.new(-math.huge,-math.huge)
  for _,d in Skills.List do
   local st=d.kind=='root' and 'owned' or Skills.state(owned,d.id)
   if st~='hidden' then
    local h=SIZE[d.kind]/2;local x,y=d.x*UNIT,d.y*UNIT
    local below=st=='available' and 50 or st=='owned' and 26 or 0
    a=Vector2.new(math.min(a.X,x-h-24),math.min(a.Y,y-h-10))
    b=Vector2.new(math.max(b.X,x+h+24),math.max(b.Y,y+h+below+8))
   end
  end
  boxMin,boxMax=a,b
 end
 local function place()
  if not (board and P) then return end
  -- The free area's centre may travel anywhere over the drawn tree, no further.
  pan=Vector2.new(math.clamp(pan.X,-boxMax.X*zoom,-boxMin.X*zoom),math.clamp(pan.Y,-boxMax.Y*zoom,-boxMin.Y*zoom))
  board.Position=UDim2.fromOffset(P.fcx+pan.X,P.fcy+pan.Y)
  boardScale.Scale=zoom
 end
 -- Zoom at which the drawn tree exactly fits the free area.
 local function fitRaw()
  local size=boxMax-boxMin
  return math.min((P.fx1-P.fx0)/size.X,(P.fy1-P.fy0)/size.Y)
 end
 -- The auto-fit stops where tiles stay tappable and names readable: on touch screens and small
 -- canvases tiles >= 44 px and names >= 9 px (phone, scale .5: zoom 1.0), on a gamepad names
 -- >= 9 px (1080p TV: .5). With a mouse it shows the whole tree (1920x1080, full tree: .43).
 local function zoomFloor()
  local kind=inputKind()
  if kind=='Touch' or P.s<.6 then return math.max(44/(SIZE.node*P.s),9/(18*P.s)) end
  if kind=='Gamepad' then return 9/(18*P.s) end
  return .3
 end
 local function zoomMin() return P and math.min(ZOOM_MIN,fitRaw()) or ZOOM_MIN end
 -- Zoom and pan that frame everything the player can see in the free area. The tree zooms out on
 -- its own as it grows; past the floor the player pans to the rest.
 local function fittedZoom()
  local z=math.clamp(fitRaw(),math.min(zoomFloor(),1.15),1.15)
  return z,-(boxMin+boxMax)/2*z
 end
 -- Smooth camera move to a zoom and pan; any drag, wheel or stick input cancels it.
 local glide
 local function stopGlide() if glide then glide:Destroy();glide=nil end end
 local function glideTo(z1,p1,time,delay)
  stopGlide()
  local z0,p0=zoom,pan
  local v=Instance.new('NumberValue');glide=v
  v.Changed:Connect(function(a) if glide==v then zoom=z0+(z1-z0)*a;pan=p0:Lerp(p1,a);place() end end)
  tween(v,time,{Value=1},Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,delay)
  task.delay(time+(delay or 0)+.1,function() if glide==v then stopGlide() end end)
 end
 -- Pans just enough to bring a skill (tile, name and price) inside the free area: anywhere right of
 -- the bonus column (to x1), not only the centred band.
 local function showNode(id,animated)
  local d=Skills.ById[id]
  if not (d and P and board) then return end
  local h=SIZE[d.kind]/2;local x,y=d.x*UNIT,d.y*UNIT
  -- On one axis the node covers c+v+a*zoom .. c+v+b*zoom (v = pan); the free span is lo..hi.
  local function axis(v,c,lo,hi,a,b)
   local s0,s1=c+v+a*zoom,c+v+b*zoom
   if s1-s0>hi-lo then return v+(lo+hi-s0-s1)/2 end
   if s0<lo then return v+lo-s0 end
   if s1>hi then return v-(s1-hi) end
   return v
  end
  local to=Vector2.new(axis(pan.X,P.fcx,P.fx0,P.x1,x-h-12,x+h+12),axis(pan.Y,P.fcy,P.fy0,P.fy1,y-h-12,y+h+56))
  if (to-pan).Magnitude<1 then return end
  if animated then glideTo(zoom,to,.3) else pan=to;place() end
 end
 -- When a purchase grows the tree past the view, ease the camera out to fit it.
 local function easeToFit()
  local target,targetPan=fittedZoom()
  if target>=zoom-.01 then return end
  glideTo(target,targetPan,.6,.35)
 end

 -- Board: links, nodes, effects -----------------------------------------------------
 local function pos(d) return Vector2.new(d.x,d.y)*UNIT end
 local function makeLink(layer,d)
  local a,b=pos(Skills.ById[d.parent]),pos(d)
  local delta=b-a;local len=delta.Magnitude;local mid=(a+b)/2
  -- The holder rotates around its centre; the visible Fill grows from the parent end.
  local holder=T.make('Frame',layer,{Name=d.id,BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(mid.X,mid.Y),Size=UDim2.fromOffset(len,10),Rotation=math.deg(math.atan2(delta.Y,delta.X)),ZIndex=2})
  local fill=T.make('Frame',holder,{Name='Fill',BackgroundColor3=LINK_IDLE,BorderSizePixel=0,Size=UDim2.fromScale(1,1),ZIndex=2})
  T.make('UIStroke',fill,{Color=Color3.fromRGB(6,9,10),Thickness=2.5,Transparency=.1})
  T.make('UICorner',fill,{CornerRadius=UDim.new(1,0)})
  local charge=T.make('Frame',fill,{Name='Charge',BackgroundColor3=C.limeSoft,BorderSizePixel=0,Size=UDim2.fromScale(0,1),BackgroundTransparency=1,ZIndex=3})
  T.make('UICorner',charge,{CornerRadius=UDim.new(1,0)})
  links[d.id]={holder=holder,fill=fill,charge=charge}
 end
 local function makeNode(layer,d)
  local size=SIZE[d.kind]
  local p=pos(d)
  local holder=T.make('Frame',layer,{Name=d.id,BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(p.X,p.Y),Size=UDim2.fromOffset(size,size),ZIndex=5})
  local scale=T.make('UIScale',holder,{Scale=1})
  local glow=T.make('ImageLabel',holder,{Name='Glow',BackgroundTransparency=1,Image=FX.Asset.glow,ImageColor3=C.lime,ImageTransparency=1,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromScale(2.1,2.1),ZIndex=4})
  local tile=T.make('ImageButton',holder,{Name='Tile',BackgroundTransparency=1,Size=UDim2.fromScale(1,1),Image=T.Asset.panel,ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=.5,AutoButtonColor=false,Selectable=true,ZIndex=6})
  local accent
  if d.kind~='node' then
   -- Capstones and the centre star get gold corner accents.
   accent=T.make('ImageLabel',tile,{Name='Accent',BackgroundTransparency=1,Size=UDim2.fromScale(1,1),Image=T.Asset.corners,ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=.5,ImageColor3=C.gold,ZIndex=7})
  end
  local icon=T.make('ImageLabel',tile,{Name='Icon',BackgroundTransparency=1,Image=d.icon,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromScale(d.kind=='root' and .82 or .7,d.kind=='root' and .82 or .7),ScaleType=Enum.ScaleType.Fit,ZIndex=8})
  local q=T.label(tile,'Unknown','?',0,0,size,size,math.floor(size*.5),C.dim);q.Size=UDim2.fromScale(1,1);q.ZIndex=8
  local name=centred(T.label(holder,'Name',d.name,-60,size-4,size+120,26,d.kind=='node' and 18 or 21))
  name.TextWrapped=false;name.ZIndex=9
  local cost=T.make('Frame',holder,{Name='Cost',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,0),Position=UDim2.new(.5,0,0,size+20),Size=UDim2.fromOffset(160,26),ZIndex=9})
  T.make('UIListLayout',cost,{FillDirection=Enum.FillDirection.Horizontal,HorizontalAlignment=Enum.HorizontalAlignment.Center,VerticalAlignment=Enum.VerticalAlignment.Center,Padding=UDim.new(0,3),SortOrder=Enum.SortOrder.LayoutOrder})
  local amount=T.label(cost,'Amount',tostring(d.cost),0,0,textWidth(tostring(d.cost),20)+4,26,20,C.gold);amount.TextWrapped=false;amount.LayoutOrder=1;amount.ZIndex=9
  local keyIcon=T.icon(cost,'Key',0,0,26,'emerald');keyIcon.LayoutOrder=2;keyIcon.ZIndex=9
  local n={d=d,holder=holder,scale=scale,glow=glow,tile=tile,accent=accent,icon=icon,q=q,name=name,cost=cost,amount=amount,home=UDim2.fromOffset(p.X,p.Y)}
  nodes[d.id]=n
  tile.MouseEnter:Connect(function() if not n.busy then tween(scale,.12,{Scale=1.07},Enum.EasingStyle.Back) end end)
  tile.MouseLeave:Connect(function() if not n.busy then tween(scale,.12,{Scale=1}) end end)
  tile.Activated:Connect(function() self.Select(d.id) end)
  -- Gamepad: moving the selection onto a skill shows it in the card and pans it into view.
  tile.SelectionGained:Connect(function() if selected~=d.id then self.Select(d.id) end end)
  return n
 end

 local function paintLink(id)
  local l=links[id];if not l then return end
  local st=Skills.state(owned,id)
  -- The tree only draws as far as the player can see; links to unseen skills don't exist yet.
  l.holder.Visible=st~='hidden'
  if st=='owned' then l.fill.BackgroundColor3=C.lime;l.fill.BackgroundTransparency=0;l.holder.Size=UDim2.fromOffset(l.holder.Size.X.Offset,12)
  elseif st=='available' then l.fill.BackgroundColor3=C.limeDark;l.fill.BackgroundTransparency=0;l.holder.Size=UDim2.fromOffset(l.holder.Size.X.Offset,10)
  else
   l.fill.BackgroundColor3=LINK_IDLE;l.holder.Size=UDim2.fromOffset(l.holder.Size.X.Offset,8)
   l.fill.BackgroundTransparency=.15
  end
 end
 local function paintNode(id)
  local n=nodes[id];local d=n.d
  local st=d.kind=='root' and 'owned' or Skills.state(owned,id)
  local afford=d.cost<=gems
  n.state=st
  -- The centre star keeps a charcoal tile so the lime star reads against it.
  n.tile.Image=d.kind=='root' and T.Asset.panelPlain or st=='owned' and T.Asset.button or st=='available' and T.Asset.panel or T.Asset.inset
  n.tile.ImageColor3=WHITE
  -- Unseen skills aren't drawn at all; the ring just past what you can buy shows as '?'.
  n.holder.Visible=st~='hidden'
  n.icon.Visible=st=='owned' or st=='available';n.q.Visible=st=='known'
  n.icon.ImageColor3=WHITE
  n.name.Visible=st=='owned' or st=='available'
  n.name.TextColor3=C.white
  n.cost.Visible=st=='available'
  n.amount.TextColor3=afford and C.emerald or C.negative
  if n.accent then n.accent.Visible=st~='known';n.accent.ImageTransparency=0 end
  -- Soft glow: steady under owned skills, breathing under ones you can afford right now.
  if n.breathe then n.breathe:Cancel();n.breathe=nil end
  n.glow.ImageColor3=d.kind=='root' and C.gold or C.lime
  if st=='available' and afford then
   n.glow.ImageTransparency=.8
   n.breathe=TweenService:Create(n.glow,TweenInfo.new(.9,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,-1,true),{ImageTransparency=.45})
   n.breathe:Play()
  else
   n.glow.ImageTransparency=st=='owned' and .6 or 1
  end
 end

 -- Small spark flecks thrown out from a point on the board.
 local function sparks(at,count,radius)
  for i=1,count do
   local a=(i/count)*math.pi*2+math.random()*.5
   local r=radius*(.75+math.random()*.6)
   local s=math.random(8,14)
   local f=T.make('Frame',fxLayer,{Name='Spark',BackgroundColor3=i%3==0 and C.gold or C.limeSoft,BorderSizePixel=0,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(at.X,at.Y),Size=UDim2.fromOffset(s,s),Rotation=45,ZIndex=12})
   T.make('UIStroke',f,{Color=Color3.fromRGB(8,12,6),Thickness=1.5})
   local to=at+Vector2.new(math.cos(a),math.sin(a))*r
   tween(f,.55,{Position=UDim2.fromOffset(to.X,to.Y),Size=UDim2.fromOffset(2,2),Rotation=45+math.random(-90,90),BackgroundTransparency=1},Enum.EasingStyle.Quart)
   task.delay(.6,function() f:Destroy() end)
  end
 end
 -- A newly reachable skill flips into view; a brand-new '?' also grows its link from the parent.
 local function reveal(id,delay,grow)
  local n=nodes[id];if not n then return end
  n.busy=true
  n.scale.Scale=grow and 0 or .55
  local l=links[id]
  if grow and l then
   l.fill.Size=UDim2.fromScale(0,1)
   tween(l.fill,.25,{Size=UDim2.fromScale(1,1)},Enum.EasingStyle.Quad,Enum.EasingDirection.Out,delay or 0)
   delay=(delay or 0)+.15
  end
  task.delay(delay or 0,function()
   if not n.holder.Parent then return end
   tween(n.scale,.4,{Scale=1},Enum.EasingStyle.Back)
   task.delay(.4,function() n.busy=false end)
  end)
 end

 -- Info card, bonuses and emeralds ----------------------------------------------------
 local drawInfo,drawBonuses
 local function setGems(animated)
  if not gemsValue then return end
  local from,to=shownGems,gems
  shownGems=gems
  if gemsCounter then gemsCounter:Destroy();gemsCounter=nil end
  if not animated or from==to then gemsValue.Text=fmt(to);return end
  -- Counter ticks toward the new total.
  local v=Instance.new('NumberValue');v.Value=from;gemsCounter=v
  v.Changed:Connect(function(x) gemsValue.Text=fmt(x) end)
  tween(v,.5,{Value=to},Enum.EasingStyle.Quad)
  task.delay(.55,function() if gemsCounter==v then v:Destroy();gemsCounter=nil;gemsValue.Text=fmt(to) end end)
  if to<from then
   -- '-15' drifts up off the key pill.
   local f=centred(T.label(gemsPill,'Spent','-'..fmt(from-to),150,6,90,40,26,C.negative));f.ZIndex=25
   tween(f,.8,{Position=UDim2.fromOffset(170,-36),TextTransparency=1,TextStrokeTransparency=1},Enum.EasingStyle.Quad)
   task.delay(.85,function() f:Destroy() end)
  end
 end

 local function celebrate(id)
  local n=nodes[id];if not n then return end
  local d=n.d;local at=pos(d);local size=SIZE[d.kind]
  n.busy=true
  play(Skills.Sounds.Buy,.4,1+math.min(d.depth,5)*.025)
  -- Squash, then spring back a touch bigger.
  n.scale.Scale=.8
  tween(n.scale,.42,{Scale=1},Enum.EasingStyle.Back)
  task.delay(.45,function() n.busy=false end)
  -- White flash off the tile.
  local flash=T.make('ImageLabel',n.holder,{Name='Flash',BackgroundTransparency=1,Image=FX.Asset.glow,ImageColor3=WHITE,ImageTransparency=0,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromScale(1.1,1.1),ZIndex=10})
  tween(flash,.5,{Size=UDim2.fromScale(2.8,2.8),ImageTransparency=1})
  task.delay(.55,function() flash:Destroy() end)
  sparks(at,d.kind=='capstone' and 16 or 10,size*.95)
  -- Charge the links out to the children, then flip them into view.
  for _,child in d.children do
   local l=links[child]
   if l then
    l.charge.BackgroundTransparency=0;l.charge.Size=UDim2.fromScale(0,1)
    tween(l.charge,.28,{Size=UDim2.fromScale(1,1)},Enum.EasingStyle.Quad,Enum.EasingDirection.In,.1)
    task.delay(.42,function() if l.charge.Parent then tween(l.charge,.35,{BackgroundTransparency=1}) end end)
   end
  end
 end

 -- Re-read the profile and repaint in place (never rebuilds, so animations keep running).
 local function refresh(animated)
  if not root then return end
  readProfile()
  local prev=table.clone(lastState)
  for _,d in Skills.List do
   local before=prev[d.id]
   paintNode(d.id);paintLink(d.id)
   local now=nodes[d.id].state
   if animated and before and before~=now then
    if d.id==pending and now=='owned' then
     pending=nil;celebrate(d.id)
    elseif before=='hidden' or before=='known' then
     -- Reveals right after a purchase wait for the charging link to arrive.
     reveal(d.id,d.parent and prev[d.parent]~=nodes[d.parent].state and .36 or 0,before=='hidden')
    end
   end
   lastState[d.id]=now
  end
  measure()
  setGems(animated)
  if animated and P then easeToFit() end
  if drawInfo then drawInfo() end
  if drawBonuses then drawBonuses(animated) end
 end

 function self.Select(id)
  if not Skills.ById[id] then return end
  selected=id
  local n=nodes[id]
  if selection and n then
   selection.Parent=n.holder
   selection.Size=UDim2.new(1,24,1,24)
  end
  if drawInfo then drawInfo() end
  showNode(id,true)
 end

 local function buy(id)
  local d=Skills.ById[id]
  if pending or not d then return end
  pending=id
  local ok,result=pcall(request,'BuySkill',id)
  if not ok or type(result)~='table' or not result.ok then
   pending=nil
   T.toast(screen,ok and type(result)=='table' and result.message or 'Could not buy that right now',C.negative)
   if info and info.Buy then
    -- Head-shake on the button.
    local b=info.Buy;local x=b.Position
    for i,dx in {-8,8,-5,5,0} do task.delay(i*.04,function() if b.Parent then b.Position=x+UDim2.fromOffset(dx,0) end end) end
   end
   return
  end
  -- The profile attribute may land just before or after this reply; refresh() celebrates once.
  task.delay(.6,function()
   if pending~=id then return end
   refresh(true)
   pending=nil -- never leave the tree locked if the confirmation was missed
  end)
 end

 drawInfo=function()
  if not info then return end
  local body=info.Body
  -- Gamepad: a Buy button that had the selection gets it back after the redraw (or the skill does).
  local hadFocus=T.selectionPath(body)
  for _,c in body:GetChildren() do c:Destroy() end
  info.Buy=nil
  if Skills.state(owned,selected)=='hidden' then selected=Skills.ROOT end
  local d=Skills.ById[selected];local st=d.kind=='root' and 'owned' or Skills.state(owned,d.id)
  local mystery=st=='known' or st=='hidden'
  local tile=T.panel(body,'IconTile',16,26,118,118,d.kind=='root' and 'panel' or st=='owned' and 'button' or st=='available' and 'panel' or 'inset')
  if not mystery then T.icon(tile,'Icon',14,14,90,d.icon)
  else T.label(tile,'Q','?',0,0,118,118,60,C.dim) end
  local title=left(T.label(body,'Name',mystery and '???' or d.name,152,14,440,42,32,mystery and C.muted or C.white));title.TextWrapped=false
  local lines=Skills.lines(d)
  local effect=mystery and 'A skill you haven\'t found yet.' or d.kind=='root' and d.blurb or table.concat(lines,'   ·   ')
  -- One or two lines ('Sharp Stuff' is about 470 px at 24, the box 450); the line below follows it.
  local effectSize=d.kind=='root' and 18 or 24
  local effectH=math.ceil(effectSize*1.2)*(textWidth(effect,effectSize)>444 and 2 or 1)+4
  local effectLabel=left(T.label(body,'Effect',effect,152,58,450,effectH,effectSize,d.kind=='root' and C.muted or C.limeSoft))
  effectLabel.TextWrapped=true;effectLabel.TextYAlignment=Enum.TextYAlignment.Top
  local sub
  if d.kind=='root' then
   local n,total,spent=0,#Skills.List-1,0
   for id in owned do local x=Skills.ById[id];if x and x.kind~='root' then n+=1;spent+=x.cost end end
   sub=n..' / '..total..' skills  ·  '..fmt(spent)..' emeralds spent'
  elseif mystery then sub='Unlock '..Skills.ById[d.parent].name..' to reveal it'
  else
   local leads={}
   for _,c in d.children do table.insert(leads,Skills.ById[c].name) end
   sub=d.blurb or (#leads>0 and ('Leads to '..table.concat(leads,', ')) or '')
  end
  T.text(body,'Sub',sub,152,58+effectH+2,450,math.min(44,INFO_H-62-effectH),18,C.muted).TextYAlignment=Enum.TextYAlignment.Top
  -- Right side: BUY / OWNED / LOCKED. Buy is 84 tall: 42 px on a phone (scale .5).
  if st=='available' then
   local afford=d.cost<=gems
   local b=T.button(body,'Buy','',620,30,212,84,function() buy(d.id) end)
   b.Caption.Visible=false;b.Interactable=afford
   info.Buy=b
   local row=T.make('Frame',b,{Name='Row',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromOffset(200,50),ZIndex=3})
   T.make('UIListLayout',row,{FillDirection=Enum.FillDirection.Horizontal,HorizontalAlignment=Enum.HorizontalAlignment.Center,VerticalAlignment=Enum.VerticalAlignment.Center,Padding=UDim.new(0,8),SortOrder=Enum.SortOrder.LayoutOrder})
   local l1=T.label(row,'Buy','BUY',0,0,textWidth('BUY',30)+4,44,30);l1.LayoutOrder=1;l1.TextWrapped=false;l1.ZIndex=3
   local l2=T.label(row,'Cost',tostring(d.cost),0,0,textWidth(tostring(d.cost),30)+4,44,30,afford and C.white or C.negative);l2.LayoutOrder=2;l2.TextWrapped=false;l2.ZIndex=3
   local k=T.icon(row,'Key',0,0,40,'emerald');k.LayoutOrder=3;k.ZIndex=3
   if afford then FX.pulse(b,.03)
   else centred(T.label(body,'Need','Need '..fmt(d.cost-gems)..' more emeralds',600,120,252,28,18,C.negative)) end
  elseif st=='owned' then
   centred(T.label(body,'Owned',d.kind=='root' and 'SKILL TREE' or 'OWNED',600,57,252,56,d.kind=='root' and 30 or 40,C.lime))
  else
   centred(T.label(body,'Locked','LOCKED',600,57,252,56,36,C.dim))
  end
  if hadFocus then
   local n=nodes[selected]
   GuiService.SelectedObject=info.Buy and info.Buy.Interactable and info.Buy or n and n.tile or nil
  end
 end

 drawBonuses=function(animated)
  if not bonusPanel then return end
  local list=bonusPanel.List
  local before={}
  for _,c in list:GetChildren() do if c:IsA('GuiObject') then before[c.Name]=c:GetAttribute('Value') end;if not c:IsA('UIListLayout') then c:Destroy() end end
  local totals=Skills.bonuses(owned)
  local n,total=0,#Skills.List-1
  for id in owned do if Skills.ById[id] and id~=Skills.ROOT then n+=1 end end
  bonusPanel.Progress.Text=n..' / '..total..' skills'
  T.setBar(bonusPanel.Bar,n/total,animated)
  local any=false
  for i,st in Stats.List do
   local v=totals[st.id]
   if v then
    any=true
    local row=T.frame(list,st.id,0,0,300,34);row.LayoutOrder=i;row:SetAttribute('Value',v)
    T.icon(row,'Icon',0,1,32,Skills.Icons[STAT_ICON[st.id] or st.id] or '')
    local l=left(T.label(row,'Text',Skills.effect(st.id,v),42,0,258,34,20,C.white));l.TextWrapped=false
    if animated and before[st.id]~=v then
     -- Rows that just changed flash lime and settle back to white.
     l.TextColor3=C.lime;tween(l,.8,{TextColor3=C.white},Enum.EasingStyle.Quad,Enum.EasingDirection.In,.2)
    end
   end
  end
  if not any then
   local l=T.text(list,'Empty','Buy a skill to get a small bonus in every run.',0,0,290,48,18,C.muted);l.LayoutOrder=1
  end
 end

 local hint
 local function paintHint() if hint and hint.Parent then hint.Text=HINTS[inputKind()] end end
 -- Builds the HUD for the current plan P; called again (replacing it) when the screen resizes.
 local function drawHud(profile,animate)
  for _,f in groups do f:Destroy() end
  table.clear(groups)
  -- Top: title plate and key pill (side by side on short screens).
  local top=group('Top',P.topX,P.topY,P.topW,P.topH,Vector2.new(0,-40))
  local p,w=plate(top,'SKILL TREE',0,0,P.plateSize)
  local chipY=142
  -- (The plate's stone caps poke 18 px past its ends, hence the 18 px inset.)
  if P.compact then p.Position=UDim2.fromOffset(18,0);gemsPill=T.panel(top,'Emeralds',18+w+12,3,P.pillW,58,'inset');chipY=70
  else p.Position=UDim2.fromOffset((P.topW-w)/2,0);gemsPill=T.panel(top,'Emeralds',(P.topW-P.pillW)/2,78,P.pillW,58,'inset') end
  T.icon(gemsPill,'Icon',10,6,46,'emerald')
  gemsValue=left(T.label(gemsPill,'Value',fmt(gems),64,6,P.pillW-80,46,30,C.emerald));gemsValue.TextWrapped=false
  shownGems=gems
  if not profile.connected or RunService:IsStudio() then
   local chip=T.chip(top,'PreviewChip',profile.connected and 'STUDIO TEST · NOT SAVED' or 'PROFILE LOADING',0,chipY,Color3.fromRGB(58,48,20),C.gold)
   chip.AnchorPoint=Vector2.new(.5,0);chip.Position=UDim2.fromOffset(P.topW/2,chipY)
   -- Its 14 px text would be 7 px on a phone (scale .5); 1.3x makes it 9.
   if P.compact then T.make('UIScale',chip,{Scale=1.3}) end
  end
  -- Left: running totals of every bonus the tree gives. The list scrolls when the panel is short
  -- (13 rows need 520 px; a phone gives it about 230).
  local side=group('Bonuses',M,P.colY,BONUS_W,P.panelH+P.colExtra,Vector2.new(-40,0))
  local panel=T.panel(side,'Panel',0,0,BONUS_W,P.panelH,'panel')
  left(T.label(panel,'Title','YOUR BONUSES',22,16,300,34,26))
  local progress=left(T.label(panel,'Progress','',22,52,300,24,18,C.muted));progress.TextWrapped=false
  local bar=T.bar(panel,'Bar',22,80,296,10) -- the fill; T.setBar animates it
  local list=T.scroll(panel,'List',22,104,306,P.panelH-120)
  list.ZIndex=21;list.AutomaticCanvasSize=Enum.AutomaticSize.Y;list.ScrollBarThickness=6
  T.make('UIListLayout',list,{Padding=UDim.new(0,6),SortOrder=Enum.SortOrder.LayoutOrder})
  bonusPanel={Frame=panel,Progress=progress,Bar=bar,List=list}
  -- Controls hint for whatever the player is using (mouse, touch or gamepad); 20 px = 10 on a phone.
  hint=T.text(side,'Hint','',6,P.panelH+8,330,HINT_H,20,C.muted)
  hint.TextXAlignment=Enum.TextXAlignment.Left;hint.TextYAlignment=Enum.TextYAlignment.Top
  paintHint()
  if RunService:IsStudio() then
   -- Studio-only test helpers (server refuses them outside Studio).
   local function dev(action)
    task.spawn(function()
     local ok,r=pcall(request,action)
     if not ok then r=nil end
     if type(r)=='table' and r.message then T.toast(screen,r.message,r.ok and C.lime or C.negative) end
    end)
   end
   local y=P.panelH+8+HINT_H
   local a=T.button(side,'DevEmeralds','+200 EMERALDS',0,y,160,40,function() dev('DevEmeralds') end,true);a.Caption.TextSize=17
   local b=T.button(side,'DevReset','RESET TREE',172,y,168,40,function() dev('DevResetSkills') end,true);b.Caption.TextSize=17
  end
  -- Bottom: info card for the selected skill.
  local bottom=group('Info',P.infoX,P.infoY,INFO_W,INFO_H,Vector2.new(0,40))
  local card=T.panel(bottom,'Card',0,0,INFO_W,INFO_H,'panel')
  info={Card=card,Body=T.frame(card,'Body',0,0,INFO_W,INFO_H)}
  -- Close (same red button as the Armory).
  local closeGroup=group('Close',P.closeX,P.closeY,CLOSE_W,CLOSE_H,Vector2.new(0,40))
  local close=T.button(closeGroup,'Close','CLOSE',0,0,CLOSE_W,CLOSE_H,function() self.Close() end,true)
  T.setTier(close,4);close.Caption.TextSize=40
  -- HUD slides in with the board (on open only, not when the screen resizes).
  if animate then
   for _,f in groups do
    local home=f.Position
    f.Position=home+UDim2.fromOffset(f:GetAttribute('Slide').X,f:GetAttribute('Slide').Y)
    tween(f,.32,{Position=home},Enum.EasingStyle.Quad,Enum.EasingDirection.Out,.12)
   end
  end
 end

 -- Pan and zoom ----------------------------------------------------------------------
 local dragging,dragStart,panStart,pinching,pinchZoom
 local padStick,padZoom=Vector2.zero,0
 -- Input positions are screen px in the same space as AbsolutePosition; the board lives on the
 -- canvas, so convert with the canvas origin and scale (not the viewport centre, which is off by
 -- the top-bar inset).
 local function toCanvas(v) return (v-canvas.AbsolutePosition)/L.s end
 -- cp: canvas point that stays put while zooming (cursor, pinch centre, or the free area's centre).
 local function zoomAt(factor,cp)
  if not P then return end
  local old=zoom
  zoom=math.clamp(zoom*factor,zoomMin(),ZOOM_MAX)
  if zoom==old then return end
  stopGlide()
  -- The board point under cp sits (cp - centre)/old board px from the board centre; keep it there.
  local c=Vector2.new(P.fcx,P.fcy)
  local rel=(cp-c-pan)/old
  pan=cp-c-rel*zoom
  place()
 end
 local function bindInput(drag)
  drag.InputBegan:Connect(function(input)
   if pinching then return end
   if input.UserInputType==Enum.UserInputType.MouseButton1 or input.UserInputType==Enum.UserInputType.Touch then
    stopGlide()
    dragging=input;dragStart=Vector2.new(input.Position.X,input.Position.Y);panStart=pan
   end
  end)
  table.insert(conns,Input.InputChanged:Connect(function(input)
   if not (root and P) then return end
   if dragging and not pinching and (input.UserInputType==Enum.UserInputType.MouseMovement or input==dragging) then
    -- Screen px to canvas px: a 100 px drag on a phone (scale .5) pans 200 canvas px.
    pan=panStart+(Vector2.new(input.Position.X,input.Position.Y)-dragStart)/L.s;place()
   elseif input.UserInputType==Enum.UserInputType.MouseWheel then
    -- Only over the board (right of the bonus column), so the wheel still scrolls the bonus list.
    local cp=toCanvas(Vector2.new(input.Position.X,input.Position.Y))
    if cp.X>=P.fx0 and cp.X<=P.x1 and cp.Y>=P.fy0 and cp.Y<=P.fy1 then zoomAt(input.Position.Z>0 and 1.1 or 1/1.1,cp) end
   end
  end))
  table.insert(conns,Input.InputEnded:Connect(function(input)
   if input==dragging or input.UserInputType==Enum.UserInputType.MouseButton1 then dragging=nil end
   if input.UserInputType==Enum.UserInputType.Touch then pinching=false end
  end))
  -- Two fingers only zoom (around their midpoint): the one-finger drag stops when a pinch starts.
  table.insert(conns,Input.TouchPinch:Connect(function(points,scale,_,state)
   if not (root and P) or #points<2 then return end
   dragging=nil
   if state==Enum.UserInputState.Begin or not pinching then pinching=true;pinchZoom=zoom end
   if state==Enum.UserInputState.End or state==Enum.UserInputState.Cancel then pinching=false;return end
   zoomAt(math.clamp(pinchZoom*scale,zoomMin(),ZOOM_MAX)/zoom,toCanvas((points[1]+points[2])/2))
  end))
  -- Gamepad: the left stick / d-pad move the selection between skills (Roblox's own UI
  -- navigation), the right stick pans, LB/LT zoom out, RB/RT zoom in, X buys the selected skill.
  -- Sunk while open so the stick doesn't also turn the camera behind the blur.
  padStick,padZoom=Vector2.zero,0
  CAS:BindActionAtPriority(PAD_ACTION,function(_,state,input)
   local k=input.KeyCode
   local held=state==Enum.UserInputState.Begin or state==Enum.UserInputState.Change
   if k==Enum.KeyCode.Thumbstick2 then padStick=held and Vector2.new(input.Position.X,input.Position.Y) or Vector2.zero
   elseif k==Enum.KeyCode.ButtonR1 or k==Enum.KeyCode.ButtonR2 then padZoom=held and 1 or 0
   elseif k==Enum.KeyCode.ButtonL1 or k==Enum.KeyCode.ButtonL2 then padZoom=held and -1 or 0
   elseif k==Enum.KeyCode.ButtonX and state==Enum.UserInputState.Begin then
    if Skills.state(owned,selected)=='available' then buy(selected) end
   end
   return Enum.ContextActionResult.Sink
  end,false,Enum.ContextActionPriority.High.Value+50,Enum.KeyCode.Thumbstick2,Enum.KeyCode.ButtonL1,Enum.KeyCode.ButtonR1,
   Enum.KeyCode.ButtonL2,Enum.KeyCode.ButtonR2,Enum.KeyCode.ButtonX)
  table.insert(conns,RunService.RenderStepped:Connect(function(dt)
   if not P then return end
   -- Full stick pans 1100 canvas px a second; held shoulder zooms x2.3 a second.
   if padStick.Magnitude>.2 then stopGlide();pan-=Vector2.new(padStick.X,-padStick.Y)*1100*dt;place() end
   if padZoom~=0 then zoomAt(2.3^(padZoom*dt),Vector2.new(P.fcx,P.fcy)) end
  end))
 end

 -- Lays everything out for the current canvas: HUD rebuilt for the plan, board refitted.
 local animateHud=false
 local function layout()
  if not (L and board) then return end
  local focus=T.selectionPath(canvas)
  P=plan(L)
  drawHud(hudProfile or {},animateHud);animateHud=false
  drawInfo();drawBonuses(false)
  zoom,pan=fittedZoom()
  place()
  showNode(selected,false)
  T.restoreSelection(canvas,focus)
 end

 -- Opening -----------------------------------------------------------------------------
 local function playOpen()
  play(Skills.Sounds.Open,.3,1.05)
  tween(shade,.3,{BackgroundTransparency=.28})
  tween(blur,.3,{Size=16})
  -- Nodes spring out from the star, one depth at a time.
  for _,d in Skills.List do
   local n=nodes[d.id]
   local delay=d.kind=='root' and 0 or .1+d.depth*.075
   n.busy=true
   n.scale.Scale=0
   n.holder.Position=UDim2.fromOffset(d.x*UNIT*.35,d.y*UNIT*.35)
   tween(n.holder,.46,{Position=n.home},Enum.EasingStyle.Back,Enum.EasingDirection.Out,delay)
   tween(n.scale,.46,{Scale=1},Enum.EasingStyle.Back,Enum.EasingDirection.Out,delay)
   task.delay(delay+.48,function() n.busy=false end)
   local l=links[d.id]
   if l then
    -- Links draw outward from the parent once the child has landed.
    l.fill.Size=UDim2.fromScale(0,1)
    tween(l.fill,.22,{Size=UDim2.fromScale(1,1)},Enum.EasingStyle.Quad,Enum.EasingDirection.Out,delay+.16)
   end
  end
 end

 function self.Open()
  if root then self.Close() end
  local profile=readProfile()
  root=T.frame(screen,'Root',0,0,0,0);root.Size=UDim2.fromScale(1,1)
  screen.Enabled=true
  blur=T.make('BlurEffect',Lighting,{Name='SkillTreeBlur',Size=0})
  -- The shade reaches past the safe area (under notches and the top bar).
  shade=T.make('Frame',root,{Name='Shade',Position=UDim2.fromOffset(-100,-100),Size=UDim2.new(1,200,1,200),BackgroundColor3=C.shade,BackgroundTransparency=1,BorderSizePixel=0,ZIndex=0})
  T.make('UIGradient',shade,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.25),NumberSequenceKeypoint.new(.5,.05),NumberSequenceKeypoint.new(1,.25)}),Rotation=90})
  -- Everything else sits on the canvas; layout() runs now and whenever the root changes size.
  L,P,board=nil,nil,nil
  local relayout
  canvas,relayout=T.canvas(root,function(c) L=c;layout() end)
  canvas.ZIndex=1
  local drag=T.make('TextButton',canvas,{Name='DragArea',Text='',BackgroundTransparency=1,Size=UDim2.fromScale(1,1),AutoButtonColor=false,Selectable=false,ZIndex=1})
  -- Pans and zooms under the cards on purpose (they draw over it), so the layout audit skips it.
  board=T.make('Frame',canvas,{Name='Board',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Size=UDim2.fromOffset(0,0),ZIndex=2})
  board:SetAttribute('AuditIgnore',true)
  boardScale=T.make('UIScale',board,{Scale=1})
  local linkLayer=T.make('Frame',board,{Name='Links',BackgroundTransparency=1,Size=UDim2.fromOffset(0,0),ZIndex=2})
  fxLayer=T.make('Frame',board,{Name='Effects',BackgroundTransparency=1,Size=UDim2.fromOffset(0,0),ZIndex=3})
  local nodeLayer=T.make('Frame',board,{Name='Nodes',BackgroundTransparency=1,Size=UDim2.fromOffset(0,0),ZIndex=5})
  table.clear(nodes);table.clear(links);table.clear(lastState);table.clear(groups)
  for _,d in Skills.List do
   if d.parent then makeLink(linkLayer,d) end
   makeNode(nodeLayer,d)
  end
  -- Selection frame: white corner accents that breathe around the chosen skill.
  selection=T.make('ImageLabel',nil,{Name='Selection',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Image=T.Asset.corners,ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=.5,ImageColor3=WHITE,ZIndex=9})
  local ss=T.make('UIScale',selection,{Scale=1})
  TweenService:Create(ss,TweenInfo.new(.7,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,-1,true),{Scale=1.06}):Play()
  bindInput(drag)
  pending=nil
  refresh(false)
  -- Gamepad: start on the cheapest skill that can be bought right now (else the last one viewed).
  if inputKind()=='Gamepad' then
   local best
   for _,d in Skills.List do
    if Skills.state(owned,d.id)=='available' and d.cost<=gems and (not best or d.cost<best.cost) then best=d end
   end
   if best then selected=best.id end
  end
  hudProfile=profile;animateHud=true
  relayout() -- HUD, info card, bonuses and the board fit for this screen
  self.Select(selected)
  T.gamepadSelect(nodes[selected].holder)
  if opts.onVisible then opts.onVisible(false) end
  T.hideTouchControls('SkillTree',true)
  table.insert(conns,Input.LastInputTypeChanged:Connect(paintHint))
  pcall(function() table.insert(conns,Input:GetPropertyChangedSignal('PreferredInput'):Connect(paintHint)) end)
  -- Emeralds and skills change on purchase (and when Studio test buttons grant emeralds).
  table.insert(conns,player.AttributeChanged:Connect(function(name)
   if name=='ProfileSkills' or name=='ProfileGems' or name=='ProfileLoaded' then refresh(true) end
  end))
  playOpen()
  return {Root=root,Close=self.Close}
 end

 function self.Close()
  if not root then return end
  for _,c in conns do c:Disconnect() end
  table.clear(conns)
  CAS:UnbindAction(PAD_ACTION)
  stopGlide()
  local r=root;root=nil;r:Destroy()
  if blur then blur:Destroy();blur=nil end
  if gemsCounter then gemsCounter:Destroy();gemsCounter=nil end
  board,fxLayer,info,bonusPanel,selection,gemsValue,gemsPill=nil,nil,nil,nil,nil,nil,nil
  canvas,L,P,hint,dragging,pinching=nil,nil,nil,nil,nil,false
  table.clear(groups)
  pending=nil
  screen.Enabled=false
  T.hideTouchControls('SkillTree',false)
  if opts.onVisible then opts.onVisible(true) end
 end

 function self.IsOpen() return root~=nil end
 -- Same path as the BUY button (also used by gamepad/keyboard shortcuts and Studio tests).
 function self.Buy(id) if root then self.Select(id);buy(id) end end
 -- Leaving the lobby or respawning closes the tree.
 player.CharacterRemoving:Connect(function() self.Close() end)
 return self
end

return U
