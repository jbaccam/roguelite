-- Full-screen run setup: MAP (ladder, difficulty, wave track, rewards) then CLASS (class cards,
-- starting weapon), over the chosen map's blurred mini island (MapSelectBackdrop). Opened by PLAY,
-- the Armory class picker and stepping onto a portal pad. Presentation and requests only: the lobby server
-- validates map, difficulty, class and weapon (RunSetupRules) before starting.
-- Modes: Play/Host -> READY UP, Member -> READY UP / UNREADY, Loadout -> SAVE CLASS.
local RS=game:GetService('ReplicatedStorage')
local Lighting=game:GetService('Lighting')
local Input=game:GetService('UserInputService')
local TweenService=game:GetService('TweenService')
local GuiService=game:GetService('GuiService')
local TextService=game:GetService('TextService')
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

-- Starting-weapon tiles (2026-10-04, user: "I don't like scrolling, it should be just smaller boxes
-- or better UI design and layout"): every starter shows at once and the tiles shrink to fit. An
-- owned tile of size S is padding, the icon, then a thin upgrade bar: tileParts(S) -> padding, bar
-- height, icon size. Example: S 85 -> 3, 6, 71 (53 screen px on a phone's .75x page).
function M.tileParts(S)
 local p=S>=110 and 7 or S>=90 and 5 or 3;local bar=S>=110 and 14 or S>=90 and 8 or 6
 return p,bar,S-2*p-bar-2
end
-- One balanced grid for the whole class. Ownership changes the tile's treatment, never its
-- footprint: one owned pan should sit beside the other starters, not above a bank of tiny locks.
-- Returns the old shape for callers, with split=false and identical owned/locked sizes.
function M.weaponTiles(o,u,W,H,g,maxS,lockedMin)
 local function grid(n,S)
  if n<=0 then return 0,0,0,0 end
  local most=math.max(1,math.floor((W+g)/(S+g)));local rows=math.ceil(n/most);local cols=math.ceil(n/rows)
  return cols,rows,cols*S+(cols-1)*g,rows*S+(rows-1)*g
 end
 local S=math.floor(maxS)
 while S>24 do
  local c,r,w,h=grid(o+u,S)
  if w<=W and h<=H then return {S=S,s=S,cols=c,rows=r,split=false,w=w,h=h} end
  S-=1
 end
 local c,r,w,h=grid(o+u,S)
 return {S=S,s=S,cols=c,rows=r,split=false,w=w,h=h}
end

-- opts: profile() -> LobbyUI profile, need(rec), cost(parent,amount,asset,size),
-- selection (shared with the lobby HUD), findPortal(), hostMap() -> map id chosen by my pad's host.
function M.new(player,opts)
 local self={mode=nil,step=nil}
 local sel=opts.selection
 local starters={} -- keep each browsed class's chosen starter; tapping the same class never clears it
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
  -- px: screen px per page px (.75 on phones), so sizes can be held to a screen minimum.
  local g={w=w,h=h,top=L.top/U,corner=180/(L.s*U),px=L.s*U,compact=w<DW-.5 or h<DH-.5}
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
 -- Panel content taller than the panel scrolls inside it; otherwise it is drawn on the panel.
 local function body(panel,contentH)
  if panel.Size.Y.Offset>=contentH then return panel end
  local sc=T.scroll(panel,'Body',0,8,0,0);sc.Size=UDim2.new(1,-8,1,-16);sc.CanvasSize=UDim2.fromOffset(0,contentH)
  return sc
 end
 function self.Close()
  if not screen.Enabled then return end
  local closedMode=self.mode
  screen.Enabled=false;self.mode=nil;self.step=nil;primary=nil
  if root then root:Destroy() end
  root,cv,cvScale,canvas,G=nil,nil,nil,nil,nil
  T.hideTouchControls('RunSetup',false)
  if blur then blur:Destroy();blur=nil end
  Backdrop.Hide()
  if opts.onClose then opts.onClose(closedMode) end
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
  -- Gear power (GEAR_POWER.md): at the map's recommended power it plays like Pine Valley does for a
  -- new player. Yours counts the starter you'd take (picked here or in the Armory), armor and pet.
  local mine=Rules.power(player,sel.weapon or player:GetAttribute('LoadoutWeapon') or player:GetAttribute('RunWeapon'))
  effect=string.format('<font color="%s">Your power %d  ·  recommended %d</font>   ·   %s',T.hex(mine>=m.power and C.lime or C.gold),mine,m.power,effect)
  centred(T.text(canvas,'DiffEffect',effect,0,cp and 304 or 438,CW,24,cp and 17 or 18,C.muted))
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
  T.label(canvas,'Step',mode=='Loadout' and 'ARMORY · CHOOSE CLASS' or 'CONFIRM CLASS & STARTER',hx,cp and 4 or 18,hw,cp and 36 or 42,cp and 30 or 38)
  local mapText,mapIndex=nil,sel.map
  if mode=='Member' then
   local portal=myPortal();local id=opts.hostMap();mapIndex=id and Rules.MapIndex[id] or sel.map
   local d=portal and portal:GetAttribute('Difficulty')
   mapText=id and Rules.Maps[mapIndex].name..(d and d~='Normal' and '  ·  '..d or '') or 'Host is choosing the map'
  elseif mode~='Loadout' then mapText=Rules.Maps[sel.map].name..(sel.difficulty~='Normal' and '  ·  '..sel.difficulty or '') end
  if mapText then
   local chip=T.label(canvas,'MapChip',string.upper(mapText),hx,cp and 40 or 64,hw,cp and 24 or 26,cp and 18 or 19,C.cream)
   -- A member on a pad already counting down (pulled along by their party, 2026-10-03) sees the
   -- time left, so they know to LOCK IN. The loop ends with the redraw or close that removes the chip.
   if mode=='Member' then
    local base=chip.Text
    task.spawn(function()
     while chip.Parent do
      local portal=myPortal();local at=portal and portal:GetAttribute('LaunchAt')
      local picking=portal and portal:GetAttribute('Picking') or 0
      local count=portal and portal:GetAttribute('QueueCount') or 0
      chip.Text=type(at)=='number' and base..'  ·  STARTING IN '..math.max(0,math.ceil(at-workspace:GetServerTimeNow())) or base..(portal and portal:GetAttribute('MapId') and ('  ·  READY %d / %d'):format(count-picking,count) or '')
      task.wait(.25)
     end
    end)
   end
  end
  stage(mapIndex,false)
  local order=Rules.classOrder(profile.classes)
  local class=sel.class;local owned=profile.classes[class]==true
  -- Starters (2026-10-04): every weapon with this class anywhere in its list, owned first, then owned
  -- Godlies (any class can start with one), then NOT OWNED. Up to 17 (Thrower 11 + 6 Godlies).
  local list,unowned={},{}
  for _,w in Rules.classWeapons(class) do table.insert(profile.weapons[w.id] and list or unowned,w) end
  for _,w in Rules.ownedGodlies(profile.weapons) do table.insert(list,w) end
  local nOwned=#list
  table.move(unowned,1,#unowned,#list+1,list)
  -- Starter tiles never scroll (2026-10-04): M.weaponTiles sizes them to the room. Icons stay at
  -- least 48 screen px (65 page px on a .75x phone page); NOT OWNED tiles are never under that either.
  local iconMin=math.ceil(48/G.px)+1;local lockedMin=iconMin+8
  -- Layout. Desktop: class cards in a row over the details panel (left) and the starting weapons
  -- (right, 600 x 338 under their heading, clear of the buttons at 636). Phones: the same shape:
  -- the six class cards in one short row under the title, then details and weapons side by side;
  -- the weapons get the width their tiles need, the details at least 300.
  -- Example: 889x500 page (667x375 phone, 58 px top bar): cards 136 x 46, details 303, 17 weapons
  -- 6 x 3 at 85 px (icons 53 screen px). Owned and locked starters always share the same grid.
  local cw,ch,cgap,cardsAt,cardsIn -- class card size, gap, position of card n, its parent
  local infoX,infoY,infoW,infoH,wx,wy,ww,tiles,tgap,headH,gridY
  if not cp then
   -- Cards 140 tall (were 150) so the details panel is 380 tall and fits every class unscrolled.
   cw,ch,cgap=170,140,14;local x0=(CW-(#order*cw+(#order-1)*cgap))/2
   cardsIn=canvas;cardsAt=function(n) return x0+(n-1)*(cw+cgap),100 end
   infoX,infoY,infoW,infoH=95,252,470,380
   wx,wy,ww,tgap,headH=585,252,600,10,30;gridY=wy+headH+6
   tiles=M.weaponTiles(nOwned,#list-nOwned,ww,626-gridY,tgap,150,lockedMin)
  else
   -- The map chip (Play, Host, Member) sits at 40-64; without it the cards move up to the top bar.
   local M0,gap=16,14;local midY=math.max(mapText and 70 or 48,G.top+6)
   cw,ch,cgap=math.min(190,math.floor((CW-2*M0-5*8)/#order)),46,8
   local x0=(CW-(#order*cw+(#order-1)*cgap))/2
   cardsIn=canvas;cardsAt=function(n) return x0+(n-1)*(cw+cgap),midY end
   local top=midY+ch+8;local h=CH-64-top -- the buttons start at CH-60
   tgap,headH=6,20;gridY=top+headH+4
   tiles=M.weaponTiles(nOwned,#list-nOwned,CW-2*M0-gap-300,CH-64-gridY,tgap,112,lockedMin)
   ww=math.max(tiles.w,250) -- the heading row needs about 250
   infoW=math.min(440,CW-2*M0-gap-ww);infoH=h;infoY=top;wy=top
   infoX=(CW-(infoW+gap+ww))/2;wx=infoX+infoW+gap
  end
  -- Class cards: owned first, then locked; locked cards dimmed with a padlock. Desktop: icon over
  -- the name, the fit badge over the corner. Phones: icon left, then the name over an inline badge.
  for k,c in order do
   local cOwned=profile.classes[c]==true;local selected=class==c
   local x,y=cardsAt(k)
   local card=T.button(cardsIn,'Class_'..c,'',x,y,cw,ch,function()
    if sel.class~=c then starters[sel.class]=sel.weapon;sel.class=c;sel.weapon=starters[c] end
    draw()
   end,not selected)
   card.Interactable=not (mode=='Member' and player:GetAttribute('LobbyLockedIn')==true)
   card.Caption.Visible=false
   -- Weapon fit badge: damage with this class's weapons when you play the picked class
   -- (CharacterStats.ClassFit). DMG with the number (2026-10-03: a bare "-5%" read like a discount);
   -- the details panel says what it means.
   local _,pct=Stats.classFit({home=c},class)
   if cp then
    local art=T.icon(card,'Icon',6,7,32,WeaponIcons[Rules.Signature[c]]);art.ImageTransparency=cOwned and 0 or .6
    local n=T.label(card,'Name',c,44,2,cw-50,21,17,cOwned and C.white or C.dim);n.TextXAlignment=Enum.TextXAlignment.Left;n.TextWrapped=false
    T.fitBadge(card,'Fit',44,24,math.min(cw-50,88),19,pct,'DMG',true)
    if not cOwned then M.lock(card,2,2,18) end
   else
    local is=72
    local art=T.icon(card,'Icon',(cw-is)/2,12,is,WeaponIcons[Rules.Signature[c]]);art.ImageTransparency=cOwned and 0 or .6
    local n=T.label(card,'Name',c,0,86,cw,32,24,cOwned and C.white or C.dim);n.Size=UDim2.new(1,0,0,32);n.TextWrapped=false
    local bw,bh=58,44
    local badge=T.fitBadge(card,'Fit',cw-bw+8,-8,bw,bh,pct,'DMG');badge.ZIndex=5;badge.Word.TextSize=13
    for _,d in badge:GetDescendants() do if d:IsA('GuiObject') then d.ZIndex=6 end end
    if not cOwned then
     M.lock(card,8,8,28)
     local l=T.label(card,'Locked','LOCKED',0,120,cw,22,16,C.gold);l.Size=UDim2.new(1,0,0,22)
    end
   end
  end
  -- Class details, top to bottom: name, description, weapon damage (the card badges), always-on buffs |
  -- drawbacks, then the 2 / 4 home weapon bonuses. Drawn into a holder; if it is taller than the
  -- panel (phones, or a locked class with its buy buttons) the holder moves into a scroll.
  local c=Stats.Classes[class]
  local pad=cp and 14 or 18;local tw=infoW-2*pad
  local info=T.panel(canvas,'ClassInfo',infoX,infoY,infoW,infoH,'panel')
  local box=T.frame(info,'Content',0,0,infoW,0)
  -- Spacing 2 px tighter (2026-10-03) so the weapon damage chips fit on desktop: a class with 4 buff
  -- rows ends about 364 px down the 380 px panel, unscrolled.
  local y=cp and 10 or 12
  local n=T.label(box,'Name',class,pad,y,tw,cp and 34 or 36,cp and 28 or 30);n.TextXAlignment=Enum.TextXAlignment.Left
  y+=36
  local descH=math.ceil(TextService:GetTextSize(c.description,cp and 16 or 16,T.Body,Vector2.new(tw,1000)).Y)+2
  T.text(box,'Description',c.description,pad,y,tw,descH,16,C.muted).TextYAlignment=Enum.TextYAlignment.Top
  y+=descH+6
  -- The card badges spelled out (2026-10-03: the legend sentence didn't explain the +/-): your damage
  -- with each class's weapons as this class, one chip per class (its card's icon), best first,
  -- coloured like the badges. Gunner: Gunner +15%, Thrower 0%, Handyman 0%, Juggler -5%, Mage -5%,
  -- Brawler -15%. Desktop: 3 x 2 with 'Godly: no change' on the heading line (66 px in all);
  -- phones: 2 across and the Godly line under them.
  local fits={}
  for i,other in Stats.ClassOrder do local _,pct=Stats.classFit({home=other},class);table.insert(fits,{c=other,pct=pct,i=i}) end
  table.sort(fits,function(a,b) if a.pct~=b.pct then return a.pct>b.pct end return a.i<b.i end)
  local head,godly='WEAPON DAMAGE AS A '..string.upper(class),'Godly: no change'
  local headW=math.ceil(TextService:GetTextSize(head,14,T.Font,Vector2.new(1000,100)).X*1.12)
  local noteW=math.ceil(TextService:GetTextSize(godly,14,T.Body,Vector2.new(1000,100)).X*1.12)
  local inline=headW+12+noteW<=tw
  local headH=T.section(box,'FitTitle',head,pad,y,inline and tw-noteW-8 or tw,14)
  if inline then T.text(box,'FitGodly',godly,pad+tw-noteW,y,noteW,headH,14,C.muted).TextXAlignment=Enum.TextXAlignment.Right end
  y+=headH+3
  local cols=tw>=400 and 3 or 2;local fw,fh=math.floor((tw-(cols-1)*6)/cols),20
  for k,f in fits do
   local own=f.c==class
   local chip=T.make('Frame',box,{Name='Fit_'..f.c,Position=UDim2.fromOffset(pad+((k-1)%cols)*(fw+6),y+math.floor((k-1)/cols)*(fh+3)),Size=UDim2.fromOffset(fw,fh),BackgroundColor3=own and Color3.fromRGB(32,48,24) or Color3.fromRGB(26,32,36),BorderSizePixel=0})
   T.make('UICorner',chip,{CornerRadius=UDim.new(0,6)})
   T.make('UIStroke',chip,{Color=own and C.lime or Color3.fromRGB(8,10,11),Thickness=own and 2 or 1.5})
   T.icon(chip,'Icon',3,1,fh-2,WeaponIcons[Rules.Signature[f.c]])
   T.text(chip,'Name',f.c,fh+4,0,fw-fh-52,fh,14,own and C.white or C.muted)
   T.label(chip,'Pct',T.fitText(f.pct),fw-46,0,42,fh,15,T.fitColor(f.pct)).TextXAlignment=Enum.TextXAlignment.Right
  end
  local rows=math.ceil(#fits/cols)
  y+=rows*fh+(rows-1)*3
  if not inline then T.text(box,'FitGodly','Godly weapons: no change',pad,y+3,tw,18,14,C.muted);y+=21 end
  y+=6
  local good,bad=Stats.classLines(class)
  local _,h=T.statColumns(box,'AlwaysOn',pad,y,tw,good,bad,{size=cp and 15 or 16,stack=cp})
  y+=h+6
  _,h=T.homeRows(box,'HomeBonus',pad,y,tw,{{n=2,text=Stats.bonusText(c.two)},{n=4,text='also '..Stats.bonusText(c.four)}},{size=cp and 14 or 15,stack=cp,labelW=126})
  y+=h+8
  if not owned then
   T.text(box,'Earn','Earn it: '..(Rules.ClassUnlock[class] or 'an achievement'),pad,y,tw,cp and 40 or 24,16,C.gold)
   y+=(cp and 40 or 24)+4
   local key='Class'..class;local product=Money.Products[key];local bw=(tw-12)/2
   if product then T.button(box,'BuyRobux','R$ '..Money.price(key),pad,y,bw,54,function() combat.PurchaseRequest:FireServer(key) end).Caption.TextSize=20 end
   local eb=T.button(box,'BuyEmeralds','',pad+bw+12,y,bw,54,function()
    local r=combat.ProfileAction:InvokeServer('BuyClass',class)
    T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
   end,true)
   eb.Caption.Visible=false;opts.cost(eb,Money.ClassEmeraldPrice,'emerald',20)
   y+=54+12
  end
  box.Size=UDim2.fromOffset(infoW,y)
  if y>infoH then
   local sc=T.scroll(info,'Body',0,8,0,0);sc.Size=UDim2.new(1,-8,1,-16);sc.CanvasSize=UDim2.fromOffset(0,y)
   box.Parent=sc
  end
  -- Starting weapons (2026-10-04, no scrolling): every tile shows at once (M.weaponTiles), the block
  -- centred under its heading. Owned: icon, tier badge and upgrade bar; the pick is the lime tile.
  -- NOT OWNED: a dim well with a padlock, sharing the same rows and size. Names: the pick's
  -- beside the heading; hovering, gamepad-selecting or tapping a tile shows that one's instead.
  local bx=wx+math.floor((ww-tiles.w)/2)
  local gridIn=T.frame(canvas,'Weapons',bx,gridY,tiles.w,tiles.h)
  local head,hs='STARTING WEAPON',cp and 18 or 24
  local headW=math.ceil(TextService:GetTextSize(head,hs,T.Font,Vector2.new(1000,100)).X*1.12)+6
  T.label(canvas,'WeaponTitle',head,bx,wy,headW,headH,hs).TextXAlignment=Enum.TextXAlignment.Left
  local nameL=T.label(canvas,'WeaponName','',bx+headW+10,wy,math.max(80,wx+ww-(bx+headW+10)),headH,hs-4,C.lime);nameL.TextXAlignment=Enum.TextXAlignment.Left
  nameL.TextWrapped=false;nameL.TextTruncate=Enum.TextTruncate.AtEnd
  -- The pick, if it is an owned starter for this class; else the class's signature weapon (a
  -- saved Handyman Nail Gun opened as a Mage shows the Magic Staff). The server checks it again.
  local pick=Rules.Signature[class];local pickW
  for _,w in list do if w.id==sel.weapon and profile.weapons[w.id] then pick=w.id end end
  for _,w in list do if w.id==pick then pickW=w end end
  local function showName(w)
   if not nameL.Parent then return end
   w=w or pickW;local locked=w~=nil and not profile.weapons[w.id]
   nameL.Text=w and string.upper(w.name)..(locked and '  ·  NOT OWNED' or '') or ''
   nameL.TextColor3=locked and C.dim or w==pickW and C.lime or C.white
  end
  showName()
  local S,g=tiles.S,tgap
  for k,wpn in list do
   local rec=profile.weapons[wpn.id];local canPick=owned and rec~=nil;local selected=canPick and pick==wpn.id
   local size,x,y=S,((k-1)%tiles.cols)*(S+g),math.floor((k-1)/tiles.cols)*(S+g)
   local c
   if rec then
    c=T.button(gridIn,'Weapon_'..wpn.id,'',x,y,size,size,function() if canPick then sel.weapon=wpn.id;draw() end end,not selected)
    c.Interactable=not (mode=='Member' and player:GetAttribute('LobbyLockedIn')==true)
    c.Caption.Visible=false
    if not selected then T.setTier(c,rec.tier) end
    local p,barH,is=M.tileParts(size)
    T.icon(c,'Icon',(size-is)/2,p,is,WeaponIcons[wpn.id])
    T.tierBadge(c,rec.tier,3,3)
    -- Copies toward the next tier: "2 / 5" in the bar on big tiles, the bar alone on small ones.
    local need=opts.need(rec)
    if barH>=14 then T.upgradeBar(c,'Upgrade',p+2,size-p-barH,size-2*p-4,barH,rec.have,need)
    else T.setBar((T.bar(c,'Upgrade',p+2,size-p-barH,size-2*p-4,barH,need and rec.have>=need and C.gold or C.lime)),need and rec.have/need or 1) end
   else
    c=T.make('ImageButton',gridIn,{Name='Weapon_'..wpn.id,BackgroundTransparency=1,Image='',AutoButtonColor=false,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(size,size)})
    T.panel(c,'Well',0,0,size,size,'inset')
    local p=size>=90 and 6 or 4
    local art=T.icon(c,'Icon',p,p,size-2*p,WeaponIcons[wpn.id]);art.ImageTransparency=.55;art.ImageColor3=Color3.fromRGB(150,150,150);art.ZIndex=2
    local ls=math.clamp(math.floor(size*.26),16,26);M.lock(c,3,3,ls)
    c.Activated:Connect(function() showName(wpn) end) -- touch has no hover: a tap names it
   end
   c:SetAttribute('Owned',rec~=nil)
   c.MouseEnter:Connect(function() showName(wpn) end);c.MouseLeave:Connect(function() showName() end)
   c.SelectionGained:Connect(function() showName(wpn) end);c.SelectionLost:Connect(function() showName() end)
  end
  -- Host: Open pad (anyone, up to 4) or Private (only you and your party; just you when you're not
  -- in one). Private was Solo (user, 2026-10-03: "what if were in a group ... that wanted it to be
  -- private"). sel.solo still carries it. Compact: bottom-left, with BACK / START right of it.
  local tabs=mode=='Host' or mode=='Play'
  if tabs then T.tabs(canvas,cp and 16 or 95,cp and CH-60 or 636,cp and 240 or 260,cp and 54 or 62,{'Open','Private'},sel.solo and 'Private' or 'Open',function(id) sel.solo=id=='Private';draw() end) end
  local locked=mode=='Member' and player:GetAttribute('LobbyLockedIn')==true
  local portal=mode=='Member' and myPortal()
  local mapReady=mode~='Member' or (portal~=nil and portal:GetAttribute('MapId')~=nil)
  local labels={Play='READY UP',Host='READY UP',Member=locked and 'UNREADY' or mapReady and 'READY UP' or 'WAIT FOR HOST',Loadout='SAVE CLASS'}
  local weaponOwned=profile.weapons[pick]~=nil
  local back=(mode=='Play' or mode=='Host') and function() self.step='Map';draw() end or self.Close
  local _,go=buttons((mode=='Play' or mode=='Host') and 'BACK' or 'CLOSE',back,owned and labels[mode] or 'LOCKED',function()
   if locked then setupRemote:FireServer('Unready');return end
   if mode=='Play' or mode=='Host' then
    player:SetAttribute('LobbyMap',Rules.Maps[sel.map].id)
    -- LobbyUI won't reopen this screen when the server puts this player on the pad it just started.
    self.startedAt=os.clock()
    setupRemote:FireServer(mode=='Play' and 'Play' or 'Start',Rules.Maps[sel.map].id,class,pick,sel.solo==true,sel.difficulty)
   elseif mode=='Member' then setupRemote:FireServer('Ready',class,pick)
   else setupRemote:FireServer('Loadout',class,pick) end
  end,locked or (owned and weaponOwned and mapReady and player:GetAttribute('ProfileLoaded')==true),cp and tabs and 272 or nil)
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
  -- Once already readied, always show the exact server-confirmed class and weapon.
  if mode=='Member' and player:GetAttribute('LobbyLockedIn')==true then
   sel.class=player:GetAttribute('RunClass') or sel.class;sel.weapon=player:GetAttribute('RunWeapon') or sel.weapon
  end
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
 function self.FocusClass(class)
  if not Stats.Classes[class] then return end
  if sel.class~=class then
   starters[sel.class]=sel.weapon;sel.class=class;sel.weapon=starters[class] or Rules.Signature[class]
  end
  self.Refresh()
 end
 function self.IsOpen() return screen.Enabled end
 setupRemote.OnClientEvent:Connect(function(kind,ok,message,action)
  if kind~='Result' then return end
  if type(message)=='string' then T.toast(screen.Enabled and screen or opts.toastScreen,message,ok and C.lime or C.negative) end
  if ok then
   if action=='Unready' then self.Refresh()
   elseif self.mode=='Host' or self.mode=='Member' or self.mode=='Play' or self.mode=='Loadout' then self.Close() end
  end
 end)
 player:GetAttributeChangedSignal('LobbyLockedIn'):Connect(function() if self.mode=='Member' then self.Refresh() end end)
 Input.InputBegan:Connect(function(input,processed)
  if not screen.Enabled or Input:GetFocusedTextBox() or GuiService.MenuIsOpen then return end
  local key=input.KeyCode
  -- B still goes back while a button is selected (the controller selection may report it processed).
  if processed and key~=Enum.KeyCode.ButtonB then return end
  if key==Enum.KeyCode.Escape or key==Enum.KeyCode.ButtonB then
   if self.step=='Class' and (self.mode=='Play' or self.mode=='Host') then self.step='Map';draw() else self.Close() end
  -- Enter / Start: NEXT, START, LOCK IN or CONFIRM (the same button the screen shows).
  elseif key==Enum.KeyCode.Return or key==Enum.KeyCode.KeypadEnter or key==Enum.KeyCode.ButtonStart then
   if primary and primary.action and primary.button.Parent and primary.button.Interactable then primary.action() end
  -- D-pad moves the controller selection once a button is selected, so the bumpers change map too.
  elseif self.step=='Map' and (key==Enum.KeyCode.Left or key==Enum.KeyCode.DPadLeft or key==Enum.KeyCode.ButtonL1) then cycle(-1)
  elseif self.step=='Map' and (key==Enum.KeyCode.Right or key==Enum.KeyCode.DPadRight or key==Enum.KeyCode.ButtonR1) then cycle(1) end
 end)
 return self
end
return M
