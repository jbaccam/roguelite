-- The tutorial guide, client side (plans/2026-10-03-tutorial-design.md). Five times a second it
-- decides what Eggbert (the egg merchant) says and what the arrow points at, from what is on
-- screen and the replicated state, and TutorialGuideUI draws it:
--   the run part: RogueliteCombat.TutorialRun with this player in the run, then its results screen;
--   the lobby part: ProfileTutorial Chests -> Armory -> Equip -> Offer -> Play, in the lobby.
-- Lobby steps are saved on the server (ProfileAction 'TutorialStep', forward only) once the thing
-- they ask for is done, so a rejoin carries on where it stopped. The arrow suggests one thing, but
-- any pick counts: every step moves on whatever the player chooses, and skips itself when there
-- is nothing left to choose (user, 2026-10-03: picking something else got the guide stuck). While the arrow points at a lobby
-- bottom button, the other bottom buttons are dimmed and can't be clicked.
-- Presentation and requests only: every reward, step and purchase is checked on the server.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local Http=game:GetService('HttpService')
local Tags=game:GetService('CollectionService')
local GuiService=game:GetService('GuiService')
local player=Players.LocalPlayer
local combat=RS:WaitForChild('RogueliteCombat')
local Config=require(combat:WaitForChild('TutorialConfig'))
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local Armor=require(combat:WaitForChild('ArmorCatalog'))
local Chests=require(combat:WaitForChild('ChestConfig'))
local GuideUI=require(RS:WaitForChild('TutorialGuideUI'))
local pg=player:WaitForChild('PlayerGui')
local guide
local function ui() if not guide then guide=GuideUI.new(player,Config.Asset,Config.GuideName) end;return guide end

-- What's on screen ------------------------------------------------------------------------------
local function screen(name) local g=pg:FindFirstChild(name);return g and g:IsA('ScreenGui') and g.Enabled and g or nil end
local function shown(obj)
 if not obj or not obj.Parent or not obj:IsA('GuiObject') then return false end
 local layer=obj:FindFirstAncestorWhichIsA('LayerCollector');if not layer then return false end
 local p=obj
 while p and p~=layer do if p:IsA('GuiObject') and not p.Visible then return false end;p=p.Parent end
 return obj.AbsoluteSize.X>1
end
-- The first shown descendant of root named `name` (a button that can be clicked, when `button`).
local function find(root,name,button)
 if not root then return nil end
 for _,d in root:GetDescendants() do
  if d.Name==name and (not button or d:IsA('GuiButton') and d.Interactable) and shown(d) then return d end
 end
 return nil
end
-- Whether a details panel's header (ArmoryUI: the Name label) reads `text`.
local function titled(panel,text)
 local name=panel and panel:FindFirstChild('Name')
 return name~=nil and name:IsA('TextLabel') and name.Text==text
end
local function myState() local f=combat:FindFirstChild('PlayerStates');return f and f:FindFirstChild(tostring(player.UserId)) end
local function snapshot()
 local s=myState();local ok,d=pcall(Http.JSONDecode,Http,s and s:GetAttribute('ShopSnapshot') or '')
 return ok and type(d)=='table' and d or nil
end
local function count(attr,key)
 for k,v in string.gmatch(player:GetAttribute(attr) or '','([^,:]+):(%d+)') do if k==key then return tonumber(v) end end
 return 0
end
local function weaponTier(id)
 for k,tier in string.gmatch(player:GetAttribute('ProfileWeapons') or '','([^,:]+):(%d+):%d+') do if k==id then return tonumber(tier) end end
 return 0
end
-- Every owned weapon, armor piece and pet: id -> tier.
local function tierMap()
 local m={}
 for _,attr in {'ProfileWeapons','ProfileArmor','ProfilePets'} do
  for id,tier in string.gmatch(player:GetAttribute(attr) or '','([^,:]+):(%d+):%d+') do m[id]=tonumber(tier) end
 end
 return m
end
-- Something owned is a tier above `base` (a tierMap); a new item at Tier I isn't an upgrade.
local function upgradedSince(base)
 for id,tier in tierMap() do if tier>(base[id] or 1) then return true end end
 return false
end
-- Enough copies AND emeralds for the next tier (ProfileService.upgrade's rule), for one item or
-- (id nil) anything owned.
local function canUpgrade(id)
 local gems=player:GetAttribute('ProfileGems') or 0
 for _,attr in {'ProfileWeapons','ProfileArmor','ProfilePets'} do
  for k,tier,have in string.gmatch(player:GetAttribute(attr) or '','([^,:]+):(%d+):(%d+)') do
   tier,have=tonumber(tier),tonumber(have)
   if (id==nil or k==id) and tier<4 then
    local need,cost=Chests.upgradeCost(k,tier),Chests.upgradeEmeralds(k,tier)
    if need and have>=need and gems>=(cost or 0) then return true end
   end
  end
 end
 return false
end
local function wearing(slot)
 for k,set in string.gmatch(player:GetAttribute('ProfileWearing') or '','([^,:]+):([^,:]+)') do if k==slot then return set end end
 return nil
end
local function lobbyButton(name)
 local hud=screen('RogueliteLobbyHUD');local bottom=hud and hud:FindFirstChild('Bottom',true)
 local b=bottom and bottom:FindFirstChild(name)
 return b and shown(b) and b or nil
end

-- Things the run part reacts to ------------------------------------------------------------------
local seenRunAt=nil
local redUntil,redShown=0,0
local runId -- RogueliteRunState.RunId these belong to
-- Crystals (user, 2026-10-03: the tutorial never talked about collecting them). Wave 1: once one
-- is on the ground the arrow points at it ("walk over them"); after the first pickup it points at
-- the crystal counter for a few seconds ("XP and money").
local crystal,pickedAt -- the crystal pointed at; when the first pickup was seen
local function nearestCrystal()
 local drops=workspace:FindFirstChild('RogueliteShardDrops')
 local root=player.Character and player.Character:FindFirstChild('HumanoidRootPart')
 if not drops or not root then return nil end
 if crystal and crystal.Parent==drops and not crystal:GetAttribute('MagnetUserId') then return crystal end
 local best,bestDistance
 for _,m in drops:GetChildren() do
  local origin=m:GetAttribute('Origin')
  if m:IsA('Model') and typeof(origin)=='Vector3' and not m:GetAttribute('MagnetUserId') then
   local d=(origin-root.Position).Magnitude
   if not bestDistance or d<bestDistance then best,bestDistance=m,d end
  end
 end
 crystal=best
 return best
end
-- During a fight the box keeps to the screen's corners and sides, clear of the player and the boss.
-- The bosses: the old Hammer (tag HammerBoss) and map bosses, the rebuilt Hammer Brute included
-- (MapBoss). Kept up to date by the tag signals below, not looked up every frame.
local bossList={}
local function fightContext() return {edges=true,avoid=bossList} end
-- The boss's first two attacks after his entrance: "Red circle = move!"
local function watchBoss(npc)
 npc:GetAttributeChangedSignal('BossSerial'):Connect(function()
  if combat:GetAttribute('TutorialRun')~=true or redShown>=2 then return end
  if workspace:GetServerTimeNow()<(npc:GetAttribute('BossIntroUntil') or 0) then return end
  redShown+=1;redUntil=os.clock()+3.5
 end)
end
Tags:GetInstanceAddedSignal('HammerBoss'):Connect(watchBoss)
for _,npc in Tags:GetTagged('HammerBoss') do watchBoss(npc) end
local function listBosses() bossList=Tags:GetTagged('HammerBoss');for _,npc in Tags:GetTagged('MapBoss') do table.insert(bossList,npc) end end
for _,tag in {'HammerBoss','MapBoss'} do Tags:GetInstanceAddedSignal(tag):Connect(listBosses);Tags:GetInstanceRemovedSignal(tag):Connect(listBosses) end
listBosses()
Tags:GetInstanceAddedSignal('MapBoss'):Connect(watchBoss)
for _,npc in Tags:GetTagged('MapBoss') do watchBoss(npc) end

-- The run part: {line=Lines id, target=GuiObject or nil}, {hide=true}, or nil when not in it.
local function runStep()
 local result=player:GetAttribute('RunResult')
 if type(result)=='string' and string.find(result,'"tutorial"',1,true) then
  return {line='Loot',target=find(screen('RunResults'),'BackToLobby',true)}
 end
 if combat:GetAttribute('TutorialRun')~=true or not player:GetAttribute('RunMember') then return nil end
 local run=RS:FindFirstChild('RogueliteRunState');if not run then return nil end
 -- A new run (the admin panel's Start tutorial again): its lines start over.
 if run:GetAttribute('RunId')~=runId then runId=run:GetAttribute('RunId');seenRunAt=nil;crystal=nil;pickedAt=nil;redShown=0;redUntil=0 end
 -- The loading screen still covers the arena: the welcome waits for it (it used to type out and
 -- time out underneath, 2026-10-03).
 if pg:FindFirstChild('LoadingScreen') then return {hide=true} end
 seenRunAt=seenRunAt or os.clock()
 -- Won: nothing until the results screen (user, 2026-10-03: no VICTORY banner; it came from the
 -- reference game, and the results screen is the win screen).
 if run:GetAttribute('TutorialWon') then return {hide=true} end
 if screen('BossIntro') then return {hide=true} end -- the boss entrance has the screen
 local phase,wave=run:GetAttribute('Phase'),run:GetAttribute('Wave') or 1
 if phase=='Combat' then
  local fight=fightContext()
  if wave==1 then
   if os.clock()-seenRunAt<5 then return {line='Welcome',ctx=fight} end
   local st=myState()
   if not pickedAt and (st and st:GetAttribute('Shards') or 0)>Config.START_SHARDS then pickedAt=os.clock() end
   if pickedAt then
    if os.clock()-pickedAt<7 then return {line='CrystalsUse',target=find(screen('RogueliteHUD'),'Shards'),ctx=fight} end
    return {line='Bat',ctx=fight}
   end
   local c=nearestCrystal()
   if c then return {line='Crystals',target=c,ctx=fight} end
   return {line='Bat',ctx=fight}
  end
  if wave<Config.BOSS_WAVE then return {line='Survive',ctx=fight} end
  return {line=os.clock()<redUntil and 'RedCircle' or 'Boss',ctx=fight}
 end
 if phase~='Shop' then return nil end
 if wave==1 then return {line='Welcome'} end -- waiting for wave 1
 local st=myState()
 local pending=st and st:GetAttribute('PendingLevelUps') or 0
 if pending>0 then
  -- By the count, not the wave: with worth-1 crystals each shop has one card (2026-10-03).
  local card=find(screen('LevelUpOffers'),'Offer1')
  return {line=pending>=2 and 'LevelUp2' or 'LevelUp',target=card and find(card,'Choose',true)}
 end
 local shop
 for _,g in pg:GetChildren() do if g:IsA('ScreenGui') and g.Enabled then shop=find(g,'ShopLayout');if shop then break end end end
 local offers=Config.Offers[wave]
 if offers then
  -- The arrow suggests the guided offer (the Glock) while it can be bought; any buy counts.
  -- After one, GO; nothing bought and the Glock gone or too dear, buy-then-GO.
  local snap=snapshot();local list=snap and snap.offers or {}
  for _,o in list do if o.sold then return {line='ShopGo',target=shop and find(shop,'StartWave',true)} end end
  for i,o in list do
   if o.id==offers[1] and (snap.shards or 0)>=(o.price or math.huge) then
    local card=shop and find(shop,'Offer'..i)
    return {line='Shop',target=card and find(card,'Buy',true)}
   end
  end
  return {line='Shop2',target=shop and find(shop,'StartWave',true)}
 end
 return {line='Shop2',target=shop and find(shop,'StartWave',true)}
end

-- The lobby part -------------------------------------------------------------------------------
local asked={} -- step -> true: reported to the server (cleared if it said no, to try again)
local function report(step)
 if asked[step] then return end;asked[step]=true
 task.spawn(function()
  local ok,r=pcall(function() return combat:WaitForChild('ProfileAction'):InvokeServer('TutorialStep',step) end)
  if not ok or type(r)~='table' or not r.ok then task.wait(1);asked[step]=nil end
 end)
end
local offerOpened,offerSince,playSince=false,nil,nil
local base={} -- what a lobby step started from: Armory = tierMap(), Equip = ProfileWearing
local lastStep -- a new step (or the admin panel restarting the tutorial) starts these over
local function stepChanged(step)
 if step==lastStep then return end
 lastStep=step;table.clear(base);table.clear(asked);offerOpened=false;offerSince=nil;playSince=nil
end
local function openWindow(name,arg)
 local hud=pg:FindFirstChild('RogueliteLobbyHUD');local hook=hud and hud:FindFirstChild('GuideOpenWindow')
 if hook then hook:Fire(name,arg);return true end
 return false
end
-- The chest screen (user, 2026-10-03: the box covered the chest): right of the chest menu first,
-- never over the chests on the island.
local function chestContext(chests)
 local island=workspace:FindFirstChild('RogueliteLobby');island=island and island:FindFirstChild('ChestIsland')
 local models=island and island:FindFirstChild('Chests');local avoid={}
 if models then for _,m in models:GetChildren() do if m:IsA('Model') then table.insert(avoid,m) end end end
 local row=find(chests,'Row_'..Config.SeedChest)
 local prefer
 if row then
  local right=row.AbsolutePosition.X+row.AbsoluteSize.X+(GuiService:GetGuiInset()).X+16
  local full=pg:FindFirstChild('TutorialGuide') and pg.TutorialGuide.AbsoluteSize or workspace.CurrentCamera.ViewportSize
  prefer={right,0,full.X,full.Y}
 end
 return {avoid=avoid,prefer=prefer}
end
local function lobbyLine()
 local step=player:GetAttribute('ProfileTutorial')
 local index=Config.stepIndex(step)
 if not index or index<2 or step=='Done' or player:GetAttribute('LobbyPreviewActive')~=true then return nil end
 stepChanged(step)
 local chests,armory=screen('ChestScreen'),screen('Armory')
 local silver=count('ProfileChests',Config.SeedChest)
 if step=='Chests' then
  if chests then
   local results=find(chests,'Results')
   if results then
    if silver>0 then
     -- OPEN AGAIN reopens the chest just opened (its caption counts that kind): point at it only
     -- when that's the Silver Chest, otherwise CLAIM back to the list.
     local again=find(results,'Again',true);local caption=again and again:FindFirstChild('Caption')
     if caption and caption.Text==('OPEN AGAIN ('..silver..')') then return {line='ChestMore',target=again} end
     return {line='ChestMore',target=find(results,'Claim',true)}
    end
    return {line='ChestOpen',target=find(results,'Claim',true)}
   end
   if find(chests,'Opening') then return {line='ChestTap'} end
   if silver<=0 then report('Armory');return {line='Armory',target=find(chests,'Exit',true)} end
   local open=find(chests,'Open',true)
   local caption=open and open:FindFirstChild('Caption')
   if caption and string.find(caption.Text,'×',1,true) then return {line='ChestOpen',target=open} end
   return {line='ChestOpen',target=find(chests,'Row_'..Config.SeedChest,true)}
  end
  if silver<=0 then report('Armory') end
  return {line='Chests',target=lobbyButton('Chests'),dim='Chests'}
 elseif step=='Armory' then
  base.Armory=base.Armory or tierMap()
  -- Done once anything is a tier up (the arrow suggests the tutorial weapon, the Baseball Bat
  -- since 2026-10-10, which the seeded chest made ready), or when nothing can be upgraded any more
  -- (copies or emeralds went elsewhere).
  if upgradedSince(base.Armory) or weaponTier(Config.Weapon)>=2 or not canUpgrade() then report('Equip') end
  if chests then return {line='Armory',target=find(chests,'Exit',true)} end
  if armory then
   local big=find(armory,'UpgradeBig',true);if big then return {line='Upgrade',target=big} end
   if not canUpgrade(Config.Weapon) then return {line='Upgrade'} end -- something else is ready
   local up=find(armory,'Upgrades',true)
   if up and titled(up.Parent,Weapons.ById[Config.Weapon].name) then return {line='Upgrade',target=up} end
   local card=find(armory,'W_'..Config.Weapon,true)
   return {line='Armory',target=card or find(armory,'Tab_Weapons',true)}
  end
  return {line='Armory',target=lobbyButton('Armory'),dim='Armory'}
 elseif step=='Equip' then
  local worn=player:GetAttribute('ProfileWearing') or ''
  base.Equip=base.Equip or worn
  -- Done once they wear the seeded piece or change what they wear at all (any armor counts), or
  -- own no armor to put on.
  if wearing(Config.SeedArmorSlot)==Config.SeedArmorSet or worn~=base.Equip or (player:GetAttribute('ProfileArmor') or '')=='' then report('Offer') end
  if armory then
   local eq=find(armory,'Equip',true)
   local set=Armor.ById[Config.SeedArmorSet]
   if eq and set and titled(eq.Parent,string.upper(set.name)) then return {line='Equip',target=eq} end
   local card=find(armory,'A_'..Config.SeedArmor,true)
   -- Still on the gloves' upgrade view (no cards there): its BACK button (named Close) first.
   return {line='Equip',target=card or find(armory,'Tab_Armor',true) or find(armory,'Close',true)}
  end
  if chests then return {line='Equip',target=find(chests,'Exit',true)} end
  return {line='Equip',target=lobbyButton('Armory'),dim='Armory'}
 elseif step=='Offer' then
  if armory then return {line='Equipped',target=find(armory,'Close',true)} end
  local hud=pg:FindFirstChild('RogueliteLobbyHUD')
  local open=hud and hud:GetAttribute('OpenWindow')
  if not offerOpened then
   if open==nil and openWindow('Store','Bundles') then offerOpened=true end
   -- The store couldn't open (another window stays up, or no hook): skip the offer.
   offerSince=offerSince or os.clock()
   if not offerOpened and os.clock()-offerSince>6 then report('Play') end
   return {line='Offer'}
  end
  if open~='Store' then report('Play');return {line='Play'} end -- closed it themselves
  return {line='Offer',button={label='NO THANKS',neutral=true,onClick=function() openWindow(nil);report('Play') end}}
 elseif step=='Play' then
  playSince=playSince or os.clock()
  local play=lobbyButton('Play')
  if not play or os.clock()-playSince>Config.PLAY_SECONDS then report('Done');return nil end
  return {line='Play',target=play,dim='Play'}
 end
 return nil
end
local function lobbyStep()
 local d=lobbyLine()
 local chests=screen('ChestScreen')
 if d and not d.hide and chests then d.ctx=chestContext(chests) end
 return d
end

-- Dimming the other lobby bottom buttons -------------------------------------------------------
local dimmed={} -- button -> true
local function undim()
 for b in dimmed do
  if b.Parent then
   b.Interactable=true
   local icon,cap=b:FindFirstChild('Icon'),b:FindFirstChild('Caption')
   if icon then icon.ImageTransparency=0 end;if cap then cap.TextTransparency=0 end
  end
 end
 table.clear(dimmed)
end
local function dimOthers(keep)
 if not keep then undim();return end
 local hud=screen('RogueliteLobbyHUD');local bottom=hud and hud:FindFirstChild('Bottom',true)
 if not bottom then return end
 for _,b in bottom:GetChildren() do
  if b:IsA('GuiButton') then
   local off=b.Name~=keep
   if off and not dimmed[b] then
    dimmed[b]=true;b.Interactable=false
    local icon,cap=b:FindFirstChild('Icon'),b:FindFirstChild('Caption')
    if icon then icon.ImageTransparency=.6 end;if cap then cap.TextTransparency=.55 end
   elseif not off and dimmed[b] then
    dimmed[b]=nil;b.Interactable=true
    local icon,cap=b:FindFirstChild('Icon'),b:FindFirstChild('Caption')
    if icon then icon.ImageTransparency=0 end;if cap then cap.TextTransparency=0 end
   end
  end
 end
end

-- The loop -------------------------------------------------------------------------------------
local function apply(d)
 if not d or d.hide then
  if guide then guide.hide() end;undim();return
 end
 local g=ui()
 -- The target before the line: a box that appears picks its spot clear of the new target.
 g.context(d.ctx)
 g.point(d.target)
 g.say(Config.Lines[d.line] or '',d.button)
 dimOthers(d.dim)
end
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.2 then return end;elapsed=0
 local ok,d=pcall(function() return runStep() or lobbyStep() end)
 if not ok then warn('TutorialGuide:',d);d=nil end
 apply(d)
end)
