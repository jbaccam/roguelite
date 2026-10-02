-- Full-screen run setup: MAP (ladder, difficulty, wave track, rewards) then CLASS (class cards,
-- starting weapon), over the chosen map's blurred mini island (MapSelectBackdrop). Opened by PLAY,
-- LOADOUT and stepping onto a portal pad. Presentation and requests only: the lobby server
-- validates map, difficulty, class and weapon (RunSetupRules) before starting.
-- Modes: Play -> START (server claims a free pad), Host -> START, Member -> READY, Loadout -> CONFIRM.
local RS=game:GetService('ReplicatedStorage')
local Lighting=game:GetService('Lighting')
local Input=game:GetService('UserInputService')
local TweenService=game:GetService('TweenService')
local GuiService=game:GetService('GuiService')
local T=require(RS:WaitForChild('UITheme'))
local Rules=require(RS:WaitForChild('RunSetupRules'))
local Backdrop=require(RS:WaitForChild('MapSelectBackdrop'))
local combat=RS:WaitForChild('RogueliteCombat')
local Stats=require(combat:WaitForChild('CharacterStats'))
local Money=require(combat:WaitForChild('MonetizationConfig'))
local WeaponIcons=require(RS:WaitForChild('WeaponInventoryUI')).Icons
local C=T.Color
local M={}
-- Layout units: page px, U canvas px each (T.canvas, 1920x1080 design). The desktop layout is
-- DWxDH page px, so at 1080p it fills the screen at 1.5x as before. Pages smaller than that
-- (phones) use the compact layout, at least MIN_H tall; shorter pages scroll.
-- Example: 844x390 iPhone 14 (750x369 safe area) -> canvas 1500x738 at .5 -> page 1000x492 at .75x.
local DW,DH=1280,720
local U,MIN_H=1.5,480

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
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='RunSetup',ResetOnSpawn=false,DisplayOrder=60,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,Enabled=false,
  -- Content stays out of phone notches and rounded corners; the shade reaches under them.
  ScreenInsets=Enum.ScreenInsets.DeviceSafeInsets,ClipToDeviceSafeArea=false})
 self.Screen=screen
 local shade=T.make('Frame',screen,{Name='Shade',Position=UDim2.fromOffset(-100,-100),Size=UDim2.new(1,200,1,200),BackgroundColor3=C.shade,BackgroundTransparency=.1,BorderSizePixel=0,Active=true})
 T.make('UIGradient',shade,{Rotation=90,Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.25),NumberSequenceKeypoint.new(.5,.42),NumberSequenceKeypoint.new(1,.1)})})
 -- root: Size 1,1 frame made on open (T.canvas follows its size). cv: the T.canvas frame, in page
 -- px; every piece is drawn straight onto it (canvas), or onto a scroll in it on very short pages.
 -- G: the current layout (plan); CW x CH the content size.
 local root,cv,cvScale,canvas,G
 local CW,CH=DW,DH
 local blur,profile,draw
 local primary -- {button, action} of the current step's primary button (Enter / Start)

 local function plan(L)
  local w,h=L.w/U,L.h/U
  -- corner: width of Roblox's top-bar buttons (~180 screen px) at each top corner, in page px.
  local g={w=w,h=h,top=L.top/U,corner=180/(L.s*U),compact=w<DW-.5 or h<DH-.5}
  g.cw=g.compact and w or DW;g.ch=g.compact and math.max(h,MIN_H) or DH
  return g
 end
 local function centred(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
 -- Back and the primary action, centred under the content (or in the room right of `left`).
 local function buttons(backText,backFn,primaryText,primaryFn,enabled,left)
  local cp=G.compact;local bw,bh,gap=cp and 200 or 210,cp and 54 or 62,cp and 12 or 20
  local c=((left or 0)+CW)/2;local y=cp and CH-60 or 636
  local back=T.button(canvas,'Back',backText,c-gap-bw,y,bw,bh,backFn,true);back.Caption.TextSize=cp and 24 or 26;back.Caption.TextColor3=C.negative
  local go=T.button(canvas,'Primary',primaryText,c+gap,y,bw,bh,primaryFn);go.Caption.TextSize=cp and 24 or 26;go.Interactable=enabled~=false
  primary={button=go,action=enabled~=false and primaryFn or nil}
  return back,go
 end
 -- Compact layout column; scrolls when its content is taller than the room.
 local function column(name,x,y,w,h,contentH)
  if contentH<=h then return T.frame(canvas,name,x,y,w,h) end
  local sc=T.scroll(canvas,name,x,y,w,h);sc.CanvasSize=UDim2.fromOffset(0,contentH)
  return sc
 end
 -- Panel content taller than the panel scrolls inside it; otherwise it is drawn on the panel.
 local function body(panel,contentH)
  if panel.Size.Y.Offset>=contentH then return panel end
  local sc=T.scroll(panel,'Body',0,8,0,0);sc.Size=UDim2.new(1,-8,1,-16);sc.CanvasSize=UDim2.fromOffset(0,contentH)
  return sc
 end
 function self.Close()
  if not screen.Enabled then return end
  screen.Enabled=false;self.mode=nil;self.step=nil;primary=nil
  if root then root:Destroy() end
  root,cv,cvScale,canvas,G=nil,nil,nil,nil,nil
  T.hideTouchControls('RunSetup',false)
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
  -- Compact (phones): smaller headline and tighter rows; the arrows sit below the top bar.
  local cp=G.compact;local hx=G.corner;local hw=CW-2*hx -- top rows clear of the top-bar corners
  T.label(canvas,'Step','CHOOSE A MAP',hx,cp and 4 or 30,hw,cp and 26 or 30,22,C.muted)
  for k=1,#Rules.Maps do
   local on=k==i
   local d=T.make('Frame',canvas,{Name='Dot'..k,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(CW/2+(k-3)*28,cp and 44 or 76),Size=UDim2.fromOffset(on and 16 or 10,on and 16 or 10),BackgroundColor3=on and C.lime or C.dim,BorderSizePixel=0})
   T.make('UICorner',d,{CornerRadius=UDim.new(.5,0)})
   T.make('UIStroke',d,{Color=Color3.fromRGB(8,10,11),Thickness=2}) -- readable over the light island sky
  end
  local ax,aw,ah=cp and 16 or 40,cp and 80 or 90,cp and 100 or 120;local ay=cp and math.max(G.top+4,60) or 236
  if cp then
   T.label(canvas,'MapName',string.upper(m.name),hx,52,hw,56,52,mapOpen and C.white or C.dim)
   T.label(canvas,'Sub','MAP '..i..'  ·  BOSS: '..string.upper(m.boss),hx,108,hw,22,18,C.muted)
  else
   T.label(canvas,'MapName',string.upper(m.name),0,92,DW,100,92,mapOpen and C.white or C.dim)
   T.label(canvas,'Sub','MAP '..i..'  ·  BOSS: '..string.upper(m.boss),0,192,DW,30,22,C.muted)
  end
  -- Wave track: 0 -> 20 with the special waves marked, filled to the best wave reached. One group:
  -- the markers sit on the bar on purpose.
  local TX=cp and 160 or 200;local TW=CW-2*TX;local TY=cp and 30 or 46;local th,ms=cp and 18 or 20,cp and 24 or 28
  local track=T.frame(canvas,'Track',0,cp and 134 or 238,CW,TY+th+(cp and 32 or 36))
  local best=profile.best[key] or 0
  local fill=T.bar(track,'WaveTrack',TX,TY,TW,th,C.lime);T.setBar(fill,best/Rules.WinWave)
  local function marker(wave,tag)
   local x=TX+TW*wave/Rules.WinWave;local reached=best>=wave and wave>0
   local dm=T.make('Frame',track,{Name='Mark'..wave,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(x,TY+th/2),Size=UDim2.fromOffset(ms,ms),Rotation=45,BackgroundColor3=reached and C.lime or tag=='BOSS' and C.red or C.well,BorderSizePixel=0})
   T.make('UIStroke',dm,{Color=Color3.fromRGB(8,10,11),Thickness=3})
   T.label(track,'Wave'..wave,tostring(wave),x-40,TY+th+10,80,cp and 22 or 26,cp and 18 or 22) -- clear of the diamond's tip
   if tag then T.label(track,'Tag'..wave,tag,x-55,0,110,cp and 22 or 28,cp and 18 or 20,tag=='BOSS' and C.negative or C.gold) end
  end
  marker(0);for _,mk in Rules.Milestones do marker(mk[1],mk[2]) end
  local prev=T.button(canvas,'PrevMap','<',ax,ay,aw,ah,function() cycle(-1) end,true);prev.Caption.TextSize=cp and 56 or 64
  local nxt=T.button(canvas,'NextMap','>',CW-ax-aw,ay,aw,ah,function() cycle(1) end,true);nxt.Caption.TextSize=cp and 56 or 64
  stage(i,not mapOpen)
  -- Locked map: the island is a silhouette; one big padlock and the unlock rule replace the
  -- difficulty and reward rows, which would all be locked anyway.
  if not mapOpen then
   local ls=cp and 88 or 136
   T.icon(canvas,'LockBig',(CW-ls)/2,cp and 220 or 352,ls,'lock')
   T.label(canvas,'Locked','LOCKED',0,cp and 312 or 490,CW,cp and 40 or 52,cp and 40 or 48,C.white)
   T.label(canvas,'Unlock',string.upper(m.unlock),0,cp and 356 or 546,CW,cp and 28 or 32,cp and 22 or 26,C.gold)
   buttons('BACK',self.Close,'NEXT',nil,false)
   return
  end
  local won=profile.wins[key]==true
  local status=not unlocked and string.upper(Rules.difficultyLock(i,diff))
   or won and ('WON  ·  BEST WAVE '..best) or best>0 and ('BEST WAVE '..best..' OF '..Rules.WinWave) or 'NOT PLAYED YET'
  T.label(canvas,'Status',status,TX,cp and 214 or 342,TW,cp and 24 or 26,cp and 20 or 22,unlocked and C.cream or C.gold)
  -- Difficulty: each tier buffs enemies and pays more emeralds. Locked tiers show a padlock, with
  -- the caption moved left of it (NIGHTMARE is nearly as wide as the button).
  local DWB,DBH,DGAP=200,56,16;local dx=(CW-(3*DWB+2*DGAP))/2
  for k,d in Rules.Difficulties do
   local open=Rules.difficultyUnlocked(profile.wins,i,d.id)
   local b=T.button(canvas,'Diff_'..d.id,string.upper(d.id),dx+(k-1)*(DWB+DGAP),cp and 244 or 378,DWB,DBH,function() sel.difficulty=d.id;draw() end,d.id~=diff or not mapOpen)
   b.Caption.TextSize=cp and 22 or 24
   if d.id~=diff or not mapOpen then b.Caption.TextColor3=not open and C.dim or d.id=='Hard' and C.gold or d.id=='Nightmare' and C.negative or C.lime end
   if not open then M.lock(b,DWB-36,(DBH-24)/2,24);b.Caption.Size=UDim2.new(1,-52,1,-8) end
  end
  local effect=diff=='Normal' and 'Standard enemies  ·  standard emeralds'
   or string.format('Enemies  x%s health  ·  x%s damage  ·  x%s emeralds',tier.hp,tier.damage,tier.reward)
  centred(T.text(canvas,'DiffEffect',effect,0,cp and 304 or 438,CW,22,cp and 17 or 18,C.muted))
  -- Rewards for this map and difficulty.
  local tiles={
   {'emerald',Rules.winEmeralds(i,diff)..' EMERALDS','by wave '..Rules.WinWave..'  ·  paid every 5 waves',C.emerald},
   {'achievements',won and 'CLAIMED' or '+'..Rules.firstWinEmeralds(i,diff)..' EMERALDS','first win bonus',won and C.dim or C.emerald},
   {'play','ENDLESS','keep going after wave '..Rules.WinWave,C.lime},
  }
  -- Compact pages under 120 px of room get row tiles: icon left, value and a two-line caption.
  local gap=cp and 16 or 22;local tw=math.min(cp and 300 or 270,(CW-32-2*gap)/3);local x0=(CW-(#tiles*tw+(#tiles-1)*gap))/2
  local ry=cp and 332 or 474;local rh=cp and math.min(138,CH-68-ry) or 138
  for k,t in tiles do
   local tile=T.panel(canvas,'Reward'..k,x0+(k-1)*(tw+gap),ry,tw,rh,'inset')
   if rh>=120 then
    T.icon(tile,'Icon',(tw-56)/2,8,56,t[1])
    T.label(tile,'Value',t[2],8,68,tw-16,30,24,t[4])
    centred(T.text(tile,'Caption',t[3],10,100,tw-20,22,16,C.muted))
   else
    local ty=math.floor((rh-62)/2)
    T.icon(tile,'Icon',10,(rh-44)/2,44,t[1])
    T.label(tile,'Value',t[2],62,ty,tw-72,26,22,t[4]).TextXAlignment=Enum.TextXAlignment.Left
    T.text(tile,'Caption',t[3],62,ty+26,tw-72,36,16,C.muted)
   end
  end
  buttons('BACK',self.Close,'NEXT',function() self.step='Class';draw() end,unlocked)
 end

 -- Step 2: class and starting weapon ---------------------------------------------------
 local function drawClass()
  local mode=self.mode
  local cp=G.compact;local hx=G.corner;local hw=CW-2*hx -- top rows clear of the top-bar corners
  T.label(canvas,'Step','CHOOSE YOUR CLASS',hx,cp and 4 or 18,hw,cp and 36 or 42,cp and 30 or 38)
  local mapText,mapIndex=nil,sel.map
  if mode=='Member' then
   local portal=myPortal();local id=opts.hostMap();mapIndex=id and Rules.MapIndex[id] or sel.map
   local d=portal and portal:GetAttribute('Difficulty')
   mapText=id and Rules.Maps[mapIndex].name..(d and d~='Normal' and '  ·  '..d or '') or 'Host is choosing the map'
  elseif mode~='Loadout' then mapText=Rules.Maps[sel.map].name..(sel.difficulty~='Normal' and '  ·  '..sel.difficulty or '') end
  if mapText then T.label(canvas,'MapChip',string.upper(mapText),hx,cp and 40 or 64,hw,cp and 24 or 26,cp and 18 or 19,C.cream) end
  stage(mapIndex,false)
  local order=Rules.classOrder(profile.classes)
  local class=sel.class;local owned=profile.classes[class]==true
  local list=Rules.homeWeapons(class)
  for _,w in Rules.ownedGodlies(profile.weapons) do table.insert(list,w) end -- any class can start with one
  -- Layout. Desktop: class cards in a row over the details panel and a 3-wide weapon grid.
  -- Compact (phones): three columns between the title and the buttons, class cards 2 wide,
  -- details, weapons 3 wide (2 on narrow pages); a column too tall for the room scrolls.
  -- Example: 1000x492 page (iPhone 14) -> classes 250, details 320, weapons 3 x 114 px cells.
  local cw,ch,cgap,cardsAt,cardsIn -- class card size, gap, position of card n, its parent
  local infoX,infoY,infoW,infoH,wx,wy,ww,wcols,cell,wgap,gridIn,gx,gy
  if not cp then
   cw,ch,cgap=170,150,14;local x0=(CW-(#order*cw+(#order-1)*cgap))/2
   cardsIn=canvas;cardsAt=function(n) return x0+(n-1)*(cw+cgap),100 end
   infoX,infoY,infoW,infoH=95,270,440,360
   wx,wy,ww,wcols,cell,wgap=560,270,625,3,150,12
   gridIn=canvas;gx,gy=wx+(ww-(3*cell+2*wgap))/2,306
   -- Owned Godlies join the class's six: past two rows the grid scrolls.
   if #list>6 then local rows=math.ceil(#list/3);gridIn=column('Weapons',gx,306,3*cell+2*wgap+8,2*cell+wgap,rows*cell+(rows-1)*wgap);gx,gy=0,0 end
  else
   local M0,gap=16,14;local midY=math.max(70,G.top+6);local midH=CH-68-midY
   cw,ch,cgap=120,100,10;local classW=2*cw+cgap
   local avail=CW-2*M0-classW-2*gap
   wgap=10;cell=math.floor(math.min((avail-320-28)/3,(midH-44)/2,124));wcols=3
   if cell<104 then wcols=2;cell=math.clamp(math.floor(math.min((avail-320-18)/2,(midH-54)/3)),104,124) end
   ww=wcols*cell+(wcols-1)*wgap+8 -- +8: room for a scroll bar
   infoW=math.min(440,avail-ww);infoH=midH;infoY=midY;wy=midY
   local x0=(CW-(classW+infoW+ww+2*gap))/2
   infoX=x0+classW+gap;wx=infoX+infoW+gap
   local rows=math.ceil(#order/2)
   cardsIn=column('Classes',x0,midY,classW,midH,rows*ch+(rows-1)*cgap)
   cardsAt=function(n) return ((n-1)%2)*(cw+cgap),math.floor((n-1)/2)*(ch+cgap) end
   local wrows=math.ceil(#list/wcols)
   gridIn=column('Weapons',wx,wy+34,ww,midH-34,wrows*cell+(wrows-1)*wgap);gx,gy=0,0
  end
  -- Class cards: owned first, then locked. Names centred; locked cards dimmed with a padlock.
  for k,c in order do
   local cOwned=profile.classes[c]==true;local selected=class==c
   local x,y=cardsAt(k)
   local card=T.button(cardsIn,'Class_'..c,'',x,y,cw,ch,function() sel.class=c;sel.weapon=nil;draw() end,not selected)
   card.Caption.Visible=false
   local is=cp and 44 or 72
   local art=T.icon(card,'Icon',(cw-is)/2,cp and 6 or 12,is,WeaponIcons[Rules.Signature[c]]);art.ImageTransparency=cOwned and 0 or .6
   local n=T.label(card,'Name',c,0,cp and 52 or 86,cw,cp and 24 or 32,cp and 20 or 24,cOwned and C.white or C.dim);n.Size=UDim2.new(1,0,0,cp and 24 or 32);n.TextWrapped=false
   if not cOwned then
    M.lock(card,cw-(cp and 30 or 40),cp and 6 or 10,cp and 24 or 28)
    local l=T.label(card,'Locked','LOCKED',0,cp and 76 or 120,cw,cp and 20 or 22,16,C.gold);l.Size=UDim2.new(1,0,0,cp and 20 or 22)
   end
  end
  -- Class details. Rows top to bottom; the panel scrolls when they don't fit (phones).
  local lines={}
  for _,d in Stats.List do
   local v=Stats.Classes[class].buffs[d.id]
   if v then table.insert(lines,'<font color="'..T.hex(v>0 and C.lime or C.negative)..'">'..(v>0 and '+' or '')..v..d.unit..'</font>  '..d.label) end
  end
  local pad=20;local tw=infoW-2*pad
  local nameY,nameH=cp and 10 or 14,cp and 36 or 40
  local descY,descH=nameY+nameH+4,cp and 60 or 48
  local buffY,buffH=descY+descH+4,(cp and 22 or 21)*#lines
  local tailY=buffY+buffH+8;local noteH=cp and 40 or 24 -- second note: two lines on phones
  local contentH=owned and tailY+42+noteH+12 or tailY+noteH+4+54+12
  local info=T.panel(canvas,'ClassInfo',infoX,infoY,infoW,infoH,'panel')
  local box=body(info,contentH)
  local n=T.label(box,'Name',class,pad,nameY,tw,nameH,cp and 28 or 32);n.TextXAlignment=Enum.TextXAlignment.Left
  T.text(box,'Description',Stats.Classes[class].description,pad,descY,tw,descH,cp and 17 or 18,C.muted)
  T.text(box,'Buffs',table.concat(lines,'\n'),pad,buffY,tw,buffH,cp and 18 or 19)
  if owned then
   T.text(box,'Affinity','Equip 2 home weapons for the first class bonus, 4 for the stronger one.',pad,tailY,tw,40,16,C.cream)
   T.text(box,'Armor','Armor: none yet  ·  armor sets arrive with chest rewards',pad,tailY+42,tw,noteH,16,C.dim)
  else
   T.text(box,'Earn','Earn it: '..(Rules.ClassUnlock[class] or 'an achievement'),pad,tailY,tw,noteH,16,C.gold)
   local key='Class'..class;local product=Money.Products[key];local by,bw=tailY+noteH+4,(tw-12)/2
   if product then T.button(box,'BuyRobux','R$ '..product.robux,pad,by,bw,54,function() combat.PurchaseRequest:FireServer(key) end).Caption.TextSize=20 end
   local eb=T.button(box,'BuyEmeralds','',pad+bw+12,by,bw,54,function()
    local r=combat.ProfileAction:InvokeServer('BuyClass',class)
    T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
   end,true)
   eb.Caption.Visible=false;opts.cost(eb,Money.ClassEmeraldPrice,'emerald',20)
  end
  -- Starting weapon grid. Phone cells (under 150) shrink the art and give names two lines.
  local h=T.label(canvas,'WeaponTitle','STARTING WEAPON',wx,wy,ww,30,cp and 22 or 24);h.TextXAlignment=Enum.TextXAlignment.Left
  local pick=sel.weapon or Rules.Signature[class]
  local big=cell>=150;local is=big and 70 or math.min(70,cell-68)
  for k,wpn in list do
   local rec=profile.weapons[wpn.id];local canPick=owned and rec~=nil;local selected=canPick and pick==wpn.id
   local c=T.button(gridIn,'Weapon_'..wpn.id,'',gx+((k-1)%wcols)*(cell+wgap),gy+math.floor((k-1)/wcols)*(cell+wgap),cell,cell,function()
    if canPick then sel.weapon=wpn.id;draw() end
   end,not selected)
   c.Caption.Visible=false
   if rec and not selected then T.setTier(c,rec.tier) end
   local art=T.icon(c,'Icon',(cell-is)/2,big and 12 or 6,is,WeaponIcons[wpn.id]);art.ImageTransparency=rec and 0 or .6
   if big then centred(T.text(c,'Name',wpn.name,10,84,cell-20,22,17,rec and C.white or C.dim))
   else centred(T.text(c,'Name',wpn.name,6,8+is,cell-12,36,16,rec and C.white or C.dim)) end
   if rec then
    T.tierBadge(c,rec.tier,big and 10 or 6,big and 10 or 6)
    if big then T.upgradeBar(c,'Upgrade',16,cell-36,cell-32,18,rec.have,opts.need(rec)) else T.upgradeBar(c,'Upgrade',10,cell-22,cell-20,16,rec.have,opts.need(rec)) end
   else centred(T.text(c,'Locked','NOT OWNED',8,big and cell-38 or cell-24,cell-16,20,16,C.dim)) end
  end
  -- Host: open pad (up to 4) or solo. Compact: bottom-left, with BACK / START right of it.
  local tabs=mode=='Host' or mode=='Play'
  if tabs then T.tabs(canvas,cp and 16 or 95,cp and CH-60 or 636,cp and 240 or 260,cp and 54 or 62,{'Open','Solo'},sel.solo and 'Solo' or 'Open',function(id) sel.solo=id=='Solo';draw() end) end
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
  end,owned and weaponOwned,cp and tabs and 272 or nil)
 end

 draw=function()
  if not cv then return end
  local path=T.selectionPath(cv) -- controller selection, kept across the redraw
  for _,c in cv:GetChildren() do if not c:IsA('UIScale') then c:Destroy() end end
  CW,CH=G.cw,G.ch;primary=nil;canvas=cv
  if CH>G.h+.5 then
   -- Shorter than the compact layout (screens under ~360 px tall): the whole screen scrolls.
   canvas=T.scroll(cv,'Scroll',0,0,G.w,G.h);canvas.CanvasSize=UDim2.fromOffset(0,CH);canvas.VerticalScrollBarInset=Enum.ScrollBarInset.None
  end
  if self.step=='Map' then drawMap() else drawClass() end
  -- Desktop: the DWxDH layout sits in the middle of a taller (4:3) or wider (ultrawide) page.
  local ox,oy=math.floor((G.w-CW)/2),math.floor((G.h-CH)/2)
  if canvas==cv and (ox>0 or oy>0) then
   for _,c in cv:GetChildren() do if c:IsA('GuiObject') then c.Position+=UDim2.fromOffset(ox,oy) end end
  end
  -- Opened with a controller (or its button is gone after a step change): start on the primary
  -- button (BACK while it is disabled).
  local same=path and cv;for _,name in path or {} do same=same and same:FindFirstChild(name) end
  if same then T.restoreSelection(cv,path)
  elseif path or Input:GetLastInputType().Name:find('^Gamepad') then
   T.restoreSelection(canvas,{primary and primary.button.Interactable and 'Primary' or 'Back'})
  end
 end
 function self.Open(mode)
  profile=opts.profile()
  if not Rules.mapUnlocked(profile.wins,sel.map) then sel.map=1 end
  sel.difficulty=sel.difficulty or 'Normal'
  if not Rules.difficultyUnlocked(profile.wins,sel.map,sel.difficulty) then sel.difficulty='Normal' end
  if not profile.classes[sel.class] then sel.class='Brawler' end
  local wasOpen=screen.Enabled
  self.mode=mode;self.step=(mode=='Member' or mode=='Loadout') and 'Class' or 'Map'
  screen.Enabled=true
  if wasOpen and cv then draw();return end
  T.hideTouchControls('RunSetup',true)
  root=T.frame(screen,'Root',0,0,0,0);root.Size=UDim2.fromScale(1,1)
  -- Lays out now and again whenever the screen changes size (window resize, phone rotation).
  -- The canvas is kept in page px (U canvas px each) and centred, so the open pop grows from
  -- the middle.
  T.canvas(root,function(L,frame)
   cv=frame;cvScale=frame:FindFirstChildOfClass('UIScale')
   G=plan(L)
   cv.AnchorPoint=Vector2.new(.5,.5);cv.Position=UDim2.fromScale(.5,.5);cv.Size=UDim2.fromOffset(G.w,G.h);cvScale.Scale=L.s*U
   draw()
  end)
  if cvScale then
   local s=cvScale.Scale;cvScale.Scale=s*.94
   TweenService:Create(cvScale,TweenInfo.new(.16,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=s}):Play()
  end
 end
 function self.Refresh() if screen.Enabled then profile=opts.profile();draw() end end
 function self.IsOpen() return screen.Enabled end
 setupRemote.OnClientEvent:Connect(function(kind,ok,message)
  if kind~='Result' then return end
  if type(message)=='string' then T.toast(screen.Enabled and screen or opts.toastScreen,message,ok and C.lime or C.negative) end
  if ok and (self.mode=='Host' or self.mode=='Member' or self.mode=='Play') then self.Close() end
 end)
 Input.InputBegan:Connect(function(input,processed)
  if not screen.Enabled or Input:GetFocusedTextBox() or GuiService.MenuIsOpen then return end
  local key=input.KeyCode
  -- B still goes back while a button is selected (the controller selection may report it processed).
  if processed and key~=Enum.KeyCode.ButtonB then return end
  if key==Enum.KeyCode.Escape or key==Enum.KeyCode.ButtonB then
   if self.step=='Class' and (self.mode=='Play' or self.mode=='Host') then self.step='Map';draw() else self.Close() end
  -- Enter / Start: NEXT, START, READY or CONFIRM (the same button the screen shows).
  elseif key==Enum.KeyCode.Return or key==Enum.KeyCode.KeypadEnter or key==Enum.KeyCode.ButtonStart then
   if primary and primary.action and primary.button.Parent and primary.button.Interactable then primary.action() end
  -- D-pad moves the controller selection once a button is selected, so the bumpers change map too.
  elseif self.step=='Map' and (key==Enum.KeyCode.Left or key==Enum.KeyCode.DPadLeft or key==Enum.KeyCode.ButtonL1) then cycle(-1)
  elseif self.step=='Map' and (key==Enum.KeyCode.Right or key==Enum.KeyCode.DPadRight or key==Enum.KeyCode.ButtonR1) then cycle(1) end
 end)
 return self
end
return M
