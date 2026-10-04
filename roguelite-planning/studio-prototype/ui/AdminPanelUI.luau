-- ADMIN panel window (ADMIN_PANEL.md): one green-theme window with Travel, Mobs, Waves and Player
-- tabs. Presentation and requests only: AdminService checks the developer and every argument.
-- The Player tab reuses the old STATS (CharacterStatsUI) and GEAR (WeaponInventoryUI) views.
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local T=require(RS:WaitForChild('UITheme'))
local combat=RS:WaitForChild('RogueliteCombat')
local Admin=require(combat:WaitForChild('AdminConfig'))
local Maps=require(combat:WaitForChild('MapConfig'))
local Enemies=require(combat:WaitForChild('EnemyCatalog'))
local Items=require(combat:WaitForChild('ShopCatalog'))
local Economy=require(combat:WaitForChild('EconomyConfig')) -- Set-box limits, same as AdminConfig
local XP=require(combat:WaitForChild('RunXP'))
local Rules=require(RS:WaitForChild('RunSetupRules')) -- map display names
local C=T.Color
local M={}
local W,H=920,600 -- window content size; the Body inside is (W-36) x (H-58)
local CW=W-60 -- canvas width inside the scroll frame; 850+ puts the stat cards in two columns
local TABS={'Travel','Mobs','Waves','Player'}
local function left(l) l.TextXAlignment=Enum.TextXAlignment.Left;return l end
function M.new(player)
 local remote=combat:WaitForChild('AdminAction')
 local run=RS:WaitForChild('RogueliteRunState')
 local own=combat:WaitForChild('PlayerStates'):WaitForChild(tostring(player.UserId))
 -- DisplayOrder 65: above LevelUpOffers and RunSetup (60), below DeathScreen (80).
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='AdminPanel',ResetOnSpawn=false,DisplayOrder=65,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets})
 local helpers={panel=T.panel,label=T.label,button=T.button,icon=T.icon}
 local self={Screen=screen,tab='Travel',mobs={},spawnCount=5,keepCount=10,jump=1}
 local win,list,draw
 local statsView=require(RS:WaitForChild('CharacterStatsUI')).new(player,helpers)
 local inventory=require(RS:WaitForChild('WeaponInventoryUI')).new(player,helpers,function() if win and self.tab=='Player' then task.defer(draw) end end)
 -- One request: the server's reply shows as a toast, then the tab redraws with the new state.
 local function send(action,a,b)
  local ok,res=pcall(remote.InvokeServer,remote,action,a,b)
  local good=ok and type(res)=='table' and res.ok==true
  local message=ok and type(res)=='table' and res.message or 'No reply from the server'
  if message~='' then T.toast(screen,message,good and C.lime or C.negative) end
  if win then task.defer(draw) end
  return good
 end
 local function button(parent,name,text,x,y,w,callback,primary)
  local b=T.button(parent,name,text,x,y,w,40,callback,not primary);b.Caption.TextSize=17;return b
 end
 local function heading(parent,name,text,y) return left(T.label(parent,name,text,0,y,CW,30,22)) end
 local function note(parent,name,text,y,color) return T.text(parent,name,text,0,y,CW,22,15,color or C.muted) end
 -- Number field: a rounded box a shade lighter than the panel, in an inset well (<name>Well, behind
 -- it), with a lime wash while typing. It shows get(); Enter or clicking away calls onSet(number),
 -- anything else puts get() back. With inst/attr it follows that attribute's live value whenever
 -- it isn't being typed in.
 local INPUT=C.well:Lerp(C.white,.1)
 local function numberBox(parent,name,get,x,y,w,onSet,hint,inst,attr)
  T.panel(parent,name..'Well',x,y,w,40,'inset')
  local box=T.make('TextBox',parent,{Name=name,Position=UDim2.fromOffset(x+5,y+5),Size=UDim2.fromOffset(w-10,30),ZIndex=2,BackgroundColor3=INPUT,BorderSizePixel=0,TextColor3=C.white,Font=T.Font,TextSize=18,Text=tostring(get()),PlaceholderText=hint,PlaceholderColor3=C.dim,ClearTextOnFocus=false})
  T.make('UICorner',box,{CornerRadius=UDim.new(0,6)})
  local function show() if not box:IsFocused() then box.Text=tostring(get()) end end
  box.Focused:Connect(function() box.BackgroundColor3=INPUT:Lerp(C.lime,.18) end)
  box.FocusLost:Connect(function()
   box.BackgroundColor3=INPUT
   local v=tonumber(box.Text);if v and v==v then onSet(v) else show() end
  end)
  if inst then local conn=inst:GetAttributeChangedSignal(attr):Connect(show);box.Destroying:Connect(function() conn:Disconnect() end) end
  return box
 end
 -- A label that follows one attribute while it is on screen.
 local function live(l,inst,attr,format)
  local function set() l.Text=format(inst:GetAttribute(attr)) end
  set();local conn=inst:GetAttributeChangedSignal(attr):Connect(set)
  l.Destroying:Connect(function() conn:Disconnect() end)
 end
 local tabs={}
 -- Travel: instant only where the lobby and the maps share one Studio server. Published servers
 -- need plan C's teleports, so the buttons stay disabled with the reason underneath.
 function tabs.Travel(c)
  local instant=RunService:IsStudio() and RS:GetAttribute('ServerRole')=='Combined'
  heading(c,'TravelTitle','Travel',0)
  note(c,'TravelNote',instant and 'Maps open in Sandbox (no waves). Lobby takes you back to the portals.' or 'Needs lobby/match teleports (plan C)',32,instant and C.muted or C.gold)
  local places={{id='Lobby',name='Lobby',order=0}}
  for id in Maps.Maps do local i=Rules.MapIndex[id];table.insert(places,{id=id,name=i and Rules.Maps[i].name or id,order=i or 99}) end
  table.sort(places,function(a,b) return a.order<b.order end)
  local here=player:GetAttribute('StudioArea')=='Lobby' and 'Lobby' or combat:GetAttribute('RunMap')
  local bw=math.min(260,(CW-8*(#places-1))/#places)
  for i,place in places do
   local b=button(c,'Go_'..place.id,place.name,(i-1)*(bw+8),64,bw,function() send('Travel',place.id) end,place.id==here)
   b.Interactable=instant
  end
  return 120
 end
 -- Mobs: pick types (any EnemyCatalog enemy or a boss). Spawn adds that many of each
 -- picked type; Keep N alive uses the picked regular types.
 local options={}
 for _,d in Enemies.List do table.insert(options,{id=d.id,name=d.name}) end
 table.insert(options,{id=Admin.BossId,name='Hammer boss'})
 for _,o in {{id='KingCrab',name='King Crab boss'},{id='Pharaoh',name='Pharaoh boss'},{id='FrostCyclops',name='Frost Cyclops boss'},{id='Dragon',name='Dragon boss'}} do table.insert(options,o) end
 local function picked(regularOnly)
  local out={}
  for _,o in options do if self.mobs[o.id] and not (regularOnly and table.find(Admin.BossIds,o.id)) then table.insert(out,o.id) end end
  return out
 end
 function tabs.Mobs(c)
  heading(c,'MobsTitle','Enemies',0)
  note(c,'MobsNote','Pick types. Spawn puts extras 20-40 studs around you: they fight normally and never respawn.',32)
  local cols=4;local cw=(CW-(cols-1)*8)/cols
  for i,o in options do
   local on=self.mobs[o.id]==true
   local b=button(c,'Mob_'..o.id,(on and '✓ ' or '')..o.name,((i-1)%cols)*(cw+8),64+math.floor((i-1)/cols)*48,cw,function() self.mobs[o.id]=not on or nil;draw() end,on)
   b.Caption.TextSize=15
  end
  local y=64+math.ceil(#options/cols)*48+8
  left(T.label(c,'CountLabel','Count',0,y,80,40,20))
  numberBox(c,'SpawnCount',function() return self.spawnCount end,90,y,90,function(v) self.spawnCount=math.clamp(math.floor(v),1,50);draw() end,'1-50')
  button(c,'Spawn','Spawn',190,y,200,function()
   if self.spawning then return end -- one Spawn at a time
   local ids=picked(false)
   if #ids==0 then T.toast(screen,'Pick an enemy first',C.negative);return end
   self.spawning=true
   -- Stop at the first refusal: the other types would be refused the same way (one toast, not three).
   for i,id in ids do
    if i>1 then task.wait(.2) end
    if not send('Spawn',id,table.find(Admin.BossIds,id) and math.min(self.spawnCount,5) or self.spawnCount) then break end -- bosses cap at 5 (AdminConfig)
   end
   self.spawning=false
  end,true)
  y+=60
  heading(c,'KeepTitle','Keep N alive',y);y+=32
  note(c,'KeepNote','Keeps this many of the picked types alive, respawning as they die. Nothing picked: the map mix.',y);y+=30
  numberBox(c,'KeepCount',function() return self.keepCount end,0,y,90,function(v) self.keepCount=math.clamp(math.floor(v),1,100);draw() end,'1-100')
  button(c,'KeepOn','Keep alive',100,y,200,function() send('KeepAlive',self.keepCount,table.concat(picked(true),',')) end,true)
  button(c,'KeepOff','Stop',310,y,120,function() send('KeepAlive',0,'') end)
  local keeping=combat:GetAttribute('TestZombieCountOverride')
  T.text(c,'KeepStatus',keeping and ('Keeping '..keeping..' alive') or 'Off',444,y+9,CW-444,22,16,keeping and C.lime or C.muted)
  y+=60
  local frozen=combat:GetAttribute('AdminFreeze')==true
  button(c,'ClearAll','Clear all',0,y,200,function() send('ClearMobs') end)
  button(c,'Freeze',frozen and 'Unfreeze' or 'Freeze',210,y,200,function() send('Freeze',not frozen) end,frozen)
  note(c,'FreezeNote','Frozen enemies stop moving and attacking; you can still hit them.',y+48)
  return y+80
 end
 function tabs.Waves(c)
  local phase=run:GetAttribute('Phase');local sandbox=phase=='Practice';local fighting=phase=='Combat'
  heading(c,'ModeTitle','Mode',0)
  button(c,'Sandbox','Sandbox (no waves)',0,36,280,function() send('Sandbox') end,sandbox)
  button(c,'Waves','Waves',290,36,200,function() send('Waves') end,not sandbox)
  note(c,'ModeNote',sandbox and 'Sandbox: no wave timer and no shop. Enemies only come from Mobs.' or ('Wave '..tostring(run:GetAttribute('Wave'))..' · '..(fighting and 'fighting' or 'shop')),84)
  heading(c,'JumpTitle','Jump to wave (1-20)',120)
  numberBox(c,'JumpWave',function() return self.jump end,0,156,90,function(v) self.jump=math.clamp(math.floor(v),1,20) end,'1-20')
  button(c,'Jump','Start this wave now',100,156,260,function() send('JumpWave',self.jump) end,true)
  local paused=run:GetAttribute('AdminPaused')==true
  local e=button(c,'EndWave','End this wave',0,216,220,function() send('EndWave') end);e.Interactable=fighting
  local p=button(c,'Pause',paused and 'Resume' or 'Pause',230,216,160,function() send('Pause',not paused) end,paused);p.Interactable=fighting
  -- Endless bosses (RogueliteZombieChase, 2026-10-03): test one without playing 20 waves.
  heading(c,'EndlessTitle','Endless',272)
  local eb=button(c,'EndlessBoss','Spawn Endless boss',0,308,260,function() send('EndlessBoss') end,true);eb.Interactable=fighting or phase=='Shop'
  note(c,'EndlessNote','In a wave it lands now; in the shop it comes with the next wave. Wave 21: Jump to 20, End this wave, GO.',356)
  -- Tutorial (plans/2026-10-03-tutorial-design.md), Studio's combined server only.
  local y=392
  heading(c,'TutorialTitle','Tutorial',y);y+=36
  local here=RunService:IsStudio() and RS:GetAttribute('ServerRole')=='Combined'
  local on=combat:GetAttribute('TutorialRun')==true
  local step=player:GetAttribute('ProfileTutorial') or 'Done'
  local b1=button(c,'TutorialStart','Start tutorial',0,y,220,function() send('TutorialStart') end,true)
  local b2=button(c,'TutorialLobby','Lobby part',230,y,200,function() send('TutorialLobby') end)
  local b3=button(c,'TutorialEnd','End tutorial',440,y,200,function() send('TutorialEnd') end,on or step~='Done')
  for _,b in {b1,b2,b3} do b.Interactable=here end
  local now=on and 'the tutorial run' or step=='Done' and 'off' or ('lobby step: '..step)
  note(c,'TutorialNote',here and ('Start: the 3-wave run from the top. Lobby part: skip to the reward and the chest/Armory steps. Now: '..now) or 'Studio only: the live tutorial starts on first join',y+48,here and C.muted or C.gold)
  return y+84
 end
 function tabs.Player(c)
  heading(c,'PlayerTitle','Player',0)
  -- A click sends the opposite of the attribute as it is now, and the button repaints from that
  -- attribute: a new run clears God and restores weapons without redrawing this tab.
  local function toggle(name,action,x,text,inst,attr,isOn)
   local b=button(c,name,'',x,36,260,function() send(action,not isOn()) end)
   local function paint() local on=isOn();T.setPrimary(b,on);b.Caption.Text=text..(on and 'ON' or 'OFF') end
   paint();local conn=inst:GetAttributeChangedSignal(attr):Connect(paint)
   b.Destroying:Connect(function() conn:Disconnect() end)
  end
  toggle('God','God',0,'God mode: ',player,'AdminGod',function() return player:GetAttribute('AdminGod')==true end)
  toggle('WeaponsToggle','Weapons',270,'Weapons: ',own,'WeaponEnabled',function() return own:GetAttribute('WeaponEnabled')~=false end)
  local shards=left(T.label(c,'ShardsLabel','',0,90,220,40,20))
  live(shards,own,'Shards',function(v) return 'Shards · '..tostring(v or 0) end)
  button(c,'Shards100','+100',230,90,110,function() send('Shards','Add',100) end)
  button(c,'Shards1000','+1000',350,90,120,function() send('Shards','Add',1000) end)
  numberBox(c,'ShardsSet',function() return own:GetAttribute('Shards') or 0 end,480,90,140,function(v) send('Shards','Set',math.clamp(math.floor(v),0,Economy.MAX_SHARDS)) end,'Set shards',own,'Shards')
  local level=left(T.label(c,'LevelLabel','',0,140,220,40,20))
  live(level,own,'RunLevel',function(v) return 'Level · '..tostring(v or 1) end)
  button(c,'LevelUp','+1',230,140,110,function() send('Level','Add',1) end)
  numberBox(c,'LevelSet',function() return own:GetAttribute('RunLevel') or 1 end,350,140,120,function(v) send('Level','Set',math.clamp(math.floor(v),1,XP.MAX_LEVEL)) end,'Set level',own,'RunLevel')
  note(c,'SetHint','Type a number and press Enter to set it.',188)
  heading(c,'ItemsTitle','Give item',220)
  local items={};for _,e in Items.List do if e.kind~='Weapon' then table.insert(items,e) end end
  local cols=4;local cw=(CW-(cols-1)*8)/cols
  for i,e in items do
   button(c,'Item_'..e.id,e.name,((i-1)%cols)*(cw+8),256+math.floor((i-1)/cols)*48,cw,function() send('GiveItem',e.id) end).Caption.TextSize=15
  end
  local y=256+math.ceil(#items/cols)*48+16
  -- Handyman turret (HANDYMAN_TURRET.md): AdminService action Turret.
  heading(c,'TurretTitle','Handyman turret',y);y+=36
  button(c,'TurretGive','Give turret',0,y,170,function() send('Turret','Give') end,true)
  for t=1,4 do button(c,'TurretTier'..t,'Tier '..T.Roman[t],180+(t-1)*96,y,88,function() send('Turret','Tier',t) end) end
  button(c,'TurretClear','Clear turrets',566,y,180,function() send('Turret','Clear') end)
  note(c,'TurretNote','Give: one at you now, any class, for this run. Tier: your turret this run. Clear: every turret, until the next wave or BUILD (B / pad R1).',y+48)
  y+=84
  -- Class, stat edits, heal and emeralds: the old STATS panel, without its mob controls (Mobs tab).
  local stats=T.frame(c,'StatsView',0,y,CW,1)
  local h=statsView:render(stats,CW,{skipMobs=true});stats.Size=UDim2.fromOffset(CW,h);y+=h+16
  -- Give weapon: the old GEAR inventory, any weapon and tier into the next free slot.
  heading(c,'GearTitle','Give weapon',y);y+=36
  local gear=T.frame(c,'Inventory',0,y,CW,1)
  h=inventory:render(gear,CW);gear.Size=UDim2.fromOffset(CW,h)
  return y+h+16
 end
 draw=function()
  if not win then return end
  local keep=list and list.Parent and list.CanvasPosition
  statsView.refreshers={} -- the old stat widgets stop updating; the Player tab adds its own again
  for _,child in win.Body:GetChildren() do child:Destroy() end
  T.tabs(win.Body,0,0,W-36,46,TABS,self.tab,function(id) self.tab=id;list=nil;draw() end)
  list=T.scroll(win.Body,'Content',0,56,W-36,H-58-56)
  local canvas=T.frame(list,'Canvas',0,0,CW,0)
  local height=tabs[self.tab](canvas)
  canvas.Size=UDim2.fromOffset(CW,height);list.CanvasSize=UDim2.fromOffset(0,height)
  if keep then list.CanvasPosition=keep end
  screen:SetAttribute('Tab',self.tab)
 end
 function self.Open()
  if win then return end
  win=T.window(screen,'AdminWindow','Admin',W,H,function() win=nil;list=nil;statsView.refreshers={};screen:SetAttribute('Open',false) end)
  screen:SetAttribute('Open',true);draw()
 end
 function self.Close() if win then win.Close() end end
 function self.Toggle() if win then self.Close() else self.Open() end end
 function self.Show(tab) if tab and tabs[tab] then self.tab=tab end;if win then list=nil;draw() else self.Open() end end
 -- Redraw live state (phase, wave, pause, freeze, map, area) while open. The Player tab redraws
 -- only after its own requests: rebuilding the stat editor on every shard pickup would fight typing.
 local function changed() if win and self.tab~='Player' then draw() end end
 for _,a in {'Phase','Wave','AdminPaused'} do run:GetAttributeChangedSignal(a):Connect(changed) end
 for _,a in {'AdminFreeze','TestZombieCountOverride','RunMap'} do combat:GetAttributeChangedSignal(a):Connect(changed) end
 player:GetAttributeChangedSignal('StudioArea'):Connect(changed)
 combat:GetAttributeChangedSignal('TutorialRun'):Connect(changed)
 player:GetAttributeChangedSignal('ProfileTutorial'):Connect(changed)
 return self
end
return M
