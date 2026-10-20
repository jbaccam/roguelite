-- ADMIN panel window (ADMIN_PANEL.md): one green-theme window with Travel, Mobs, Waves, Player, Give
-- and Shop tabs. Presentation and requests only: AdminService checks the developer and every argument.
-- The Player tab reuses the old STATS (CharacterStatsUI) and GEAR (WeaponInventoryUI) views.
-- Lag (2026-10-12, user: "make admin panel less laggy and more usable like minecraft creative"): a
-- request no longer rebuilds the whole tab. Buttons repaint from the attributes they show, and the
-- tabs that show run state redraw only when that state changes. Give is built once per open window.
local RS=game:GetService('ReplicatedStorage')
local Players=game:GetService('Players')
local Input=game:GetService('UserInputService')
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
local Commands=require(combat:WaitForChild('AdminCommands')) -- the Give tab's catalog and the command box
local Inventory=require(RS:WaitForChild('WeaponInventoryUI')) -- weapon icons (Inventory.Icons)
local C=T.Color
local M={}
local W,H=920,600 -- window content size; the Body inside is (W-36) x (H-58)
local CW=W-60 -- canvas width inside the scroll frame; 850+ puts the stat cards in two columns
local TABS={'Travel','Mobs','Waves','Player','Give','Shop'}
local GIVE_H=H-58-56 -- the Give tab fills the content area; its grid scrolls inside it
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
 -- One request: the server's reply shows as a toast. No redraw (2026-10-12): what a request changes
 -- comes back as attributes, which the buttons and tabs already follow. target: a UserId for
 -- AdminConfig.Targeted actions (nil = you).
 local function send(action,a,b,c,target)
  local ok,res=pcall(remote.InvokeServer,remote,action,a,b,c,target)
  local good=ok and type(res)=='table' and res.ok==true
  local message=ok and type(res)=='table' and res.message or 'No reply from the server'
  if message~='' then T.toast(screen,message,good and C.lime or C.negative) end
  return good,message
 end
 -- A chat command's text (AdminCommands), from the chat or the Give tab's command box.
 function self.Command(text)
  if type(text)~='string' or text=='' then return false,'' end
  if string.sub(text,1,1)~='/' then text='/'..text end
  return send('Command',text)
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
 table.insert(options,{id=Admin.BossId,name='Hammer Brute'})
 for _,o in {{id='KingCrab',name='Giant King Crab'},{id='Pharaoh',name='The Pharaoh'},{id='FrostCyclops',name='Frost Cyclops'},{id='Dragon',name='Inferno Dragon'}} do table.insert(options,o) end
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
  -- TEST RUN tag (2026-10-20): hidden for filming; the run still pays nothing (AdminService HideTestTag).
  local hidden=combat:GetAttribute('AdminHideTestTag')==true
  button(c,'HideTestTag',hidden and 'TEST RUN tag: hidden' or 'TEST RUN tag: shown',540,36,CW-540,function() send('HideTestTag',not hidden) end,hidden)
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
  -- Round 10 events (Round10Service): start this map's event, skip its intro, clear it.
  local y=392
  heading(c,'Round10Title','Round 10 event',y);y+=36
  local eventId=run:GetAttribute('EventId');local eventPhase=run:GetAttribute('EventPhase')
  button(c,'Round10Start','Start round 10 event',0,y,260,function() send('Round10Start') end,true)
  local skip=button(c,'Round10Skip','Skip intro',270,y,170,function() send('Round10Skip') end);skip.Interactable=eventPhase=='Intro'
  local clear=button(c,'Round10Clear','Clear event',450,y,190,function() send('Round10Clear') end);clear.Interactable=eventPhase=='Intro' or eventPhase=='Active'
  note(c,'Round10Note',eventId and ('Running: '..tostring(eventId)..' · '..tostring(eventPhase)) or 'Jumps to wave 10 on this map. Without its models installed the midboss comes instead (the reply says why).',y+48)
  y+=84
  -- Tutorial (plans/2026-10-03-tutorial-design.md), Studio's combined server only.
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
  y+=84
  -- Gifts (2026-10-04): a fake Starter Pack gift through the real inbox delivery (AdminService
  -- GiftTest), so the GIFT FROM popup can be checked without Robux. Studio only.
  heading(c,'GiftTitle','Gifts',y);y+=36
  local studio=RunService:IsStudio()
  button(c,'GiftTest','Simulate gift to me',0,y,260,function() send('GiftTest') end,true).Interactable=studio
  note(c,'GiftNote',studio and 'A Starter Pack from "Studio test" pops up in the lobby. The second one pays emeralds (already owned).' or 'Studio only: real gifts come from Robux',y+48,studio and C.muted or C.gold)
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
  toggle('Ghost','Ghost',540,'Ghost: ',player,'AdminGhost',function() return player:GetAttribute('AdminGhost')==true end) -- /ghost
  local shards=left(T.label(c,'ShardsLabel','',0,90,220,40,20))
  live(shards,own,'Shards',function(v) return 'Shards · '..tostring(v or 0) end)
  button(c,'Shards100','+100',230,90,110,function() send('Shards','Add',100) end)
  button(c,'Shards1000','+1000',350,90,120,function() send('Shards','Add',1000) end)
  numberBox(c,'ShardsSet',function() return own:GetAttribute('Shards') or 0 end,480,90,140,function(v) send('Shards','Set',math.clamp(math.floor(v),0,Economy.MAX_SHARDS)) end,'Set shards',own,'Shards')
  local level=left(T.label(c,'LevelLabel','',0,140,220,40,20))
  live(level,own,'RunLevel',function(v) return 'Level · '..tostring(v or 1) end)
  button(c,'LevelUp','+1',230,140,110,function() send('Level','Add',1) end)
  numberBox(c,'LevelSet',function() return own:GetAttribute('RunLevel') or 1 end,350,140,120,function(v) send('Level','Set',math.clamp(math.floor(v),1,XP.MAX_LEVEL)) end,'Set level',own,'RunLevel')
  note(c,'SetHint','Type a number and press Enter to set it. Items, weapons, armor and pets for anyone: the Give tab.',188)
  local y=228
  -- Turrets (HANDYMAN_TURRET.md, turret items 2026-10-04): AdminService action Turret.
  heading(c,'TurretTitle','Turrets',y);y+=36
  local names={'Give Nail','Give Twin','Give Quad','Give Gatling'}
  local tw=(CW-3*8-188)/4
  for t=1,4 do button(c,'TurretGive'..t,names[t],(t-1)*(tw+8),y,tw,function() send('Turret','Give',t) end,true).Caption.TextSize=15 end
  button(c,'TurretClear','Clear turrets',CW-180,y,180,function() send('Turret','Clear') end)
  note(c,'TurretNote','Give: one more turret item in your run inventory (10 at most); in a wave it stands at once. Clear: your turret items and every standing turret; others come back next wave.',y+48)
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
 -- Give (2026-10-12, user: "give players items ... like minecraft creative panel"): every weapon,
 -- run item, turret, armor piece and set, pet and class in one grid, built once per open window and
 -- only filtered after (This run / Saved, kind, search), so a click never rebuilds anything. A tile
 -- gives itself to the picked player (Me, anyone here, or All): This run = TempGive into the picked
 -- weapon slot (Next = the next free one; 2026-10-13, was copies) at the tier, or for an armor set
 -- the run armor (Armor: worn this run only); Saved = Give at the tier (+1 = one more copy). The command box runs
 -- the chat commands, for phones. Example: Saved, Tier IV, Katana -> that player's Katana Tier IV.
 local catalog,giveView
 local function catalogEntries()
  if catalog then return catalog end
  local Stats=require(combat:WaitForChild('CharacterStats'))
  catalog=Commands.entries({Weapons=require(combat:WaitForChild('WeaponCatalog')),Items=Items,Armor=require(combat:WaitForChild('ArmorCatalog')),
   Pets=require(combat:WaitForChild('PetConfig')),Classes=Stats.ClassOrder,Signature=Stats.Signature,WeaponIcons=Inventory.Icons})
  return catalog
 end
 -- Tab completion for a command box (2026-10-13, user: "if i tab on /armor all _ it will type
 -- dragon and if i tab again it will cycle thru the sets"). A list above the box shows what fits
 -- the word being typed (AdminCommands.suggest); Tab puts the next one in, Shift+Tab the one
 -- before, and tapping a row puts it in with a space (phones). Typing anything starts over.
 local MAX_ROWS=8
 local function esc(text) return (string.gsub(string.gsub(string.gsub(tostring(text),'&','&amp;'),'<','&lt;'),'>','&gt;')) end
 local function completionContext()
  local list={};for _,q in Players:GetPlayers() do table.insert(list,{name=q.Name,display=q.DisplayName}) end
  return {entries=catalogEntries(),players=list}
 end
 local function completer(box)
  local frame=T.make('Frame',box.Parent,{Name=box.Name..'Suggestions',AnchorPoint=Vector2.new(0,1),Position=UDim2.new(box.Position.X.Scale,box.Position.X.Offset-6,box.Position.Y.Scale,box.Position.Y.Offset-10),Size=UDim2.new(box.Size.X.Scale,box.Size.X.Offset+12,0,0),AutomaticSize=Enum.AutomaticSize.Y,BackgroundColor3=C.track,BorderSizePixel=0,Visible=false,ZIndex=40})
  T.make('UICorner',frame,{CornerRadius=UDim.new(0,8)})
  T.make('UIStroke',frame,{Color=C.lime,Thickness=1,Transparency=.4})
  T.make('UIListLayout',frame,{SortOrder=Enum.SortOrder.LayoutOrder,Padding=UDim.new(0,2)})
  T.make('UIPadding',frame,{PaddingTop=UDim.new(0,6),PaddingBottom=UDim.new(0,6),PaddingLeft=UDim.new(0,8),PaddingRight=UDim.new(0,8)})
  local rows={}
  for i=1,MAX_ROWS do
   rows[i]=T.make('TextButton',frame,{Name='Row'..i,LayoutOrder=i,AutoButtonColor=false,BackgroundColor3=C.limeDark,BackgroundTransparency=1,Size=UDim2.new(1,0,0,24),Font=T.Body,TextSize=16,RichText=true,TextColor3=C.white,TextXAlignment=Enum.TextXAlignment.Left,TextTruncate=Enum.TextTruncate.AtEnd,Text='',ZIndex=41})
   T.make('UICorner',rows[i],{CornerRadius=UDim.new(0,4)})
  end
  local hint=T.make('TextLabel',frame,{Name='Hint',LayoutOrder=100,BackgroundTransparency=1,Size=UDim2.new(1,0,0,18),Font=T.Body,TextSize=13,TextColor3=C.dim,TextXAlignment=Enum.TextXAlignment.Left,Text='',ZIndex=41})
  local state={options={},before='',first=1,index=nil,applying=false}
  local function show()
   local options=state.options
   frame.Visible=box:IsFocused() and #options>0
   local k=state.index
   if k then if k<state.first then state.first=k elseif k>=state.first+MAX_ROWS then state.first=k-MAX_ROWS+1 end end
   for i,row in rows do
    local n=state.first+i-1;local o=options[n]
    row.Visible=o~=nil
    if o then
     row.Text='<font color="#91EF14">'..esc(o.token)..'</font>   <font color="#AEB7B9">'..esc(o.label)..'</font>'
     row.BackgroundTransparency=n==k and .15 or 1
    end
   end
   hint.Text=(#options>MAX_ROWS and (#options..' options · ') or '')..'Tab: next · Shift+Tab: back · Enter: run'
  end
  local function refresh()
   local found=Commands.suggest(box.Text,completionContext())
   state.options=found.options;state.before=found.before;state.index=nil;state.first=1
   show()
  end
  local function apply(n,space)
   local o=state.options[n];if not o then return end
   state.index=n;state.applying=true
   box.Text=state.before..o.token..(space and ' ' or '')
   box.CursorPosition=#box.Text+1
   state.applying=false
   if space then refresh() else show() end
  end
  for i,row in rows do
   row.Activated:Connect(function()
    apply(state.first+i-1,true)
    box:CaptureFocus();task.defer(function() box.CursorPosition=#box.Text+1 end)
   end)
  end
  box:GetPropertyChangedSignal('Text'):Connect(function()
   if state.applying then return end
   -- A Tab may land in the box as a character: take it out; the Tab handler completes.
   if string.find(box.Text,'\t',1,true) then state.applying=true;box.Text=string.gsub(box.Text,'\t','');state.applying=false;return end
   refresh()
  end)
  box.Focused:Connect(refresh)
  -- Lost focus: hide, unless a row tap takes it straight back.
  box.FocusLost:Connect(function() task.delay(.2,function() if not box:IsFocused() then frame.Visible=false end end) end)
  local conn=Input.InputBegan:Connect(function(input)
   if input.KeyCode~=Enum.KeyCode.Tab or not box:IsFocused() or #state.options==0 then return end
   local back=Input:IsKeyDown(Enum.KeyCode.LeftShift) or Input:IsKeyDown(Enum.KeyCode.RightShift)
   local n=#state.options
   local k=state.index and ((state.index-1+(back and -1 or 1))%n+1) or (back and n or 1)
   task.defer(apply,k,false) -- after a Tab character, if one landed
  end)
  box.Destroying:Connect(function() conn:Disconnect() end)
 end
 local KINDS={'All','Weapon','Item','Turret','Armor','Pet','Class'}
 local KIND_LABEL={All='All',Weapon='Weapons',Item='Items',Turret='Turrets',Armor='Armor',Pet='Pets',Class='Classes'}
 self.give={mode='temp',kind='All',slot=0,tier=1,search='',target=nil}
 local function buildGive()
  local g=self.give
  local v=T.frame(nil,'GiveView',0,0,CW,GIVE_H)
  -- Chips: one row of small buttons; the picked one is lime. They repaint, never rebuild.
  local function chips(name,x,y,w,list,get,set)
   local bs={}
   local function paint() for i,o in list do T.setPrimary(bs[i],get()==o.value);if o.enabled then bs[i].Interactable=o.enabled() end;if o.text then bs[i].Caption.Text=o.text() end end end
   for i,o in list do
    bs[i]=T.button(v,name..i,o.label,x+(i-1)*(w+6),y,w,36,function() set(o.value);paint() end,true);bs[i].Caption.TextSize=15
   end
   paint();return paint
  end
  -- Row 1: who gets it. Rebuilt when players join or leave (a few buttons).
  left(T.label(v,'ToLabel','Give to',0,0,90,36,18))
  local who=T.frame(v,'Targets',96,0,CW-96,36)
  local function targets()
   for _,child in who:GetChildren() do child:Destroy() end
   local list={{id=nil,name='Me'}}
   for _,q in Players:GetPlayers() do if q~=player then table.insert(list,{id=q.UserId,name=q.DisplayName}) end end
   if #list>1 then table.insert(list,{id=0,name='All'}) end
   local still=false;for _,t in list do if t.id==g.target then still=true end end
   if not still then g.target=nil end
   local bw=math.min(150,(CW-96-6*(#list-1))/#list)
   for i,t in list do
    local b=T.button(who,'Target'..i,t.name,(i-1)*(bw+6),0,bw,36,function() g.target=t.id;targets() end,g.target~=t.id);b.Caption.TextSize=15
   end
  end
  targets()
  local joins={Players.PlayerAdded:Connect(targets),Players.PlayerRemoving:Connect(function() task.defer(targets) end)}
  v.Destroying:Connect(function() for _,conn in joins do conn:Disconnect() end end)
  -- Row 2: This run / Saved / Shop, weapon slot (This run only; Next = the next free one) and tier
  -- (+1: Saved only, one more copy). Shop (2026-10-20): the tile is queued into the picked player's
  -- shop at the tier, on the picked roll: Next = the next time their offers roll (the shop opening
  -- or a reroll), 2nd = the roll after that. Example: Shop, Next, III, Fart Gun, then 2nd, IV, Fart
  -- Gun -> a Tier III Fart Gun in the next shop and a Tier IV one after its first reroll.
  local paintCopies,paintTier,filter,slotLabel
  local ORDINAL={'1st','2nd','3rd','4th','5th','6th','7th'}
  chips('Mode',0,44,72,{{label='This run',value='temp'},{label='Saved',value='perm'},{label='Shop',value='shop'}},function() return g.mode end,function(m)
   g.mode=m;if m~='perm' and g.tier==0 then g.tier=1 end
   slotLabel.Text=m=='shop' and 'Roll' or 'Slot'
   paintCopies();paintTier();filter()
  end)
  slotLabel=left(T.label(v,'SlotLabel',g.mode=='shop' and 'Roll' or 'Slot',236,44,40,36,16))
  local function slotText(n) return function() return n==0 and 'Next' or g.mode=='shop' and ORDINAL[n+1] or tostring(n) end end
  local slotList={{label='Next',value=0,enabled=function() return g.mode~='perm' end,text=slotText(0)}}
  for n=1,6 do table.insert(slotList,{label=tostring(n),value=n,enabled=function() return g.mode~='perm' end,text=slotText(n)}) end
  paintCopies=chips('Slot',278,44,34,slotList,function() return g.slot end,function(n) g.slot=n end)
  left(T.label(v,'TierLabel','Tier',576,44,36,36,16))
  local tierList={{label='+1',value=0,enabled=function() return g.mode=='perm' end}}
  for t=1,4 do table.insert(tierList,{label=T.Roman[t],value=t}) end
  paintTier=chips('Tier',612,44,42,tierList,function() return g.tier end,function(t) g.tier=t end)
  -- Row 3: search and kind.
  T.panel(v,'SearchWell',0,88,300,36,'inset')
  local search=T.make('TextBox',v,{Name='Search',Position=UDim2.fromOffset(6,92),Size=UDim2.fromOffset(288,28),ZIndex=2,BackgroundColor3=INPUT,BorderSizePixel=0,TextColor3=C.white,Font=T.Font,TextSize=17,Text='',PlaceholderText='Search',PlaceholderColor3=C.dim,ClearTextOnFocus=false,TextXAlignment=Enum.TextXAlignment.Left})
  T.make('UICorner',search,{CornerRadius=UDim.new(0,6)})
  local kindList={};for _,k in KINDS do table.insert(kindList,{label=KIND_LABEL[k],value=k}) end
  chips('Kind',308,88,(CW-308-6*(#KINDS-1))/#KINDS,kindList,function() return g.kind end,function(k) g.kind=k;filter() end)
  -- The grid.
  local gridH=GIVE_H-134-48
  local grid=T.make('ScrollingFrame',v,{Name='Grid',Position=UDim2.fromOffset(0,134),Size=UDim2.fromOffset(CW,gridH),BackgroundTransparency=1,BorderSizePixel=0,CanvasSize=UDim2.new(),AutomaticCanvasSize=Enum.AutomaticSize.Y,ScrollBarThickness=6,ScrollBarImageColor3=C.lime,ScrollingDirection=Enum.ScrollingDirection.Y,VerticalScrollBarInset=Enum.ScrollBarInset.ScrollBar})
  T.make('UIGridLayout',grid,{CellSize=UDim2.fromOffset(98,96),CellPadding=UDim2.fromOffset(6,6),SortOrder=Enum.SortOrder.LayoutOrder})
  local busy=false
  local function give(e)
   if busy then return end
   busy=true
   local ids={g.target}
   if g.target==0 then ids={};for _,q in Players:GetPlayers() do table.insert(ids,q.UserId) end end
   for i,id in ids do
    if i>1 then task.wait(.2) end -- AdminService's rate limit
    if id==player.UserId then id=nil end
    if g.mode=='shop' then send('ShopQueue',e.key,math.max(1,g.tier),g.slot+1,id)
    elseif g.mode=='temp' and e.set then send('Armor',e.id,math.max(1,g.tier),nil,id)
    elseif g.mode=='temp' then send('TempGive',e.key,e.kind=='Weapon' and g.slot or 0,math.max(1,g.tier),id)
    else send('Give',e.key,g.tier>0 and g.tier or nil,nil,id) end
   end
   busy=false
  end
  local tiles={}
  for i,e in catalogEntries() do
   local tile=T.make('TextButton',grid,{Name='Tile_'..e.key,Text='',AutoButtonColor=false,BackgroundColor3=C.well,BorderSizePixel=0,LayoutOrder=i})
   T.make('UICorner',tile,{CornerRadius=UDim.new(0,8)})
   T.make('UIStroke',tile,{Color=e.godly and C.red or e.kind=='Turret' and T.Tier[e.tier or 1] or C.track,Thickness=2,ApplyStrokeMode=Enum.ApplyStrokeMode.Border})
   if e.icon and e.icon~='' then T.make('ImageLabel',tile,{Name='Icon',BackgroundTransparency=1,Position=UDim2.fromOffset(21,4),Size=UDim2.fromOffset(56,56),Image=e.icon,ScaleType=Enum.ScaleType.Fit}) end
   local name=T.make('TextLabel',tile,{Name='Name',BackgroundTransparency=1,Position=UDim2.fromOffset(4,e.icon and 60 or 6),Size=UDim2.fromOffset(90,e.icon and 32 or 84),Text=e.name,TextColor3=C.white,Font=T.Body,TextScaled=true,TextWrapped=true,TextStrokeTransparency=.6})
   T.make('UITextSizeConstraint',name,{MaxTextSize=14,MinTextSize=8})
   tile.MouseEnter:Connect(function() tile.BackgroundColor3=C.well:Lerp(C.lime,.25) end)
   tile.MouseLeave:Connect(function() tile.BackgroundColor3=C.well end)
   tile.Activated:Connect(function() give(e) end)
   tiles[i]={tile=tile,e=e}
  end
  filter=function()
   local q=Commands.norm(g.search)
   for _,t in tiles do
    local e=t.e
    t.tile.Visible=(g.mode=='temp' and (e.temp or e.set) or g.mode=='perm' and e.perm or g.mode=='shop' and e.temp and not e.godly) and (g.kind=='All' or e.kind==g.kind) and (q=='' or string.find(e.norm,q,1,true)~=nil)
   end
   grid.CanvasPosition=Vector2.zero
  end
  search:GetPropertyChangedSignal('Text'):Connect(function() g.search=search.Text;filter() end)
  filter()
  -- Row 4: a chat command, typed here (phones have no slash commands at hand).
  T.panel(v,'CommandWell',0,GIVE_H-40,CW-128,40,'inset')
  local box=T.make('TextBox',v,{Name='CommandBox',Position=UDim2.fromOffset(6,GIVE_H-35),Size=UDim2.fromOffset(CW-140,30),ZIndex=2,BackgroundColor3=INPUT,BorderSizePixel=0,TextColor3=C.white,Font=T.Font,TextSize=16,Text='',PlaceholderText='/tempgive bob katana 2 3 · /armor all iron · /wave 10 · /pause · /resume',PlaceholderColor3=C.dim,ClearTextOnFocus=false,TextXAlignment=Enum.TextXAlignment.Left})
  T.make('UICorner',box,{CornerRadius=UDim.new(0,6)})
  completer(box)
  local function run() local text=box.Text;if text~='' and self.Command(text) then box.Text='' end end
  box.FocusLost:Connect(function(enter) if enter then run() end end)
  T.button(v,'RunCommand','Run',CW-120,GIVE_H-40,120,40,run).Caption.TextSize=18
  return v
 end
 function tabs.Give(c)
  giveView=giveView or buildGive()
  giveView.Parent=c
  return GIVE_H
 end
 -- Shop (2026-10-20, user: "change the % chance some things spawn in the shop for content purposes"):
 -- what is queued for your shop (queue items from the Give tab's Shop mode), and the odds every
 -- player's shop rolls with until set back (ShopService adminOdds). Example: tiers 0 / 0 / 50 / 50 ->
 -- every offer is Tier III or IV; Boost Fart Gun 30 -> about 3 in 10 offers are Fart Guns.
 self.odds={50,30,15,5};self.weaponPct=35;self.boostPct=25
 local function decode(text) local ok,v=pcall(function() return game:GetService('HttpService'):JSONDecode(text) end);return ok and v or nil end
 function tabs.Shop(c)
  local names={};for _,e in catalogEntries() do names[e.key]=e.name end
  heading(c,'QueueTitle','Queued for your shop',0)
  local queue=left(T.text(c,'QueueText','',0,32,CW,44,16,C.white));queue.TextWrapped=true
  live(queue,player,'AdminShopQueue',function(v)
   local steps=type(v)=='string' and decode(v) or nil
   if not steps or #steps==0 then return 'Nothing queued. Give tab, Shop mode: pick the roll (Next = the next shop or reroll) and the tier, then tap an item.' end
   local parts={}
   for i,step in steps do table.insert(parts,(i==1 and 'Next' or ('Roll '..i))..': '..(#step>0 and table.concat(step,', ') or 'normal')) end
   return table.concat(parts,' · ')
  end)
  button(c,'QueueClear','Clear queue',0,80,200,function() send('ShopQueueClear') end)
  button(c,'QueueGive','Queue items (Give tab)',210,80,280,function() self.give.mode='shop';giveView=giveView and giveView:Destroy() or nil;self.tab='Give';list=nil;draw() end,true)
  local now=type(combat:GetAttribute('AdminShopOdds'))=='string' and decode(combat:GetAttribute('AdminShopOdds')) or {}
  local y=140
  heading(c,'OddsTitle','Odds (every player\'s shop)',y);y+=32
  note(c,'OddsNote','Until you set them back. A run they change pays no rewards, like any admin use.',y);y+=34
  left(T.label(c,'TierLabel','Tiers %',0,y,90,40,18))
  local roman={'I','II','III','IV'}
  for t=1,4 do
   local x=90+(t-1)*100
   left(T.label(c,'TierName'..t,roman[t],x,y,30,40,16))
   numberBox(c,'Tier'..t,function() return self.odds[t] end,x+30,y,64,function(v) self.odds[t]=math.clamp(math.floor(v),0,100) end,'%')
  end
  button(c,'TiersApply','Set',500,y,110,function() send('ShopOdds','Tiers',table.concat(self.odds,',')) end,true)
  button(c,'TiersNormal','Normal',620,y,120,function() send('ShopOdds','Tiers') end,now.tiers==nil)
  y+=46
  note(c,'TiersNow',now.tiers and ('Now: I '..now.tiers[1]..'% · II '..now.tiers[2]..'% · III '..now.tiers[3]..'% · IV '..now.tiers[4]..'%') or 'Now: normal (by wave and Luck)',y,now.tiers and C.lime or C.muted);y+=34
  left(T.label(c,'WeaponLabel','Weapons %',0,y,120,40,18))
  numberBox(c,'WeaponPct',function() return self.weaponPct end,120,y,80,function(v) self.weaponPct=math.clamp(math.floor(v),0,100) end,'%')
  button(c,'WeaponApply','Set',210,y,110,function() send('ShopOdds','Weapon',self.weaponPct) end,true)
  button(c,'WeaponNormal','Normal',330,y,120,function() send('ShopOdds','Weapon') end,now.weapon==nil)
  T.text(c,'WeaponNow',now.weapon and ('Now: '..now.weapon..'% of offers are weapons, the rest items') or 'Now: normal (by wave and slot)',462,y+9,CW-462,22,15,now.weapon and C.lime or C.muted)
  y+=56
  heading(c,'BoostTitle','Boost one thing',y);y+=32
  note(c,'BoostNote','Each offer is this first, by its own chance (a weapon at the tier the offer rolled). 0 or its x button takes it off.',y);y+=30
  T.panel(c,'BoostWell',0,y,300,40,'inset')
  local name=T.make('TextBox',c,{Name='BoostName',Position=UDim2.fromOffset(6,y+5),Size=UDim2.fromOffset(288,30),ZIndex=2,BackgroundColor3=INPUT,BorderSizePixel=0,TextColor3=C.white,Font=T.Font,TextSize=17,Text=self.boostName or '',PlaceholderText='fart gun, knee of justice...',PlaceholderColor3=C.dim,ClearTextOnFocus=false,TextXAlignment=Enum.TextXAlignment.Left})
  T.make('UICorner',name,{CornerRadius=UDim.new(0,6)})
  name:GetPropertyChangedSignal('Text'):Connect(function() self.boostName=name.Text end)
  numberBox(c,'BoostPct',function() return self.boostPct end,310,y,80,function(v) self.boostPct=math.clamp(math.floor(v),0,100) end,'%')
  button(c,'BoostAdd','Boost',400,y,140,function()
   local e,why=Commands.find(catalogEntries(),name.Text,'temp')
   if e and e.godly then e,why=nil,'Godly weapons are never sold in the shop' end
   if not e then T.toast(screen,why or 'Name an item',C.negative);return end
   send('ShopBoost',e.key,self.boostPct)
  end,true)
  y+=52
  local bx=0
  for _,b in now.boosts or {} do
   local text=(names[b.key] or b.key)..' '..b.pct..'%  x'
   local w=math.min(CW,40+#text*9)
   if bx+w>CW then bx=0;y+=46 end
   button(c,'Boost_'..b.key,text,bx,y,w,function() send('ShopBoost',b.key,0) end,true).Caption.TextSize=15
   bx+=w+8
  end
  if #(now.boosts or {})>0 then y+=52 end
  button(c,'OddsOff','All odds back to normal',0,y,300,function() send('ShopOdds','Off') end)
  return y+60
 end
 draw=function()
  if not win then return end
  local keep=list and list.Parent and list.CanvasPosition
  statsView.refreshers={} -- the old stat widgets stop updating; the Player tab adds its own again
  if giveView then giveView.Parent=nil end -- kept for the next visit to Give, never rebuilt
  for _,child in win.Body:GetChildren() do child:Destroy() end
  T.tabs(win.Body,0,0,W-36,46,TABS,self.tab,function(id) self.tab=id;list=nil;draw() end)
  list=T.scroll(win.Body,'Content',0,56,W-36,H-58-56)
  local canvas=T.frame(list,'Canvas',0,0,CW,0)
  local body=canvas
  local offset=0
  if self.tab=='Mobs' or self.tab=='Waves' then
   heading(canvas,'DifficultyTitle','Difficulty',0)
   local choices={};for _,d in Rules.Difficulties do table.insert(choices,d.id) end
   T.tabs(canvas,0,36,CW,40,choices,Rules.difficulty(combat:GetAttribute('RunDifficulty')).id,function(id) send('Difficulty',id) end)
   note(canvas,'DifficultyNote','Shared test difficulty. New mobs and waves use it; existing enemies keep their stats.',84)
   offset=124;body=T.frame(canvas,'DifficultyContent',0,offset,CW,0)
  end
  local bodyHeight=tabs[self.tab](body)
  if body~=canvas then body.Size=UDim2.fromOffset(CW,bodyHeight) end
  local height=bodyHeight+offset
  canvas.Size=UDim2.fromOffset(CW,height);list.CanvasSize=UDim2.fromOffset(0,height)
  if keep then list.CanvasPosition=keep end
  screen:SetAttribute('Tab',self.tab)
 end
 function self.Open()
  if win then return end
  win=T.window(screen,'AdminWindow','Admin',W,H,function()
   win=nil;list=nil;statsView.refreshers={};screen:SetAttribute('Open',false)
   if giveView then giveView:Destroy();giveView=nil end
  end)
  screen:SetAttribute('Open',true);draw()
 end
 -- The command bar (2026-10-13): ';' opens it at the bottom of the screen with '/' typed, Tab
 -- completes (completer), Enter runs the command and closes it, Esc or clicking away closes it.
 -- Games can't read Roblox's own chat box, so this is where the completion lives.
 local bar,barBox
 function self.OpenBar()
  if not bar then
   bar=T.make('Frame',screen,{Name='CommandBar',AnchorPoint=Vector2.new(.5,1),Position=UDim2.new(.5,0,1,-96),Size=UDim2.new(1,-24,0,52),BackgroundTransparency=1,ZIndex=35})
   T.make('UISizeConstraint',bar,{MaxSize=Vector2.new(760,52)})
   local well=T.panel(bar,'Well',0,0,0,0,'inset');well.Size=UDim2.fromScale(1,1);well.ZIndex=35
   barBox=T.make('TextBox',bar,{Name='CommandBox',Position=UDim2.fromOffset(8,8),Size=UDim2.new(1,-16,1,-16),ZIndex=36,BackgroundColor3=INPUT,BorderSizePixel=0,TextColor3=C.white,Font=T.Font,TextSize=20,Text='',PlaceholderText='/armor all dragonscale 4',PlaceholderColor3=C.dim,ClearTextOnFocus=false,TextXAlignment=Enum.TextXAlignment.Left})
   T.make('UICorner',barBox,{CornerRadius=UDim.new(0,6)})
   completer(barBox)
   barBox.FocusLost:Connect(function(enter)
    if enter then
     local text=barBox.Text;bar.Visible=false
     if text~='' and text~='/' then self.Command(text) end
    else task.delay(.2,function() if not barBox:IsFocused() then bar.Visible=false end end) end
   end)
  end
  bar.Visible=true
  task.defer(function()
   barBox:CaptureFocus()
   task.defer(function() barBox.Text='/';barBox.CursorPosition=2 end) -- after the ';' key's own character
  end)
 end
 function self.Close() if win then win.Close() end end
 function self.Toggle() if win then self.Close() else self.Open() end end
 function self.Show(tab) if tab and tabs[tab] then self.tab=tab end;if win then list=nil;draw() else self.Open() end end
 -- Redraw live state (phase, wave, pause, freeze, map, area) while open. The Player tab redraws
 -- only after its own requests: rebuilding the stat editor on every shard pickup would fight typing.
 local function changed() if win and self.tab~='Player' and self.tab~='Give' then draw() end end
 for _,a in {'Phase','Wave','AdminPaused','EventId','EventPhase'} do run:GetAttributeChangedSignal(a):Connect(changed) end
 for _,a in {'AdminFreeze','TestZombieCountOverride','RunMap','RunDifficulty','AdminShopOdds','AdminHideTestTag'} do combat:GetAttributeChangedSignal(a):Connect(changed) end
 player:GetAttributeChangedSignal('StudioArea'):Connect(changed)
 combat:GetAttributeChangedSignal('TutorialRun'):Connect(changed)
 player:GetAttributeChangedSignal('ProfileTutorial'):Connect(changed)
 return self
end
return M
