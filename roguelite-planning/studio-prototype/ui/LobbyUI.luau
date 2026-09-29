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
local Stats=require(combat:WaitForChild('CharacterStats'))
local ShopCatalog=require(combat:WaitForChild('ShopCatalog'))
local Chests=require(combat:WaitForChild('ChestConfig'))
local Money=require(combat:WaitForChild('MonetizationConfig'))
local RunService=game:GetService('RunService')
local Http=game:GetService('HttpService')
local WeaponIcons=require(RS:WaitForChild('WeaponInventoryUI')).Icons
local FX=require(RS:WaitForChild('StoreFX'))
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
local SkillTree=require(combat:WaitForChild('SkillTreeConfig'))
L.Maps=Rules.Maps
L.Signature=Rules.Signature
L.ClassUnlock=Rules.ClassUnlock
L.Achievements={
 {'Reach wave 10 on Pine Valley','Thrower class'},{'Win Pine Valley','Juggler class'},
 {'Defeat 1,000 enemies with Utility weapons','Handyman class'},{'Win any map holding 4 Thrower weapons','Molotov'},
 {'Win a map using only Gun weapons','Rocket Launcher'},{'Chain lightning 1,000 times','Tinfoil Antlers'},
 {'Kill 500 burning enemies',"Grandma's Oven Mitt"},{'Win with 3 or more projectile weapons','Two Straws, One Juice Box'},
 {'Defeat 3 different map bosses','Bone Crown'},{'Win Frozen Pass','Mjolnir'},{'Reach wave 30 in any Endless run','An armor set'},
}
-- Store layout. Prices and grants come from MonetizationConfig; the server validates everything.
L.Store={
 tabs={{'Daily','quests','DAILY'},{'Bundles','store','BUNDLES'},{'Chests','chest','CHESTS'},{'Emeralds','emerald','EMERALDS'}},
 classes={{'Thrower','12','ClassThrower'},{'Juggler','19','ClassJuggler'},{'Handyman','24','ClassHandyman'}},
 gemSizes={70,84,98,112},
 chestRibbons={nil,'MOST POPULAR','BEST VALUE'},
 gemRibbons={nil,'MOST POPULAR',nil,'BEST VALUE'},
}
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
 p.best=csvMap(player:GetAttribute('ProfileBestWaves'))
 p.wins=csvSet(player:GetAttribute('ProfileMapWins'))
 p.pity=csvMap(player:GetAttribute('ProfilePity'));p.picks=csvMap(player:GetAttribute('ProfilePicks'))
 p.chests=csvMap(player:GetAttribute('ProfileChests'))
 p.starter=player:GetAttribute('ProfileStarterPack')==true;p.vip=player:GetAttribute('ProfileVIP')==true
 p.restricted=player:GetAttribute('PaidRandomRestricted')==true
 p.quickOpen=player:GetAttribute('ProfileQuickOpen')==true or p.vip
 p.rerolls=player:GetAttribute('ProfileRerolls') or 0;p.banishes=player:GetAttribute('ProfileBanishes') or 0
 local ok,daily=pcall(Http.JSONDecode,Http,player:GetAttribute('ProfileDaily') or '')
 p.daily=ok and type(daily)=='table' and daily or {deals={}}
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
 local l=T.label(g,'Amount',tostring(amount),0,0,tw+4,size+6,size);l.LayoutOrder=1;l.TextWrapped=false;l.ZIndex=3
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
 local goals=T.panel(left,'Goals',0,140,300,212,'panel')
 T.icon(goals,'Icon',10,6,40,'quests')
 local goalsTitle=T.label(goals,'Title','QUESTS',54,10,236,32,22);goalsTitle.TextXAlignment=Enum.TextXAlignment.Left
 local goalRows={}
 for i=1,3 do
  local y=50+(i-1)*52
  local n=T.text(goals,'Goal'..i,'',14,y,272,20,16)
  local r=T.text(goals,'Reward'..i,'',14,y+20,272,16,13,C.gold)
  local bar=T.bar(goals,'Progress'..i,14,y+38,272,8)
  goalRows[i]={n,r,bar}
 end
 goals.Active=true
 local goalsButton=T.make('TextButton',goals,{Name='Open',Text='',BackgroundTransparency=1,Size=UDim2.fromScale(1,1),ZIndex=3})
 goalsButton.Activated:Connect(function() open('Quests','Achievements') end)
 -- Right edge: store, rewards, settings.
 local right,rightScale=scaled('Right',Vector2.new(1,.5),UDim2.new(1,-12,.45,0),Vector2.new(96,592))
 T.make('UIListLayout',right,{Padding=UDim.new(0,10),HorizontalAlignment=Enum.HorizontalAlignment.Center,SortOrder=Enum.SortOrder.LayoutOrder})
 local store=T.iconButton(right,'Store','store','STORE',78,function() open('Store') end);store.LayoutOrder=1
 local skills=T.iconButton(right,'Skills',SkillTree.Icons.Hud,'SKILLS',78,function() open('Skills') end);skills.LayoutOrder=2
 local awards=T.iconButton(right,'Awards','achievements','REWARDS',78,function() open('Quests','Achievements') end);awards.LayoutOrder=3
 local settings=T.iconButton(right,'Settings','settings','SETTINGS',64,function() open('Settings') end);settings.LayoutOrder=4
 -- LayoutOrder 6 (after ATTACKS) is the developers' ADMIN button, added by AdminPanel.client (ADMIN_PANEL.md).
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
  for i=1,3 do
   local a=L.Achievements[i];local row=goalRows[i]
   row[1].Text=a[1];row[2].Text='Unlocks '..a[2];T.setBar(row[3],0)
  end
  goalsTitle.Text='QUESTS'
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

 builders.Settings=function() return T.settingsWindow(screen) end

 builders.Profile=function()
  local w=T.window(screen,'ProfileWindow','Profile',720,470);local b=w.Body;local W=684
  local card=T.panel(b,'Card',0,10,230,392,'inset')
  local portrait=T.make('ImageLabel',card,{Name='Headshot',BackgroundTransparency=1,Position=UDim2.fromOffset(35,20),Size=UDim2.fromOffset(160,160),Image=''});T.headshot(portrait,player.UserId)
  T.label(card,'Name',player.DisplayName,10,188,210,34,24)
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

 builders.Armory=function(tab) return armory.Open(tab) end

 builders.Quests=function(tab)
  local w=T.window(screen,'QuestsWindow','Quests',860,560);local b=w.Body;local W=824
  self.selection.questTab=tab or self.selection.questTab or 'Daily'
  local draw
  draw=function()
   for _,c in b:GetChildren() do c:Destroy() end
   local active=self.selection.questTab
   T.tabs(b,0,4,W,46,{'Daily','Weekly','Achievements'},active,function(id) self.selection.questTab=id;draw() end)
   if active~='Achievements' then
    local empty=T.panel(b,'Empty',0,64,W,220,'panel')
    T.icon(empty,'Icon',30,40,140,active=='Daily' and 'quests' or 'achievements')
    T.label(empty,'Title',active..' quests',190,44,W-220,40,30).TextXAlignment=Enum.TextXAlignment.Left
    T.text(empty,'Body',(active=='Daily' and 'Three rotating goals every day' or 'Bigger goals every week')..' that pay emeralds. Missing a day never loses anything permanent.',190,90,W-220,50,18,C.muted)
    T.chip(empty,'Status','COMING SOON',190,150,C.well,C.gold)
    return
   end
   local list=T.scroll(b,'List',0,60,W,440)
   for i,a in L.Achievements do
    local y=(i-1)*84
    local row=T.panel(list,'Achievement'..i,2,y,W-24,76,'panel')
    T.icon(row,'Icon',12,10,56,'achievements')
    local n=T.label(row,'Name',a[1],80,8,W-360,28,20);n.TextXAlignment=Enum.TextXAlignment.Left
    local fill=T.bar(row,'Progress',80,44,W-360,14);T.setBar(fill,0)
    T.text(row,'Reward','Unlocks',W-270,10,220,18,13,C.muted)
    T.text(row,'RewardName',a[2],W-270,28,220,26,19,C.gold)
   end
   list.CanvasSize=UDim2.fromOffset(0,#L.Achievements*84)
   preview(b,W-340,-24,profile)
  end
  draw()
  return w
 end

 builders.Store=function(focus)
  local w=T.window(screen,'StoreWindow','Store',1100,640,nil,{large=true});local b=w.Body;local W=1064
  self.selection.storeTab=focus or self.selection.storeTab or 'Daily'
  local list
  local function buy(key) combat.PurchaseRequest:FireServer(key) end
  local function act(action,a)
   local r=combat.ProfileAction:InvokeServer(action,a)
   T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
  end
  local draw
  local gold=C.gold
  -- Robux price button (pulses when `pulse`), or OWNED.
  local function priceButton(parent,name,x,yy,bw,bh,key,owned,pulse)
   local item=Money.Products[key] or Money.Passes[key]
   local pb=T.button(parent,name,owned and 'OWNED' or ('R$ '..item.robux),x,yy,bw,bh,function() buy(key) end,owned)
   pb.Caption.TextSize=math.min(32,bh-16)
   if owned then pb.Interactable=false elseif pulse then FX.pulse(pb,.05) end
   return pb
  end
  -- Contents tile inside a bundle card.
  local function tile(parent,name,x,yy,size,asset,text,color)
   local t=T.panel(parent,name,x,yy,size,size,'inset')
   local ic=T.icon(t,'Icon',size*.18,size*.06,size*.64,asset)
   local l=T.text(t,'Label',text,9,size*.66,size-18,size*.28,15,color);l.TextXAlignment=Enum.TextXAlignment.Center
   FX.popIcon(t,ic)
   return t
  end
  -- Card with rays + glow behind a big icon that grows on hover.
  local function art(card,asset,cx,cy,size,color,raySize)
   -- Rays are clipped to the card's inner area so they never spill past its border.
   local clip=card:FindFirstChild('RayClip') or T.make('Frame',card,{Name='RayClip',BackgroundTransparency=1,ClipsDescendants=true,Position=UDim2.fromOffset(10,10),Size=UDim2.new(1,-20,1,-20)})
   local _,rays=FX.burst(clip,cx-10,cy-10,raySize or size*1.7,color)
   local ic=T.icon(card,'Art',cx-size/2,cy-size/2,size,asset)
   FX.popIcon(card,ic,rays)
   return ic
  end
  -- Wide hero card: title/sub/tiles on the left, big art + price on the right.
  local function hero(name,y,h,tier,color,title,sub,tiles,asset,key,owned,opts)
   opts=opts or {}
   local SW=W-14;local cw=SW-4
   local card=T.panel(list,name,2,y,cw,h,'panel');if tier then T.setTier(card,tier) end
   if opts.cornerColor then card.RarityCorners.ImageColor3=opts.cornerColor end
   art(card,asset,cw-150,h/2-36,opts.artSize or 150,color,opts.raySize)
   local t=T.label(card,'Title',title,26,16,cw-340,50,opts.titleSize or 42,opts.titleColor);t.TextXAlignment=Enum.TextXAlignment.Left
   T.text(card,'Sub',sub,28,66,cw-340,24,18,C.cream)
   local size=math.min(96,h-118,math.floor((cw-340-26-(#tiles-1)*10)/math.max(#tiles,1)))
   for i,it in tiles do tile(card,'Item'..i,26+(i-1)*(size+10),h-size-18,size,it[1],it[2],it[3]) end
   priceButton(card,'Buy',cw-268,h-78,240,62,key,owned,opts.pulse)
   if opts.ribbon then FX.ribbon(card,opts.ribbon,opts.ribbonWidth,opts.ribbonColor) end
   if opts.shine then FX.shine(card) end
   FX.lift(card)
   return card
  end
  local function section(title,sub,y)
   local t=T.label(list,'Section_'..title,title,4,y,400,36,30);t.TextXAlignment=Enum.TextXAlignment.Left
   local tw=game:GetService('TextService'):GetTextSize(title,30,T.Font,Vector2.new(1000,100)).X
   if sub then return T.text(list,'Sub_'..title,sub,tw+18,y+9,W-tw-40,22,17,C.cream) end
  end
  local tabs={}
  function tabs.Daily(SW)
   local y=4
   local timer=section('Daily Deals','',y);y+=58
   local function tick()
    local sec=Money.secondsToReset()
    timer.Text=string.format('New deals in %02d:%02d:%02d',sec//3600,sec%3600//60,sec%60)
   end
   tick()
   task.spawn(function() while timer.Parent do task.wait(1);if timer.Parent then tick() end end end)
   local deals=profile.daily.deals or {}
   local n=math.max(1,#deals);local cw=(SW-(n-1)*12)/n;local ch=292
   for i,deal in deals do
    local x=(i-1)*(cw+12)
    local free=deal.kind=='Emeralds'
    local rarity=deal.rarity or 'Common'
    local card=T.panel(list,'Deal'..i,x,y,cw,ch,'panel');T.setTier(card,free and 4 or 2)
    -- Weapon deals wear their rarity's colour (ChestConfig.RarityColor), like chest reveal cards.
    local color=free and C.emerald or Chests.RarityColor[rarity]
    if not free and card:FindFirstChild('RarityCorners') then card.RarityCorners.ImageColor3=color end
    art(card,free and 'emerald' or WeaponIcons[deal.id],cw/2,104,92,color,150)
    local amt=T.label(card,'Amount',(free and '+' or '×')..deal.amount,0,22,cw,34,32,free and C.emerald or C.gold);amt.TextXAlignment=Enum.TextXAlignment.Center;amt.ZIndex=3
    local name=free and 'Emeralds' or Weapons.ById[deal.id].name
    local nm=T.text(card,'Name',name,10,156,cw-20,22,18);nm.TextXAlignment=Enum.TextXAlignment.Center
    if deal.kind=='Weapon' then
     local rl=T.text(card,'Rarity',string.upper(rarity)..'  ·  '..(deal.each or deal.price)..' each',10,180,cw-20,20,15,color);rl.TextXAlignment=Enum.TextXAlignment.Center
     local rec=profile.weapons[deal.id]
     if rec then T.upgradeBar(card,'Bar',14,204,cw-28,18,rec.have,L.need(rec)) else local l=T.text(card,'New','NEW WEAPON',14,202,cw-28,20,15,C.gold);l.TextXAlignment=Enum.TextXAlignment.Center end
    end
    local label=deal.bought and 'CLAIMED' or deal.currency=='Free' and 'FREE' or ''
    local pb=T.button(card,'Buy',label,12,ch-64,cw-24,52,function() act('BuyDeal',i) end,deal.bought)
    pb.Caption.TextSize=24
    if deal.bought then pb.Interactable=false
    elseif deal.currency=='Emeralds' then cost(pb,deal.price,'emerald',22) end
    if deal.currency=='Free' and not deal.bought then FX.ribbon(card,'FREE!',110,gold);FX.pulse(pb,.06) end
    FX.lift(card)
   end
   y+=ch+30
   if profile.vip then
    local claimed=profile.daily.vipClaimed
    local row=T.panel(list,'VipDaily',2,y,SW-4,130,'panel');T.setTier(row,3)
    art(row,'chest',80,65,90,T.Tier[3],160)
    local t=T.label(row,'Title','VIP DAILY CHEST',160,22,500,40,34);t.TextXAlignment=Enum.TextXAlignment.Left
    T.text(row,'Sub','A free '..Chests.ById[Money.VIPDailyChest].name..', every single day.',162,66,500,24,18,C.cream)
    local cb=T.button(row,'Claim',claimed and 'CLAIMED' or 'CLAIM',SW-4-242,34,220,62,function() act('ClaimVipChest') end,claimed)
    cb.Caption.TextSize=28;cb.Interactable=not claimed;if not claimed then FX.pulse(cb,.06) end
   else
    local row=T.panel(list,'VipPromo',2,y,SW-4,130,'panel');T.setTier(row,3)
    art(row,'chest',80,65,90,T.Tier[3],160)
    local t=T.label(row,'Title','FREE '..string.upper(Chests.ById[Money.VIPDailyChest].name)..' EVERY DAY',160,20,SW-440,40,32);t.TextXAlignment=Enum.TextXAlignment.Left
    T.text(row,'Sub','Plus +25% emeralds from every run and open ×10 chests.',162,64,SW-440,24,18,C.cream)
    local go=T.button(row,'Go','GET VIP',SW-4-242,34,220,62,function() self.selection.storeTab='Bundles';draw() end)
    go.Caption.TextSize=28;FX.pulse(go,.05);FX.shine(row)
   end
   return y+146
  end
  function tabs.Bundles(SW)
   local y=22
   local sp=Money.Products.StarterPack
   hero('Starter',y,270,4,gold,'STARTER PACK','One time only · the best deal in the game.',
    {{'emerald',sp.emeralds..'',C.emerald},{Chests.ById.Legendary.icon,'Legendary Chest'},{'quests',sp.rerolls..' Rerolls'}},'chest','StarterPack',profile.starter,
    {cornerColor=gold,titleColor=gold,titleSize=46,pulse=true,shine=true,ribbon='BEST VALUE',ribbonColor=gold,artSize=170})
   y+=296
   local ab=Money.Products.ArsenalBundle
   local tiles={}
   for _,cl in Stats.ClassOrder do table.insert(tiles,{WeaponIcons[L.Signature[cl]],'+'..ab.signatureUpgrades,C.lime}) end
   table.insert(tiles,{'emerald',ab.emeralds..'',C.emerald})
   hero('Arsenal',y,250,2,T.Tier[2],'ARSENAL BUNDLE','+'..ab.signatureUpgrades..' upgrades to every class starter weapon.',tiles,WeaponIcons['00'],'ArsenalBundle',false,{pulse=true,shine=true})
   y+=272
   hero('VIP',y,250,3,T.Tier[3],'VIP PASS','Permanent. Yours on every visit.',
    {{'emerald','+25% Emeralds'},{'chest','Daily Chest'},{'store','Open ×10'},{'profile','VIP Tag'}},'profile','VIP',profile.vip,{pulse=true,shine=true,ribbon='VIP',ribbonWidth=120})
   y+=272
   hero('QuickOpen',y,220,nil,C.lime,'QUICK OPEN','Open 10 chests in one click.',
    {{'chest','×10'}},'chest','QuickOpen',profile.quickOpen,{artSize=130})
   y+=244
   if not profile.restricted then
    local half=(SW-16)/2
    for i,spec in {{'Rerolls','Reroll level-up and shop choices.',Money.RerollPacks,'quests',profile.rerolls,2},{'Banishes','Remove unwanted level-ups for the run.',Money.BanishPacks,'armory',profile.banishes,4}} do
     local x=(i-1)*(half+16)
     local card=T.panel(list,spec[1],x,y,half,290,'panel');T.setTier(card,spec[6])
     art(card,spec[4],80,86,100,T.Tier[spec[6]],170)
     local t=T.label(card,'Title',string.upper(spec[1]),150,24,half-170,44,40);t.TextXAlignment=Enum.TextXAlignment.Left
     T.text(card,'Sub',spec[2],152,72,half-170,44,17,C.cream)
     T.text(card,'Have','You have '..spec[5],152,118,half-170,20,16,C.muted)
     local key='pack'..spec[1];self.selection[key]=self.selection[key] or 1
     local idx=self.selection[key];local packKey=spec[3][idx];local pack=Money.Products[packKey]
     local sw=(half-36-16)/3
     T.button(card,'Less','-',18,158,sw,52,function() self.selection[key]=math.max(1,idx-1);draw() end,true).Caption.TextSize=32
     local amt=T.panel(card,'Qty',26+sw,158,sw,52,'inset');T.label(amt,'Text','×'..(pack.rerolls or pack.banishes),0,0,sw,52,28)
     T.button(card,'More','+',34+2*sw,158,sw,52,function() self.selection[key]=math.min(#spec[3],idx+1);draw() end,true).Caption.TextSize=32
     priceButton(card,'Buy',18,222,half-36,56,packKey,false,true)
     FX.lift(card)
    end
    y+=310
   end
   section('Classes','Play them right now.',y);y+=48
   local tw=(SW-2*14)/3
   for i,cl in L.Store.classes do
    local x=(i-1)*(tw+14);local owned=profile.classes[cl[1]]==true
    local t=T.rarityPanel(list,'Class_'..cl[1],x,y,tw,290,2)
    art(t,WeaponIcons[cl[2]],tw/2,86,120,T.Tier[2],190)
    local n=T.label(t,'Name',cl[1],10,160,tw-20,36,32);n.TextXAlignment=Enum.TextXAlignment.Center
    local d=T.text(t,'Desc',Stats.Classes[cl[1]].description,16,196,tw-32,36,15,C.cream);d.TextXAlignment=Enum.TextXAlignment.Center
    local half=(tw-32-10)/2
    priceButton(t,'Buy',16,238,half,44,cl[3],owned)
    local eb=T.button(t,'BuyEmeralds','',26+half,238,half,44,function()
     local r=combat.ProfileAction:InvokeServer('BuyClass',cl[1]);T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
    end,true)
    eb.Caption.Visible=false;if owned then eb.Interactable=false end
    cost(eb,owned and 'OWNED' or Money.ClassEmeraldPrice,not owned and 'emerald' or nil,19)
    FX.lift(t)
   end
   return y+304
  end
  function tabs.Chests(SW)
   local y=4
   if profile.restricted then
    T.text(list,'Restricted','Chest packs are not available in your region. Open chests with emeralds earned in runs in the Chests menu.',4,8,SW-8,50,18,C.muted)
    return 70
   end
   section('Legendary Chests',Chests.ById.Legendary.copies..' weapons and a guaranteed Legendary in every chest.',y)
   local odds=T.button(list,'Odds','SEE ODDS',SW-186,y,182,40,function() self.selection.chest='Legendary';open('Chests','Legendary') end,true);odds.Caption.TextSize=18
   y+=66
   local cw=(SW-2*14)/3;local base=Money.Products[Money.ChestPacks[1]]
   for i,key in Money.ChestPacks do
    local pack=Money.Products[key];local nChests=pack.chests.Legendary
    local card=T.panel(list,key,(i-1)*(cw+14),y,cw,360,'panel');T.setTier(card,i+1)
    art(card,Chests.ById.Legendary.icon,cw/2,168,120+i*14,T.Tier[i+1],250)
    local t=T.label(card,'Count','×'..nChests,0,26,cw,54,52,C.gold);t.TextXAlignment=Enum.TextXAlignment.Center;t.ZIndex=3
    local n=T.text(card,'Name',nChests==1 and 'LEGENDARY CHEST' or 'LEGENDARY CHESTS',10,80,cw-20,24,20);n.TextXAlignment=Enum.TextXAlignment.Center;n.ZIndex=3
    local each=math.floor(pack.robux/nChests+.5)
    local save=nChests>1 and math.floor((1-each/base.robux)*100+.5) or 0
    local d=T.text(card,'Drops',(nChests*Chests.ById.Legendary.copies)..' weapons'..(save>0 and ('  ·  SAVE '..save..'%') or ''),10,252,cw-20,22,17,save>0 and C.lime or C.cream);d.TextXAlignment=Enum.TextXAlignment.Center
    priceButton(card,'Buy',16,288,cw-32,58,key,false,i==3)
    if L.Store.chestRibbons[i] then FX.ribbon(card,L.Store.chestRibbons[i],180,i==3 and gold or nil) end
    if i==3 then FX.shine(card) end
    FX.lift(card)
   end
   y+=388
   local mb=Money.Products.MegaBundle
   hero('Mega',y,260,4,gold,'MEGA CHEST BUNDLE','The biggest pile of chests in the game.',
    {{Chests.ById.Legendary.icon,'×'..mb.chests.Legendary..' Legendary'},{'emerald',mb.emeralds..'',C.emerald},{'quests',mb.rerolls..' Rerolls'},{'armory',mb.banishes..' Banishes'}},'chest','MegaBundle',false,
    {cornerColor=gold,titleColor=gold,pulse=true,shine=true,ribbon='INSANE DEAL',ribbonColor=gold,artSize=170})
   y+=284
   local owned=profile.chests.Legendary or 0
   if owned>0 then
    local ob=T.button(list,'OpenOwned','OPEN YOUR '..owned..' LEGENDARY CHEST'..(owned>1 and 'S' or ''),2,y,SW-4,60,function() self.selection.chest='Legendary';open('Chests','Legendary') end)
    ob.Caption.TextSize=26;FX.pulse(ob,.03);y+=72
   end
   return y
  end
  function tabs.Emeralds(SW)
   local y=4
   section('Emeralds','Open chests, buy skills and unlock classes. You also earn them in every run.',y);y+=62
   local gw=(SW-3*14)/4
   for i,key in Money.EmeraldPacks do
    local pack=Money.Products[key];local x=(i-1)*(gw+14)
    local card=T.panel(list,'Emeralds_'..pack.name,x,y,gw,320,'panel');if i>1 then T.setTier(card,i) end
    art(card,'emerald',gw/2,112,L.Store.gemSizes[i],C.emerald,190)
    local amt=T.label(card,'Amount',tostring(pack.emeralds),10,184,gw-20,40,38,C.emerald);amt.TextXAlignment=Enum.TextXAlignment.Center
    local bonus=Money.bonusPercent(key)
    local sub=T.text(card,'Bonus',bonus>0 and ('+'..bonus..'% MORE') or pack.name,10,224,gw-20,22,18,bonus>0 and C.lime or C.cream);sub.TextXAlignment=Enum.TextXAlignment.Center
    priceButton(card,'Buy',14,254,gw-28,54,key,false,i==4)
    if L.Store.gemRibbons[i] then FX.ribbon(card,L.Store.gemRibbons[i],170,i==4 and gold or nil) end
    if i==4 then FX.shine(card) end
    FX.lift(card)
   end
   y+=346
   section('Codes','Enter a code for free rewards.',y);y+=50
   local row=T.panel(list,'Codes',2,y,SW-4,84,'panel')
   local field=T.panel(row,'Field',16,14,SW-4-264,56,'inset')
   local box=T.make('TextBox',field,{Name='Input',BackgroundTransparency=1,Position=UDim2.fromOffset(16,0),Size=UDim2.new(1,-32,1,0),Font=T.Font,TextSize=24,TextColor3=C.white,PlaceholderText='Enter code',PlaceholderColor3=C.dim,Text='',ClearTextOnFocus=false,TextXAlignment=Enum.TextXAlignment.Left})
   T.button(row,'Claim','CLAIM',SW-4-234,14,218,56,function() if box.Text~='' then act('Redeem',box.Text);box.Text='' end end).Caption.TextSize=28
   return y+100
  end
  draw=function()
   local keep=list and list.Parent and self.selection.storeTabDrawn==self.selection.storeTab and list.CanvasPosition
   for _,c in b:GetChildren() do c:Destroy() end
   profile=L.profile(player)
   local active=self.selection.storeTab
   -- Emerald pill on the right; tabs share the remaining width equally (never overlap).
   local pillW,gap=140,8
   local pillsX=W-pillW
   local tw=math.floor((pillsX-16-3*gap)/4)
   for i,t in L.Store.tabs do
    local tb=T.button(b,'Tab_'..t[1],'',(i-1)*(tw+gap),0,tw,64,function() self.selection.storeTab=t[1];draw() end,t[1]~=active)
    tb.Caption.Visible=false
    local ic=T.icon(tb,'Icon',10,10,44,t[2])
    local l=T.label(tb,'Label',t[3],58,0,tw-68,64,18);l.TextXAlignment=Enum.TextXAlignment.Left;l.TextWrapped=false;l.TextScaled=true
    T.make('UITextSizeConstraint',l,{MinTextSize=10,MaxTextSize=18})
    FX.popIcon(tb,ic)
   end
   local function pill(name,x,asset,value,color,target)
    local pl=T.panel(b,name,x,8,pillW,48,'inset');T.icon(pl,'Icon',8,6,36,asset)
    local v=T.label(pl,'Value',fmt(value),48,4,52,40,22,color);v.TextXAlignment=Enum.TextXAlignment.Left
    T.button(pl,'Plus','+',pillW-42,6,36,36,function() self.selection.storeTab=target;draw() end).Caption.TextSize=26
   end
   pill('EmeraldsPill',pillsX,'emerald',profile.gems,C.emerald,'Emeralds')
   list=T.scroll(b,'Offers',0,78,W,500)
   local h=tabs[active](W-14)
   list.CanvasSize=UDim2.fromOffset(0,h)
   if keep then list.CanvasPosition=keep end
   self.selection.storeTabDrawn=active
  end
  -- Deals roll over at UTC midnight; ask the server for today's set if ours is stale.
  if profile.daily.deals and (profile.daily.resetIn or 0)>0 and Money.secondsToReset()>(profile.daily.resetIn or 0) then
   task.spawn(function() combat.ProfileAction:InvokeServer('Refresh') end)
  end
  draw();self.redraw=draw
  return w
 end

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
  if input.KeyCode==Enum.KeyCode.Escape or input.KeyCode==Enum.KeyCode.ButtonB then if win then win.Close() end;return end
  if processed or Input:GetFocusedTextBox() then return end
  local keys={[Enum.KeyCode.L]='Loadout',[Enum.KeyCode.C]='Chests',[Enum.KeyCode.J]='Quests',[Enum.KeyCode.K]='Skills'}
  local route=keys[input.KeyCode];if route then if self.current==route and win then win.Close() else open(route) end end
 end)
 -- Layout: scale everything to the viewport; bottom bar stays above the touch jump area.
 local function layout()
  local v=screen.AbsoluteSize;if v.X<=0 then return end
  local s=math.clamp(math.min(v.X/1280,v.Y/760),.55,1.1)*T.setting('HudScale')
  leftScale.Scale=s;rightScale.Scale=s;bottomScale.Scale=s;bannerScale.Scale=s
  goals.Visible=v.Y>=520
 end
 screen:GetPropertyChangedSignal('AbsoluteSize'):Connect(layout)
 player:GetAttributeChangedSignal('Setting_HudScale'):Connect(layout)
 local pendingRedraw=false
 local function profileChanged()
  refreshHud()
  if pendingRedraw then return end;pendingRedraw=true
  task.defer(function() pendingRedraw=false;if win and self.redraw then self.redraw() end end)
 end
 for _,attr in {'ProfileLoaded','ProfileGems','ProfileGemsEarned','ProfileClasses','ProfileWeapons','ProfilePity','ProfilePicks','ProfileChests','ProfileStarterPack','ProfileVIP','PaidRandomRestricted','ProfileSkills'} do player:GetAttributeChangedSignal(attr):Connect(profileChanged) end
 combat:WaitForChild('PurchaseResult').OnClientEvent:Connect(function(_,ok,message)
  if screen.Enabled and type(message)=='string' then T.toast(screen,message,ok and C.lime or C.negative) end
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
  if not screen.Enabled then if win then win.Close() end;setup.Close();clearGuide();banner.Visible=false end
 end
 player:GetAttributeChangedSignal('LobbyPreviewActive'):Connect(enabled)
 player.CharacterRemoving:Connect(clearGuide)
 refreshHud();refreshQueue();enabled();task.defer(layout)
 return self
end
return L
