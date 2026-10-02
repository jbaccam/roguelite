-- Quests window: DAILY (three quest cards and the streak track) and ACHIEVEMENTS (unlocks and
-- trophy roads), drawn as colour cards (StoreFX). It shows the server's ProfileQuests view
-- (QuestService) through QuestConfig; every CLAIM asks the server (ProfileAction ClaimQuest /
-- ClaimStreak / ClaimRoad / ClaimUnlock), which checks it and grants the reward.
-- plans/2026-10-01-H-store-and-quests.md
local RS=game:GetService('ReplicatedStorage')
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

local W=1064;local SW=W-14;local CW=SW-4
local INK=FX.INK
-- Rank diamond colours by tiers done: none, bronze, silver, gold, emerald, ruby (mastered).
Q.TierColors={Color3.fromRGB(96,106,112),Color3.fromRGB(214,132,58),Color3.fromRGB(200,210,218),Color3.fromRGB(255,200,60),Color3.fromRGB(70,226,120),Color3.fromRGB(255,64,96)}
local function center(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
local function weaponId(name) for id,w in Weapons.ById do if w.name==name then return id end end end

-- Slots for a reward: {emeralds, chests, class, weapon (name), armorSet}.
function Q.rewardTiles(Config,r,signature)
 local out={}
 if r.emeralds and r.emeralds>0 then table.insert(out,{'emerald',Config.comma(r.emeralds),'Emerald'}) end
 for _,kind in {'Wooden','Silver','Gold','Magical','Legendary'} do
  local n=r.chests and r.chests[kind]
  if n and n>0 then table.insert(out,{Chests.ById[kind].icon,kind,FX.ChestRarity[kind],n>1 and ('×'..n) or nil}) end
 end
 if r.class then table.insert(out,{WeaponIcons[signature and signature[r.class] or ''] or 'profile',r.class,'Rare'}) end
 if r.weapon then local id=weaponId(r.weapon);table.insert(out,{(id and WeaponIcons[id]) or (WeaponArt.IconsByName and WeaponArt.IconsByName[r.weapon]) or 'armory',r.weapon,'Legendary'}) end
 if r.armorSet then local set=Armor.ById[r.armorSet];table.insert(out,{Armor.Icons[Armor.pieceId(r.armorSet,'Chest')],set and set.name or r.armorSet,set and set.rarity or 'Epic'}) end
 return out
end

-- What can be claimed right now: daily (quests + streak) and achievements, from the view.
function Q.counts(Config,view)
 local daily,ach=0,0
 for _,d in view.daily or {} do local q=Config.DailyById[d.id];if q and not d.claimed and d.progress>=q.target then daily+=1 end end
 daily+=#(view.streak and view.streak.pending or {})
 for _,r in Config.Roads do
  local t=((view.roads or {})[r.id] or 0)+1
  if r.targets[t] and ((view.stats or {})[r.stat] or 0)>=r.targets[t] then ach+=1 end
 end
 for _,u in Config.Unlocks do local s=(view.unlocks or {})[u.id];if s and not s.claimed and s.have>=s.need then ach+=1 end end
 return daily,ach
end

-- ctx: config (QuestConfig), profile() (LobbyUI profile with .quests), selection, signature
-- (class -> signature weapon id), setRedraw(fn).
function Q.open(screen,ctx,tab)
 local Config=ctx.config
 local w=T.window(screen,'QuestsWindow','Quests',1100,640,nil,{large=true});local b=w.Body
 local sel=ctx.selection
 sel.questTab=(tab=='Daily' or tab=='Achievements') and tab or sel.questTab or 'Daily'
 local list,draw
 local view
 local function act(action,a)
  local r=combat.ProfileAction:InvokeServer(action,a)
  if r.ok then T.sound('ui_purchase') end
  T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
 end
 local function tiles(face,items,x,y,size,gap)
  for i,it in items do FX.tile(face,'Reward'..i,x+(i-1)*(size+gap),y,size,it[1],it[2],it[3],it[4]) end
 end
 -- Rotated rank diamond with an upright icon on it.
 local function diamond(parent,name,cx,cy,size,color,asset)
  local d=T.make('Frame',parent,{Name=name,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(cx,cy),Size=UDim2.fromOffset(size,size),Rotation=45,BackgroundColor3=Color3.new(1,1,1),BorderSizePixel=0})
  T.make('UICorner',d,{CornerRadius=UDim.new(0,math.floor(size*.18))})
  T.make('UIGradient',d,{Rotation=90,Color=ColorSequence.new(color:Lerp(Color3.new(1,1,1),.35),color:Lerp(Color3.new(0,0,0),.45))})
  T.make('UIStroke',d,{Color=INK,Thickness=3})
  local icon
  if asset then icon=T.icon(parent,name..'Icon',cx-size*.42,cy-size*.42,size*.84,asset) end
  return d,icon
 end

 local tabs={}
 function tabs.Daily()
  local y=10
  local timer=FX.header(list,'DAILY QUESTS','',y,SW);y+=72+16
  local function tick()
   local sec=86400-os.time()%86400
   timer.Text=string.format('New quests in %02d:%02d:%02d',sec//3600,sec%3600//60,sec%60)
  end
  tick()
  task.spawn(function() while timer.Parent do task.wait(1);if timer.Parent then tick() end end end)
  local gap=18;local cw=math.floor((SW-2*gap)/3);local ch=392
  for i,d in view.daily do
   local q=Config.DailyById[d.id]
   if not q then continue end
   local done=d.progress>=q.target
   local face,th=FX.card(list,'Quest'..i,(i-1)*(cw+gap),y,cw,ch,d.claimed and 'steel' or done and 'gold' or 'night')
   -- Header band in the quest's colour.
   local band=T.make('Frame',face,{Name='Band',Position=UDim2.fromOffset(12,24),Size=UDim2.new(1,-24,0,52),BackgroundColor3=d.claimed and Color3.fromRGB(110,120,126) or q.color,BorderSizePixel=0})
   T.make('UICorner',band,{CornerRadius=UDim.new(0,12)});T.make('UIStroke',band,{Color=INK,Thickness=3})
   T.make('UIGradient',band,{Rotation=90,Color=ColorSequence.new(Color3.new(1,1,1),Color3.fromRGB(170,170,170))})
   center(FX.title(band,'Title',q.title,10,4,cw-44,44,24))
   FX.art(face,Config.Icons[q.stat] or Config.Icons.quests,cw/2,124,84,th,done and 260 or 170)
   FX.progress(face,'Progress',20,174,cw-40,32,d.progress/q.target,Config.comma(d.progress)..' / '..Config.comma(q.target),done and C.gold or C.lime)
   center(T.label(face,'RewardsTitle','REWARDS',12,214,cw-24,20,16,C.cream))
   local items=Q.rewardTiles(Config,q,ctx.signature)
   local size=70;local tw=#items*size+(#items-1)*10
   tiles(face,items,math.floor((cw-tw)/2),238,size,10)
   local bt=FX.button(face,'Claim',d.claimed and 'CLAIMED' or done and 'CLAIM' or 'IN PROGRESS',16,ch-66,cw-32,52,function() act('ClaimQuest',i) end,not done or d.claimed)
   bt.Caption.TextSize=24
   if d.claimed or not done then bt.Interactable=false elseif done then FX.pulse(bt,.05) end
   if done and not d.claimed then FX.tag(face,'COMPLETE!',th.tag,th.accent);FX.shine(face) end
   if d.claimed then FX.check(face,cw-36,-10,30) end
  end
  y+=ch+30
  -- Streak: today's status, the day count on a flame, and the reward track.
  local sk=view.streak
  local sh=268
  local face,th=FX.card(list,'Streak',2,y,CW,sh,'ember')
  FX.art(face,Config.Icons.streak,104,96,140,th,240)
  center(FX.title(face,'Count',tostring(sk.count),44,92,120,60,58))
  center(FX.title(face,'Days','DAY STREAK',14,168,180,28,24,th.tint))
  center(FX.sub(face,'Best','Best: '..sk.best..(sk.best==1 and ' day' or ' days'),14,198,180,22,16))
  FX.title(face,'TrackTitle','STREAK REWARDS',232,20,420,38,32,th.tint)
  FX.sub(face,'TrackHelp','Finish all 3 daily quests every day. Miss a day and the streak starts over.',234,60,560,22,16)
  -- Today's status pill (a check once today counts).
  local status=sk.today and 'TODAY COUNTED' or 'FINISH ALL 3 TODAY'
  local pill=T.make('Frame',face,{Name='Today',Position=UDim2.fromOffset(CW-290,22),Size=UDim2.fromOffset(250,34),BackgroundColor3=sk.today and C.limeDark or Color3.fromRGB(110,34,10),BorderSizePixel=0})
  T.make('UICorner',pill,{CornerRadius=UDim.new(1,0)});T.make('UIStroke',pill,{Color=INK,Thickness=2.5})
  center(FX.title(pill,'Text',status,12,3,226,28,18,not sk.today and Color3.fromRGB(255,206,140) or nil))
  if sk.today then FX.check(face,CW-326,24,30) end
  -- Track: seven evenly spaced milestones; the fill reaches between them by days.
  local x0,x1,ty=262,CW-60,132
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
    T.make('ImageLabel',face,{Name='NodeGlow'..i,BackgroundTransparency=1,Image=FX.Asset.glow,ImageColor3=pending[m.day] and Color3.fromRGB(255,230,120) or Color3.fromRGB(255,140,40),ImageTransparency=.15,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(nx,ty),Size=UDim2.fromOffset(120,120)})
   end
   local reward=Q.rewardTiles(Config,m)[1]
   local _,icon=diamond(face,'Node'..i,nx,ty,58,reached and Color3.fromRGB(255,190,60) or Color3.fromRGB(96,106,112),reward and reward[1])
   if icon and not reached and not pending[m.day] then icon.ImageTransparency=.35 end
   local label=(m.chests and Q.rewardTiles(Config,m)[1][4]) or (m.emeralds and Config.comma(m.emeralds)) or nil
   if label then
    local a=T.label(face,'NodeAmount'..i,label,nx-10,ty+8,46,22,17);a.TextXAlignment=Enum.TextXAlignment.Left;a.TextStrokeTransparency=1
    T.make('UIStroke',a,{Color=INK,Thickness=2.5})
   end
   center(T.label(face,'Day'..i,'DAY '..m.day,nx-44,ty+44,88,22,17,reached and C.white or C.muted))
   if pending[m.day] then
    local cb=FX.button(face,'ClaimDay'..m.day,pending[m.day]>1 and ('CLAIM ×'..pending[m.day]) or 'CLAIM',nx-56,ty+72,112,40,function() act('ClaimStreak',m.day) end)
    cb.Caption.TextSize=18;FX.pulse(cb,.06)
   end
  end
  y+=sh+20
  return y
 end

 function tabs.Achievements()
  local y=10
  local done,total=0,0
  for _,r in Config.Roads do done+=(view.roads[r.id] or 0);total+=#r.targets end
  for _,u in Config.Unlocks do total+=1;if (view.unlocks[u.id] or {}).claimed then done+=1 end end
  FX.header(list,'ACHIEVEMENTS','Permanent goals. Each one pays out once and keeps going to the next tier.',y,SW);y+=72+6
  FX.progress(list,'Total',math.floor(SW/2-260),y,520,30,done/math.max(total,1),done..' / '..total..' complete',C.lime)
  y+=30+40
  local function claimButton(face,name,state,pct,onClaim)
   local text=state=='ready' and 'CLAIM' or state=='done' and 'DONE' or (pct..'%')
   local bt=FX.button(face,name,text,CW-196,32,176,58,onClaim,state~='ready')
   bt.Caption.TextSize=state=='ready' and 28 or 22
   if state=='ready' then FX.pulse(bt,.05) else bt.Interactable=false end
   if state=='done' then FX.check(face,CW-208,22,30) end
   return bt
  end
  -- Row: rank diamond, name and goal, progress under them, reward slots, CLAIM.
  local RH=124
  local function row(name,y_,state,title,goal,have,need,diamondColor,icon,rewards,onClaim,extra)
   local face,th=FX.card(list,name,2,y_,CW,RH,state=='ready' and 'gold' or state=='done' and 'steel' or 'night')
   diamond(face,'Rank',70,RH/2,78,diamondColor,icon)
   FX.title(face,'Name',title,140,14,430,36,30,th.tint)
   FX.sub(face,'Goal',goal,142,50,500,22,17)
   FX.progress(face,'Progress',142,80,488,28,need>0 and have/need or 1,Config.comma(have)..' / '..Config.comma(need),state=='ready' and C.gold or C.lime)
   local size=78
   for i,it in rewards do FX.tile(face,'Reward'..i,650+(i-1)*(size+8),18,size,it[1],it[2],it[3],it[4]) end
   claimButton(face,'Claim',state,need>0 and math.floor(math.min(have/need,1)*100) or 100,onClaim)
   if state=='ready' then FX.shine(face) end
   if extra then extra(face,th) end
   return face
  end
  local order={ready=1,open=2,done=3}
  -- Unlocks.
  FX.header(list,'UNLOCKS',nil,y,SW);y+=46+18
  local unlocks={}
  for i,u in Config.Unlocks do
   local s=view.unlocks[u.id] or {have=0,need=1}
   local state=s.claimed and 'done' or s.have>=s.need and 'ready' or 'open'
   table.insert(unlocks,{u=u,s=s,state=state,i=i})
  end
  table.sort(unlocks,function(a,b) if order[a.state]~=order[b.state] then return order[a.state]<order[b.state] end;return a.i<b.i end)
  for _,e in unlocks do
   local u,s=e.u,e.s
   row('Unlock_'..u.id,y,e.state,u.name,u.desc,s.have,s.need,e.state=='open' and Q.TierColors[1] or C.lime,Config.Icons[u.icon],Q.rewardTiles(Config,u.reward,ctx.signature),function() act('ClaimUnlock',u.id) end)
   y+=RH+22
  end
  -- Trophy roads: each shows its next tier (or Master when finished), with tier pips.
  y+=12
  FX.header(list,'TROPHY ROADS',nil,y,SW);y+=46+18
  local roads={}
  for i,r in Config.Roads do
   local tier=view.roads[r.id] or 0;local nextT=math.min(tier+1,#r.targets)
   local have=view.stats[r.stat] or 0;local need=r.targets[nextT]
   local state=tier>=#r.targets and 'done' or have>=need and 'ready' or 'open'
   table.insert(roads,{r=r,tier=tier,nextT=nextT,have=have,need=need,state=state,i=i,pct=math.min(have/need,1)})
  end
  table.sort(roads,function(a,b)
   if order[a.state]~=order[b.state] then return order[a.state]<order[b.state] end
   if a.pct~=b.pct then return a.pct>b.pct end
   return a.i<b.i
  end)
  for _,e in roads do
   local r=e.r
   local tierName=Config.TierNames[e.nextT]
   row('Road_'..r.id,y,e.state,r.name..'  ·  '..string.upper(e.state=='done' and 'Master' or tierName),string.format(r.goal,Config.comma(e.need)),math.min(e.have,e.need),e.need,
    Q.TierColors[e.tier+1],Config.Icons[r.stat] or Config.Icons.quests,Q.rewardTiles(Config,Config.TierRewards[e.nextT]),function() act('ClaimRoad',r.id) end,
    function(face)
     -- Tier pips beside the name: filled for every tier done.
     for k=1,#r.targets do
      local pip=T.make('Frame',face,{Name='Pip'..k,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(584+(k-1)*12,32),Size=UDim2.fromOffset(9,9),Rotation=45,BackgroundColor3=k<=e.tier and Q.TierColors[k+1] or Color3.fromRGB(40,46,50),BorderSizePixel=0})
      T.make('UIStroke',pip,{Color=INK,Thickness=1.5})
     end
    end)
   y+=RH+22
  end
  return y+10
 end

 draw=function()
  local keep=list and list.Parent and sel.questTabDrawn==sel.questTab and list.CanvasPosition
  for _,c in b:GetChildren() do c:Destroy() end
  local profile=ctx.profile()
  view=profile.quests or {}
  local active=sel.questTab
  local dailyN,achN=0,0
  if view.daily and Config then dailyN,achN=Q.counts(Config,view) end
  local tw=math.floor((W-8)/2)
  for i,t in {{'Daily','quests','DAILY',dailyN},{'Achievements','achievements','ACHIEVEMENTS',achN}} do
   local tb=FX.button(b,'Tab_'..t[1],'',(i-1)*(tw+8),0,tw,64,function() sel.questTab=t[1];draw() end,t[1]~=active)
   tb.Caption.Visible=false
   local ic=T.icon(tb,'Icon',math.floor(tw/2)-120,10,44,t[2])
   local l=T.label(tb,'Label',t[3],math.floor(tw/2)-66,0,220,64,22);l.TextXAlignment=Enum.TextXAlignment.Left;l.TextWrapped=false
   FX.popIcon(tb,ic)
   T.badge(tb,t[4]>0 and tostring(t[4]) or nil)
  end
  list=T.scroll(b,'List',0,78,W,500)
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
