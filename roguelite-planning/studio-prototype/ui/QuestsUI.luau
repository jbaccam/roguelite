-- Quests window: DAILY (the streak strip and today's quest cards), WEEKLY (this week's 3 quests) and
-- ACHIEVEMENTS (10-level roads, feats and unlocks), drawn as colour cards (StoreFX); plus the lobby's
-- left-side tracker (Q.tracker). It shows the server's ProfileQuests view (QuestService) through
-- QuestConfig; every CLAIM asks the server (ProfileAction ClaimQuest / ClaimStreak / ClaimWeekly /
-- ClaimRoad / ClaimFeat / ClaimUnlock), which checks it and grants the reward; once it says yes, a
-- short flat CLAIM effect plays (Q.claimFX, user 2026-10-03).
-- plans/2026-10-01-H-store-and-quests.md, plans/2026-10-02-K-quests-power-ui.md,
-- plans/2026-10-02-M-feats-weekly-roads.md
local RS=game:GetService('ReplicatedStorage')
local TextService=game:GetService('TextService')
local TweenService=game:GetService('TweenService')
local T=require(RS:WaitForChild('UITheme'))
local FX=require(RS:WaitForChild('StoreFX'))
local combat=RS:WaitForChild('RogueliteCombat')
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local Chests=require(combat:WaitForChild('ChestConfig'))
local Armor=require(combat:WaitForChild('ArmorCatalog'))
local WeaponArt=require(RS:WaitForChild('WeaponInventoryUI'))
local WeaponIcons=WeaponArt.Icons
local C=T.Color
local Q={}

-- Window content 1480 x 840 (plan K; it was 1100 x 640). W: the body's width; SW: the list's
-- width inside the scroll bar; CW: a full-width card.
local WIN_W,WIN_H=1480,840
local W=WIN_W-36;local SW=W-14;local CW=SW-4
local INK=FX.INK
Q.Locked=Color3.fromRGB(96,106,112)
-- Rims on the last two levels: Grandmaster gold, Legend red and pulsing.
Q.Rims={[9]={Color3.fromRGB(255,203,64),false},[10]={Color3.fromRGB(255,58,82),true}}
local function center(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
local function left(l) l.TextXAlignment=Enum.TextXAlignment.Left;return l end
local function weaponId(name) for id,w in Weapons.ById do if w.name==name then return id end end end
local function textWidth(s,size) return TextService:GetTextSize(s,size,T.Font,Vector2.new(4000,200)).X end
local function resetText() local sec=86400-os.time()%86400;return string.format('%02d:%02d:%02d',sec//3600,sec%3600//60,sec%60) end
-- Time to the next Monday 00:00 UTC: '3d 04h', or 'hh:mm:ss' on the last day.
local function weekText(Config)
 local now=os.time();local sec=Config.weekResetIn(now//86400,86400-now%86400)
 if sec>=86400 then return string.format('%dd %02dh',sec//86400,sec%86400//3600) end
 return string.format('%02d:%02d:%02d',sec//3600,sec%3600//60,sec%60)
end

-- Slots for a reward: {asset, label, rarity, amount, kind, count}; kind ('emerald'/'chest') and
-- count tell the CLAIM effect what to throw.
function Q.rewardTiles(Config,r,signature)
 local out={}
 if r.emeralds and r.emeralds>0 then table.insert(out,{'emerald',Config.comma(r.emeralds),'Emerald',nil,'emerald',r.emeralds}) end
 for _,kind in {'Wooden','Silver','Gold','Magical','Legendary'} do
  local n=r.chests and r.chests[kind]
  if n and n>0 then table.insert(out,{Chests.ById[kind].icon,kind,FX.ChestRarity[kind],n>1 and ('×'..n) or nil,'chest',n}) end
 end
 if r.class then table.insert(out,{WeaponIcons[signature and signature[r.class] or ''] or 'profile',r.class,'Rare'}) end
 if r.weapon then local id=weaponId(r.weapon);table.insert(out,{(id and WeaponIcons[id]) or (WeaponArt.IconsByName and WeaponArt.IconsByName[r.weapon]) or 'armory',r.weapon,'Legendary'}) end
 if r.armorSet then local set=Armor.ById[r.armorSet];table.insert(out,{Armor.Icons[Armor.pieceId(r.armorSet,'Chest')],set and set.name or r.armorSet,set and set.rarity or 'Epic'}) end
 return out
end

-- What can be claimed right now, from the view: daily (quests + streak), achievements (roads, feats
-- and unlocks) and weekly.
function Q.counts(Config,view)
 local daily,ach,weekly=0,0,0
 for _,d in view.daily or {} do local q=Config.DailyById[d.id];if q and not d.claimed and d.progress>=q.target then daily+=1 end end
 daily+=#(view.streak and view.streak.pending or {})
 for _,w in view.weekly or {} do local q=Config.WeeklyById[w.id];if q and not w.claimed and w.progress>=q.target then weekly+=1 end end
 for _,r in Config.Roads do
  local t=((view.roads or {})[r.id] or 0)+1
  if r.targets[t] and ((view.stats or {})[r.stat] or 0)>=r.targets[t] then ach+=1 end
 end
 for _,u in Config.Unlocks do local s=(view.unlocks or {})[u.id];if s and not s.claimed and s.have>=s.need then ach+=1 end end
 for _,f in Config.Feats do local s=(view.feats or {})[f.id];if s and not s.claimed and s.have>=s.need then ach+=1 end end
 return daily,ach,weekly
end

-- CLAIM effect (user, 2026-10-03) ----------------------------------------------------------------
-- Once the server says a claim worked: the reward slots pop, emeralds splatter out and fly into the
-- HUD's emerald counter, a chest squashes and stretches in a sparkle ring, a title card gets a shine
-- sweep, all over a soft glow (~1 s). The window redraws on the result (a claimed row re-sorts), so
-- the slots are copied at click time (Q.snapshot) and the effect plays from where they were, on its
-- own layer in the ScreenGui above the window. Flat images and tweens only (no 3D effects); nothing
-- in it takes input, and the layer and everything in it is destroyed after 1.7 s.
local RunService=game:GetService('RunService')
local STAR='rbxassetid://119142062258395' -- ChestFX.Tex.star
local RING='rbxassetid://112313196019616' -- ChestFX.Tex.ring
local WHITE=Color3.new(1,1,1)
local function tween(o,time,props,style,dir)
 local tw=TweenService:Create(o,TweenInfo.new(time,style or Enum.EasingStyle.Quad,dir or Enum.EasingDirection.Out),props);tw:Play();return tw
end
local function later(t,o,fn) task.delay(t,function() if o.Parent then fn() end end) end
local function commas(n) local s=tostring(math.floor(n));local k;repeat s,k=s:gsub('^(%d+)(%d%d%d)','%1,%2') until k==0;return s end
-- Reward slots say what they are: ClaimKind ('emerald', 'chest', 'title' or 'item'), ClaimAmount
-- and ClaimColor (the flash colour).
local function tagReward(o,kind,amount,color)
 o:SetAttribute('ClaimKind',kind);o:SetAttribute('ClaimAmount',amount);o:SetAttribute('ClaimColor',color)
 return o
end
local function rewardTile(parent,name,x,y,size,it)
 return tagReward(FX.tile(parent,name,x,y,size,it[1],it[2],it[3],it[4]),it[5] or 'item',it[6],(FX.Rarity[it[3]] or FX.Rarity.Common).top)
end
local function rewardsOf(face)
 local out={}
 for _,c in face:GetChildren() do if c:GetAttribute('ClaimKind') then table.insert(out,c) end end
 return out
end
-- Each slot's place on screen now, plus a copy to pop.
function Q.snapshot(parts)
 local out={}
 for _,o in parts do
  if o.Parent and o.AbsoluteSize.X>0 then
   table.insert(out,{kind=o:GetAttribute('ClaimKind'),amount=o:GetAttribute('ClaimAmount'),color=o:GetAttribute('ClaimColor'),
    pos=o.AbsolutePosition,size=o.AbsoluteSize,design=o.Size.X.Offset,copy=o:Clone()})
  end
 end
 return out
end
local function fadeOut(root,time)
 local all=root:GetDescendants();table.insert(all,root)
 for _,o in all do
  local goal={}
  if o:IsA('GuiObject') and o.BackgroundTransparency<1 then goal.BackgroundTransparency=1 end
  if o:IsA('ImageLabel') then goal.ImageTransparency=1 end
  if o:IsA('TextLabel') then goal.TextTransparency=1;goal.TextStrokeTransparency=1 end
  if o:IsA('UIStroke') then goal.Transparency=1 end
  if next(goal) then tween(o,time,goal,Enum.EasingStyle.Quad,Enum.EasingDirection.In) end
 end
end
-- Scale punch on a live element (the HUD counter, the tracker's check), from `from` if given. Its
-- UIScale goes again once no effect needs it; an element with its own UIScale is left alone.
local punching={}
local function punch(o,peak,from)
 if not (o and o.Parent) then return end
 local s=o:FindFirstChild('ClaimPop')
 if not s then
  if o:FindFirstChildOfClass('UIScale') then return end
  s=T.make('UIScale',o,{Name='ClaimPop',Scale=1})
 end
 punching[s]=(punching[s] or 0)+1
 if from then s.Scale=from end
 tween(s,.07,{Scale=peak})
 later(.07,s,function() tween(s,.24,{Scale=1},Enum.EasingStyle.Back) end)
 task.delay(.45,function() punching[s]-=1;if punching[s]<=0 then punching[s]=nil;s:Destroy() end end)
end
-- The lobby HUD's emerald counter icon (LobbyUI: HUD.Left.Gems.Icon) while it is on screen.
local function emeraldCounter(screen)
 local hud=screen:FindFirstChild('HUD');local side=hud and hud:FindFirstChild('Left')
 local row=side and side:FindFirstChild('Gems');local icon=row and row:FindFirstChild('Icon')
 if icon and hud.Visible and side.Visible and icon.AbsoluteSize.X>0 then return icon end
end
-- Stars flying out of c to about `spread` (x, y) away, spinning and fading.
local function sparkles(layer,c,base,spread,n,color)
 for i=1,n do
  local a=(i+math.random()*.6)/n*math.pi*2;local dir=Vector2.new(math.cos(a),math.sin(a))
  local size=math.max(8,base*(.16+math.random()*.12));local d=.7+math.random()*.5
  local p=c+dir*base*.3
  local st=T.make('ImageLabel',layer,{Name='Sparkle',BackgroundTransparency=1,Image=STAR,ImageColor3=color:Lerp(WHITE,.55),AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(p.X,p.Y),Size=UDim2.fromOffset(size,size),Rotation=math.random(0,90),ZIndex=4})
  tween(st,.45,{Position=UDim2.fromOffset(c.X+dir.X*spread.X*d,c.Y+dir.Y*spread.Y*d),Rotation=st.Rotation+math.random(-140,140)},Enum.EasingStyle.Quart)
  tween(st,.45,{ImageTransparency=1,Size=UDim2.fromOffset(size*.3,size*.3)},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
 end
end
-- shots: Q.snapshot entries {kind, amount, color, pos, size, design, copy}; copy may be nil.
-- Positions are AbsolutePosition minus the ScreenGui's own, so top-bar and safe-area insets cancel.
function Q.claimFX(screen,shots)
 if not (screen and screen.Parent and screen.Enabled) or #shots==0 then
  for _,s in shots do if s.copy then s.copy:Destroy() end end;return
 end
 local layer=T.make('Frame',screen,{Name='ClaimFX',BackgroundTransparency=1,BorderSizePixel=0,Size=UDim2.fromScale(1,1),ZIndex=45,Active=false,Interactable=false})
 task.delay(1.7,function() layer:Destroy() end)
 local origin=screen.AbsolutePosition
 local counter=emeraldCounter(screen)
 local goal=counter and counter.AbsolutePosition+counter.AbsoluteSize/2-origin
 local function image(name,asset,p,size,color,z)
  return T.make('ImageLabel',layer,{Name=name,BackgroundTransparency=1,Image=asset,ImageColor3=color,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(p.X,p.Y),Size=UDim2.fromOffset(size,size),ZIndex=z})
 end
 local gems,total={},0
 for _,s in shots do
  local c=s.pos+s.size/2-origin;local base=math.min(s.size.X,s.size.Y);local color=s.color or C.gold
  -- Soft flash under the slot: glow and fast rays (StoreFX.burst) that grow as they fade.
  local burst,rays=FX.burst(layer,c.X,c.Y,base*1.5,color,150);burst.ZIndex=1
  burst.Glow.ImageTransparency=.1;rays.ImageTransparency=.3
  tween(burst,.45,{Size=UDim2.fromOffset(base*3,base*3)},Enum.EasingStyle.Quart)
  tween(burst.Glow,.55,{ImageTransparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
  tween(rays,.5,{ImageTransparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
  -- The slot pops: punch up 22%, settle with a small bounce, then lift away and fade (0.7 s).
  local g=s.copy
  if g then
   local k=s.size.X/math.max(s.design,1) -- the window's scale, so the copy matches on phones too
   g.AnchorPoint=Vector2.new(.5,.5);g.Position=UDim2.fromOffset(c.X,c.Y);g.ZIndex=2
   local sc=g:FindFirstChildOfClass('UIScale') or T.make('UIScale',g,{})
   sc.Scale=k;g.Parent=layer
   tween(sc,.08,{Scale=k*1.22})
   later(.08,g,function() tween(sc,.26,{Scale=k},Enum.EasingStyle.Back) end)
   later(.48,g,function() fadeOut(g,.22);tween(g,.22,{Position=UDim2.fromOffset(c.X,c.Y-base*.15)}) end)
  end
  if s.kind=='chest' then
   -- Squash and stretch on the chest art, from its base, inside a sparkle ring.
   local icon=g and g:FindFirstChild('Icon')
   if icon and icon:IsA('ImageLabel') then
    local p,z=icon.Position,icon.Size
    icon.ScaleType=Enum.ScaleType.Stretch;icon.AnchorPoint=Vector2.new(.5,1)
    icon.Position=p+UDim2.fromOffset(z.X.Offset/2,z.Y.Offset)
    local function to(x,y,t,style) tween(icon,t,{Size=UDim2.fromOffset(z.X.Offset*x,z.Y.Offset*y)},style) end
    to(1.3,.7,.07)
    later(.07,icon,function() to(.85,1.25,.1) end)
    later(.17,icon,function() to(1,1,.3,Enum.EasingStyle.Back) end)
   end
   local ring=image('Ring',RING,c,base*.6,color:Lerp(WHITE,.35),3)
   tween(ring,.45,{Size=UDim2.fromOffset(base*2.4,base*2.4)},Enum.EasingStyle.Quart)
   tween(ring,.45,{ImageTransparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
   sparkles(layer,c,base,Vector2.new(base,base),8,color)
  elseif s.kind=='title' then
   -- One quick shine sweep across the title card.
   if g then
    local clip=T.make('Frame',g,{Name='ClaimShine',BackgroundTransparency=1,ClipsDescendants=true,Position=UDim2.fromOffset(5,5),Size=UDim2.new(1,-10,1,-10),ZIndex=6})
    local bar=T.make('Frame',clip,{Name='Shine',BackgroundColor3=WHITE,BorderSizePixel=0,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.new(-.2,0,.5,0),Size=UDim2.new(0,56,2.5,0),Rotation=22,ZIndex=6})
    T.make('UIGradient',bar,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.5,.2),NumberSequenceKeypoint.new(1,1)})})
    tween(bar,.4,{Position=UDim2.new(1.2,0,.5,0)},Enum.EasingStyle.Quad,Enum.EasingDirection.InOut)
   end
   sparkles(layer,c,base,Vector2.new(s.size.X*.62,s.size.Y*.9),6,color)
  elseif s.kind=='emerald' then
   -- Emeralds splatter out of the slot (more for bigger amounts: 6 at 50, 12 from 1,500), mostly
   -- upwards, then each arcs into the counter; with no counter on screen they drop and fade.
   total+=s.amount or 0
   for _=1,math.clamp(6+math.floor((s.amount or 0)/250),6,12) do
    local a=-math.pi/2+(math.random()*2-1)*math.pi*.8;local dir=Vector2.new(math.cos(a),math.sin(a))
    local size=math.clamp(base*(.3+math.random()*.14),12,36)
    local p0=c+dir*base*.15;local p1=c+dir*base*((goal and .65 or .8)+math.random()*.7)
    local gem=image('Emerald',T.Asset.emerald,p0,size*.4,WHITE,3);gem.Rotation=math.random(-30,30)
    table.insert(gems,{img=gem,size=size,p0=p0,p1=p1,dir=dir,ctrl=p1+dir*base*.8,drop=base*1.6,drift=base*.5,
     burst=.2+math.random()*.1,fly=.3+math.random()*.12,r0=gem.Rotation,spin=(math.random()<.5 and -1 or 1)*(90+math.random()*180)})
   end
   sparkles(layer,c,base,Vector2.new(base,base),4,color)
  else
   sparkles(layer,c,base,Vector2.new(base,base),6,color)
  end
 end
 if #gems==0 then return end
 for i,g in gems do g.wait=.04+(i-1)*.022 end
 -- First emerald in: a glow on the counter and "+50" rising off it; every one bumps the counter.
 local function land(n)
  punch(counter,n==1 and 1.3 or 1.15)
  if n>1 then return end
  local cs=math.min(counter.AbsoluteSize.X,counter.AbsoluteSize.Y)
  local glow=image('CounterGlow',FX.Asset.glow,goal,cs*1.2,FX.Rarity.Emerald.top,1);glow.ImageTransparency=.15
  tween(glow,.4,{Size=UDim2.fromOffset(cs*3,cs*3)},Enum.EasingStyle.Quart)
  tween(glow,.45,{ImageTransparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
  if total<=0 then return end
  local text='+'..commas(total);local size=math.clamp(math.floor(cs*.6),14,30)
  local l=FX.title(layer,'Plus',text,goal.X+cs*.6,goal.Y-size*.75,textWidth(text,size)*1.15+12,size*1.5,size,C.emerald);l.ZIndex=6
  tween(l,.7,{Position=UDim2.fromOffset(goal.X+cs*.6,goal.Y-size*.75-cs*.7)})
  later(.35,l,function() fadeOut(l,.35) end)
 end
 local t0=os.clock();local arrived=0;local conn
 conn=RunService.Heartbeat:Connect(function()
  if not layer.Parent then conn:Disconnect();return end
  local t=os.clock()-t0;local live=false
  for _,g in gems do
   if g.img.Parent then
    live=true
    local pos,scale=g.p1,1
    if t<g.burst then
     local a=1-(1-t/g.burst)^3
     pos=g.p0:Lerp(g.p1,a);scale=.4+.6*a
    elseif goal then
     -- Ease-in along a curve that swings outwards first: it hangs, then gets pulled in.
     local a=math.clamp((t-g.burst-g.wait)/g.fly,0,1);local e=a*a
     pos=g.p1:Lerp(g.ctrl,e):Lerp(g.ctrl:Lerp(goal,e),e);scale=1-.5*e
     if a>=1 then g.img:Destroy();arrived+=1;land(arrived);continue end
    else
     local a=math.clamp((t-g.burst)/.45,0,1)
     pos=g.p1+g.dir*g.drift*a+Vector2.new(0,g.drop*a*a);g.img.ImageTransparency=a
     if a>=1 then g.img:Destroy();continue end
    end
    g.img.Position=UDim2.fromOffset(pos.X,pos.Y);g.img.Size=UDim2.fromOffset(g.size*scale,g.size*scale);g.img.Rotation=g.r0+g.spin*t
   end
  end
  if not live then conn:Disconnect() end
 end)
end

-- Rotated rank diamond with an upright icon on it; rim = {colour, pulses} for the top levels.
local function diamond(parent,name,cx,cy,size,color,asset,rim)
 local d=T.make('Frame',parent,{Name=name,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(cx,cy),Size=UDim2.fromOffset(size,size),Rotation=45,BackgroundColor3=Color3.new(1,1,1),BorderSizePixel=0})
 T.make('UICorner',d,{CornerRadius=UDim.new(0,math.floor(size*.18))})
 T.make('UIGradient',d,{Rotation=90,Color=ColorSequence.new(color:Lerp(Color3.new(1,1,1),.35),color:Lerp(Color3.new(0,0,0),.45))})
 local stroke=T.make('UIStroke',d,{Color=rim and rim[1] or INK,Thickness=rim and 4 or 3})
 if rim and rim[2] then TweenService:Create(stroke,TweenInfo.new(.9,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,-1,true),{Transparency=.65}):Play() end
 local icon
 if asset then icon=T.icon(parent,name..'Icon',cx-size*.42,cy-size*.42,size*.84,asset) end
 return d,icon
end

-- The lobby's left-side tracker (LobbyUI): one see-through panel holding today's quests (a finished
-- one gets its own CLAIM), the reset clock and the streak, with OPEN QUESTS under it. Rows sit in
-- the panel instead of each in its own box. ctx: config (QuestConfig or nil while it loads), open()
-- opens the Quests window, claim(i) claims daily quest i. Returns {Root, OpenButton, update(view)}.
Q.TRACKER_W,Q.TRACKER_H=372,382
local CLOCK_ICON='rbxassetid://79916703515403' -- hud/clock.png
local function hoursLeft() local sec=86400-os.time()%86400;return string.format('%dh %02dm',sec//3600,sec%3600//60) end
function Q.tracker(parent,x,y,ctx)
 local TW=Q.TRACKER_W
 local rowY,rowH=54,56
 local footY=rowY+4*rowH
 local root=T.frame(parent,'Goals',x,y,TW,Q.TRACKER_H)
 -- The panel itself opens the window; the CLAIM buttons sit on top of it.
 local panel=T.make('TextButton',root,{Name='Panel',Text='',AutoButtonColor=false,Size=UDim2.fromOffset(TW,footY+48),BackgroundColor3=INK,BackgroundTransparency=.38,BorderSizePixel=0})
 T.make('UICorner',panel,{CornerRadius=UDim.new(0,14)});T.make('UIStroke',panel,{Color=INK,Thickness=2,Transparency=.35})
 panel.Activated:Connect(ctx.open)
 T.icon(panel,'Icon',8,4,42,'quests')
 FX.title(panel,'Title','DAILY QUESTS',56,9,190,32,22)
 local pill=T.make('Frame',panel,{Name='Reset',Position=UDim2.fromOffset(TW-108,11),Size=UDim2.fromOffset(98,28),BackgroundColor3=C.well,BackgroundTransparency=.15,BorderSizePixel=0})
 T.make('UICorner',pill,{CornerRadius=UDim.new(1,0)});T.make('UIStroke',pill,{Color=INK,Thickness=2})
 T.icon(pill,'Icon',6,3,22,CLOCK_ICON)
 local timer=left(T.label(pill,'Time','',32,2,60,24,16));timer.TextWrapped=false
 local rule=T.make('Frame',panel,{Name='Rule',Position=UDim2.fromOffset(12,48),Size=UDim2.fromOffset(TW-24,2),BackgroundColor3=C.lime,BorderSizePixel=0})
 T.make('UIGradient',rule,{Transparency=NumberSequence.new(0,1)})
 local rows={}
 for i=1,4 do
  local row=T.frame(panel,'Quest'..i,0,rowY+(i-1)*rowH,TW,rowH)
  -- Gold mark on the left edge while a finished quest waits for CLAIM.
  local mark=T.make('Frame',row,{Name='Ready',Position=UDim2.fromOffset(4,9),Size=UDim2.fromOffset(4,rowH-18),BackgroundColor3=C.gold,BorderSizePixel=0,Visible=false})
  T.make('UICorner',mark,{CornerRadius=UDim.new(1,0)})
  local icon=T.icon(row,'Icon',14,8,40,'quests')
  local name=left(T.label(row,'Name','',62,5,206,24,18));name.TextWrapped=false
  local fill,track=T.bar(row,'Bar',62,34,150,10,C.lime)
  local count=left(T.label(row,'Count','',218,28,52,20,14,C.muted));count.TextWrapped=false
  local gem=T.icon(row,'Gem',TW-88,13,28,'emerald')
  local amount=left(T.label(row,'Amount','',TW-58,13,52,30,20,C.gold));amount.TextWrapped=false
  local chest=T.icon(row,'Chest',TW-30,2,22,Chests.ById.Silver.icon)
  local claim=FX.button(row,'Claim','CLAIM',TW-98,9,88,38,function()
   -- Remembered for the CLAIM effect, which plays once the server's view shows it claimed.
   local r=rows[i];r.Pending={id=r.Id,t=os.clock(),pos=r.Claim.AbsolutePosition,size=r.Claim.AbsoluteSize}
   ctx.claim(i)
  end)
  claim.Caption.TextSize=18;FX.pulse(claim,.05)
  local check=FX.check(row,TW-48,14,28)
  if i<4 then T.make('Frame',row,{Name='Divider',Position=UDim2.fromOffset(14,rowH-1),Size=UDim2.fromOffset(TW-28,1),BackgroundColor3=Color3.new(1,1,1),BackgroundTransparency=.88,BorderSizePixel=0}) end
  rows[i]={Row=row,Mark=mark,Icon=icon,Name=name,Track=track,Fill=fill,Count=count,Gem=gem,Amount=amount,Chest=chest,Claim=claim,Check=check}
 end
 -- Footer: the streak.
 T.make('Frame',panel,{Name='FootRule',Position=UDim2.fromOffset(12,footY),Size=UDim2.fromOffset(TW-24,2),BackgroundColor3=Color3.fromRGB(255,140,60),BackgroundTransparency=.5,BorderSizePixel=0})
 local flame=T.icon(panel,'Flame',12,footY+7,34,'quests')
 local streakText=left(FX.title(panel,'Streak','0 DAY STREAK',52,footY+10,190,28,19,Color3.fromRGB(255,206,140)))
 local today=T.text(panel,'Today','',TW-150,footY+13,138,22,16,C.muted);today.TextXAlignment=Enum.TextXAlignment.Right
 local openButton=FX.button(root,'OpenQuests','OPEN QUESTS',0,footY+58,TW,Q.TRACKER_H-footY-58,ctx.open,true)
 openButton.Caption.TextSize=21
 task.spawn(function() while root.Parent do timer.Text=hoursLeft();task.wait(20) end end)
 local self={Root=root,OpenButton=openButton}
 function self.update(view)
  view=view or {}
  local Config=ctx.config
  local daily=view.daily or {}
  local doneToday=0
  for i,r in rows do
   local d=daily[i];local q=d and Config and Config.DailyById[d.id]
   r.Row.Visible=q~=nil or i==1
   if q then
    local done=d.progress>=q.target;local ready=done and not d.claimed
    if done then doneToday+=1 end
    r.Icon.Image=Config.Icons[q.stat] or Config.Icons.quests;r.Icon.Visible=true;r.Icon.ImageTransparency=d.claimed and .45 or 0
    r.Name.Text=q.short or q.title;r.Name.TextColor3=d.claimed and C.muted or ready and C.gold or C.white
    r.Track.Visible=true;T.setBar(r.Fill,d.progress/q.target);r.Fill.BackgroundColor3=d.claimed and C.dim or done and C.gold or C.lime
    r.Count.Visible=not ready;r.Count.Text=Config.comma(math.min(d.progress,q.target))..' / '..Config.comma(q.target)
    r.Gem.Visible=not done;r.Amount.Visible=not done;r.Amount.Text='+'..q.emeralds
    r.Chest.Visible=not done and q.chests~=nil
    r.Claim.Visible=ready;r.Check.Visible=d.claimed==true;r.Mark.Visible=ready
    -- This row's CLAIM went through (user, 2026-10-03): emeralds from the button into the counter
    -- just above, and the check pops in. A click left unconfirmed for 8 s is forgotten.
    local p=r.Pending
    if p and (p.id~=d.id or os.clock()-p.t>8) then r.Pending=nil;p=nil end
    if p and d.claimed then
     r.Pending=nil
     Q.claimFX(root:FindFirstAncestorOfClass('ScreenGui'),{{kind='emerald',amount=q.emeralds,color=FX.Rarity.Emerald.top,pos=p.pos,size=p.size}})
     punch(r.Check,1.3,.3)
    end
    r.Id=d.id
   else
    r.Name.Text=i==1 and 'Quests appear once your profile loads' or '';r.Name.TextColor3=C.muted
    r.Icon.Visible=false;r.Track.Visible=false;r.Count.Visible=false;r.Gem.Visible=false;r.Amount.Visible=false
    r.Chest.Visible=false;r.Claim.Visible=false;r.Check.Visible=false;r.Mark.Visible=false
   end
  end
  if Config then flame.Image=Config.Icons.streak end
  local sk=view.streak
  streakText.Text=(sk and sk.count or 0)..' DAY STREAK'
  today.Text=sk and sk.today and 'today counted' or (doneToday..' / '..math.max(#daily,1)..' today')
 end
 self.update(nil)
 return self
end

-- ctx: config (QuestConfig), profile() (LobbyUI profile with .quests), selection, signature
-- (class -> signature weapon id), setRedraw(fn).
function Q.open(screen,ctx,tab)
 local Config=ctx.config
 local w=T.window(screen,'QuestsWindow','Quests',WIN_W,WIN_H,nil,{large=true,seeThrough=.05});local b=w.Body
 local sel=ctx.selection
 local function valid(t) return (t=='Daily' or t=='Weekly' or t=='Achievements') and t or nil end
 sel.questTab=valid(tab) or valid(sel.questTab) or 'Daily'
 local list,draw
 local view
 -- parts: the reward slots being claimed. They are copied before asking, because the redraw on the
 -- result can replace them before InvokeServer returns; the CLAIM effect plays only on success.
 local function act(action,a,parts)
  local shots=Q.snapshot(parts or {})
  local r=combat.ProfileAction:InvokeServer(action,a)
  if r.ok then T.sound('ui_purchase') end
  if r.ok and w.Root.Parent then Q.claimFX(screen,shots) else for _,s in shots do s.copy:Destroy() end end
  T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
 end

 local tabs={}
 function tabs.Daily()
  local daily=view.daily or {}
  -- 1. Streak strip: the flame and count, today's status, and the 7-milestone track.
  local sk=view.streak;local sh=150
  local face,th=FX.card(list,'Streak',2,8,CW,sh,'ember',true)
  FX.art(face,Config.Icons.streak,78,72,92,th,180)
  center(FX.title(face,'Count',tostring(sk.count),30,44,96,56,54))
  FX.title(face,'Days','DAY STREAK',150,20,240,40,30,th.tint)
  FX.sub(face,'Best','Best: '..sk.best..(sk.best==1 and ' day' or ' days'),152,60,220,22,17)
  local doneToday=0
  for _,d in daily do local q=Config.DailyById[d.id];if q and d.progress>=q.target then doneToday+=1 end end
  local pill=T.make('Frame',face,{Name='Today',Position=UDim2.fromOffset(150,98),Size=UDim2.fromOffset(222,32),BackgroundColor3=sk.today and C.limeDark or Color3.fromRGB(110,34,10),BorderSizePixel=0})
  T.make('UICorner',pill,{CornerRadius=UDim.new(1,0)});T.make('UIStroke',pill,{Color=INK,Thickness=2.5})
  center(FX.title(pill,'Text',sk.today and 'TODAY COUNTED' or ('TODAY: '..doneToday..' / '..#daily..' DONE'),10,3,202,26,17,not sk.today and Color3.fromRGB(255,206,140) or nil))
  local x0,x1,ty=430,CW-70,58
  local track=T.make('Frame',face,{Name='Track',Position=UDim2.fromOffset(x0,ty-9),Size=UDim2.fromOffset(x1-x0,18),BackgroundColor3=Color3.fromRGB(28,12,8),BorderSizePixel=0})
  T.make('UICorner',track,{CornerRadius=UDim.new(1,0)});T.make('UIStroke',track,{Color=INK,Thickness=3})
  local marks=Config.Streak;local n=#marks;local pos=sk.position
  local ratio=0
  if pos>=marks[n].day then ratio=1
  else
   for i=1,n-1 do
    if pos>=marks[i].day and pos<marks[i+1].day then ratio=((i-1)+(pos-marks[i].day)/(marks[i+1].day-marks[i].day))/(n-1);break end
   end
  end
  local fill=T.make('Frame',track,{Name='Fill',Size=UDim2.fromScale(ratio,1),BackgroundColor3=Color3.new(1,1,1),BorderSizePixel=0})
  T.make('UICorner',fill,{CornerRadius=UDim.new(1,0)});T.make('UIGradient',fill,{Rotation=90,Color=ColorSequence.new(Color3.fromRGB(255,200,70),Color3.fromRGB(232,96,12))})
  local pending={};for _,m in sk.pending do pending[m]=(pending[m] or 0)+1 end
  local nextDay;for _,m in marks do if m.day>pos then nextDay=m.day;break end end
  for i,m in marks do
   local nx=math.floor(x0+(i-1)*(x1-x0)/(n-1))
   local reached=pos>=m.day
   if m.day==nextDay or pending[m.day] then
    T.make('ImageLabel',face,{Name='NodeGlow'..i,BackgroundTransparency=1,Image=FX.Asset.glow,ImageColor3=pending[m.day] and Color3.fromRGB(255,230,120) or Color3.fromRGB(255,140,40),ImageTransparency=.15,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(nx,ty),Size=UDim2.fromOffset(112,112)})
   end
   local reward=Q.rewardTiles(Config,m)[1]
   local _,icon=diamond(face,'Node'..i,nx,ty,54,reached and Color3.fromRGB(255,190,60) or Q.Locked,reward and reward[1])
   if icon and not reached and not pending[m.day] then icon.ImageTransparency=.35 end
   if icon and reward then tagReward(icon,reward[5] or 'item',reward[6],(FX.Rarity[reward[3]] or FX.Rarity.Common).top) end
   local label=(m.chests and reward and reward[4]) or (m.emeralds and Config.comma(m.emeralds)) or nil
   if label then
    local a=left(T.label(face,'NodeAmount'..i,label,nx-8,ty+6,48,22,17));a.TextStrokeTransparency=1
    T.make('UIStroke',a,{Color=INK,Thickness=2.5})
   end
   center(T.label(face,'Day'..i,'DAY '..m.day,nx-44,ty+32,88,20,16,reached and C.white or C.muted))
   if pending[m.day] then
    local cb=FX.button(face,'ClaimDay'..m.day,pending[m.day]>1 and ('CLAIM ×'..pending[m.day]) or 'CLAIM',nx-52,ty+54,104,34,function() act('ClaimStreak',m.day,icon and {icon}) end)
    cb.Caption.TextSize=17;FX.pulse(cb,.06)
   end
  end
  -- 2. Header with the reset timer.
  local y=8+sh+18
  local timer=FX.header(list,'DAILY QUESTS','New quests in '..resetText(),y,SW);y+=72+8
  task.spawn(function() while timer.Parent do task.wait(1);if timer.Parent then timer.Text='New quests in '..resetText() end end end)
  -- 3. Today's quest cards in one row.
  local gap=18;local count=math.max(#daily,1);local cw=math.floor((SW-(count-1)*gap)/count);local ch=424
  for i,d in daily do
   local q=Config.DailyById[d.id]
   if not q then continue end
   local done=d.progress>=q.target
   local f,cth=FX.card(list,'Quest'..i,(i-1)*(cw+gap)+2,y,cw-4,ch,d.claimed and 'steel' or done and 'gold' or 'night')
   local fw=cw-4
   local band=T.make('Frame',f,{Name='Band',Position=UDim2.fromOffset(12,22),Size=UDim2.new(1,-24,0,52),BackgroundColor3=d.claimed and Color3.fromRGB(110,120,126) or q.color,BorderSizePixel=0})
   T.make('UICorner',band,{CornerRadius=UDim.new(0,12)});T.make('UIStroke',band,{Color=INK,Thickness=3})
   T.make('UIGradient',band,{Rotation=90,Color=ColorSequence.new(Color3.new(1,1,1),Color3.fromRGB(170,170,170))})
   center(FX.title(band,'Title',q.title,8,4,fw-40,44,22))
   FX.art(f,Config.Icons[q.stat] or Config.Icons.quests,fw/2,148,100,cth,done and 280 or 190)
   FX.progress(f,'Progress',20,206,fw-40,34,d.progress/q.target,Config.comma(d.progress)..' / '..Config.comma(q.target),done and C.gold or C.lime)
   center(T.label(f,'RewardsTitle','REWARDS',12,250,fw-24,20,16,C.cream))
   local items=Q.rewardTiles(Config,q,ctx.signature)
   local size=70;local tw=#items*size+(#items-1)*10
   for k,it in items do rewardTile(f,'Reward'..k,math.floor((fw-tw)/2)+(k-1)*(size+10),274,size,it) end
   local bt=FX.button(f,'Claim',d.claimed and 'CLAIMED' or done and 'CLAIM' or 'IN PROGRESS',16,ch-66,fw-32,52,function() act('ClaimQuest',i,rewardsOf(f)) end,not done or d.claimed)
   bt.Caption.TextSize=24
   if d.claimed or not done then bt.Interactable=false else FX.pulse(bt,.05) end
   if done and not d.claimed then FX.tag(f,'COMPLETE!',cth.tag,cth.accent);FX.shine(f) end
   if d.claimed then FX.check(f,fw-36,-10,30) end
  end
  return y+ch+20
 end

 -- Plan M: this week's 3 quests (2 normal, then the hard one) and what they pay together.
 function tabs.Weekly()
  local weekly=view.weekly or {}
  local y=8
  local function sub() return 'New quests in '..weekText(Config)..' · every Monday' end
  local timer=FX.header(list,'WEEKLY QUESTS',sub(),y,SW);y+=72+8
  task.spawn(function() while timer.Parent do task.wait(1);if timer.Parent then timer.Text=sub() end end end)
  local gap=18;local count=math.max(#weekly,1);local cw=math.floor((SW-(count-1)*gap)/count);local ch=470
  local claimed,emeralds,gold=0,0,0
  for i,w in weekly do
   local q=Config.WeeklyById[w.id]
   if not q then continue end
   if w.claimed then claimed+=1 end
   emeralds+=q.emeralds;gold+=q.chests and q.chests.Gold or 0
   local done=w.progress>=q.target
   local f,cth=FX.card(list,'Weekly'..i,(i-1)*(cw+gap)+2,y,cw-4,ch,w.claimed and 'steel' or done and 'gold' or q.hard and 'ember' or 'night')
   local fw=cw-4
   local band=T.make('Frame',f,{Name='Band',Position=UDim2.fromOffset(12,22),Size=UDim2.new(1,-24,0,56),BackgroundColor3=w.claimed and Color3.fromRGB(110,120,126) or q.color,BorderSizePixel=0})
   T.make('UICorner',band,{CornerRadius=UDim.new(0,12)});T.make('UIStroke',band,{Color=INK,Thickness=3})
   T.make('UIGradient',band,{Rotation=90,Color=ColorSequence.new(Color3.new(1,1,1),Color3.fromRGB(170,170,170))})
   center(FX.title(band,'Title',q.title,8,4,fw-40,48,25))
   if q.hard and not done and not w.claimed then
    local hint=T.text(f,'Hint','harder · bigger reward',16,84,fw-32,20,15,Color3.fromRGB(255,206,140))
    hint.TextXAlignment=Enum.TextXAlignment.Right
   end
   FX.art(f,Config.Icons[q.stat] or Config.Icons.quests,fw/2,172,116,cth,done and 300 or 220)
   FX.progress(f,'Progress',20,244,fw-40,36,w.progress/q.target,Config.comma(w.progress)..' / '..Config.comma(q.target),done and C.gold or C.lime)
   center(T.label(f,'RewardsTitle','REWARDS',12,292,fw-24,20,16,C.cream))
   local items=Q.rewardTiles(Config,q,ctx.signature)
   local size=80;local tw=#items*size+(#items-1)*12
   for k,it in items do rewardTile(f,'Reward'..k,math.floor((fw-tw)/2)+(k-1)*(size+12),316,size,it) end
   local bt=FX.button(f,'Claim',w.claimed and 'CLAIMED' or done and 'CLAIM' or 'IN PROGRESS',16,ch-68,fw-32,54,function() act('ClaimWeekly',i,rewardsOf(f)) end,not done or w.claimed)
   bt.Caption.TextSize=24
   if w.claimed or not done then bt.Interactable=false else FX.pulse(bt,.05) end
   if done and not w.claimed then FX.tag(f,'COMPLETE!',cth.tag,cth.accent);FX.shine(f)
   elseif q.hard and not w.claimed then FX.tag(f,'HARD',cth.tag,cth.accent) end
   if w.claimed then FX.check(f,fw-36,-10,30) end
  end
  y+=ch+22
  -- The week at a glance: how many are claimed and what all of them pay.
  local strip=T.make('Frame',list,{Name='WeekSummary',Position=UDim2.fromOffset(2,y),Size=UDim2.fromOffset(CW,52),BackgroundColor3=INK,BackgroundTransparency=.35,BorderSizePixel=0})
  T.make('UICorner',strip,{CornerRadius=UDim.new(0,12)});T.make('UIStroke',strip,{Color=INK,Thickness=2,Transparency=.35})
  T.icon(strip,'Icon',10,4,44,Config.Icons.weekly)
  left(FX.title(strip,'Count','THIS WEEK: '..claimed..' / '..#weekly..' CLAIMED',64,10,420,32,21))
  local pays='All '..#weekly..' pay '..Config.comma(emeralds)..' emeralds'..(gold==1 and ' + a Gold Chest' or gold>1 and (' + '..gold..' Gold Chests') or '')
  local total=T.text(strip,'Pays',pays,480,14,CW-500,24,18,C.cream);total.TextXAlignment=Enum.TextXAlignment.Right
  return y+52+20
 end

 function tabs.Achievements()
  local y=8
  local done,total=0,0
  for _,r in Config.Roads do done+=math.min(view.roads[r.id] or 0,#r.targets);total+=#r.targets end
  for _,u in Config.Unlocks do total+=1;if (view.unlocks[u.id] or {}).claimed then done+=1 end end
  for _,f in Config.Feats do total+=1;if ((view.feats or {})[f.id] or {}).claimed then done+=1 end end
  FX.header(list,'ACHIEVEMENTS','Claim one and it levels up to a harder goal with a bigger reward.',y,SW);y+=72+8
  FX.progress(list,'Total',math.floor(SW/2-270),y,540,30,done/math.max(total,1),done..' / '..total..' complete',C.lime)
  y+=30+30
  local RH=124
  -- One row. o: name, count ('(4/10)'), stars (a feat's 1-3), chip (level name), chipColor, goal,
  -- ratio, text, state ('ready'/'open'/'done'), color, rim, icon, rewards, nextRewards (the level
  -- after, as a NEXT: line), title, levels, level, onClaim.
  local function row(key,yy,o)
   local f,rth=FX.card(list,key,2,yy,CW,RH,o.state=='ready' and 'gold' or o.state=='done' and 'steel' or 'night')
   diamond(f,'Rank',70,RH/2-2,78,o.color,o.icon,o.rim)
   local nx=140
   local nw=math.min(textWidth(o.name,30),360)
   FX.title(f,'Name',o.name,nx,10,nw+8,38,30,rth.tint)
   local x=nx+nw+14
   if o.count then
    local c=FX.title(f,'Count',o.count,x,13,textWidth(o.count,26)+8,34,26)
    c.TextColor3=o.state=='ready' and Color3.fromRGB(255,243,192) or C.limeSoft
    x+=textWidth(o.count,26)+18
   end
   if o.stars then
    for k=1,3 do
     local s=T.label(f,'Star'..k,'★',x+(k-1)*30,8,30,40,30,k<=o.stars and C.gold or Color3.fromRGB(58,68,72))
     s.TextWrapped=false;s.TextStrokeTransparency=1;T.make('UIStroke',s,{Color=INK,Thickness=2.5})
    end
    x+=100
   end
   if o.chip then
    local cw_=textWidth(o.chip,15)+28
    local chip=T.make('Frame',f,{Name='Level',Position=UDim2.fromOffset(x,16),Size=UDim2.fromOffset(cw_,28),BackgroundColor3=o.chipColor,BorderSizePixel=0})
    T.make('UICorner',chip,{CornerRadius=UDim.new(0,8)});T.make('UIStroke',chip,{Color=INK,Thickness=2.5})
    local l=T.label(chip,'Text',o.chip,0,0,cw_,28,15);l.Size=UDim2.fromScale(1,1);l.TextWrapped=false
   end
   FX.sub(f,'Goal',o.goal,nx+2,50,560,22,17)
   FX.progress(f,'Progress',nx+2,78,560,28,o.ratio,o.text,o.state=='ready' and C.gold or C.lime)
   for k=1,o.levels or 0 do
    local pip=T.make('Frame',f,{Name='Pip'..k,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(nx+8+(k-1)*16,115),Size=UDim2.fromOffset(9,9),Rotation=45,BackgroundColor3=k<=o.level and Config.TierColors[k] or Color3.fromRGB(40,46,50),BorderSizePixel=0})
    T.make('UIStroke',pip,{Color=INK,Thickness=1.5})
   end
   -- With a NEXT: line under them the tiles shrink a little to make room. ty/th: the tiles' top and
   -- height (FX.tile is 8% taller than wide); the title card uses the same.
   local size=o.nextRewards and 70 or 78;local rx=730
   local ty,th=o.nextRewards and 6 or 16,math.floor(size*1.08)
   for i,it in o.rewards do rewardTile(f,'Reward'..i,rx+(i-1)*(size+8),ty,size,it) end
   if o.nextRewards then
    left(T.label(f,'NextLabel','NEXT:',rx,94,54,24,15,C.cream)).TextWrapped=false
    local nx2=rx+54
    for i,it in o.nextRewards do
     T.icon(f,'NextIcon'..i,nx2,94,24,it[1]);nx2+=26
     local text=it[2]..(it[4] and (' '..it[4]) or '')
     local l=left(T.label(f,'NextText'..i,text,nx2,94,textWidth(text,15)+16,24,15,it[3]=='Emerald' and (C.emerald or C.lime) or C.white))
     l.TextWrapped=false;nx2+=textWidth(text,15)+12
    end
   end
   if o.title then
    -- Title reward card (fixed 2026-10-03): the ribbon, TITLE and the name crowded each other (6 px
    -- from ribbon to text, the name's box touching TITLE's), the card sat up to 14 px below the tiles
    -- and hung over the NEXT: line, and a long name that hit its 9 px floor on a small screen spilled
    -- up over TITLE. Now the card has the tiles' top and height and up to 236 px (stopping 16 px short
    -- of CLAIM); the ribbon is a square on the left; TITLE and the name share the column right of it,
    -- 4 px apart and centred together. The name may shrink to 7 px, then cuts off with "...", only
    -- grows downwards, and the card clips anything left over.
    local tx=rx+#o.rewards*(size+8)+4
    local tw=math.min(236,CW-216-tx)
    local tile=T.make('Frame',f,{Name='TitleReward',Position=UDim2.fromOffset(tx,ty),Size=UDim2.fromOffset(tw,th),BackgroundColor3=Color3.fromRGB(46,40,26),BorderSizePixel=0,ClipsDescendants=true})
    T.make('UICorner',tile,{CornerRadius=UDim.new(0,12)});T.make('UIStroke',tile,{Color=INK,Thickness=3,ApplyStrokeMode=Enum.ApplyStrokeMode.Border})
    local is=math.min(th-20,52)
    T.icon(tile,'Icon',8,math.floor((th-is)/2),is,Config.Icons.title)
    local cx=8+is+10;local cw=tw-cx-8
    -- One line when it fits (12% slack: text draws wider at small window scales), else two.
    local nh=textWidth(o.title,17)*1.12<=cw and 24 or 40
    local top=math.max(4,math.floor((th-(16+4+nh))/2))
    local cap=left(T.label(tile,'Label','TITLE',cx,top,cw,16,14,C.cream));cap.TextWrapped=false;cap.TextStrokeTransparency=.5;cap.FitText.MinTextSize=7
    local name=left(T.label(tile,'Name',o.title,cx,top+20,cw,math.min(nh,th-top-24),17))
    name.TextYAlignment=Enum.TextYAlignment.Top;name.TextTruncate=Enum.TextTruncate.AtEnd;name.FitText.MinTextSize=7
    tagReward(tile,'title',nil,C.gold)
   end
   local text=o.state=='ready' and 'CLAIM' or o.state=='done' and 'DONE' or (math.floor(math.min(o.ratio,1)*100)..'%')
   local bt=FX.button(f,'Claim',text,CW-200,33,176,58,function() o.onClaim(rewardsOf(f)) end,o.state~='ready')
   bt.Caption.TextSize=o.state=='ready' and 28 or 22
   if o.state=='ready' then FX.pulse(bt,.05);FX.tag(f,'READY!',rth.tag,rth.accent);FX.shine(f) else bt.Interactable=false end
   if o.state=='done' then FX.check(f,CW-212,22,30) end
  end
  local order={ready=1,open=2,done=3}
  -- Feats first (plan M), kept short: everything ready to claim plus the easiest open ones, at
  -- least 3 rows, and SHOW ALL for the rest. Ready first, then by stars, so the next to chase leads.
  FX.header(list,'FEATS','One-time challenges. More stars = harder = bigger reward.',y,SW);y+=72+8
  local feats,ready={},0
  for i,f in Config.Feats do
   local s=(view.feats or {})[f.id] or {have=0,need=1}
   local state=s.claimed and 'done' or s.have>=s.need and 'ready' or 'open'
   if state=='ready' then ready+=1 end
   table.insert(feats,{f=f,s=s,state=state,i=i})
  end
  table.sort(feats,function(a,b)
   if order[a.state]~=order[b.state] then return order[a.state]<order[b.state] end
   if a.f.stars~=b.f.stars then return a.f.stars<b.f.stars end
   return a.i<b.i
  end)
  local shown=sel.allFeats and #feats or math.min(#feats,math.max(3,ready))
  for k=1,shown do
   local e=feats[k];local f,s=e.f,e.s;local g=f.goal
   local have=Config.comma(math.min(s.have,s.need))..' / '..Config.comma(s.need)
   row('Feat_'..f.id,y,{
    name=f.name,stars=f.stars,goal=f.desc,ratio=s.have/math.max(s.need,1),
    text=g.best and ('Best wave '..have) or g.classes and (have..' classes') or have,
    state=e.state,color=Config.StarColors[f.stars],icon=Config.Icons[f.icon] or Config.Icons.achievements,
    rewards=Q.rewardTiles(Config,Config.FeatRewards[f.stars]),onClaim=function(parts) act('ClaimFeat',f.id,parts) end,
   })
   y+=RH+18
  end
  if sel.allFeats or shown<#feats then
   local bt=FX.button(list,'FeatsToggle',sel.allFeats and 'SHOW FEWER' or ('SHOW ALL '..#feats..' FEATS'),math.floor(SW/2-170),y,340,48,function() sel.allFeats=not sel.allFeats;draw() end,true)
   bt.Caption.TextSize=20
   y+=48+18
  end
  y+=12
  -- Then the roads: each shows its next level (n/10) until Legend is done.
  FX.header(list,'TROPHY ROADS',nil,y,SW);y+=46+16
  local roads={}
  for i,r in Config.Roads do
   local level=math.min(view.roads[r.id] or 0,#r.targets)
   local nextL=math.min(level+1,#r.targets)
   local have=view.stats[r.stat] or 0;local need=r.targets[nextL]
   local state=level>=#r.targets and 'done' or have>=need and 'ready' or 'open'
   table.insert(roads,{r=r,level=level,nextL=nextL,have=have,need=need,state=state,i=i,pct=math.min(have/need,1)})
  end
  table.sort(roads,function(a,b)
   if order[a.state]~=order[b.state] then return order[a.state]<order[b.state] end
   if a.pct~=b.pct then return a.pct>b.pct end
   return a.i<b.i
  end)
  for _,e in roads do
   local r=e.r;local finished=e.state=='done'
   row('Road_'..r.id,y,{
    name=r.name,count=not finished and ('('..e.nextL..'/'..#r.targets..')') or nil,
    chip=string.upper(Config.TierNames[e.nextL]),chipColor=Config.TierColors[e.nextL],
    goal=finished and 'Every level done!' or string.format(r.goal,Config.amount(r,e.need)),
    ratio=finished and 1 or e.have/e.need,text=Config.progressText(r,math.min(e.have,e.need),e.need),
    state=e.state,color=Config.TierColors[e.nextL],rim=Q.Rims[e.nextL],
    icon=Config.Icons[r.stat] or Config.Icons.quests,
    rewards=finished and {} or Q.rewardTiles(Config,Config.TierRewards[e.nextL]),
    -- Plan M: what the level after this one pays, so the bigger prizes show.
    nextRewards=not finished and e.nextL<#r.targets and Q.rewardTiles(Config,Config.TierRewards[e.nextL+1]) or nil,
    title=not finished and (r.name..' '..Config.TierNames[e.nextL]) or nil,
    levels=#r.targets,level=e.level,
    onClaim=function(parts) act('ClaimRoad',r.id,parts) end,
   })
   y+=RH+18
  end
  -- Unlocks: one-time rewards (classes, Mjolnir, the Samurai set).
  y+=12
  FX.header(list,'UNLOCKS',nil,y,SW);y+=46+16
  local unlocks={}
  for i,u in Config.Unlocks do
   local s=view.unlocks[u.id] or {have=0,need=1}
   local state=s.claimed and 'done' or s.have>=s.need and 'ready' or 'open'
   table.insert(unlocks,{u=u,s=s,state=state,i=i})
  end
  table.sort(unlocks,function(a,b) if order[a.state]~=order[b.state] then return order[a.state]<order[b.state] end;return a.i<b.i end)
  for _,e in unlocks do
   local u,s=e.u,e.s
   row('Unlock_'..u.id,y,{
    name=u.name,goal=u.desc,ratio=s.have/math.max(s.need,1),text=Config.comma(math.min(s.have,s.need))..' / '..Config.comma(s.need),
    state=e.state,color=e.state=='open' and Q.Locked or C.lime,icon=Config.Icons[u.icon],
    rewards=Q.rewardTiles(Config,u.reward,ctx.signature),onClaim=function(parts) act('ClaimUnlock',u.id,parts) end,
   })
   y+=RH+18
  end
  return y+10
 end

 draw=function()
  local keep=list and list.Parent and sel.questTabDrawn==sel.questTab and list.CanvasPosition
  for _,c in b:GetChildren() do c:Destroy() end
  local profile=ctx.profile()
  view=profile.quests or {}
  local active=sel.questTab
  local dailyN,achN,weekN=0,0,0
  if view.daily and Config then dailyN,achN,weekN=Q.counts(Config,view) end
  local tw=math.floor((W-16)/3)
  local weeklyIcon=Config and Config.Icons.weekly or 'quests'
  for i,t in {{'Daily','quests','DAILY',dailyN},{'Weekly',weeklyIcon,'WEEKLY',weekN},{'Achievements','achievements','ACHIEVEMENTS',achN}} do
   local tb=FX.button(b,'Tab_'..t[1],'',(i-1)*(tw+8),0,tw,64,function() sel.questTab=t[1];draw() end,t[1]~=active)
   tb.Caption.Visible=false
   -- Icon and label centred together on the tab.
   local x0=math.floor((tw-(44+10+textWidth(t[3],22)))/2)
   local ic=T.icon(tb,'Icon',x0,10,44,t[2])
   local l=T.label(tb,'Label',t[3],x0+54,0,220,64,22);l.TextXAlignment=Enum.TextXAlignment.Left;l.TextWrapped=false
   FX.popIcon(tb,ic)
   T.badge(tb,t[4]>0 and tostring(t[4]) or nil)
  end
  list=T.scroll(b,'List',0,78,W,WIN_H-58-78)
  local h
  if not view.daily or not Config then
   local face=FX.card(list,'Loading',2,30,CW,180,'night',true)
   FX.art(face,'quests',110,90,120,FX.Themes.night,200)
   FX.title(face,'Title','QUESTS ARE LOADING',220,50,700,46,40)
   FX.sub(face,'Body','Your quests appear here once your profile has loaded.',222,100,700,24,18)
   h=240
  else h=tabs[active]() end
  list.CanvasSize=UDim2.fromOffset(0,h)
  if keep then list.CanvasPosition=keep end
  sel.questTabDrawn=active
 end
 -- New quests at UTC midnight: ask the server for today's set if ours is from yesterday.
 local first=ctx.profile().quests
 if first and first.resetIn and 86400-os.time()%86400>first.resetIn+5 then
  task.spawn(function() combat.ProfileAction:InvokeServer('Refresh') end)
 end
 draw()
 if ctx.setRedraw then ctx.setRedraw(draw) end
 return w
end
return Q
