-- Lobby HUD and menus, drawn with the shared green theme (UITheme).
-- Presentation and requests only: chests, upgrades, class unlocks and purchases go through
-- server remotes (ProfileAction, PurchaseRequest) and are validated there. Saved progression
-- is read from LocalPlayer attributes published by ProfileService.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local Input=game:GetService('UserInputService')
local Social=game:GetService('SocialService')
local T=require(RS:WaitForChild('UITheme'))
local combat=RS:WaitForChild('RogueliteCombat')
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local ShopCatalog=require(combat:WaitForChild('ShopCatalog'))
local Chests=require(combat:WaitForChild('ChestConfig'))
local RunService=game:GetService('RunService')
local Http=game:GetService('HttpService')
-- Store and Quests windows (plans/2026-10-01-H-store-and-quests.md).
local StoreUI=require(RS:WaitForChild('StoreUI'))
local QuestsUI=require(RS:WaitForChild('QuestsUI'))
-- Daily quest names for the HUD tracker; nil (and the tracker says so) until it is installed.
local questModule=combat:WaitForChild('QuestConfig',10)
local QuestConfig=questModule and require(questModule)
local C=T.Color
local L={}

-- Design data from PROGRESSION_AND_SESSION_FLOW.md / MONETIZATION_AND_REWARDS.md (proposals).
-- Maps, signature weapons and class unlocks are shared with the lobby server (RunSetupRules).
local Rules=require(RS:WaitForChild('RunSetupRules'))
local RunSetup=require(RS:WaitForChild('RunSetupUI'))
local ArmoryUI=require(RS:WaitForChild('ArmoryUI'))
local StationApproach=require(RS:WaitForChild('StationApproach'))
local SkillTreeUI=require(RS:WaitForChild('SkillTreeUI'))
local ChestScreenUI=require(RS:WaitForChild('ChestScreenUI'))
-- The egg merchant's screen, protected: a fault in it must never take the lobby HUD down.
local eggsOk,EggScreenUI=pcall(require,RS:WaitForChild('EggScreenUI'))
if not eggsOk then warn('LobbyUI: EggScreenUI failed to load:',EggScreenUI);EggScreenUI=nil end
local SkillTree=require(combat:WaitForChild('SkillTreeConfig'))
L.Maps=Rules.Maps
L.Signature=Rules.Signature
L.ClassUnlock=Rules.ClassUnlock
L.StationRoutes={Collection='Loadout',Workshop='Armory',Rewards='Chests',Store='Store',Quests='Quests'}

-- Profile adapter (ProfileService attributes): ProfileGems (emeralds, the only currency),
-- ProfileGemsEarned (the part not bought with Robux; all that restricted regions may spend on chests),
-- ProfileClasses ('Brawler,Gunner'), ProfileWeapons ('01:2:3' = id:tier:duplicates held),
-- ProfilePity / ProfilePicks / ProfileChests ('Brawler:3'), ProfileBestWaves, ProfileMapWins,
-- ProfileStarterPack, ProfileVIP, and PaidRandomRestricted (PolicyService).
local function csvSet(text) local out={};for v in string.gmatch(text or '','[^,]+') do out[v]=true end;return out end
local function csvMap(text) local out={};for k,v in string.gmatch(text or '','([^,:]+):(%d+)') do out[k]=tonumber(v) end;return out end
function L.profile(player)
 local connected=player:GetAttribute('ProfileLoaded')==true
 local p={connected=connected,gems=player:GetAttribute('ProfileGems') or 0}
 p.gemsEarned=player:GetAttribute('ProfileGemsEarned') or p.gems
 p.classes=connected and csvSet(player:GetAttribute('ProfileClasses')) or {Brawler=true,Gunner=true,Mage=true}
 p.weapons={}
 if connected then
  for id,tier,have in string.gmatch(player:GetAttribute('ProfileWeapons') or '','([^,:]+):(%d+):(%d+)') do p.weapons[id]={id=id,tier=math.clamp(tonumber(tier),1,4),have=tonumber(have)} end
 else for class in p.classes do p.weapons[L.Signature[class]]={id=L.Signature[class],tier=1,have=0} end end
 -- Armor: ProfileArmor ('DragonScale.Helmet:1:0' = piece:tier:copies), ProfileWearing ('Helmet:DragonScale').
 p.armor={};p.wearing={}
 for id,tier,have in string.gmatch(player:GetAttribute('ProfileArmor') or '','([^,:]+):(%d+):(%d+)') do p.armor[id]={id=id,tier=math.clamp(tonumber(tier),1,4),have=tonumber(have)} end
 for slot,set in string.gmatch(player:GetAttribute('ProfileWearing') or '','([^,:]+):([^,:]+)') do p.wearing[slot]=set end
 -- Pets: ProfilePets ('Fox:2:1' = pet:tier:copies), ProfilePet (the equipped pet id, '' = none).
 p.pets={}
 for id,tier,have in string.gmatch(player:GetAttribute('ProfilePets') or '','([^,:]+):(%d+):(%d+)') do p.pets[id]={id=id,tier=math.clamp(tonumber(tier),1,4),have=tonumber(have)} end
 local pet=player:GetAttribute('ProfilePet');p.pet=type(pet)=='string' and p.pets[pet] and pet or nil
 p.freeChestDay=player:GetAttribute('ProfileFreeChestDay') or 0 -- = MonetizationConfig.day(): today's free Wooden Chest is claimed
 p.best=csvMap(player:GetAttribute('ProfileBestWaves'))
 p.wins=csvSet(player:GetAttribute('ProfileMapWins'))
 p.pity=csvMap(player:GetAttribute('ProfilePity'));p.picks=csvMap(player:GetAttribute('ProfilePicks'))
 p.chests=csvMap(player:GetAttribute('ProfileChests'))
 p.starter=player:GetAttribute('ProfileStarterPack')==true;p.vip=player:GetAttribute('ProfileVIP')==true
 p.bundles=csvSet(player:GetAttribute('ProfileBundles')) -- one-time Godly bundles already bought
 p.restricted=player:GetAttribute('PaidRandomRestricted')==true
 p.quickOpen=player:GetAttribute('ProfileQuickOpen')==true or p.vip
 p.rerolls=player:GetAttribute('ProfileRerolls') or 0;p.banishes=player:GetAttribute('ProfileBanishes') or 0
 local ok,daily=pcall(Http.JSONDecode,Http,player:GetAttribute('ProfileDaily') or '')
 p.daily=ok and type(daily)=='table' and daily or {deals={}}
 -- Daily quests, streak and achievements (QuestService view); {} until the server sends it.
 local okQ,quests=pcall(Http.JSONDecode,Http,player:GetAttribute('ProfileQuests') or '')
 p.quests=okQ and type(quests)=='table' and quests or {}
 return p
end
-- Upgrading spends copies from chests: have/need shown as numbers, e.g. 5 / 4 -> upgrade -> 1 / 10.
-- Rarer weapons need fewer copies (ChestConfig.UpgradeByRarity); records carry their weapon id.
L.UpgradeCost=Chests.UpgradeCost
function L.need(rec) return rec and rec.tier<4 and (rec.id and Chests.upgradeCost(rec.id,rec.tier) or L.UpgradeCost[rec.tier]) or nil end
function L.mapUnlocked(p,index) return Rules.mapUnlocked(p.wins,index) end
local function homeWeapons(class) local out={};for _,w in Weapons.List do if w.home==class then table.insert(out,w) end end;return out end
local function passives() local out={};for _,e in ShopCatalog.List do if not e.weaponId then table.insert(out,e) end end;return out end
local function fmt(n) n=tonumber(n) or 0;if n>=1e6 then return string.format('%.1fM',n/1e6) elseif n>=1e4 then return string.format('%.1fK',n/1e3) end;return tostring(n) end

local function rowButton(parent,name,x,y,w,h,selected,callback)
 local b=T.button(parent,name,'',x,y,w,h,callback,not selected);b.Caption.Visible=false;return b
end
local function sectionTitle(parent,name,text,x,y,w)
 local l=T.label(parent,name,text,x,y,w,30,22,C.white);l.TextXAlignment=Enum.TextXAlignment.Left;return l
end
-- Studio profiles live in memory only; say so wherever progress is shown.
local function preview(parent,x,y,p)
 if not RunService:IsStudio() and p.connected then return end
 return T.chip(parent,'PreviewChip',p.connected and 'STUDIO TEST · NOT SAVED' or 'PROFILE LOADING',x,y,Color3.fromRGB(58,48,20),C.gold)
end
-- Currency amount with its icon, centred as one group (e.g. on a price button).
local function cost(parent,amount,asset,size)
 local g=T.make('Frame',parent,{Name='Cost',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),AutomaticSize=Enum.AutomaticSize.X,Size=UDim2.fromOffset(0,size+6),ZIndex=3})
 T.make('UIListLayout',g,{FillDirection=Enum.FillDirection.Horizontal,VerticalAlignment=Enum.VerticalAlignment.Center,Padding=UDim.new(0,6),SortOrder=Enum.SortOrder.LayoutOrder})
 local tw=game:GetService('TextService'):GetTextSize(tostring(amount),size,T.Font,Vector2.new(1000,100)).X
 -- A little wider than the text so it still fits at the smallest (phone) scale.
 local l=T.label(g,'Amount',tostring(amount),0,0,math.ceil(tw*1.2)+6,size+6,size);l.LayoutOrder=1;l.TextWrapped=false;l.ZIndex=3
 if asset then local i=T.icon(g,'Icon',0,0,size+6,asset);i.LayoutOrder=2;i.ZIndex=3 end
 return g
end

function L.mount(player)
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='RogueliteLobbyHUD',ResetOnSpawn=false,DisplayOrder=35,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets,ClipToDeviceSafeArea=true,Enabled=false})
 local hud=T.frame(screen,'HUD',0,0,0,0);hud.Size=UDim2.fromScale(1,1)
 local self={Screen=screen,current=nil,selection={map=1,class=player:GetAttribute('LoadoutClass') or 'Brawler',weapon=player:GetAttribute('LoadoutWeapon')}}
 local open -- forward
 local function scaled(name,anchor,position,size)
  local f=T.frame(hud,name,0,0,size.X,size.Y);f.AnchorPoint=anchor;f.Position=position
  return f,T.make('UIScale',f,{Scale=1})
 end
 -- Upper left: profile chip, party button, currencies, quest tracker.
 local left,leftScale=scaled('Left',Vector2.new(0,0),UDim2.fromOffset(14,10),Vector2.new(330,420))
 local chip=T.button(left,'ProfileChip','',0,0,250,70,function() open('Profile') end,true);chip.Caption.Visible=false
 local ring=T.panel(chip,'Portrait',10,8,54,54,'inset')
 local head=T.make('ImageLabel',ring,{Name='Headshot',BackgroundTransparency=1,Position=UDim2.fromOffset(3,3),Size=UDim2.fromOffset(48,48),Image=''})
 T.make('UICorner',head,{CornerRadius=UDim.new(0,8)})
 T.headshot(head,player.UserId)
 local nameLabel=T.label(chip,'Name',player.DisplayName,72,8,168,30,20);nameLabel.TextXAlignment=Enum.TextXAlignment.Left;nameLabel.TextTruncate=Enum.TextTruncate.AtEnd;nameLabel.TextWrapped=false
 local chipSub=T.text(chip,'Sub','',72,38,168,22,15,C.muted)
 local party=T.button(left,'PartyButton','',258,0,70,70,function() open('Party') end,true);party.Caption.Visible=false
 T.icon(party,'Icon',9,9,52,'party')
 local plus=T.label(party,'Plus','+',44,38,26,26,24,C.lime)
 local function currency(name,asset,y,color)
  local row=T.panel(left,name,0,y,220,48,'inset')
  T.icon(row,'Icon',8,4,40,asset)
  local v=T.label(row,'Value','0',54,4,100,40,26,color);v.TextXAlignment=Enum.TextXAlignment.Left
  -- + opens the store's Emeralds tab.
  local plusB=T.button(left,name..'Plus','+',226,y+4,40,40,function() open('Store','Emeralds') end)
  plusB.Caption.TextSize=28
  return v
 end
 -- Emeralds are the only currency: earned in runs and bought with Robux.
 local gemsValue=currency('Gems','emerald',82,C.emerald)
 local gt=T.label(left.Gems,'Tag','EMERALDS',110,10,100,28,14,C.muted);gt.TextXAlignment=Enum.TextXAlignment.Right
 -- Quest tracker (QuestsUI.tracker, plan K): today's quests, the streak and OPEN QUESTS. A finished
 -- quest claims right on it; anywhere else on the tracker opens the Quests window.
 local tracker=QuestsUI.tracker(left,0,140,{config=QuestConfig,open=function() open('Quests','Daily') end,
  claim=function(i)
   task.spawn(function()
    local ok,r=pcall(function() return combat:WaitForChild('ProfileAction'):InvokeServer('ClaimQuest',i) end)
    if ok and type(r)=='table' then
     if r.ok then T.sound('ui_purchase') end
     T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
    end
   end)
  end})
 local goals=tracker.Root
 -- Right edge: store, rewards, settings, practice-dummy attacks switch.
 local right,rightScale=scaled('Right',Vector2.new(1,.5),UDim2.new(1,-12,.45,0),Vector2.new(96,592))
 -- Centred: the column is tall enough for the developers' ADMIN button; without it the buttons
 -- sit centred on the same spot instead of moving up.
 -- layout() sizes the column to its buttons and wraps it into two columns on short screens.
 local rightList=T.make('UIListLayout',right,{Padding=UDim.new(0,10),HorizontalAlignment=Enum.HorizontalAlignment.Center,VerticalAlignment=Enum.VerticalAlignment.Center,SortOrder=Enum.SortOrder.LayoutOrder})
 local store=T.iconButton(right,'Store','store','STORE',78,function() open('Store') end);store.LayoutOrder=1
 local skills=T.iconButton(right,'Skills',SkillTree.Icons.Hud,'SKILLS',78,function() open('Skills') end);skills.LayoutOrder=2
 local awards=T.iconButton(right,'Awards','achievements','REWARDS',78,function() open('Quests','Achievements') end);awards.LayoutOrder=3
 local settings=T.iconButton(right,'Settings','settings','SETTINGS',64,function() open('Settings') end);settings.LayoutOrder=4
 -- LayoutOrder 6 (after ATTACKS) is the developers' ADMIN button, added by AdminPanel.client (ADMIN_PANEL.md).
 -- Practice dummies: weapons auto-attack them until switched off. The server owns
 -- PlayerStates.<id>.LobbyAttacks; this button, T / gamepad Y and Settings only ask.
 local attacks=T.button(right,'DummyAttacks','ATTACKS',0,0,96,70,nil,false);attacks.LayoutOrder=5
 attacks.Caption.Position=UDim2.fromOffset(4,8);attacks.Caption.Size=UDim2.new(1,-8,0,24);attacks.Caption.TextSize=18
 local attacksState=T.label(attacks,'State','ON',4,32,88,30,26)
 local attacksKey=T.chip(attacks,'Key','T',70,-10,C.well,C.lime)
 local myState
 local setLobbyAttacks=combat:WaitForChild('SetLobbyAttacks')
 local function attacksOn() return not myState or myState:GetAttribute('LobbyAttacks')~=false end
 -- Keyboard T, gamepad Y; touch players tap the button, so no key hint.
 local function keyHint()
  local t=Input:GetLastInputType()
  if t==Enum.UserInputType.Touch then return nil end
  return t.Name:find('^Gamepad') and 'Y' or 'T'
 end
 local dummyHints={}
 local function paintAttacks()
  local on,key=attacksOn(),keyHint()
  T.setPrimary(attacks,on)
  attacksState.Text=on and 'ON' or 'OFF';attacksState.TextColor3=on and C.white or C.muted
  attacksKey.Visible=key~=nil;if key then attacksKey.Text.Text=key end
  local how=key and ('Press '..key) or 'Tap ATTACKS'
  for _,hint in dummyHints do
   hint.Status.Text=on and 'Your weapons attack it automatically.' or 'Attacks are off. Your weapons ignore it.'
   hint.How.Text=how..(on and ' to turn attacks off.' or ' to turn attacks on.')
  end
 end
 local lastToggle=-1
 local function toggleAttacks()
  if not myState or os.clock()-lastToggle<.3 then return end;lastToggle=os.clock()
  local on=not attacksOn()
  setLobbyAttacks:FireServer(on)
  T.toast(screen,on and 'Dummy attacks ON' or 'Dummy attacks OFF',on and C.lime or C.muted)
 end
 attacks.Activated:Connect(toggleAttacks)
 Input.LastInputTypeChanged:Connect(paintAttacks)
 -- Sign over each dummy saying it's a target and how to stop attacking it.
 local function addHint(dummy)
  if dummyHints[dummy] then return end
  local bb=T.make('BillboardGui',player:WaitForChild('PlayerGui'),{Name='DummyHint_'..dummy.Name,Size=UDim2.fromOffset(270,92),
   MaxDistance=60,LightInfluence=0,ResetOnSpawn=false,Enabled=screen.Enabled})
  local panel=T.panel(bb,'Panel',0,0,270,92,'panel')
  T.label(panel,'Title','PRACTICE DUMMY',10,6,250,28,21,C.lime)
  local status=T.text(panel,'Status','',14,36,242,22,16);status.TextXAlignment=Enum.TextXAlignment.Center
  local how=T.text(panel,'How','',14,60,242,22,16,C.muted);how.TextXAlignment=Enum.TextXAlignment.Center
  dummyHints[dummy]={Gui=bb,Status=status,How=how}
  -- Streaming: the dummy's parts arrive (and can leave) with distance, so follow its root.
  local function adorn()
   local root=dummy:FindFirstChild('HumanoidRootPart');bb.Adornee=root
   if root then bb.StudsOffsetWorldSpace=Vector3.new(0,root.Size.Y*.5+2.2,0) end
  end
  dummy.ChildAdded:Connect(adorn);dummy.ChildRemoved:Connect(adorn);adorn()
  paintAttacks()
 end
 local Tags=game:GetService('CollectionService')
 Tags:GetInstanceAddedSignal('LobbyPracticeDummy'):Connect(addHint)
 Tags:GetInstanceRemovedSignal('LobbyPracticeDummy'):Connect(function(d) local h=dummyHints[d];if h then h.Gui:Destroy();dummyHints[d]=nil end end)
 for _,d in Tags:GetTagged('LobbyPracticeDummy') do addHint(d) end
 task.spawn(function()
  myState=combat:WaitForChild('PlayerStates'):WaitForChild(tostring(player.UserId))
  myState:GetAttributeChangedSignal('LobbyAttacks'):Connect(function()
   paintAttacks()
   if self.onLobbyAttacks then self.onLobbyAttacks() end
  end)
  paintAttacks()
 end)
 paintAttacks()
 -- Bottom centre: main actions with PLAY in the middle.
 local bottom,bottomScale=scaled('Bottom',Vector2.new(.5,1),UDim2.new(.5,0,1,-8),Vector2.new(640,150))
 local order={{'Chests','chest','CHESTS',86},{'Armory','armory','ARMORY',86},{'Play','play','PLAY',122},{'Loadout','loadout','LOADOUT',86},{'Quests','quests','QUESTS',86}}
 local x=0;local bottomButtons={}
 for _,o in order do
  local b=T.iconButton(bottom,o[1],o[2],o[3],o[4],function() open(o[1]) end)
  b.AnchorPoint=Vector2.new(0,1);b.Position=UDim2.new(0,x,1,0);x+=o[4]+(o[1]=='Play' and 36 or 34)
  bottomButtons[o[1]]=b
 end
 bottom.Size=UDim2.fromOffset(x-34,150)
 if bottomButtons.Play.Caption then bottomButtons.Play.Caption.TextSize=30;bottomButtons.Play.Caption.TextColor3=C.lime end
 -- Top centre: portal queue status / guidance.
 local banner=T.panel(hud,'QueueBanner',0,0,420,74,'panel');banner.AnchorPoint=Vector2.new(.5,0);banner.Position=UDim2.new(.5,0,0,12);banner.Visible=false
 local bannerScale=T.make('UIScale',banner,{Scale=1})
 T.caps(banner,44)
 local bannerTitle=T.label(banner,'Title','',30,6,260,34,24);bannerTitle.TextXAlignment=Enum.TextXAlignment.Left
 local bannerSub=T.text(banner,'Sub','',30,40,260,22,15,C.muted)
 local leave=T.button(banner,'Leave','LEAVE',300,14,96,46,function() local r=workspace:FindFirstChild('RogueliteLobby') and workspace.RogueliteLobby:FindFirstChild('LeaveQueue');if r then r:FireServer() end end,true)
 leave.Caption.TextSize=18;leave.Caption.TextColor3=C.negative

 local profile
 local function refreshHud()
  profile=L.profile(player)
  gemsValue.Text=fmt(profile.gems)
  local owned=0;for _ in profile.classes do owned+=1 end
  chipSub.Text=owned..' / 6 classes'..(profile.vip and '  ·  VIP' or '')
  -- Chests badge counts chests already owned (unopened); emeralds are shared with skills.
  local ready=0;for _,n in profile.chests do ready+=n end
  T.badge(bottomButtons.Chests,ready>0 and tostring(ready) or nil)
  local buyable=SkillTree.affordable(SkillTree.parse(player:GetAttribute('ProfileSkills')),profile.gems)
  T.badge(skills,buyable>0 and tostring(buyable) or nil)
  -- Tracker (plan K): today's quests and the streak; badges count rewards waiting for CLAIM.
  local quests=profile.quests;tracker.update(quests)
  local claim=quests.claimable or 0
  T.badge(bottomButtons.Quests,claim>0 and tostring(claim) or nil)
  T.badge(awards,claim>0 and tostring(claim) or nil)
  T.badge(tracker.OpenButton,claim>0 and tostring(claim) or nil)
 end

 -- Guide beam from the character to the nearest open portal.
 local guide
 local refreshQueue -- forward: guideToPortal's timeout refreshes the banner
 local function clearGuide() if guide then guide:Destroy();guide=nil end;self.guiding=false end
 local function guideToPortal()
  clearGuide()
  local root=workspace:FindFirstChild('RogueliteLobby');local portals=root and root:FindFirstChild('Portals')
  local hrp=player.Character and player.Character:FindFirstChild('HumanoidRootPart')
  if not portals or not hrp then return end
  local best,dist
  for _,portal in portals:GetChildren() do
   local zone=portal:FindFirstChild('QueueZone')
   if zone and (portal:GetAttribute('QueueCount') or 0)<4 then
    local d=(zone.Position-hrp.Position).Magnitude
    if not dist or d<dist then best,dist=zone,d end
   end
  end
  if not best then return end
  guide=Instance.new('Folder');guide.Name='PortalGuide';guide.Parent=workspace.CurrentCamera
  local a0=Instance.new('Attachment');a0.Name='GuideStart';a0.Position=Vector3.new(0,-2.4,0);a0.Parent=hrp
  local a1=Instance.new('Attachment');a1.Name='GuideEnd';a1.Parent=best
  local beam=Instance.new('Beam');beam.Attachment0=a0;beam.Attachment1=a1;beam.FaceCamera=true;beam.Width0=1.1;beam.Width1=1.1
  beam.Color=ColorSequence.new(C.lime);beam.LightEmission=.6;beam.Transparency=NumberSequence.new(.25);beam.Segments=20;beam.Parent=guide
  guide.Destroying:Connect(function() a0:Destroy();a1:Destroy() end)
  self.guiding=true
  local mine=guide
  task.delay(25,function() if guide==mine and guide.Parent then clearGuide();refreshQueue() end end)
 end
 refreshQueue=function()
  local q=player:GetAttribute('LobbyQueue')
  if q then clearGuide() end
  local portal=q and workspace:FindFirstChild('RogueliteLobby') and workspace.RogueliteLobby.Portals:FindFirstChild('Portal'..q)
  banner.Visible=q~=nil or self.guiding==true
  leave.Visible=q~=nil
  banner.Size=UDim2.fromOffset(q and 420 or 330,74) -- No LEAVE button while only guiding.
  if q then
   bannerTitle.Text='PORTAL '..q..'  ·  '..(portal and portal:GetAttribute('QueueCount') or 1)..' / '..(portal and portal:GetAttribute('Capacity') or 4)
   local launchAt=portal and portal:GetAttribute('LaunchAt')
   local launch=portal and portal:GetAttribute('QueueState')=='Launching' and 'entering portal'
    or launchAt and string.format('starting in %ds',math.max(0,math.ceil(launchAt-workspace:GetServerTimeNow()))) or 'host is choosing'
   local mapId=portal and portal:GetAttribute('MapId')
   bannerSub.Text=(mapId and L.Maps[Rules.MapIndex[mapId]].name or 'Map not chosen')..'  ·  '..self.selection.class..'  ·  '..launch
  else
   bannerTitle.Text='FIND A PORTAL';bannerSub.Text='Follow the green beam to a queue pad'
  end
 end

 -- Windows ---------------------------------------------------------------
 local win
 local builders={}
 open=function(name,arg)
  if win then win.Close() end
  local build=builders[name];if not build then return end
  refreshHud()
  self.redraw=nil
  win=build(arg)
  if win then
   local mine=win
   win.Root.Destroying:Connect(function() if win==mine then win=nil;self.current=nil;screen:SetAttribute('OpenWindow',nil) end end)
   self.current=name;screen:SetAttribute('OpenWindow',name)
  end
 end
 self.Open=open
 -- Studio-only hook so layout tests (UILayoutAudit) can open and close windows.
 if game:GetService('RunService'):IsStudio() then
  local hook=Instance.new('BindableEvent');hook.Name='TestOpenWindow';hook.Parent=screen
  hook.Event:Connect(function(name,arg) if name then open(name,arg) elseif win then win.Close() end end)
 end
 function self.CloseWindow() if win then win.Close() end end

 builders.Settings=function()
  return T.settingsWindow(screen,{{key='DummyAttacks',title='Dummy attacks',help='Weapons auto-attack lobby practice dummies.',get=attacksOn,toggle=toggleAttacks}})
 end
 self.onLobbyAttacks=function() if self.current=='Settings' and win and win.Redraw then win.Redraw() end end

 builders.Profile=function()
  local w=T.window(screen,'ProfileWindow','Profile',720,470);local b=w.Body;local W=684
  local card=T.panel(b,'Card',0,10,230,392,'inset')
  local portrait=T.make('ImageLabel',card,{Name='Headshot',BackgroundTransparency=1,Position=UDim2.fromOffset(35,20),Size=UDim2.fromOffset(160,160),Image=''});T.headshot(portrait,player.UserId)
  T.label(card,'Name',player.DisplayName,10,188,210,34,24).TextWrapped=false -- one line: long names shrink
  T.text(card,'User','@'..player.Name,10,222,210,20,15,C.muted).TextXAlignment=Enum.TextXAlignment.Center
  local classes=0;for _ in profile.classes do classes+=1 end
  local owned=0;for _ in profile.weapons do owned+=1 end
  for i,s in {{'Classes',classes..' / 6'},{'Weapons',owned..' / '..#Weapons.List},{'Emeralds',fmt(profile.gems)}} do
   T.text(card,'Stat'..i,s[1],18,256+(i-1)*40,110,30,18,C.muted)
   local v=T.text(card,'Value'..i,s[2],110,256+(i-1)*40,100,30,20);v.TextXAlignment=Enum.TextXAlignment.Right
  end
  sectionTitle(b,'MapsTitle','Map ladder',250,6,300)
  preview(b,W-260,10,profile)
  for i,m in L.Maps do
   local row=T.panel(b,'Map'..i,250,44+(i-1)*70,W-250,62,'panel')
   local unlocked=L.mapUnlocked(profile,i)
   T.label(row,'Index',tostring(i),10,12,36,38,26,unlocked and C.lime or C.dim)
   local n=T.label(row,'Name',m.name,52,6,220,28,22,unlocked and C.white or C.dim);n.TextXAlignment=Enum.TextXAlignment.Left
   T.text(row,'Boss','Boss: '..m.boss,52,34,220,20,14,C.muted)
   local best=profile.best[m.id]
   local status=profile.wins[m.id] and 'WON' or unlocked and (best and 'BEST WAVE '..best or 'NOT PLAYED') or 'LOCKED'
   T.chip(row,'Status',status,W-250-150,20,profile.wins[m.id] and C.limeDark or C.well,profile.wins[m.id] and C.white or C.muted)
  end
  return w
 end

 builders.Party=function()
  local w=T.window(screen,'PartyWindow','Party',560,480);local b=w.Body;local W=524
  T.text(b,'Help','Stand on the same portal pad to queue together — up to 4 players per portal.',6,8,W-12,40,17,C.muted)
  local invite=T.button(b,'Invite','INVITE FRIENDS',6,52,W-12,50,function()
   local ok,can=pcall(Social.CanSendGameInviteAsync,Social,player)
   if ok and can then pcall(Social.PromptGameInvite,Social,player) end
  end)
  invite.Caption.TextSize=22
  sectionTitle(b,'ServerTitle','In this server',6,114,W)
  local list=T.scroll(b,'Players',0,150,W,262)
  local y=0
  for _,other in Players:GetPlayers() do
   local row=T.panel(list,'Player_'..other.UserId,4,y,W-20,60,'panel')
   local img=T.make('ImageLabel',row,{Name='Headshot',BackgroundTransparency=1,Position=UDim2.fromOffset(10,8),Size=UDim2.fromOffset(44,44),Image=''});T.headshot(img,other.UserId)
   local n=T.label(row,'Name',other.DisplayName..(other==player and '  (you)' or ''),64,6,W-200,28,19);n.TextXAlignment=Enum.TextXAlignment.Left
   T.text(row,'User','@'..other.Name,64,32,W-200,20,14,C.muted)
   local q=other:GetAttribute('LobbyQueue')
   T.chip(row,'Status',q and ('PORTAL '..q) or 'IN LOBBY',W-150,19,q and C.limeDark or C.well)
   y+=68
  end
  list.CanvasSize=UDim2.fromOffset(0,y)
  return w
 end

 -- Run setup (full screen): PLAY and LOADOUT open it, and so does stepping onto a pad.
 local function myPortal()
  local q=player:GetAttribute('LobbyQueue')
  return q and workspace:WaitForChild('RogueliteLobby'):WaitForChild('Portals'):FindFirstChild('Portal'..q)
 end
 -- Host while the pad is still choosing; anyone else on a pad (or a host after START) is a member.
 local function padMode()
  local portal=myPortal();if not portal then return nil end
  if portal:GetAttribute('HostId')==player.UserId and portal:GetAttribute('QueueState')=='Choosing' then return 'Host' end
  return 'Member'
 end
 local setup=RunSetup.new(player,{
  profile=function() profile=L.profile(player);return profile end,
  need=L.need,cost=cost,selection=self.selection,toastScreen=screen,
  findPortal=function() guideToPortal();refreshQueue() end,
  hostMap=function() local portal=myPortal();return portal and portal:GetAttribute('MapId') end,
 })
 self.Setup=setup
 -- The setup screen replaces the lobby HUD while it is open.
 setup.Screen:GetPropertyChangedSignal('Enabled'):Connect(function() hud.Visible=not setup.Screen.Enabled end)
 builders.Play=function() setup.Open(padMode() or 'Play') end
 builders.Loadout=function() setup.Open('Loadout') end
 -- Full-screen Armory in the 3D armory hall (ArmoryUI + ArmoryStage); also replaces the lobby HUD.
 local armory=ArmoryUI.new(player,{
  profile=function() profile=L.profile(player);return profile end,
  need=L.need,selection=self.selection,
  openWindow=function(name,arg) task.defer(open,name,arg) end,
  onVisible=function(visible) hud.Visible=visible end,
 })
 self.Armory=armory
 -- Full-screen Skill Tree (SkillTreeUI); also replaces the lobby HUD while open.
 local skillTree=SkillTreeUI.new(player,{
  profile=function() profile=L.profile(player);return profile end,
  onVisible=function(visible) hud.Visible=visible end,
 })
 self.SkillTree=skillTree
 builders.Skills=function() return skillTree.Open() end

 -- Full-screen chest screen over the chest island (ChestScreenUI + ChestStage); replaces the HUD.
 local chestScreen=ChestScreenUI.new(player,{
  profile=function() profile=L.profile(player);return profile end,
  need=L.need,selection=self.selection,
  openWindow=function(name,arg) task.defer(open,name,arg) end,
  onVisible=function(visible) hud.Visible=visible end,
 })
 self.ChestScreen=chestScreen
 builders.Chests=function(kind) return chestScreen.Open(kind) end
 -- Egg merchant (quest-board island): full-screen egg screen over the egg pedestal (EggScreenUI
 -- + EggStage); the walk-up ring in front of the merchant opens it. Replaces the HUD while open.
 if EggScreenUI then
  local ok,eggScreen=pcall(EggScreenUI.new,player,{
   profile=function() profile=L.profile(player);return profile end,
   need=L.need,
   openWindow=function(name,arg) task.defer(open,name,arg) end,
   onVisible=function(visible) hud.Visible=visible end,
  })
  if ok then self.EggScreen=eggScreen;builders.Eggs=function() return eggScreen.Open() end
  else warn('LobbyUI: egg screen failed:',eggScreen) end
 end

 builders.Armory=function(tab) return armory.Open(tab) end

 -- Quests and Store windows: QuestsUI and StoreUI draw them from this profile.
 local windowCtx={
  profile=function() profile=L.profile(player);return profile end,
  need=L.need,selection=self.selection,cost=cost,fmt=fmt,signature=L.Signature,config=QuestConfig,
  open=function(name,arg) task.defer(open,name,arg) end,
  setRedraw=function(fn) self.redraw=fn end,
 }
 builders.Quests=function(tab) return QuestsUI.open(screen,windowCtx,tab) end
 builders.Store=function(focus) return StoreUI.open(screen,windowCtx,focus) end

 -- World stations: no E prompts. Stepping onto the glowing ring in front of a stand opens its window
 -- with a quick camera push and fade; the ring re-arms once you step off (StationApproach).
 local root=workspace:WaitForChild('RogueliteLobby')
 StationApproach.start(root,{
  open=function(route) open(route) end,
  busy=function() return win~=nil or setup.IsOpen() or player:GetAttribute('LobbyQueue')~=nil or not screen.Enabled end,
  visible=function() return screen.Enabled end,
 })
 -- Stepping onto a pad pops up the run setup: the host picks the map, others pick a class.
 local lastQueue
 player:GetAttributeChangedSignal('LobbyQueue'):Connect(function()
  local q=player:GetAttribute('LobbyQueue')
  if q==lastQueue then return end
  lastQueue=q
  if q then
   if win then win.Close() end
   task.defer(function() local mode=padMode();if mode and player:GetAttribute('LobbyQueue')==q then setup.Open(mode) end end)
  elseif setup.mode=='Host' or setup.mode=='Member' then setup.Close() end
 end)
 local function portalChanged(portal)
  if portal~=myPortal() then return end
  local mode=padMode()
  -- Host handed over (previous host stepped off) while choosing: this player picks the map now.
  if mode=='Host' and setup.mode~='Host' then setup.Open('Host')
  elseif setup.mode=='Member' then setup.Refresh() end
 end
 Input.InputBegan:Connect(function(input,processed)
  if not screen.Enabled or setup.IsOpen() then return end
  -- Screens with their own back steps (Chests: odds panel -> results -> list) handle Escape/B themselves.
  if input.KeyCode==Enum.KeyCode.Escape or input.KeyCode==Enum.KeyCode.ButtonB then if win and not win.HandlesBack then win.Close() end;return end
  if processed or Input:GetFocusedTextBox() then return end
  if input.KeyCode==Enum.KeyCode.T or input.KeyCode==Enum.KeyCode.ButtonY then toggleAttacks();return end
  local keys={[Enum.KeyCode.L]='Loadout',[Enum.KeyCode.C]='Chests',[Enum.KeyCode.J]='Quests',[Enum.KeyCode.K]='Skills'}
  local route=keys[input.KeyCode];if route then if self.current==route and win then win.Close() else open(route) end end
 end)
 -- Layout: one HUD scale from the screen size, with a bigger minimum on touch screens (a thumb
 -- needs ~40 px buttons), then each group is placed so none can overlap: the right column shrinks
 -- or wraps into two columns to stay between the top and the jump button / bottom bar, and the
 -- queue banner moves under the profile chip when the top centre is too narrow. Example: an 844x390
 -- phone (750x311 HUD area) gets scale .75, two right columns above the jump button, and the banner
 -- under the chip; 1920x1080 is unchanged (scale 1.1, one column, banner top centre).
 local function jumpButton()
  -- Roblox's touch jump button, in HUD coordinates (x, y of its top-left), or nil.
  local tg=player.PlayerGui:FindFirstChild('TouchGui')
  local jump=tg and tg.Enabled and tg:FindFirstChild('JumpButton',true)
  if not (jump and jump.Visible and jump.AbsoluteSize.X>0) then return nil end
  return jump.AbsolutePosition.X-hud.AbsolutePosition.X,jump.AbsolutePosition.Y-hud.AbsolutePosition.Y
 end
 local function between(v,lo,hi) return lo<=hi and math.clamp(v,lo,hi) or (lo+hi)/2 end
 local function layout()
  local v=hud.AbsoluteSize;if v.X<=0 then return end
  local s=math.clamp(math.min(v.X/1280,v.Y/760),Input.TouchEnabled and .75 or .55,1.1)*T.setting('HudScale')
  leftScale.Scale=s;bottomScale.Scale=s
  goals.Visible=v.Y>=520
  local leftRight,leftBottom=14+(goals.Visible and QuestsUI.TRACKER_W or 328)*s,10+(goals.Visible and 140+QuestsUI.TRACKER_H or 118)*s
  local barLeft,barTop=v.X/2-bottom.Size.X.Offset*s/2,v.Y-8-150*s
  -- Right column: its buttons' natural height, one column if it fits, else two.
  local items={}
  for _,c in right:GetChildren() do if c:IsA('GuiObject') and c.Visible then table.insert(items,c) end end
  table.sort(items,function(a,b) return a.LayoutOrder<b.LayoutOrder end)
  local pad=rightList.Padding.Offset
  local function height(from,to) local h=-pad;for i=from,to do h+=items[i].Size.Y.Offset+pad end;return math.max(h,0) end
  local top,floor=8,v.Y-8
  local jx,jy=jumpButton()
  if jx and jx>v.X-240 then floor=math.min(floor,jy-8) end
  if barLeft+bottom.Size.X.Offset*s>v.X-12-(96*2+pad)*s then floor=math.min(floor,barTop-8) end
  local avail=math.max(floor-top,120)
  local cols,colH=1,height(1,#items)
  local rs=math.min(s,avail/math.max(colH,1))
  if rs<s*.8 and #items>2 then
   local half=math.ceil(#items/2)
   cols,colH=2,math.max(height(1,half),height(half+1,#items))
   rs=math.min(s,avail/colH)
  end
  -- Older clients without UIListLayout.Wraps keep one column, shrunk to fit.
  if not pcall(function() rightList.Wraps=cols==2 end) and cols==2 then
   cols,colH=1,height(1,#items);rs=math.min(s,avail/colH)
  end
  -- +16 slack: the wrap stays after the first half even with rounding or a button's hover grow
  -- (the next button needs 70+ px, so the slack never pulls an extra one into column one).
  right.Size=UDim2.fromOffset(cols*96+(cols-1)*pad,colH+16)
  rightScale.Scale=rs
  right.Position=UDim2.new(1,-12,0,between(v.Y*.45,top+colH*rs/2,floor-colH*rs/2))
  -- Queue banner: top centre between the profile chip and the right column, else under the chip.
  local rightLeft=v.X-12-right.Size.X.Offset*rs
  local bw=banner.Size.X.Offset
  local bs=math.min(s,2*(math.min(v.X/2-leftRight,rightLeft-v.X/2)-12)/bw)
  local by=12
  if bs<s*.8 then
   by=leftBottom+8
   bs=math.min(s,2*(rightLeft-v.X/2-12)/bw)
  end
  bannerScale.Scale=math.max(bs,.3);banner.Position=UDim2.new(.5,0,0,by)
 end
 hud:GetPropertyChangedSignal('AbsoluteSize'):Connect(layout)
 banner:GetPropertyChangedSignal('Size'):Connect(layout)
 right.ChildAdded:Connect(function() task.defer(layout) end) -- the ADMIN button arrives later
 player.PlayerGui.ChildAdded:Connect(function(c) if c.Name=='TouchGui' then task.delay(.5,layout) end end)
 player:GetAttributeChangedSignal('Setting_HudScale'):Connect(layout)
 local pendingRedraw=false
 local function profileChanged()
  refreshHud()
  if pendingRedraw then return end;pendingRedraw=true
  task.defer(function() pendingRedraw=false;if win and self.redraw then self.redraw() end end)
 end
 for _,attr in {'ProfileLoaded','ProfileGems','ProfileGemsEarned','ProfileClasses','ProfileWeapons','ProfilePity','ProfilePicks','ProfileChests','ProfileStarterPack','ProfileVIP','ProfileBundles','PaidRandomRestricted','ProfileSkills','ProfileQuests'} do player:GetAttributeChangedSignal(attr):Connect(profileChanged) end
 combat:WaitForChild('PurchaseResult').OnClientEvent:Connect(function(_,ok,message)
  if screen.Enabled and type(message)=='string' then
   if ok then T.sound('ui_purchase') end
   T.toast(screen,message,ok and C.lime or C.negative)
  end
 end)
 player:GetAttributeChangedSignal('LobbyQueue'):Connect(refreshQueue)
 root:WaitForChild('Portals').DescendantAdded:Connect(function() task.defer(refreshQueue) end)
 for _,portal in root.Portals:GetChildren() do
  for _,attr in {'QueueCount','QueueState','LaunchAt'} do portal:GetAttributeChangedSignal(attr):Connect(refreshQueue) end
  for _,attr in {'HostId','MapId','QueueState'} do portal:GetAttributeChangedSignal(attr):Connect(function() portalChanged(portal) end) end
 end
 -- Countdown text ticks locally from the server's LaunchAt.
 task.spawn(function() while screen.Parent do task.wait(.25);if player:GetAttribute('LobbyQueue') then refreshQueue() end end end)
 local function enabled()
  screen.Enabled=player:GetAttribute('LobbyPreviewActive')==true
  for _,hint in dummyHints do hint.Gui.Enabled=screen.Enabled end
  if not screen.Enabled then if win then win.Close() end;setup.Close();clearGuide();banner.Visible=false end
 end
 player:GetAttributeChangedSignal('LobbyPreviewActive'):Connect(enabled)
 player.CharacterRemoving:Connect(clearGuide)
 refreshHud();refreshQueue();enabled();task.defer(layout)
 return self
end
return L
