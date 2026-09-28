-- Full-screen run setup: MAP (ladder, difficulty, wave track, rewards) then CLASS (class cards,
-- starting weapon), over the chosen map's blurred mini island (MapSelectBackdrop). Opened by PLAY,
-- LOADOUT and stepping onto a portal pad. Presentation and requests only: the lobby server
-- validates map, difficulty, class and weapon (RunSetupRules) before starting.
-- Modes: Play -> START (server claims a free pad), Host -> START, Member -> READY, Loadout -> CONFIRM.
local RS=game:GetService('ReplicatedStorage')
local Lighting=game:GetService('Lighting')
local Input=game:GetService('UserInputService')
local TweenService=game:GetService('TweenService')
local T=require(RS:WaitForChild('UITheme'))
local Rules=require(RS:WaitForChild('RunSetupRules'))
local Backdrop=require(RS:WaitForChild('MapSelectBackdrop'))
local combat=RS:WaitForChild('RogueliteCombat')
local Stats=require(combat:WaitForChild('CharacterStats'))
local Money=require(combat:WaitForChild('MonetizationConfig'))
local WeaponIcons=require(RS:WaitForChild('WeaponInventoryUI')).Icons
local C=T.Color
local M={}
local DW,DH=1280,720 -- design canvas; scaled to fit the screen

-- Padlock badge (UITheme `lock` icon).
function M.lock(parent,x,y,size)
 local g=T.icon(parent,'Lock',x,y,size,'lock');g.ZIndex=4
 return g
end

-- opts: profile() -> LobbyUI profile, need(rec), cost(parent,amount,asset,size),
-- selection (shared with the lobby HUD), findPortal(), hostMap() -> map id chosen by my pad's host.
function M.new(player,opts)
 local self={mode=nil,step=nil}
 local sel=opts.selection
 local setupRemote=workspace:WaitForChild('RogueliteLobby'):WaitForChild('RunSetup')
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='RunSetup',ResetOnSpawn=false,DisplayOrder=60,IgnoreGuiInset=true,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,Enabled=false})
 self.Screen=screen
 local shade=T.make('Frame',screen,{Name='Shade',Size=UDim2.fromScale(1,1),BackgroundColor3=C.shade,BackgroundTransparency=.1,BorderSizePixel=0,Active=true})
 T.make('UIGradient',shade,{Rotation=90,Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.25),NumberSequenceKeypoint.new(.5,.42),NumberSequenceKeypoint.new(1,.1)})})
 local canvas=T.frame(screen,'Canvas',0,0,DW,DH);canvas.AnchorPoint=Vector2.new(.5,.5);canvas.Position=UDim2.fromScale(.5,.5)
 local scale=T.make('UIScale',canvas,{Scale=1})
 -- Sized from the camera viewport: a disabled ScreenGui reports a stale AbsoluteSize.
 local function target() local v=workspace.CurrentCamera.ViewportSize;return v.X>0 and math.min(v.X/DW,v.Y/DH) or 1 end
 local function fit() scale.Scale=target() end
 workspace.CurrentCamera:GetPropertyChangedSignal('ViewportSize'):Connect(fit)
 local blur,profile,draw

 local function clear() for _,c in canvas:GetChildren() do if not c:IsA('UIScale') then c:Destroy() end end end
 local function centred(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
 local function buttons(backText,backFn,primaryText,primaryFn,enabled)
  local back=T.button(canvas,'Back',backText,DW/2-230,636,210,62,backFn,true);back.Caption.TextSize=26;back.Caption.TextColor3=C.negative
  local go=T.button(canvas,'Primary',primaryText,DW/2+20,636,210,62,primaryFn);go.Caption.TextSize=26;go.Interactable=enabled~=false
  return back,go
 end
 function self.Close()
  if not screen.Enabled then return end
  screen.Enabled=false;self.mode=nil;self.step=nil;clear()
  if blur then blur:Destroy();blur=nil end
  Backdrop.Hide()
 end
 -- The map's island behind the screen, with a lighter shade so it reads; a plain blur and the
 -- dark shade when the islands are not installed.
 local function stage(index,locked)
  local shown=Backdrop.Show(Rules.Maps,index,locked)
  if shown and blur then blur:Destroy();blur=nil end
  if not shown and not blur then blur=Instance.new('BlurEffect');blur.Name='RunSetupBlur';blur.Size=16;blur.Parent=Lighting end
  shade.BackgroundTransparency=shown and .35 or .1
 end
 local function myPortal()
  local q=player:GetAttribute('LobbyQueue');local portals=workspace.RogueliteLobby:FindFirstChild('Portals')
  return q and portals and portals:FindFirstChild('Portal'..q)
 end
 local function cycle(d)
  sel.map=((sel.map-1+d)%#Rules.Maps)+1
  if not Rules.difficultyUnlocked(profile.wins,sel.map,sel.difficulty) then sel.difficulty='Normal' end
  draw()
 end

 -- Step 1: map -------------------------------------------------------------------------
 local function drawMap()
  local i=sel.map;local m=Rules.Maps[i];local mapOpen=Rules.mapUnlocked(profile.wins,i)
  local diff=sel.difficulty;local tier=Rules.difficulty(diff);local unlocked=Rules.difficultyUnlocked(profile.wins,i,diff)
  local key=Rules.runKey(m.id,diff)
  T.label(canvas,'Step','CHOOSE A MAP',0,30,DW,30,22,C.muted)
  for k=1,#Rules.Maps do
   local on=k==i
   local d=T.make('Frame',canvas,{Name='Dot'..k,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(DW/2+(k-3)*28,76),Size=UDim2.fromOffset(on and 16 or 10,on and 16 or 10),BackgroundColor3=on and C.lime or C.dim,BorderSizePixel=0})
   T.make('UICorner',d,{CornerRadius=UDim.new(.5,0)})
   T.make('UIStroke',d,{Color=Color3.fromRGB(8,10,11),Thickness=2}) -- readable over the light island sky
  end
  T.label(canvas,'MapName',string.upper(m.name),0,92,DW,100,92,mapOpen and C.white or C.dim)
  T.label(canvas,'Sub','MAP '..i..'  ·  BOSS: '..string.upper(m.boss),0,192,DW,30,22,C.muted)
  -- Wave track: 0 -> 20 with the special waves marked, filled to the best wave reached.
  local TX,TY,TW=200,284,880
  local best=profile.best[key] or 0
  local fill=T.bar(canvas,'WaveTrack',TX,TY,TW,20,C.lime);T.setBar(fill,best/Rules.WinWave)
  local function marker(wave,tag)
   local x=TX+TW*wave/Rules.WinWave;local reached=best>=wave and wave>0
   local dm=T.make('Frame',canvas,{Name='Mark'..wave,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(x,TY+10),Size=UDim2.fromOffset(28,28),Rotation=45,BackgroundColor3=reached and C.lime or tag=='BOSS' and C.red or C.well,BorderSizePixel=0})
   T.make('UIStroke',dm,{Color=Color3.fromRGB(8,10,11),Thickness=3})
   T.label(canvas,'Wave'..wave,tostring(wave),x-40,TY+30,80,30,22)
   if tag then T.label(canvas,'Tag'..wave,tag,x-70,TY-46,140,28,20,tag=='BOSS' and C.negative or C.gold) end
  end
  marker(0);for _,ms in Rules.Milestones do marker(ms[1],ms[2]) end
  local prev=T.button(canvas,'PrevMap','<',70,236,90,120,function() cycle(-1) end,true);prev.Caption.TextSize=64
  local nxt=T.button(canvas,'NextMap','>',DW-160,236,90,120,function() cycle(1) end,true);nxt.Caption.TextSize=64
  stage(i,not mapOpen)
  -- Locked map: the island is a silhouette; one big padlock and the unlock rule replace the
  -- difficulty and reward rows, which would all be locked anyway.
  if not mapOpen then
   T.icon(canvas,'LockBig',(DW-136)/2,352,136,'lock')
   T.label(canvas,'Locked','LOCKED',0,490,DW,52,48,C.white)
   T.label(canvas,'Unlock',string.upper(m.unlock),0,546,DW,32,26,C.gold)
   buttons('BACK',self.Close,'NEXT',nil,false)
   return
  end
  local won=profile.wins[key]==true
  local status=not unlocked and string.upper(Rules.difficultyLock(i,diff))
   or won and ('WON  ·  BEST WAVE '..best) or best>0 and ('BEST WAVE '..best..' OF '..Rules.WinWave) or 'NOT PLAYED YET'
  T.label(canvas,'Status',status,0,338,DW,28,22,unlocked and C.cream or C.gold)
  -- Difficulty: each tier buffs enemies and pays more emeralds. Locked tiers show a padlock.
  local DWB,DGAP=200,16;local dx=(DW-(3*DWB+2*DGAP))/2
  for k,d in Rules.Difficulties do
   local open=Rules.difficultyUnlocked(profile.wins,i,d.id)
   local b=T.button(canvas,'Diff_'..d.id,string.upper(d.id),dx+(k-1)*(DWB+DGAP),376,DWB,52,function() sel.difficulty=d.id;draw() end,d.id~=diff or not mapOpen)
   b.Caption.TextSize=24
   if d.id~=diff or not mapOpen then b.Caption.TextColor3=not open and C.dim or d.id=='Hard' and C.gold or d.id=='Nightmare' and C.negative or C.lime end
   if not open then M.lock(b,DWB-34,12,24) end
  end
  local effect=diff=='Normal' and 'Standard enemies  ·  standard emeralds'
   or string.format('Enemies  x%s health  ·  x%s damage  ·  x%s emeralds',tier.hp,tier.damage,tier.reward)
  centred(T.text(canvas,'DiffEffect',effect,0,436,DW,24,18,C.muted))
  -- Rewards for this map and difficulty.
  local tiles={
   {'emerald',Rules.winEmeralds(i,diff)..' EMERALDS','by wave '..Rules.WinWave..'  ·  paid every 5 waves',C.emerald},
   {'achievements',won and 'CLAIMED' or '+'..Rules.firstWinEmeralds(i,diff)..' EMERALDS','first win bonus',won and C.dim or C.emerald},
   {'play','ENDLESS','keep going after wave '..Rules.WinWave,C.lime},
  }
  local tw,gap=250,22;local x0=(DW-(#tiles*tw+(#tiles-1)*gap))/2
  for k,t in tiles do
   local tile=T.panel(canvas,'Reward'..k,x0+(k-1)*(tw+gap),474,tw,138,'inset')
   T.icon(tile,'Icon',(tw-56)/2,8,56,t[1])
   T.label(tile,'Value',t[2],0,68,tw,30,24,t[4])
   centred(T.text(tile,'Caption',t[3],0,100,tw,22,15,C.muted))
  end
  buttons('BACK',self.Close,'NEXT',function() self.step='Class';draw() end,unlocked)
 end

 -- Step 2: class and starting weapon ---------------------------------------------------
 local function drawClass()
  local mode=self.mode
  T.label(canvas,'Step','CHOOSE YOUR CLASS',0,22,DW,44,38)
  local mapText,mapIndex=nil,sel.map
  if mode=='Member' then
   local portal=myPortal();local id=opts.hostMap();mapIndex=id and Rules.MapIndex[id] or sel.map
   local d=portal and portal:GetAttribute('Difficulty')
   mapText=id and Rules.Maps[mapIndex].name..(d and d~='Normal' and '  ·  '..d or '') or 'Host is choosing the map'
  elseif mode~='Loadout' then mapText=Rules.Maps[sel.map].name..(sel.difficulty~='Normal' and '  ·  '..sel.difficulty or '') end
  if mapText then T.label(canvas,'MapChip',string.upper(mapText),0,64,DW,26,19,C.cream) end
  stage(mapIndex,false)
  -- Class cards: owned first, then locked. Names centred; locked cards dimmed with a padlock.
  local order=Rules.classOrder(profile.classes)
  local cw,gap=170,14;local x0=(DW-(#order*cw+(#order-1)*gap))/2
  for k,class in order do
   local owned=profile.classes[class]==true;local selected=sel.class==class
   local card=T.button(canvas,'Class_'..class,'',x0+(k-1)*(cw+gap),100,cw,150,function() sel.class=class;sel.weapon=nil;draw() end,not selected)
   card.Caption.Visible=false
   local art=T.icon(card,'Icon',(cw-72)/2,12,72,WeaponIcons[Rules.Signature[class]]);art.ImageTransparency=owned and 0 or .6
   local n=T.label(card,'Name',class,0,88,cw,34,24,owned and C.white or C.dim);n.Size=UDim2.new(1,0,0,34);n.TextWrapped=false
   if not owned then
    M.lock(card,cw-40,10,28)
    local l=T.label(card,'Locked','LOCKED',0,120,cw,22,15,C.gold);l.Size=UDim2.new(1,0,0,22)
   end
  end
  local class=sel.class;local owned=profile.classes[class]==true
  -- Class details.
  local info=T.panel(canvas,'ClassInfo',95,270,440,352,'panel')
  local n=T.label(info,'Name',class,20,14,400,40,32);n.TextXAlignment=Enum.TextXAlignment.Left
  T.text(info,'Description',Stats.Classes[class].description,20,58,400,48,18,C.muted)
  local lines={}
  for _,d in Stats.List do
   local v=Stats.Classes[class].buffs[d.id]
   if v then table.insert(lines,'<font color="'..T.hex(v>0 and C.lime or C.negative)..'">'..(v>0 and '+' or '')..v..d.unit..'</font>  '..d.label) end
  end
  T.text(info,'Buffs',table.concat(lines,'\n'),20,112,400,170,19)
  if owned then
   T.text(info,'Affinity','Equip 2 home weapons for the first class bonus, 4 for the stronger one.',20,288,400,24,15,C.cream)
   T.text(info,'Armor','Armor: none yet  ·  armor sets arrive with chest rewards',20,316,400,22,15,C.dim)
  else
   T.text(info,'Earn','Earn it: '..(Rules.ClassUnlock[class] or 'an achievement'),20,280,400,24,16,C.gold)
   local key='Class'..class;local product=Money.Products[key]
   if product then T.button(info,'BuyRobux','R$ '..product.robux,20,306,190,40,function() combat.PurchaseRequest:FireServer(key) end).Caption.TextSize=20 end
   local eb=T.button(info,'BuyEmeralds','',230,306,190,40,function()
    local r=combat.ProfileAction:InvokeServer('BuyClass',class)
    T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
   end,true)
   eb.Caption.Visible=false;opts.cost(eb,Money.ClassEmeraldPrice,'emerald',20)
  end
  -- Starting weapon grid.
  local RX,RW=560,625
  local h=T.label(canvas,'WeaponTitle','STARTING WEAPON',RX,270,RW,30,24);h.TextXAlignment=Enum.TextXAlignment.Left
  local list=Rules.homeWeapons(class);local cell,cgap=150,12;local gx=RX+(RW-(3*cell+2*cgap))/2
  local pick=sel.weapon or Rules.Signature[class]
  for k,wpn in list do
   local rec=profile.weapons[wpn.id];local canPick=owned and rec~=nil;local selected=canPick and pick==wpn.id
   local c=T.button(canvas,'Weapon_'..wpn.id,'',gx+((k-1)%3)*(cell+cgap),306+math.floor((k-1)/3)*(cell+cgap),cell,cell,function()
    if canPick then sel.weapon=wpn.id;draw() end
   end,not selected)
   c.Caption.Visible=false
   if rec and not selected then T.setTier(c,rec.tier) end
   local art=T.icon(c,'Icon',(cell-70)/2,12,70,WeaponIcons[wpn.id]);art.ImageTransparency=rec and 0 or .6
   centred(T.text(c,'Name',wpn.name,10,84,cell-20,22,17,rec and C.white or C.dim))
   if rec then T.tierBadge(c,rec.tier,10,10);T.upgradeBar(c,'Upgrade',16,cell-36,cell-32,18,rec.have,opts.need(rec))
   else centred(T.text(c,'Locked','NOT OWNED',16,cell-38,cell-32,20,14,C.dim)) end
  end
  -- Host: open pad (up to 4) or solo.
  if mode=='Host' or mode=='Play' then T.tabs(canvas,95,636,260,62,{'Open','Solo'},sel.solo and 'Solo' or 'Open',function(id) sel.solo=id=='Solo';draw() end) end
  local labels={Play='START',Host='START',Member='READY',Loadout='CONFIRM'}
  local weaponOwned=profile.weapons[pick]~=nil
  local back=(mode=='Play' or mode=='Host') and function() self.step='Map';draw() end or self.Close
  local _,go=buttons((mode=='Play' or mode=='Host') and 'BACK' or 'CLOSE',back,owned and labels[mode] or 'LOCKED',function()
   player:SetAttribute('LoadoutClass',class);player:SetAttribute('LoadoutWeapon',pick)
   if mode=='Play' or mode=='Host' then
    player:SetAttribute('LobbyMap',Rules.Maps[sel.map].id)
    setupRemote:FireServer(mode=='Play' and 'Play' or 'Start',Rules.Maps[sel.map].id,class,pick,sel.solo==true,sel.difficulty)
   elseif mode=='Member' then setupRemote:FireServer('Ready',class,pick)
   else setupRemote:FireServer('Loadout',class,pick);self.Close() end
  end,owned and weaponOwned)
 end

 draw=function()
  clear()
  if self.step=='Map' then drawMap() else drawClass() end
 end
 function self.Open(mode)
  profile=opts.profile()
  if not Rules.mapUnlocked(profile.wins,sel.map) then sel.map=1 end
  sel.difficulty=sel.difficulty or 'Normal'
  if not Rules.difficultyUnlocked(profile.wins,sel.map,sel.difficulty) then sel.difficulty='Normal' end
  if not profile.classes[sel.class] then sel.class='Brawler' end
  local wasOpen=screen.Enabled
  self.mode=mode;self.step=(mode=='Member' or mode=='Loadout') and 'Class' or 'Map'
  screen.Enabled=true;fit();draw()
  if not wasOpen then local s=target();scale.Scale=s*.94;TweenService:Create(scale,TweenInfo.new(.16,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=s}):Play() end
 end
 function self.Refresh() if screen.Enabled then profile=opts.profile();draw() end end
 function self.IsOpen() return screen.Enabled end
 setupRemote.OnClientEvent:Connect(function(kind,ok,message)
  if kind~='Result' then return end
  if type(message)=='string' then T.toast(screen.Enabled and screen or opts.toastScreen,message,ok and C.lime or C.negative) end
  if ok and (self.mode=='Host' or self.mode=='Member' or self.mode=='Play') then self.Close() end
 end)
 Input.InputBegan:Connect(function(input,processed)
  if not screen.Enabled or processed or Input:GetFocusedTextBox() then return end
  if input.KeyCode==Enum.KeyCode.Escape or input.KeyCode==Enum.KeyCode.ButtonB then
   if self.step=='Class' and (self.mode=='Play' or self.mode=='Host') then self.step='Map';draw() else self.Close() end
  elseif self.step=='Map' and (input.KeyCode==Enum.KeyCode.Left or input.KeyCode==Enum.KeyCode.DPadLeft) then cycle(-1)
  elseif self.step=='Map' and (input.KeyCode==Enum.KeyCode.Right or input.KeyCode==Enum.KeyCode.DPadRight) then cycle(1) end
 end)
 return self
end
return M
