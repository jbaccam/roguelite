-- Pause screen (plans/2026-10-02-L-pause.md): RESUME / SETTINGS / RESTART / LEAVE RUN between the
-- player's stats and build, over the run behind a darker see-through veil. Opening it asks the
-- server to pause (RunAction SetPaused); the server freezes the run only once every living member
-- has paused and reports it on RogueliteCombat (RunPaused, RunPausedCount, RunLivingCount) and on
-- each player (Paused). Presentation and requests only.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local Http=game:GetService('HttpService')
local Input=game:GetService('UserInputService')
local GuiService=game:GetService('GuiService')
local TextService=game:GetService('TextService')
local T=require(RS:WaitForChild('UITheme'))
local FX=require(RS:WaitForChild('StoreFX'))
local combat=RS:WaitForChild('RogueliteCombat')
local Stats=require(combat:WaitForChild('CharacterStats'))
local Catalog=require(combat:WaitForChild('ShopCatalog'))
local LevelUps=require(combat:WaitForChild('LevelUpCatalog'))
local Rules=require(RS:WaitForChild('RunSetupRules'))
local WeaponIcons=require(RS:WaitForChild('WeaponInventoryUI')).Icons
local C=T.Color
local INK=FX.INK
local M={}
-- Weapon types' literal icons (2026-10-09): the same table as ItemCardUI.TypeIcon / ShopUI.TypeIcon.
local TYPE_ICON={Blade='03',Blunt='06',Gun='00',Thrown='13',Explosive='11',Elemental='35',Tool='26',Culinary='01',Trick='18'}
M.PAUSE_ICON='rbxassetid://109142479841413' -- ui/assets/hud/pause.png
-- Solo RESTART: plan J's RunAction 'Restart' (ab93d9a) ends the run as Left (rewards so far kept)
-- and starts the same map and difficulty again. Set false to hide the button.
M.RESTART=true
-- Stats shown, by group; every value already includes items and level-ups.
M.Groups={
 {'OFFENSE',{'Damage','AttackSpeed','CritChance','CritDamage','MeleeDamage','RangedDamage'}},
 {'DEFENSE',{'MaxHP','Armor','Dodge'}},
 {'RECOVERY',{'Regeneration','LifeSteal'}},
 {'UTILITY',{'MoveSpeed','PickupRadius','Luck'}},
}
local SIDE_W,MID_W=520,400 -- design widths of the side panels and the button column
local function center(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
local function left(l) l.TextXAlignment=Enum.TextXAlignment.Left;return l end
local function right(l) l.TextXAlignment=Enum.TextXAlignment.Right;return l end
local function short(n)
 n=math.floor(tonumber(n) or 0)
 for _,u in {{1e9,'B'},{1e6,'M'},{1e3,'K'}} do if n>=u[1] then local v=n/u[1];return (v>=100 and tostring(math.floor(v)) or string.format('%.1f',math.floor(v*10)/10)):gsub('%.0$','')..u[2] end end
 return tostring(n)
end
-- See-through dark panel, like the lobby's quest tracker.
local function glass(parent,name,x,y,w,h)
 local g=T.make('Frame',parent,{Name=name,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),BackgroundColor3=INK,BackgroundTransparency=.5,BorderSizePixel=0})
 T.make('UICorner',g,{CornerRadius=UDim.new(0,16)});T.make('UIStroke',g,{Color=INK,Thickness=2,Transparency=.35})
 return g
end
-- A player's name on one line, up to `size` px. Long names shrink: display names run to 20
-- characters, and "xX_DragonSlayer99_Xx" fits a 4-player card at 18 px on PC and 12 px on an
-- 844x390 phone. Below 13 px (11 on a phone) it ends in "…" instead, so it never runs into the next
-- card. Under the canvas UIScale text sizes are screen pixels (`s` is the scale), and the box is too
-- short for two lines at the smallest size, so a name never wraps.
local function fitName(parent,text,x,y,w,h,size,s,color)
 local min=math.max(11,math.floor(13*s))
 local shown=text
 while #shown>1 and TextService:GetTextSize(shown==text and text or shown..'…',min,T.Font,Vector2.new(1e4,100)).X>(w-4)*s do shown=shown:sub(1,(utf8.offset(shown,-1) or #shown)-1) end
 local l=left(T.label(parent,'Name',shown==text and text or shown..'…',x,y,w,h,size,color));l.FitText.MinTextSize=min
 return l
end
-- With a note, the title keeps the left 55% and the note the rest, so on a narrow panel (387 on a
-- 667x375 phone) "LEVEL-UPS" and "level 9 · 9 picks" shrink instead of running into each other.
local function section(parent,y,w,title,note)
 left(FX.title(parent,'Section_'..title,title,24,y,note and math.floor(w*.55)-32 or w-48,32,24))
 if note then right(T.text(parent,'Note_'..title,note,math.floor(w*.55),y+6,math.ceil(w*.45)-24,24,16,C.muted)) end
 local rule=T.make('Frame',parent,{Name='Rule_'..title,Position=UDim2.fromOffset(24,y+38),Size=UDim2.fromOffset(w-48,2),BackgroundColor3=C.lime,BorderSizePixel=0})
 T.make('UIGradient',rule,{Transparency=NumberSequence.new(0,1)})
 return y+48
end

-- opts (previews and tests only): parent (where the ScreenGui goes), state (a PlayerStates-like
-- folder), runState, flags (stands in for RogueliteCombat's run attributes), remote
-- ({FireServer=fn}), party() (the run's members, downed ones included, you first).
function M.new(player,opts)
 opts=opts or {}
 player=player or Players.LocalPlayer
 local runState=opts.runState or RS:WaitForChild('RogueliteRunState')
 local state=opts.state or combat:WaitForChild('PlayerStates'):WaitForChild(tostring(player.UserId))
 local remote=opts.remote or combat:WaitForChild('RunAction')
 local flags=opts.flags or combat -- RunMap, RunDifficulty, RunPaused, RunPausedCount, RunLivingCount
 local gui=T.make('ScreenGui',opts.parent or player:WaitForChild('PlayerGui'),{Name='PauseMenu',ResetOnSpawn=false,DisplayOrder=70,Enabled=false,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,IgnoreGuiInset=true})
 local veil=T.make('TextButton',gui,{Name='Veil',Text='',AutoButtonColor=false,Active=true,Modal=true,Size=UDim2.fromScale(1,1),BackgroundColor3=Color3.fromRGB(4,7,8),BackgroundTransparency=.34,BorderSizePixel=0})
 local root=T.frame(gui,'Root',0,0,0,0);root.Size=UDim2.fromScale(1,1)
 local self={Gui=gui,Root=root,open=false}
 -- confirmWin: the Leave Run popup; restarting: when RESTART was pressed (waiting on the server);
 -- sync: keeps the server's pause in step with this menu (set below, live screens only).
 local settingsWindow,confirmWin,restarting,sync,redraw

 local function snapshot()
  local raw=state:GetAttribute('ShopSnapshot');if not raw then return {} end
  local ok,data=pcall(Http.JSONDecode,Http,raw)
  return ok and type(data)=='table' and data or {}
 end
 local function runInfo()
  local m=Rules.Maps[Rules.MapIndex[flags:GetAttribute('RunMap')] or 0]
  local diff=flags:GetAttribute('RunDifficulty') or 'Normal'
  local wave=runState:GetAttribute('Wave') or 1
  local color=diff=='Hard' and C.gold or diff=='Nightmare' and C.negative or C.lime
  -- The goal in sight (2026-10-03): WAVE 7 / 20 until the win, then ENDLESS WAVE 21. The tutorial
  -- keeps plain WAVE 2.
  local waveText=runState:GetAttribute('Won') and ('ENDLESS WAVE '..wave) or flags:GetAttribute('TutorialRun') and ('WAVE '..wave) or ('WAVE '..wave..' / '..Rules.WinWave)
  return string.upper(m and m.name or 'RUN'),string.upper(diff),color,waveText,wave
 end
 -- Everyone in the run, downed players too (their card says down; they don't count toward
 -- "n / m PAUSED"). You first, then the rest in a fixed order so cards don't swap around.
 local function party()
  if opts.party then return opts.party() end
  local list={}
  for _,p in Players:GetPlayers() do if p:GetAttribute('RunMember') then table.insert(list,p) end end
  table.sort(list,function(a,b) if (a==player)~=(b==player) then return a==player end;return a.UserId<b.UserId end)
  return list
 end

 function self.Close(silent)
  if not self.open then return end
  self.open=false;gui.Enabled=false;restarting=nil
  if settingsWindow then settingsWindow.Close() end
  if confirmWin then confirmWin.Close() end
  if not silent then remote:FireServer('SetPaused',false) end
  if sync then sync(true) end
 end
 function self.Open()
  if self.open or player:GetAttribute('RunDown') or player:GetAttribute('RunResult') or not player:GetAttribute('RunMember') then return end
  self.open=true;gui.Enabled=true;redraw()
  remote:FireServer('SetPaused',true)
  if sync then sync(true) end
  T.gamepadSelect(root)
 end
 function self.Toggle() if self.open then self.Close() else self.Open() end end

 local layoutNow
 local canvas,relayout=T.canvas(root,function(L,canvasFrame) layoutNow=L;if self.open then redraw() end end)
 redraw=function()
  for _,c in canvas:GetChildren() do if not c:IsA('UIScale') then c:Destroy() end end
  local L=layoutNow;if not L then return end
  local w,h=L.w,L.h
  local frozen=flags:GetAttribute('RunPaused')==true
  local members=party()
  local solo=#members<=1 -- the server's RESTART rule too: one run member, downed or not
  -- Only living members count toward "n / m PAUSED" (the server's RunPausedCount / RunLivingCount);
  -- a downed player never blocks a freeze. Counted here too until those attributes arrive.
  local up,upPaused=0,0
  for _,p in members do if not p:GetAttribute('RunDown') then up+=1;if p:GetAttribute('Paused') then upPaused+=1 end end end
  local count,living=flags:GetAttribute('RunPausedCount') or upPaused,flags:GetAttribute('RunLivingCount') or up
  local many=living>1 -- with everyone else down you pause alone, as in solo
  -- Short screens (phones): an 844x390 phone gets a 1688x780 canvas and Roblox's top bar covers up
  -- to 116 of it, so the plate and the map line share one row and the buttons close up. Every PC
  -- window gets a canvas at least 1080 tall and keeps the roomy layout.
  local tight=h-L.top<800
  -- Title plate, then map · difficulty · wave, the status pill and (in a party) who has paused.
  local y=L.top+(tight and 4 or 12)
  local mapName,diff,diffColor,waveText=runInfo()
  -- Phones: the map line sits right of the plate, on the plate's middle, and the pair is centred
  -- on the screen. There the line draws as tall as its box (30 → 15 px at .5 scale), so the box is
  -- the text's width at that size: one line, nothing left over to push the pair off centre.
  local iw=w
  if tight then iw=math.min(w-440,TextService:GetTextSize(mapName..'  ·  '..diff..'  ·  '..waveText,math.min(22,math.floor(30*L.s)),T.Font,Vector2.new(1e4,100)).X/L.s+8) end
  local px=tight and w/2-(350+iw)/2+18 or w/2-150 -- the left stone pokes 18 out of the plate
  local plate=T.panel(canvas,'TitlePlate',px,y,300,66,'panel');T.caps(plate,44)
  T.icon(plate,'Icon',40,11,44,M.PAUSE_ICON)
  left(T.label(plate,'Title','PAUSED',92,8,180,50,40))
  if not tight then y+=74 end
  local info=center(T.text(canvas,'RunInfo',string.format('%s  ·  <font color="%s">%s</font>  ·  %s',mapName,T.hex(diffColor),diff,waveText),tight and px+332 or 0,tight and y+18 or y,iw,30,22))
  info.Font=T.Font
  y+=tight and 74 or 40
  -- Shorter words on phones. The pill is at least its design width and grows to fit the words at
  -- full size (19 px; a phone draws them as tall as the pill allows), so they stay on one line.
  local status=frozen and (many and 'EVERYONE PAUSED  ·  GAME FROZEN' or 'GAME FROZEN') or (many and (count..' / '..living..' PAUSED  ·  '..(tight and 'GAME KEEPS GOING UNTIL ALL PAUSE' or 'THE GAME KEEPS GOING UNTIL EVERYONE PAUSES')) or 'PAUSING…')
  local pw=math.min(w-80,math.max(frozen and (many and 560 or 360) or (many and 820 or 300),TextService:GetTextSize(status,math.min(frozen and 22 or 19,math.floor(38*L.s)),T.Font,Vector2.new(1e4,100)).X/L.s+48))
  local pill=T.make('Frame',canvas,{Name='Status',Position=UDim2.fromOffset(w/2-pw/2,y),Size=UDim2.fromOffset(pw,46),BackgroundColor3=frozen and Color3.fromRGB(47,95,14) or Color3.fromRGB(110,74,10),BorderSizePixel=0})
  T.make('UICorner',pill,{CornerRadius=UDim.new(1,0)});T.make('UIStroke',pill,{Color=INK,Thickness=3})
  local pl=center(FX.title(pill,'Text',status,12,4,pw-24,38,frozen and 22 or 19,nil));pl.TextColor3=frozen and C.limeSoft or Color3.fromRGB(255,217,138)
  y+=56
  if not solo then
   -- One card per member (up to 4): headshot, the name on its own line across the card, then
   -- ✓ paused / playing / down. Your card has a lime edge. Phones get wider cards (340 vs 300) so
   -- a 20-character name still draws at 11+ px there: 4 cards fill 1396 of an 844x390 phone's 1688.
   local n=#members;local cw=math.min(tight and 340 or 300,math.floor((w-64-(n-1)*12)/n));local x=w/2-(n*cw+(n-1)*12)/2
   for i,p in members do
    local down,paused,you=p:GetAttribute('RunDown')==true,p:GetAttribute('Paused')==true,p==player
    local c=T.make('Frame',canvas,{Name='Member'..i,Position=UDim2.fromOffset(x+(i-1)*(cw+12),y),Size=UDim2.fromOffset(cw,54),BackgroundColor3=INK,BackgroundTransparency=down and .62 or .45,BorderSizePixel=0})
    T.make('UICorner',c,{CornerRadius=UDim.new(0,12)})
    if you then T.make('UIStroke',c,{Color=C.lime,Thickness=2,Transparency=.25}) end
    local head=T.make('ImageLabel',c,{Name='Head',BackgroundTransparency=1,Position=UDim2.fromOffset(6,6),Size=UDim2.fromOffset(42,42),ImageTransparency=down and .55 or 0});T.headshot(head,p.UserId)
    T.make('UICorner',head,{CornerRadius=UDim.new(1,0)})
    fitName(c,p.DisplayName,54,4,cw-60,24,18,L.s,down and C.muted or C.white)
    local sx=54
    if paused and not down then FX.check(c,54,31,18);sx=78 end
    left(T.text(c,'Status',(down and 'down' or paused and 'paused' or 'playing')..(you and '  ·  you' or ''),sx,29,cw-sx-10,22,15,down and C.negative or paused and C.limeSoft or C.gold))
   end
   y+=66
  end
  -- Three columns below: stats | buttons | build. Side panels share what's left of the width.
  local top=y+(tight and 0 or 10);local panelH=h-top-(tight and 12 or 24)
  local side=math.clamp(math.floor((w-MID_W-4*40)/2),300,SIDE_W)
  local gap=math.floor((w-2*side-MID_W)/4)
  local lx,mx,rx=gap,gap*2+side,gap*3+side+MID_W
  -- Left: stats (scrolls on short screens).
  local L1=glass(canvas,'Stats',lx,top,side,panelH)
  local ls=T.scroll(L1,'List',0,0,side,panelH);ls.ScrollBarThickness=4
  local sy=section(ls,14,side,'STATS')
  -- SETS first (2026-10-09, plans/2026-10-09-chef-roster-weapon-types-design.md): each equipped weapon
  -- type, its copies and the bonus it gives now. Numbers come from CharacterStats.typeLines.
  local setIds={}
  for i=1,6 do local slot=state:FindFirstChild('Slot'..i);local id=slot and slot:GetAttribute('WeaponId') or '';if id~='' then table.insert(setIds,id) end end
  local setLines=Stats.typeLines(setIds)
  if #setLines>0 then
   left(T.label(ls,'Group_SETS','SETS',24,sy,side-48,22,15,C.lime));sy+=26
   for _,r in setLines do
    local on=r.count>=2
    local row=T.make('Frame',ls,{Name='Set_'..r.type,Position=UDim2.fromOffset(24,sy),Size=UDim2.fromOffset(side-48,60),BackgroundColor3=INK,BackgroundTransparency=on and .35 or .6,BorderSizePixel=0})
    T.make('UICorner',row,{CornerRadius=UDim.new(0,10)})
    T.icon(row,'Icon',8,10,40,WeaponIcons[TYPE_ICON[r.type]])
    left(T.label(row,'Type',string.upper(r.type)..'  ·  '..r.count,56,4,side-48-64,26,20,on and C.white or C.muted))
    local now=on and (r.text:gsub('^'..r.type..' %d+: ','')) or 'No bonus yet. Sets start at 2.'
    left(T.text(row,'Bonus',now,56,30,side-48-64,26,15,on and C.lime or C.cream))
    sy+=66
   end
   sy+=8
  end
  local values=Stats.read(state)
  for _,g in M.Groups do
   left(T.label(ls,'Group_'..g[1],g[1],24,sy,side-48,22,15,C.lime));sy+=26
   for _,id in g[2] do
    local d=Stats.ById[id]
    if d then
     left(T.text(ls,'Name_'..id,d.label,36,sy,side*.6-36,26,18,Color3.fromRGB(201,209,211)))
     local v=values[id] or d.base -- lime above the base value, red below (like the shop's stats)
     right(T.label(ls,'Value_'..id,Stats.format(d,v),side*.55,sy,side*.45-24,26,20,v>d.base and C.lime or v<d.base and C.negative or C.white))
     sy+=27
    end
   end
   sy+=8
  end
  local snap=snapshot()
  left(T.label(ls,'Group_RUN','THIS RUN',24,sy,side-48,22,15,C.lime));sy+=26
  for _,r in {{'Level',tostring(snap.level or 1)},{'Kills',short(player:GetAttribute('RunKills'))},{'Damage dealt',short(player:GetAttribute('RunDamage'))}} do
   left(T.text(ls,'Name_'..r[1],r[1],36,sy,side*.6-36,26,18,Color3.fromRGB(201,209,211)))
   right(T.label(ls,'Value_'..r[1],r[2],side*.55,sy,side*.45-24,26,20))
   sy+=27
  end
  ls.CanvasSize=UDim2.fromOffset(0,sy+16)
  -- Centre: actions. Phones close up the gaps (RESUME to the leave note: 496 → 388 tall), keep
  -- buttons 72 tall (the 36 px tap minimum at .5 scale) and use one short line per note, each with
  -- room above the next button. A party's RESTART says SOLO ONLY on the button itself there.
  local bh=tight and 72 or 70
  local by=top+(tight and 0 or 44)
  local resume=FX.button(canvas,'Resume','RESUME',mx,by,MID_W,tight and 80 or 86,function() self.Close() end);resume.Caption.TextSize=34
  center(T.text(canvas,'ResumeHint',Input.TouchEnabled and '' or 'or press P',mx,by+(tight and 84 or 90),MID_W,22,15,C.muted))
  by+=tight and 118 or 132
  local settings=FX.button(canvas,'Settings','SETTINGS',mx,by,MID_W,bh,function()
   if settingsWindow then settingsWindow.Close() return end
   settingsWindow=T.settingsWindow(gui);settingsWindow.Root.Destroying:Connect(function() settingsWindow=nil end)
  end,true);settings.Caption.TextSize=26
  by+=bh+(tight and 12 or 20)
  if M.RESTART then
   -- The menu stays up until the run really restarts (its results flash closes it, below) or the
   -- server says no, so a refused restart can't leave the run paused behind a closed menu.
   local restart=FX.button(canvas,'Restart',restarting and 'RESTARTING...' or (tight and not solo) and 'RESTART  ·  SOLO ONLY' or 'RESTART',mx,by,MID_W,bh,function()
    if not solo or restarting then return end
    local mine=os.clock();restarting=mine;remote:FireServer('Restart');redraw()
    task.delay(5,function() if restarting==mine and self.open then restarting=nil;redraw();T.toast(gui,"Couldn't restart. Try again",C.negative) end end)
   end,true)
   restart.Caption.TextSize=26
   if not solo then restart.Interactable=false;if not tight then center(T.text(canvas,'RestartHint','Restart is for solo runs',mx,by+bh+2,MID_W,22,14,C.muted)) end end
   by+=bh+(tight and 12 or 40)
  end
  -- LEAVE RUN opens the shared confirm (UITheme.leaveConfirm, 2026-10-03), any time in the run. The
  -- menu stays open until the run has ended for this player (the results close it, below); a
  -- refusal shows in the popup. It used to send LeaveRun and close itself without unpausing, while
  -- the server refused mid-wave leaves: a paused solo run stayed frozen with no menu up.
  local leave=FX.button(canvas,'Leave','LEAVE RUN',mx,by,MID_W,bh,function()
   if confirmWin then return end
   confirmWin=T.leaveConfirm(gui,{onClose=function() confirmWin=nil end})
  end,true)
  leave.Caption.TextSize=26;leave.Caption.TextColor3=C.negative
  center(T.text(canvas,'LeaveHint',tight and 'You keep the emeralds earned so far' or 'Leaving keeps the emeralds you earned so far',mx,by+bh+(tight and 8 or 6),MID_W,tight and 22 or 44,15,C.muted))
  -- Right: build. Weapons (6), items (16 kinds, copies stack ×5), level-ups (16 cards, picks stack).
  local R1=glass(canvas,'Build',rx,top,side,panelH)
  local rs=T.scroll(R1,'List',0,0,side,panelH);rs.ScrollBarThickness=4
  local cell=math.floor((side-48-7*6)/8) -- 8 per row
  local wcell=math.min(80,math.floor((side-48-5*8)/6))
  local weaponCount=0
  for i=1,6 do local s=state:FindFirstChild('Slot'..i);if s and (s:GetAttribute('WeaponId') or '')~='' then weaponCount+=1 end end
  local ry=section(rs,14,side,'WEAPONS',weaponCount..' / 6')
  for i=1,6 do
   local s=state:FindFirstChild('Slot'..i);local id=s and s:GetAttribute('WeaponId') or ''
   local x=24+(i-1)*(wcell+8)
   if id~='' then
    local tier=s:GetAttribute('Tier') or 1
    FX.tile(rs,'Weapon'..i,x,ry,wcell,WeaponIcons[id] or '','',({'Common','Rare','Epic','Legendary'})[math.clamp(tier,1,4)])
    T.tierBadge(rs:FindFirstChild('Weapon'..i),tier,4,4)
   else
    local e=T.make('Frame',rs,{Name='Weapon'..i,Position=UDim2.fromOffset(x,ry),Size=UDim2.fromOffset(wcell,math.floor(wcell*1.08)),BackgroundTransparency=1})
    T.make('UICorner',e,{CornerRadius=UDim.new(0,12)});T.make('UIStroke',e,{Color=Color3.new(1,1,1),Transparency=.82,Thickness=2})
   end
  end
  ry+=math.floor(wcell*1.08)+20
  local items={}
  for _,it in snap.items or {} do local entry=Catalog.ById[it.id];if entry then table.insert(items,{it=it,entry=entry}) end end
  table.sort(items,function(a,b) if a.entry.tier~=b.entry.tier then return a.entry.tier>b.entry.tier end;return a.it.count>b.it.count end)
  ry=section(rs,ry,side,'ITEMS',#items..' / 16')
  if #items==0 then left(T.text(rs,'NoItems','Buy items in the shop between waves.',24,ry,side-48,24,16,C.muted));ry+=34 end
  for i,e in items do
   local x=24+((i-1)%8)*(cell+6);local yy=ry+math.floor((i-1)/8)*(math.floor(cell*1.08)+6)
   FX.tile(rs,'Item'..i,x,yy,cell,T.Asset[e.entry.icon] or e.entry.icon,'',({'Common','Rare','Epic','Legendary'})[math.clamp(e.entry.tier or 1,1,4)],e.it.count>1 and ('×'..e.it.count) or nil)
  end
  if #items>0 then ry+=math.ceil(#items/8)*(math.floor(cell*1.08)+6)+14 end
  local picks,total={},0
  for id,n in snap.upgrades or {} do if n>0 then table.insert(picks,{id=id,n=n});total+=n end end
  table.sort(picks,function(a,b) if a.n~=b.n then return a.n>b.n end;return a.id<b.id end)
  -- A narrow panel (phones) drops "level n" from the note; THIS RUN in STATS shows the level.
  ry=section(rs,ry,side,'LEVEL-UPS',side<450 and snap.upgrades and (total..' picks') or ('level '..(snap.level or 1)..(snap.upgrades and ('  ·  '..total..' picks') or '')))
  for i,u in picks do
   local x=24+((i-1)%8)*(cell+6);local yy=ry+math.floor((i-1)/8)*(cell+12)
   local c=T.make('Frame',rs,{Name='LevelUp_'..u.id,Position=UDim2.fromOffset(x,yy),Size=UDim2.fromOffset(cell,cell+6),BackgroundColor3=Color3.new(1,1,1),BackgroundTransparency=.94,BorderSizePixel=0})
   T.make('UICorner',c,{CornerRadius=UDim.new(0,10)});T.make('UIStroke',c,{Color=INK,Thickness=2,Transparency=.4})
   T.icon(c,'Icon',math.floor(cell*.12),3,math.floor(cell*.76),LevelUps.icon(u.id))
   local n=right(T.label(c,'Count','×'..u.n,2,cell-16,cell-6,20,15,C.lime));n.TextWrapped=false
  end
  if #picks>0 then ry+=math.ceil(#picks/8)*(cell+12)+6 end
  left(T.text(rs,'LevelUpHelp','Level-ups are the stat cards you pick each time you level up. Their effect is already in STATS.',24,ry,side-48,40,15,C.muted))
  rs.CanvasSize=UDim2.fromOffset(0,ry+56)
 end
 -- Live: the freeze status, party pauses, the build and stats while the menu is up.
 local pending=false
 local function changed() if not self.open or pending then return end;pending=true;task.delay(.15,function() pending=false;if self.open then redraw() end end) end
 for _,a in {'RunPaused','RunPausedCount','RunLivingCount'} do flags:GetAttributeChangedSignal(a):Connect(changed) end
 for _,a in {'Wave','Won'} do runState:GetAttributeChangedSignal(a):Connect(changed) end
 state:GetAttributeChangedSignal('ShopSnapshot'):Connect(changed)
 local function watch(p) p:GetAttributeChangedSignal('Paused'):Connect(changed);p:GetAttributeChangedSignal('RunMember'):Connect(changed);p:GetAttributeChangedSignal('RunDown'):Connect(changed) end
 for _,p in Players:GetPlayers() do watch(p) end
 Players.PlayerAdded:Connect(watch);Players.PlayerRemoving:Connect(changed)
 if opts.parent then relayout();return self end -- previews: no input hooks
 -- Keep the server's pause in step with this menu (2026-10-03): if the server still has this player
 -- paused with the menu shut (a lost resume), or not paused with it open, ask again, up to 3 times
 -- per change. Example: P tapped twice fast and the resume got lost -> 0.6 s later it goes again and
 -- the run unfreezes.
 local tries,queued=0,false
 sync=function(fresh)
  if fresh then tries=0 end
  if queued then return end
  queued=true
  task.delay(.6,function()
   queued=false
   if not player:GetAttribute('RunMember') then return end
   local want=self.open and not player:GetAttribute('RunDown') and not player:GetAttribute('RunResult')
   if (player:GetAttribute('Paused')==true)==(want==true) or tries>=3 then return end
   tries+=1;remote:FireServer('SetPaused',want==true);sync()
  end)
 end
 player:GetAttributeChangedSignal('Paused'):Connect(function() sync(true) end)
 -- RESTART refused (RunAction 'LeaveResult' with no request number; the Leave Run popup hears its
 -- own): say why, and it can be pressed again.
 if typeof(remote)=='Instance' then remote.OnClientEvent:Connect(function(kind,ok,why,token)
  if kind~='LeaveResult' or ok==true or token~=nil or not restarting then return end
  restarting=nil
  if self.open then redraw();T.toast(gui,type(why)=='string' and why or "Couldn't restart",C.negative) end
 end) end
 -- The death and results screens take over: close quietly (the server forgets the pause).
 for _,a in {'RunDown','RunResult','RunMember'} do player:GetAttributeChangedSignal(a):Connect(function() if self.open and (player:GetAttribute('RunDown') or player:GetAttribute('RunResult') or not player:GetAttribute('RunMember')) then self.Close() end end) end
 -- P toggles (not while typing); the Roblox menu (Esc, a controller's Start) opens it behind.
 Input.InputBegan:Connect(function(input,processed)
  if Input:GetFocusedTextBox() then return end
  if input.KeyCode==Enum.KeyCode.P and not processed then self.Toggle() end
 end)
 pcall(function() GuiService.MenuOpened:Connect(function() self.Open() end) end)
 relayout()
 return self
end
return M
