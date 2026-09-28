-- Full-screen Skill Tree (lobby), green theme (UITheme).
-- Opening: a ring ripples out from the centre star and the nodes spring outward in waves.
-- Buying: the node squashes and pops lime with a flash, a ring and a few sparks, the links to its
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
local T=require(RS:WaitForChild('UITheme'))
local FX=require(RS:WaitForChild('StoreFX'))
local combat=RS:WaitForChild('RogueliteCombat')
local Skills=require(combat:WaitForChild('SkillTreeConfig'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local C=T.Color
local U={}

-- Authored at 1920x1080 and scaled to the viewport (like ArmoryUI). The board also zooms.
local DW,DH=1920,1080
local UNIT=150 -- board pixels between grid units
local SIZE={root=150,capstone=128,node=108}
local ZOOM_MIN,ZOOM_MAX=.5,1.25
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
 s.Parent=SoundService;SoundService:PlayLocalSound(s)
 task.delay(5,function() s:Destroy() end)
end
local function textWidth(text,size) return TextService:GetTextSize(text,size,T.Font,Vector2.new(2000,200)).X end
local function centred(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
local function left(l) l.TextXAlignment=Enum.TextXAlignment.Left;return l end

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
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='SkillTree',ResetOnSpawn=false,DisplayOrder=58,IgnoreGuiInset=true,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,Enabled=false})
 self.Screen=screen
 local root,blur,shade,board,boardScale,fxLayer
 local groups={}
 local nodes,links={},{}
 local owned,gems={Root=true},0
 local lastState={}
 local selected=Skills.ROOT
 local zoom,pan=1,Vector2.zero
 local fitScale=1
 local pending -- node id sent to the server, celebrated when ProfileSkills confirms it
 local shownGems=0
 local gemsValue,gemsPill,gemsCounter
 local info,bonusPanel,selection
 local conns={}

 local function readProfile()
  local p=opts.profile()
  gems=p.gems or 0
  owned=Skills.parse(player:GetAttribute('ProfileSkills'))
  return p
 end

 -- Layout ----------------------------------------------------------------------
 local function group(name,anchor,pos,w,h)
  local f=T.frame(root,name,0,0,w,h);f.AnchorPoint=anchor;f.Position=pos;f.ZIndex=20
  groups[f]=T.make('UIScale',f,{Scale=1})
  return f
 end
 local function extent()
  -- Half-size of the board in pixels at the current scale, for clamping the pan.
  local s=fitScale*zoom
  return 5.8*UNIT*s,5.8*UNIT*s
 end
 local function place()
  if not board then return end
  local ex,ey=extent()
  pan=Vector2.new(math.clamp(pan.X,-ex,ex),math.clamp(pan.Y,-ey,ey))
  board.Position=UDim2.new(.5,pan.X,.5,pan.Y-10*fitScale)
  boardScale.Scale=fitScale*zoom
 end
 local function fit()
  local v=workspace.CurrentCamera.ViewportSize
  if v.X<=0 then return end
  fitScale=math.clamp(math.min(v.X/DW,v.Y/DH),.4,1.25)
  for _,sc in groups do sc.Scale=fitScale end
  place()
 end
 -- Zoom so everything the player can see (owned, buyable and next-up nodes) fits between the
 -- title and the info card. The tree zooms out on its own as it grows.
 local function fittedZoom()
  local mx,my=1,1
  for _,d in Skills.List do
   if Skills.state(owned,d.id)~='hidden' then mx=math.max(mx,math.abs(d.x));my=math.max(my,math.abs(d.y)) end
  end
  local availW,availH=DW/2-420,DH/2-190
  return math.clamp(math.min(availW/((mx+.8)*UNIT),availH/((my+.8)*UNIT)),ZOOM_MIN,1.15)
 end
 local function autoZoom() zoom=fittedZoom();pan=Vector2.zero end
 -- When a purchase grows the tree past the view, ease the camera out to fit it.
 local zoomTween
 local function easeToFit()
  local target=fittedZoom()
  if target>=zoom-.01 then return end
  if zoomTween then zoomTween:Destroy() end
  local v=Instance.new('NumberValue');v.Value=zoom;zoomTween=v
  v.Changed:Connect(function(x) if zoomTween==v then zoom=x;pan*=.9;place() end end)
  tween(v,.6,{Value=target},Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,.35)
  task.delay(1.1,function() if zoomTween==v then v:Destroy();zoomTween=nil end end)
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
 -- Expanding outline ring (open ripple and purchase ripple).
 local function ring(at,from,to,time,thickness,color,delay)
  local r=T.make('Frame',fxLayer,{Name='Ripple',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(at.X,at.Y),Size=UDim2.fromOffset(from,from),ZIndex=3})
  T.make('UICorner',r,{CornerRadius=UDim.new(1,0)})
  local stroke=T.make('UIStroke',r,{Color=color or C.lime,Thickness=thickness or 4,Transparency=delay and 1 or .1})
  task.delay(delay or 0,function()
   if not r.Parent then return end
   stroke.Transparency=.1
   tween(r,time,{Size=UDim2.fromOffset(to,to)},Enum.EasingStyle.Sine)
   tween(stroke,time,{Transparency=1,Thickness=1},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
  end)
  task.delay((delay or 0)+time+.05,function() r:Destroy() end)
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
  ring(at,size,size*3.2,.55,5,d.kind=='capstone' and C.gold or C.lime)
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
  setGems(animated)
  if animated then easeToFit() end
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
  for _,c in body:GetChildren() do c:Destroy() end
  info.Buy=nil
  if Skills.state(owned,selected)=='hidden' then selected=Skills.ROOT end
  local d=Skills.ById[selected];local st=d.kind=='root' and 'owned' or Skills.state(owned,d.id)
  local mystery=st=='known' or st=='hidden'
  local tile=T.panel(body,'IconTile',16,16,118,118,d.kind=='root' and 'panel' or st=='owned' and 'button' or st=='available' and 'panel' or 'inset')
  if not mystery then T.icon(tile,'Icon',14,14,90,d.icon)
  else T.label(tile,'Q','?',0,0,118,118,60,C.dim) end
  local title=left(T.label(body,'Name',mystery and '???' or d.name,152,12,440,42,32,mystery and C.muted or C.white));title.TextWrapped=false
  local lines=Skills.lines(d)
  local effect=mystery and 'A skill you haven\'t found yet.' or d.kind=='root' and d.blurb or table.concat(lines,'   ·   ')
  left(T.label(body,'Effect',effect,152,56,450,32,d.kind=='root' and 18 or 24,d.kind=='root' and C.muted or C.limeSoft)).TextWrapped=true
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
  T.text(body,'Sub',sub,152,92,450,34,18,C.muted)
  -- Right side: BUY / OWNED / LOCKED.
  if st=='available' then
   local afford=d.cost<=gems
   local b=T.button(body,'Buy','',620,26,212,74,function() buy(d.id) end)
   b.Caption.Visible=false;b.Interactable=afford
   info.Buy=b
   local row=T.make('Frame',b,{Name='Row',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromOffset(200,50),ZIndex=3})
   T.make('UIListLayout',row,{FillDirection=Enum.FillDirection.Horizontal,HorizontalAlignment=Enum.HorizontalAlignment.Center,VerticalAlignment=Enum.VerticalAlignment.Center,Padding=UDim.new(0,8),SortOrder=Enum.SortOrder.LayoutOrder})
   local l1=T.label(row,'Buy','BUY',0,0,textWidth('BUY',30)+4,44,30);l1.LayoutOrder=1;l1.TextWrapped=false;l1.ZIndex=3
   local l2=T.label(row,'Cost',tostring(d.cost),0,0,textWidth(tostring(d.cost),30)+4,44,30,afford and C.white or C.negative);l2.LayoutOrder=2;l2.TextWrapped=false;l2.ZIndex=3
   local k=T.icon(row,'Key',0,0,40,'emerald');k.LayoutOrder=3;k.ZIndex=3
   if afford then FX.pulse(b,.03)
   else centred(T.label(body,'Need','Need '..fmt(d.cost-gems)..' more emeralds',600,104,252,28,18,C.negative)) end
  elseif st=='owned' then
   centred(T.label(body,'Owned',d.kind=='root' and 'SKILL TREE' or 'OWNED',600,34,252,56,d.kind=='root' and 30 or 40,C.lime))
  else
   centred(T.label(body,'Locked','LOCKED',600,34,252,56,36,C.dim))
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

 local function drawHud(profile)
  -- Top: title plate and key pill.
  local top=group('Top',Vector2.new(.5,0),UDim2.new(.5,0,0,18),600,150)
  local p,w=plate(top,'SKILL TREE',0,0,40);p.Position=UDim2.fromOffset((600-w)/2,0)
  gemsPill=T.panel(top,'Emeralds',190,78,220,58,'inset')
  T.icon(gemsPill,'Icon',10,6,46,'emerald')
  gemsValue=left(T.label(gemsPill,'Value',fmt(gems),64,6,140,46,30,C.emerald));gemsValue.TextWrapped=false
  shownGems=gems
  if not profile.connected or RunService:IsStudio() then
   local chip=T.chip(top,'PreviewChip',profile.connected and 'STUDIO TEST · NOT SAVED' or 'PROFILE LOADING',0,142,Color3.fromRGB(58,48,20),C.gold)
   chip.AnchorPoint=Vector2.new(.5,0);chip.Position=UDim2.fromOffset(300,142)
  end
  -- Left: running totals of every bonus the tree gives.
  local side=group('Bonuses',Vector2.new(0,.5),UDim2.new(0,24,.5,-10),340,640)
  local panel=T.panel(side,'Panel',0,0,340,560,'panel')
  left(T.label(panel,'Title','YOUR BONUSES',22,16,300,34,26))
  local progress=left(T.label(panel,'Progress','',22,52,300,24,18,C.muted));progress.TextWrapped=false
  local bar=T.bar(panel,'Bar',22,80,296,10) -- the fill; T.setBar animates it
  local list=T.make('Frame',panel,{Name='List',BackgroundTransparency=1,Position=UDim2.fromOffset(22,104),Size=UDim2.fromOffset(300,440),ZIndex=21})
  T.make('UIListLayout',list,{Padding=UDim.new(0,6),SortOrder=Enum.SortOrder.LayoutOrder})
  bonusPanel={Frame=panel,Progress=progress,Bar=bar,List=list}
  local hint=T.text(side,'Hint','Drag to look around  ·  Scroll to zoom',6,570,330,24,16,C.muted)
  hint.TextXAlignment=Enum.TextXAlignment.Left
  if RunService:IsStudio() then
   -- Studio-only test helpers (server refuses them outside Studio).
   local function dev(action)
    task.spawn(function()
     local ok,r=pcall(request,action)
     if not ok then r=nil end
     if type(r)=='table' and r.message then T.toast(screen,r.message,r.ok and C.lime or C.negative) end
    end)
   end
   local a=T.button(side,'DevEmeralds','+200 EMERALDS',0,600,160,40,function() dev('DevEmeralds') end,true);a.Caption.TextSize=17
   local b=T.button(side,'DevReset','RESET TREE',172,600,168,40,function() dev('DevResetSkills') end,true);b.Caption.TextSize=17
  end
  -- Bottom: info card for the selected skill.
  local bottom=group('Info',Vector2.new(.5,1),UDim2.new(.5,0,1,-20),872,150)
  local card=T.panel(bottom,'Card',0,0,872,150,'panel')
  info={Card=card,Body=T.frame(card,'Body',0,0,872,150)}
  -- Close (same red button as the Armory).
  local closeGroup=group('Close',Vector2.new(1,1),UDim2.new(1,-24,1,-20),240,86)
  local close=T.button(closeGroup,'Close','CLOSE',0,0,240,86,function() self.Close() end,true)
  T.setTier(close,4);close.Caption.TextSize=40
  -- HUD slides in with the board.
  for f,_ in groups do
   local home=f.Position
   f.Position=home+UDim2.fromOffset(0,f.AnchorPoint.Y>=1 and 40 or f.AnchorPoint.Y==0 and -40 or 0)+UDim2.fromOffset(f.AnchorPoint.X==0 and -40 or 0,0)
   tween(f,.32,{Position=home},Enum.EasingStyle.Quad,Enum.EasingDirection.Out,.12)
  end
 end

 -- Pan and zoom ----------------------------------------------------------------------
 local dragging,dragStart,panStart
 local function zoomAt(factor,screenPoint)
  local old=zoom
  zoom=math.clamp(zoom*factor,ZOOM_MIN,ZOOM_MAX)
  if zoom==old then return end
  -- Keep the board point under the cursor fixed while zooming.
  local v=workspace.CurrentCamera.ViewportSize
  local centre=v/2+pan+Vector2.new(0,-10*fitScale)
  local rel=(screenPoint-centre)/(fitScale*old)
  pan=screenPoint-rel*fitScale*zoom-v/2-Vector2.new(0,-10*fitScale)
  place()
 end
 local function bindInput(drag)
  drag.InputBegan:Connect(function(input)
   if input.UserInputType==Enum.UserInputType.MouseButton1 or input.UserInputType==Enum.UserInputType.Touch then
    dragging=input;dragStart=Vector2.new(input.Position.X,input.Position.Y);panStart=pan
   end
  end)
  table.insert(conns,Input.InputChanged:Connect(function(input)
   if not root then return end
   if dragging and (input.UserInputType==Enum.UserInputType.MouseMovement or input==dragging) then
    pan=panStart+Vector2.new(input.Position.X,input.Position.Y)-dragStart;place()
   elseif input.UserInputType==Enum.UserInputType.MouseWheel then
    zoomAt(input.Position.Z>0 and 1.1 or 1/1.1,Vector2.new(input.Position.X,input.Position.Y))
   end
  end))
  table.insert(conns,Input.InputEnded:Connect(function(input)
   if input==dragging or input.UserInputType==Enum.UserInputType.MouseButton1 then dragging=nil end
  end))
  table.insert(conns,Input.TouchPinch:Connect(function(points,scale,_,state)
   if not root or #points<2 then return end
   if state==Enum.UserInputState.Begin then drag:SetAttribute('PinchZoom',zoom) end
   local start=drag:GetAttribute('PinchZoom') or zoom
   local mid=(points[1]+points[2])/2
   zoomAt(math.clamp(start*scale,ZOOM_MIN,ZOOM_MAX)/zoom,mid)
  end))
 end

 -- Opening ripple ---------------------------------------------------------------------
 local function playOpen()
  play(Skills.Sounds.Open,.3,1.05)
  tween(shade,.3,{BackgroundTransparency=.28})
  tween(blur,.3,{Size=16})
  local maxDepth=1
  for _,d in Skills.List do if Skills.state(owned,d.id)~='hidden' then maxDepth=math.max(maxDepth,d.depth) end end
  -- Two rings roll out from the star; nodes spring out on the wavefront.
  ring(Vector2.zero,60,(maxDepth+1.2)*UNIT*2,1.05,6,C.lime,.02)
  ring(Vector2.zero,60,(maxDepth+1.2)*UNIT*2,1.2,3,C.limeSoft,.16)
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
  shade=T.make('Frame',root,{Name='Shade',Size=UDim2.fromScale(1,1),BackgroundColor3=C.shade,BackgroundTransparency=1,BorderSizePixel=0,ZIndex=0})
  T.make('UIGradient',shade,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.25),NumberSequenceKeypoint.new(.5,.05),NumberSequenceKeypoint.new(1,.25)}),Rotation=90})
  local drag=T.make('TextButton',root,{Name='DragArea',Text='',BackgroundTransparency=1,Size=UDim2.fromScale(1,1),AutoButtonColor=false,ZIndex=1})
  board=T.make('Frame',root,{Name='Board',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Size=UDim2.fromOffset(0,0),ZIndex=2})
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
  drawHud(profile)
  bindInput(drag)
  pending=nil
  refresh(false)
  autoZoom()
  fit()
  self.Select(selected)
  if opts.onVisible then opts.onVisible(false) end
  table.insert(conns,workspace.CurrentCamera:GetPropertyChangedSignal('ViewportSize'):Connect(fit))
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
  local r=root;root=nil;r:Destroy()
  if blur then blur:Destroy();blur=nil end
  if gemsCounter then gemsCounter:Destroy();gemsCounter=nil end
  board,fxLayer,info,bonusPanel,selection,gemsValue,gemsPill=nil,nil,nil,nil,nil,nil,nil
  pending=nil
  screen.Enabled=false
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
