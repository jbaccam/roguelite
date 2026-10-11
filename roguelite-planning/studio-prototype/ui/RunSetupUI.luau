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
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local WeaponIcons=require(RS:WaitForChild('WeaponInventoryUI')).Icons
local C=T.Color
local M={}
function M.dashDescription(class,weapon)
 local enabled=Stats.dashes(class)
 if enabled then
  return true,'DASH AVAILABLE - Brawler class ability. Q / controller X / DASH button. '..tostring(Stats.Dash.Cooldown)..'s cooldown.'
 end
 return false,'NO DASH - Brawler class ability only. Choosing or equipping a melee weapon does not grant dash.'
end
function M.classDamageText(pct,class)
 return (pct>0 and '+' or '')..tostring(pct)..'% damage with '..class..' weapons'
end
local function num(x) return (string.format('%.1f',x):gsub('%.0$','')) end
local function rich(color,s) return '<font color="'..T.hex(color)..'">'..s..'</font>' end
-- Specialty and ability (2026-10-09, plans/2026-10-09-chef-roster-weapon-types-design.md; they
-- replaced the class fit chips and the 2 / 4 home weapon rows). The specialty line, as rich text:
-- '+10% damage with Chef weapons. Other weapons: no penalty.' A class whose own drawback lowers
-- some weapons says so: Brawler '... Other weapons: no penalty, apart from your -15% ranged damage.'
function M.specialtyText(class)
 local c=Stats.Classes[class];if not c then return '' end
 local hits={}
 for _,id in {'MeleeDamage','RangedDamage','Damage'} do
  local v=c.buffs[id];if v and v<0 then table.insert(hits,v..'% '..string.lower(Stats.ById[id].label)) end
 end
 return rich(C.lime,Stats.specialtyText(class))..'. Other weapons: no penalty'..(#hits>0 and ', apart from your '..table.concat(hits,' and ') or '')..'.'
end
-- Chef's pizza numbers come from ChefPizza (ReplicatedStorage.RogueliteCombat.ChefPizza), read when
-- drawn: Studio may not have the module yet, and then the line has no numbers. M.Pizza (previews and
-- tests) stands in for the module.
local function pizza()
 if M.Pizza then return M.Pizza end
 local m=combat:FindFirstChild('ChefPizza');if not m then return nil end
 local ok,P=pcall(require,m);return ok and type(P)=='table' and P or nil
end
-- The class ability row: {icon=, title=, text=, dash=bool} or nil (no ability). Chef: pizza drops,
-- e.g. '15% chance (about 1 in 6) on a kill with any Chef weapon; heals 10% of max health and gives
-- Full Belly: +4% damage and attack speed, +3% speed per stack (up to 5, 10 s)'.
-- Brawler: dash (CharacterStats.dashes). Handyman: the free Nail Turret.
function M.ability(class)
 if Stats.dashes(class) then
  return {icon=WeaponIcons[Rules.Signature[class]],title='DASH',dash=true,text=class..' only. Q / controller X / DASH button. '..num(Stats.Dash.Cooldown)..'s cooldown.'}
 end
 local P=pizza()
 if class=='Chef' or (P and P.CLASS==class) then
  local text='Kills with Chef weapons sometimes drop a pizza slice that heals and buffs whoever grabs it.'
  if P and type(P.CHANCE)=='number' and P.CHANCE>0 and type(P.HEAL_FRACTION)=='number' then
   text=string.format('%s%% chance (about 1 in %d) on a kill with any Chef weapon; heals %s%% of max health',num(P.CHANCE*100),math.floor(1/P.CHANCE+1e-6),num(P.HEAL_FRACTION*100))
   -- Full Belly (2026-10-10): '... and gives Full Belly: +4% damage and attack speed, +3% speed per
   -- stack (up to 5, 10 s)'. Older rules without it keep the heal-only line.
   if type(P.buffText)=='function' then text..=' and gives '..(P.BUFF_NAME or 'Full Belly')..': '..P.buffText() end
  end
  -- No pizza slice icon yet: Chef's class icon (the Frying Pan, like the dash and turret rows) stands
  -- in. It was the Pizza Cutter's, which read as a Cutter-only drop (2026-10-10: every Chef weapon).
  return {icon=WeaponIcons[Rules.Signature[class]],title='PIZZA DROPS',text=text}
 end
 if class=='Handyman' then
  return {icon=WeaponIcons[Rules.Signature[class]],title='NAIL TURRET',text='Starts every run with a free Nail Turret that spawns close to you.'}
 end
 return nil
end
-- The class's SPECIALTY and ability rows in an inset: icon, cream label, then the text (the label
-- above the text with o.stack, for narrow phone columns). Shared with the Armory's class details.
-- o: size (15), labelW (118), stack. Returns the inset and its height.
function M.perkRows(parent,name,x,y,w,class,o)
 o=o or {}
 local size=o.size or 15;local labelW=o.stack and 0 or (o.labelW or 118)
 local ab=M.ability(class)
 local dashers={};for _,c in Stats.ClassOrder do if Stats.dashes(c) then table.insert(dashers,c) end end
 local rows={{key='Specialty',icon=WeaponIcons[Rules.Signature[class]],label='SPECIALTY',text=M.specialtyText(class)},
  ab and {key='Ability',icon=ab.icon,label=ab.title,text=ab.text,dash=ab.dash==true}
   or {key='Ability',label='ABILITY',text=rich(C.dim,'None. Dash is '..table.concat(dashers,', ')..' only.'),dash=false}}
 local box=T.panel(parent,name,x,y,w,0,'inset')
 local cy=4;local is=math.floor(size*2.1)
 for i,r in rows do
  local tx=12+is+8+labelW;local tw=w-tx-12
  -- Measured a little narrower than drawn, so rounding never adds a line.
  local th=math.ceil(TextService:GetTextSize(r.text:gsub('<[^>]->',''),size,T.Body,Vector2.new(tw*.94,1000)).Y)+2
  local labelH=size+2
  local rh=o.stack and labelH+th+14 or math.max(is+12,th+16)
  if i>1 then T.make('Frame',box,{Name='Divider'..i,Position=UDim2.fromOffset(10,cy-1),Size=UDim2.fromOffset(w-20,2),BackgroundColor3=Color3.new(0,0,0),BackgroundTransparency=.45,BorderSizePixel=0}) end
  if r.icon then T.icon(box,r.key..'Icon',12,cy+math.floor((rh-is)/2),is,r.icon) end
  local l=T.label(box,r.key..'Label',r.label,12+is+8,o.stack and cy+6 or cy+math.floor((rh-labelH)/2),o.stack and tw or labelW-8,labelH,size-2,C.cream)
  l.TextXAlignment=Enum.TextXAlignment.Left;l.TextStrokeTransparency=.5
  local t=T.text(box,r.key..'Text',r.text,o.stack and 12+is+8 or tx,o.stack and cy+6+labelH or cy+math.floor((rh-th)/2),tw,th,size,C.white)
  t.TextYAlignment=Enum.TextYAlignment.Top
  if r.key=='Ability' then t:SetAttribute('Dash',r.dash) end
  cy+=rh
 end
 box.Size=UDim2.fromOffset(w,cy+4)
 return box,cy+4
end
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

-- One Godly slot (2026-10-10, user: "the god tier starter spot needs to be in the same place in the
-- class selection in queue across all classes and it should prob open up a window of selecting your
-- god items since players might have multiple unlocked ... if you dont even have 1 unlocked they
-- should be greyed out with a lock over them"). Owned Godlies are no longer mixed into the class's
-- tiles: the grid is sized for the biggest class plus the slot (Juggler 7 + 1 = 8 cells), so tiles and
-- the slot sit in exactly the same place for every class. The slot is row 1, last column; the class's
-- weapons fill the other cells in reading order. Example, 4 columns: Chef's 6 weapons take cells
-- 1-3 and 5-7, the slot is cell 4.
function M.godlies() local out={};for _,w in Weapons.List do if w.godly then table.insert(out,w) end end;return out end
function M.gridCells()
 local most=0;for _,c in Stats.ClassOrder do most=math.max(most,#Rules.classWeapons(c)) end
 return most+1
end
-- The cell each class weapon takes (k-th weapon -> cell index), skipping the slot's cell `cols`.
function M.weaponCell(k,cols) return (k>=cols and cols>1) and k+1 or k end
-- The Godly the slot shows: the pick when it is an owned Godly, else the last one chosen here, else
-- the saved loadout's, else the highest tier owned (catalog order breaks ties). nil: none owned.
function M.slotGodly(weapons,pick,last,saved)
 for _,id in {pick,last,saved} do local w=Weapons.ById[id];if w and w.godly and weapons[id] then return w end end
 local best
 for _,w in M.godlies() do local r=weapons[w.id];if r and (not best or (r.tier or 1)>(weapons[best.id].tier or 1)) then best=w end end
 return best
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
 -- Godly slot: godlyChoice the Godly it last showed (kept across classes), picker its open window,
 -- focusSlot set by a pick so the next draw puts a controller back on the slot.
 local godlyChoice,picker,focusSlot
 local openingTween
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
  if openingTween then openingTween:Cancel();openingTween=nil end
  if not screen.Enabled then return end
  local closedMode=self.mode
  screen.Enabled=false;self.mode=nil;self.step=nil;primary=nil
  picker=nil -- the Godly picker lives in root
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
 -- Starter choice: tiles and the Godly picker both set it here; the server checks it again
 -- (RunSetupRules.validLoadout).
 local function choose(id) sel.weapon=id;draw() end
 local function closePicker() if picker then local p=picker;picker=nil;p.Close() end end
 local function canChoose() return profile.classes[sel.class]==true and not (self.mode=='Member' and player:GetAttribute('LobbyLockedIn')==true) end
 -- A Godly picked in the window (tests call it too): owned only; closes the window, then the same
 -- choose() a tile tap uses, and a controller lands back on the slot.
 function self.PickGodly(id)
  local w=Weapons.ById[id]
  if not (root and w and w.godly and profile.weapons[id] and canChoose()) then return false end
  closePicker();focusSlot=true;choose(id)
  return true
 end
 -- Godly picker: all 6 Godlies, owned ones pickable (when the class is owned and the player isn't
 -- locked in), the rest a dim well with a padlock. Picking closes it and the slot becomes the pick.
 local function openGodlyPicker()
  if not root or picker then return end
  local can=canChoose()
  local list=M.godlies();local any=#Rules.ownedGodlies(profile.weapons)>0
  local shown=M.slotGodly(profile.weapons,sel.weapon,godlyChoice,player:GetAttribute('LoadoutWeapon'))
  -- Tiles of 120 with the name under each, half a gap of room either side of a column. Desktop 3 x 2
  -- ("POSEIDON'S TRIDENT" needs the 24 px gap). Phones one row of 6 with bigger, two-line names: the
  -- window is drawn at about .7 there, so 18 px names are 13 screen px.
  local small=G and G.compact
  local S,gy,subH=120,12,34
  local g,nameH,ns,cols=small and 16 or 24,small and 44 or 26,small and 18 or 14,small and 6 or 3
  local cw=cols*(S+g);local chh=subH+math.ceil(#list/cols)*(S+nameH+gy)-gy
  local win=T.window(root,'GodlyPicker','GODLY WEAPONS',cw+36,chh+58,function() picker=nil end)
  picker=win
  -- Controller selection stays inside the window (tiles and X).
  win.Holder.SelectionGroup=true
  for _,k in {'SelectionBehaviorUp','SelectionBehaviorDown','SelectionBehaviorLeft','SelectionBehaviorRight'} do win.Holder[k]=Enum.SelectionBehavior.Stop end
  local sub=any and 'Pick your Godly starter. Any class can use it.' or 'No Godly yet. Get Godly weapons from chests.'
  centred(T.text(win.Body,'Hint',sub,0,0,cw,subH-8,18,any and C.muted or C.gold))
  for k,w in list do
   local rec=profile.weapons[w.id];local x=g/2+((k-1)%cols)*(S+g);local y=subH+math.floor((k-1)/cols)*(S+nameH+gy)
   local selected=rec~=nil and shown==w and sel.weapon==w.id
   local c
   if rec then
    c=T.button(win.Body,'Godly_'..w.id,'',x,y,S,S,function() self.PickGodly(w.id) end,not selected)
    c.Caption.Visible=false;c.Interactable=can
    if not selected then T.setTier(c,rec.tier) end
    local p,barH,is=M.tileParts(S)
    T.icon(c,'Icon',(S-is)/2,p,is,WeaponIcons[w.id])
    T.tierBadge(c,rec.tier,3,3)
    local need=opts.need(rec)
    if barH>=14 and not small then T.upgradeBar(c,'Upgrade',p+2,S-p-barH,S-2*p-4,barH,rec.have,need)
    else T.setBar((T.bar(c,'Upgrade',p+2,S-p-barH,S-2*p-4,barH,need and rec.have>=need and C.gold or C.lime)),need and rec.have/need or 1) end
   else
    c=T.make('ImageButton',win.Body,{Name='Godly_'..w.id,BackgroundTransparency=1,Image='',AutoButtonColor=false,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(S,S)})
    T.panel(c,'Well',0,0,S,S,'inset')
    local art=T.icon(c,'Icon',6,6,S-12,WeaponIcons[w.id]);art.ImageTransparency=.55;art.ImageColor3=Color3.fromRGB(150,150,150);art.ZIndex=2
    M.lock(c,3,3,26)
   end
   c:SetAttribute('Owned',rec~=nil)
   T.label(win.Body,'Name_'..w.id,string.upper(w.name),x-g/2+1,y+S+2,S+g-2,nameH-4,ns,rec and (selected and C.lime or C.white) or C.dim)
  end
 end
 self.OpenGodlyPicker=openGodlyPicker
 function self.GodlyPicker() return picker end

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
  -- Class order everywhere (2026-10-09): Brawler, Gunner, Chef, Juggler, Handyman, Mage; locked
  -- classes stay in place with a padlock.
  local order=Stats.ClassOrder
  local class=sel.class;local owned=profile.classes[class]==true
  -- Tiles (2026-10-10): the class's owned weapons (one starter class per weapon), then the ones you
  -- don't own yet, dimmed and locked; owned Godlies go in the one Godly slot (M.slotGodly), picked
  -- from its window. The grid always has M.gridCells() cells (8), whatever the class.
  local list={}
  for pass=1,2 do for _,w in Rules.classWeapons(class) do if (profile.weapons[w.id]~=nil)==(pass==1) then table.insert(list,w) end end end
  local CELLS=M.gridCells()
  -- Starter tiles never scroll (2026-10-04): M.weaponTiles sizes them to the room. Icons stay at
  -- least 48 screen px (65 page px on a .75x phone page); NOT OWNED tiles are never under that either.
  local iconMin=math.ceil(48/G.px)+1;local lockedMin=iconMin+8
  -- Layout. Desktop: class cards in a row over the details panel (left) and the starting weapons
  -- (right, 600 x 338 under their heading, clear of the buttons at 636). Phones: the same shape:
  -- the six class cards in one short row under the title, then details and weapons side by side;
  -- the weapons get the width their tiles need, the details at least 300.
  -- Example: 889x500 page (667x375 phone): cards 136 x 48, details 377, the 8 cells 4 x 2 at 112 px
  -- (84 screen px); desktop 4 x 2 at 142. Owned and locked starters always share the same grid.
  local cw,ch,cgap,cardsAt,cardsIn -- class card size, gap, position of card n, its parent
  local infoX,infoY,infoW,infoH,wx,wy,ww,tiles,tgap,headH,gridY
  local NOTE_H=cp and 24 or 26 -- the Godly note under the tiles
  if not cp then
   -- Cards 140 tall (were 150) so the details panel is 380 tall and fits every class unscrolled.
   cw,ch,cgap=170,140,14;local x0=(CW-(#order*cw+(#order-1)*cgap))/2
   cardsIn=canvas;cardsAt=function(n) return x0+(n-1)*(cw+cgap),100 end
   infoX,infoY,infoW,infoH=95,252,470,380
   wx,wy,ww,tgap,headH=585,252,600,10,30;gridY=wy+headH+6
   tiles=M.weaponTiles(CELLS,0,ww,626-gridY-NOTE_H,tgap,150,lockedMin)
  else
   -- The map chip (Play, Host, Member) sits at 40-64; without it the cards move up to the top bar.
   local M0,gap=16,14;local midY=math.max(mapText and 70 or 48,G.top+6)
   cw,ch,cgap=math.min(190,math.floor((CW-2*M0-5*8)/#order)),48,8 -- 48: a 36 px tap at the .75x phone page
   local x0=(CW-(#order*cw+(#order-1)*cgap))/2
   cardsIn=canvas;cardsAt=function(n) return x0+(n-1)*(cw+cgap),midY end
   local top=midY+ch+8;local h=CH-64-top -- the buttons start at CH-60
   tgap,headH=6,20;gridY=top+headH+4
   tiles=M.weaponTiles(CELLS,0,CW-2*M0-gap-300,CH-64-gridY-NOTE_H,tgap,112,lockedMin)
   ww=math.max(tiles.w,250) -- the heading row needs about 250
   infoW=math.min(440,CW-2*M0-gap-ww);infoH=h;infoY=top;wy=top
   infoX=(CW-(infoW+gap+ww))/2;wx=infoX+infoW+gap
  end
  -- Class cards in class order; locked cards dimmed with a padlock. Desktop: icon over the name.
  -- Phones: icon left, then the name. No damage badges (2026-10-09: no class-vs-class number).
  for k,c in order do
   local cOwned=profile.classes[c]==true;local selected=class==c
   local x,y=cardsAt(k)
   local card=T.button(cardsIn,'Class_'..c,'',x,y,cw,ch,function()
    if sel.class~=c then starters[sel.class]=sel.weapon;sel.class=c;sel.weapon=starters[c] end
    draw()
   end,not selected)
   card.Interactable=not (mode=='Member' and player:GetAttribute('LobbyLockedIn')==true)
   card.Caption.Visible=false
   if cp then
    local art=T.icon(card,'Icon',6,8,32,WeaponIcons[Rules.Signature[c]]);art.ImageTransparency=cOwned and 0 or .6
    local n=T.label(card,'Name',c,44,13,cw-50,22,17,cOwned and C.white or C.dim);n.TextXAlignment=Enum.TextXAlignment.Left;n.TextWrapped=false
    if not cOwned then M.lock(card,2,2,18) end
   else
    local is=72
    local art=T.icon(card,'Icon',(cw-is)/2,12,is,WeaponIcons[Rules.Signature[c]]);art.ImageTransparency=cOwned and 0 or .6
    local n=T.label(card,'Name',c,0,86,cw,32,24,cOwned and C.white or C.dim);n.Size=UDim2.new(1,0,0,32);n.TextWrapped=false
    if not cOwned then
     M.lock(card,8,8,28)
     local l=T.label(card,'Locked','LOCKED',0,120,cw,22,16,C.gold);l.Size=UDim2.new(1,0,0,22)
    end
   end
  end
  -- Class details, top to bottom: name, description, always-on buffs | drawbacks, then the
  -- specialty and ability rows (2026-10-09; they replaced the weapon damage chips and the 2 / 4 home
  -- weapon rows). Drawn into a holder; if it is taller than the panel (phones, or a locked class
  -- with its buy buttons) the holder moves into a scroll.
  local c=Stats.Classes[class]
  -- The pick: sel.weapon if it is a starter for this class (an owned class weapon or owned Godly).
  local pick
  local valid=Rules.starters(class,profile.weapons)
  for _,w in valid do if w.id==sel.weapon then pick=sel.weapon end end
  -- Not a starter for this class: its signature weapon if owned, else the first owned starter.
  if not pick then
   local sig=Rules.Signature[class]
   pick=(profile.weapons[sig] or #valid==0) and sig or valid[1].id
  end
  local pickW=Weapons.ById[pick]
  local slotW=M.slotGodly(profile.weapons,pick,godlyChoice,player:GetAttribute('LoadoutWeapon'))
  if slotW then godlyChoice=slotW.id end
  local pad=cp and 14 or 18;local tw=infoW-2*pad
  local info=T.panel(canvas,'ClassInfo',infoX,infoY,infoW,infoH,'panel')
  local box=T.frame(info,'Content',0,0,infoW,0)
  local y=cp and 10 or 12
  local n=T.label(box,'Name',class,pad,y,tw,cp and 34 or 36,cp and 28 or 30);n.TextXAlignment=Enum.TextXAlignment.Left
  y+=36
  local descH=math.ceil(TextService:GetTextSize(c.description,16,T.Body,Vector2.new(tw*.96,1000)).Y)+2
  T.text(box,'Description',c.description,pad,y,tw,descH,16,C.muted).TextYAlignment=Enum.TextYAlignment.Top
  y+=descH+6
  local good,bad=Stats.classLines(class)
  local _,h=T.statColumns(box,'AlwaysOn',pad,y,tw,good,bad,{size=cp and 15 or 16,stack=cp})
  y+=h+8
  _,h=M.perkRows(box,'Perks',pad,y,tw,class,{size=cp and 14 or 15,stack=cp})
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
  local function showName(w,text)
   if not nameL.Parent then return end
   if text then nameL.Text=text;nameL.TextColor3=C.gold;return end
   w=w or pickW;local locked=w~=nil and not profile.weapons[w.id]
   nameL.Text=w and string.upper(w.name)..(locked and '  ·  NOT OWNED' or '') or ''
   nameL.TextColor3=locked and C.dim or w==pickW and C.lime or C.white
  end
  showName()
  local S,g=tiles.S,tgap
  local lockedIn=mode=='Member' and player:GetAttribute('LobbyLockedIn')==true
  local function cellXY(i) return ((i-1)%tiles.cols)*(S+g),math.floor((i-1)/tiles.cols)*(S+g) end
  for k,wpn in list do
   local rec=profile.weapons[wpn.id];local canPick=owned and rec~=nil;local selected=canPick and pick==wpn.id
   local size=S;local x,y=cellXY(M.weaponCell(k,tiles.cols))
   local c
   if rec then
    c=T.button(gridIn,'Weapon_'..wpn.id,'',x,y,size,size,function() if canPick then choose(wpn.id) end end,not selected)
    c.Interactable=not lockedIn
    c.Caption.Visible=false
    if not selected then T.setTier(c,rec.tier) end
    local p,barH,is=M.tileParts(size)
    T.icon(c,'Icon',(size-is)/2,p,is,WeaponIcons[wpn.id])
    T.tierBadge(c,rec.tier,3,3)
    -- Copies toward the next tier: "2 / 5" in the bar on big tiles, the bar alone on small ones and
    -- on phones (the count would draw under 12 screen px).
    local need=opts.need(rec)
    if barH>=14 and barH*G.px>=12 then T.upgradeBar(c,'Upgrade',p+2,size-p-barH,size-2*p-4,barH,rec.have,need)
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
  -- The Godly slot, row 1 last column for every class. Owned: the slot's Godly (lime when it is the
  -- pick) with a gold GODLY · ANY CLASS tag (GODLY on small tiles) and a gold chevron: tap to choose.
  -- None owned: a grey well, a padlock over it and GODLY; tapping opens the picker, all locked.
  do
   local x,y=cellXY(tiles.cols);local size=S
   local rec=slotW and profile.weapons[slotW.id]
   local c
   if rec then
    c=T.button(gridIn,'GodlySlot','',x,y,size,size,openGodlyPicker,pick~=slotW.id or not owned)
    c.Caption.Visible=false
    if pick~=slotW.id or not owned then T.setTier(c,rec.tier) end
    local p,barH,is=M.tileParts(size)
    T.icon(c,'Icon',(size-is)/2,p,is,WeaponIcons[slotW.id])
    T.tierBadge(c,rec.tier,3,3)
    -- The full tag, shrunk to the tile's width, while its text still draws at least 11 screen px
    -- (desktop: about 11 px on a 142 px tile, 17 on screen); else just GODLY (phones).
    local ts=cp and 13 or 12;local tagH=ts+8;local full='GODLY · ANY CLASS'
    local fullW=TextService:GetTextSize(full,ts,T.Font,Vector2.new(1000,100)).X*1.12+20
    local fit=math.min(1,(size-8)/fullW)
    local tag,tagW=T.tag(c,'GodlyTag',ts*fit*G.px>=11 and full or 'GODLY',0,0,{h=tagH,size=ts,maxW=size-8,color=Color3.fromRGB(90,70,16),textColor=C.gold})
    tag.Position=UDim2.fromOffset(math.floor((size-tagW)/2),size-p-barH-tagH-3);tag.ZIndex=5;tag.Text.ZIndex=6
    -- Chevron: "more inside".
    local cs=math.clamp(math.floor(size*.2),18,26)
    local chev=T.make('Frame',c,{Name='Swap',Position=UDim2.fromOffset(size-cs-4,4),Size=UDim2.fromOffset(cs,cs),BackgroundColor3=Color3.fromRGB(90,70,16),BorderSizePixel=0,ZIndex=5})
    T.make('UICorner',chev,{CornerRadius=UDim.new(1,0)})
    T.make('UIStroke',chev,{Color=Color3.fromRGB(8,10,11),Thickness=2})
    for _,b in {{.36,45},{.64,-45}} do
     local line=T.make('Frame',chev,{Name='Mark',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(b[1],.5),Size=UDim2.fromScale(.42,.14),Rotation=b[2],BackgroundColor3=C.gold,BorderSizePixel=0,ZIndex=6})
     T.make('UICorner',line,{CornerRadius=UDim.new(1,0)})
    end
    local need=opts.need(rec)
    if barH>=14 and barH*G.px>=12 then T.upgradeBar(c,'Upgrade',p+2,size-p-barH,size-2*p-4,barH,rec.have,need)
    else T.setBar((T.bar(c,'Upgrade',p+2,size-p-barH,size-2*p-4,barH,need and rec.have>=need and C.gold or C.lime)),need and rec.have/need or 1) end
    c.MouseEnter:Connect(function() showName(slotW) end);c.SelectionGained:Connect(function() showName(slotW) end)
   else
    c=T.make('ImageButton',gridIn,{Name='GodlySlot',BackgroundTransparency=1,Image='',AutoButtonColor=false,Selectable=true,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(size,size)})
    T.panel(c,'Well',0,0,size,size,'inset')
    local p=size>=90 and 6 or 4
    local art=T.icon(c,'Icon',p,p,size-2*p,WeaponIcons['36']);art.ImageTransparency=.7;art.ImageColor3=Color3.fromRGB(110,110,110);art.ZIndex=2
    local ls=math.floor(size*.42);M.lock(c,(size-ls)/2,math.floor(size*.16),ls)
    local lh=math.clamp(math.floor(size*.2),16,24)
    local l=T.label(c,'Godly','GODLY',4,size-lh-p,size-8,lh,lh-2,C.dim);l.ZIndex=4
    c.Activated:Connect(function() showName(nil,'GODLY  ·  FROM CHESTS');openGodlyPicker() end)
    c.MouseEnter:Connect(function() showName(nil,'GODLY  ·  FROM CHESTS') end)
    c.SelectionGained:Connect(function() showName(nil,'GODLY  ·  FROM CHESTS') end)
   end
   c.Interactable=not lockedIn
   c:SetAttribute('Owned',rec~=nil);c:SetAttribute('Godly',slotW and slotW.id or '')
   c.MouseLeave:Connect(function() showName() end);c.SelectionLost:Connect(function() showName() end)
  end
  -- Under the tiles: Godlies are the one exception to "starters are your class's weapons".
  local noteW=math.max(tiles.w,ww-(bx-wx));local ns=cp and 16 or 15
  local note=rich(C.gold,'Godly')..' weapons have no class: any class can start with one you own.'
  if cp or TextService:GetTextSize(note:gsub('<[^>]->',''),ns,T.Body,Vector2.new(4000,100)).X*1.2>noteW then note=rich(C.gold,'Godly')..': any class can start one you own.' end
  local nl=T.text(canvas,'GodlyNote',note,bx,gridY+tiles.h+4,noteW,NOTE_H-4,ns,C.muted);nl.TextWrapped=false
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
  -- A Godly picked in its window: a controller lands back on the Godly slot.
  if focusSlot then
   focusSlot=nil
   if Input:GetLastInputType().Name:find('^Gamepad') then T.restoreSelection(canvas,{'Weapons','GodlySlot'}) end
  elseif same then T.restoreSelection(cv,path)
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
   if openingTween then openingTween:Cancel();openingTween=nil end
   cv=frame;cvScale=frame:FindFirstChildOfClass('UIScale')
   G=plan(L)
   cv.AnchorPoint=Vector2.new(.5,.5);cv.Position=UDim2.fromScale(.5,.5);cv.Size=UDim2.fromOffset(G.w,G.h);cvScale.Scale=L.s*U
   draw()
  end)
  if cvScale then
   local s=cvScale.Scale;cvScale.Scale=s*.94
   openingTween=TweenService:Create(cvScale,TweenInfo.new(.16,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=s});openingTween:Play()
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
  -- The Godly picker is on top: Esc / B close it, other keys wait for it.
  if picker then
   if key==Enum.KeyCode.Escape or key==Enum.KeyCode.ButtonB then closePicker() end
   return
  end
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
