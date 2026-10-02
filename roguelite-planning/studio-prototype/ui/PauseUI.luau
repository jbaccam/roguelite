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
M.PAUSE_ICON='rbxassetid://109142479841413' -- ui/assets/hud/pause.png
-- Solo RESTART uses plan J's RunAction 'Restart'; hidden until that ships.
M.RESTART=false
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
local function section(parent,y,w,title,note)
 left(FX.title(parent,'Section_'..title,title,24,y,w-48,32,24))
 if note then right(T.text(parent,'Note_'..title,note,w/2,y+6,w/2-24,24,16,C.muted)) end
 local rule=T.make('Frame',parent,{Name='Rule_'..title,Position=UDim2.fromOffset(24,y+38),Size=UDim2.fromOffset(w-48,2),BackgroundColor3=C.lime,BorderSizePixel=0})
 T.make('UIGradient',rule,{Transparency=NumberSequence.new(0,1)})
 return y+48
end

-- opts (previews and tests only): parent (where the ScreenGui goes), state (a PlayerStates-like
-- folder), runState, flags (stands in for RogueliteCombat's run attributes), remote
-- ({FireServer=fn}), party() (the run's living members).
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
 local settingsWindow,leaveArmed,redraw

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
  local waveText=(runState:GetAttribute('Won') and 'ENDLESS WAVE ' or 'WAVE ')..wave
  return string.upper(m and m.name or 'RUN'),string.upper(diff),color,waveText,wave
 end
 local function party()
  if opts.party then return opts.party() end
  local list={}
  for _,p in Players:GetPlayers() do if p:GetAttribute('RunMember') and not p:GetAttribute('RunDown') then table.insert(list,p) end end
  table.sort(list,function(a,b) return a.UserId<b.UserId end)
  return list
 end

 function self.Close(silent)
  if not self.open then return end
  self.open=false;gui.Enabled=false;leaveArmed=nil
  if settingsWindow then settingsWindow.Close() end
  if not silent then remote:FireServer('SetPaused',false) end
 end
 function self.Open()
  if self.open or player:GetAttribute('RunDown') or player:GetAttribute('RunResult') or not player:GetAttribute('RunMember') then return end
  self.open=true;gui.Enabled=true;redraw()
  remote:FireServer('SetPaused',true)
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
  local solo=#members<=1
  -- Title plate, then map · difficulty · wave, the status pill and (in a party) who has paused.
  local y=L.top+12
  local plate=T.panel(canvas,'TitlePlate',w/2-150,y,300,66,'panel');T.caps(plate,44)
  T.icon(plate,'Icon',40,11,44,M.PAUSE_ICON)
  left(T.label(plate,'Title','PAUSED',92,8,180,50,40))
  y+=74
  local mapName,diff,diffColor,waveText=runInfo()
  local info=center(T.text(canvas,'RunInfo',string.format('%s  ·  <font color="%s">%s</font>  ·  %s',mapName,T.hex(diffColor),diff,waveText),0,y,w,30,22))
  info.Font=T.Font
  y+=40
  local count,living=flags:GetAttribute('RunPausedCount') or (frozen and 1 or 0),flags:GetAttribute('RunLivingCount') or #members
  local status=frozen and (solo and 'GAME FROZEN' or 'EVERYONE PAUSED  ·  GAME FROZEN') or (solo and 'PAUSING…' or (count..' / '..math.max(living,1)..' PAUSED  ·  THE GAME KEEPS GOING UNTIL EVERYONE PAUSES'))
  local pw=math.min(w-80,frozen and (solo and 360 or 560) or (solo and 300 or 820))
  local pill=T.make('Frame',canvas,{Name='Status',Position=UDim2.fromOffset(w/2-pw/2,y),Size=UDim2.fromOffset(pw,46),BackgroundColor3=frozen and Color3.fromRGB(47,95,14) or Color3.fromRGB(110,74,10),BorderSizePixel=0})
  T.make('UICorner',pill,{CornerRadius=UDim.new(1,0)});T.make('UIStroke',pill,{Color=INK,Thickness=3})
  local pl=center(FX.title(pill,'Text',status,12,4,pw-24,38,frozen and 22 or 19,nil));pl.TextColor3=frozen and C.limeSoft or Color3.fromRGB(255,217,138)
  y+=56
  if not solo then
   local cw=210;local total=#members*cw+(#members-1)*20;local x=w/2-total/2
   for i,p in members do
    local c=T.make('Frame',canvas,{Name='Member'..i,Position=UDim2.fromOffset(x+(i-1)*(cw+20),y),Size=UDim2.fromOffset(cw,40),BackgroundColor3=INK,BackgroundTransparency=.45,BorderSizePixel=0})
    T.make('UICorner',c,{CornerRadius=UDim.new(0,12)})
    local head=T.make('ImageLabel',c,{Name='Head',BackgroundTransparency=1,Position=UDim2.fromOffset(6,4),Size=UDim2.fromOffset(32,32)});T.headshot(head,p.UserId)
    T.make('UICorner',head,{CornerRadius=UDim.new(1,0)})
    local n=left(T.label(c,'Name',p.DisplayName,44,4,124,32,17));n.TextWrapped=false
    if p:GetAttribute('Paused') then FX.check(c,cw-36,7,26) else right(T.text(c,'Playing','playing',cw-70,8,62,24,14,C.gold)) end
   end
   y+=52
  end
  -- Three columns below: stats | buttons | build. Side panels share what's left of the width.
  local top=y+10;local panelH=h-top-24
  local side=math.clamp(math.floor((w-MID_W-4*40)/2),300,SIDE_W)
  local gap=math.floor((w-2*side-MID_W)/4)
  local lx,mx,rx=gap,gap*2+side,gap*3+side+MID_W
  -- Left: stats (scrolls on short screens).
  local L1=glass(canvas,'Stats',lx,top,side,panelH)
  local ls=T.scroll(L1,'List',0,0,side,panelH);ls.ScrollBarThickness=4
  local sy=section(ls,14,side,'STATS')
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
  -- Centre: actions.
  local by=top+44
  local resume=FX.button(canvas,'Resume','RESUME',mx,by,MID_W,86,function() self.Close() end);resume.Caption.TextSize=34
  center(T.text(canvas,'ResumeHint',Input.TouchEnabled and '' or 'or press P',mx,by+90,MID_W,22,15,C.muted))
  by+=132
  local settings=FX.button(canvas,'Settings','SETTINGS',mx,by,MID_W,70,function()
   if settingsWindow then settingsWindow.Close() return end
   settingsWindow=T.settingsWindow(gui);settingsWindow.Root.Destroying:Connect(function() settingsWindow=nil end)
  end,true);settings.Caption.TextSize=26
  by+=90
  if M.RESTART then
   local restart=FX.button(canvas,'Restart','RESTART',mx,by,MID_W,70,function() if solo then remote:FireServer('Restart');self.Close(true) end end,true)
   restart.Caption.TextSize=26
   if not solo then restart.Interactable=false;center(T.text(canvas,'RestartHint','Restart is for solo runs',mx,by+72,MID_W,22,14,C.muted)) end
   by+=110
  end
  local leave=FX.button(canvas,'Leave','LEAVE RUN',mx,by,MID_W,70,function()
   if leaveArmed and os.clock()-leaveArmed<3 then remote:FireServer('LeaveRun');self.Close(true);return end
   leaveArmed=os.clock();redraw()
  end,true)
  local armed=leaveArmed and os.clock()-leaveArmed<3
  leave.Caption.Text=armed and 'TAP AGAIN TO LEAVE' or 'LEAVE RUN';leave.Caption.TextSize=armed and 22 or 26;leave.Caption.TextColor3=C.negative
  center(T.text(canvas,'LeaveHint','Leaving keeps the emeralds you earned so far',mx,by+76,MID_W,44,15,C.muted))
  if armed then task.delay(3.1,function() if self.open and leaveArmed and os.clock()-leaveArmed>=3 then leaveArmed=nil;redraw() end end) end
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
  ry=section(rs,ry,side,'LEVEL-UPS','level '..(snap.level or 1)..(snap.upgrades and ('  ·  '..total..' picks') or ''))
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
