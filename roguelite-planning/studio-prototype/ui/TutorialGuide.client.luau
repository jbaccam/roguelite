-- The tutorial guide, client side (plans/2026-10-03-tutorial-design.md). Five times a second it
-- decides what the Egg Merchant says and what the arrow points at, from what is on screen and the
-- replicated state, and TutorialGuideUI draws it:
--   the run part: RogueliteCombat.TutorialRun with this player in the run, then its results screen;
--   the lobby part: ProfileTutorial Chests -> Armory -> Equip -> Offer -> Play, in the lobby.
-- Lobby steps are saved on the server (ProfileAction 'TutorialStep', forward only) once the thing
-- they ask for is done, so a rejoin carries on where it stopped. While the arrow points at a lobby
-- bottom button, the other bottom buttons are dimmed and can't be clicked.
-- Presentation and requests only: every reward, step and purchase is checked on the server.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local Http=game:GetService('HttpService')
local Tags=game:GetService('CollectionService')
local player=Players.LocalPlayer
local combat=RS:WaitForChild('RogueliteCombat')
local Config=require(combat:WaitForChild('TutorialConfig'))
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local Armor=require(combat:WaitForChild('ArmorCatalog'))
local GuideUI=require(RS:WaitForChild('TutorialGuideUI'))
local pg=player:WaitForChild('PlayerGui')
local guide
local function ui() if not guide then guide=GuideUI.new(player,Config.Asset) end;return guide end

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
local seenRunAt,sawCrystal,bannerShown=nil,false,false
local redUntil,redShown=0,0
task.spawn(function()
 local drops=workspace:WaitForChild('RogueliteShardDrops',60)
 if drops then drops.ChildAdded:Connect(function() if combat:GetAttribute('TutorialRun')==true then sawCrystal=true end end) end
end)
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

-- The run part: {line=Lines id, target=GuiObject or nil}, {hide=true}, or nil when not in it.
local function runStep()
 local result=player:GetAttribute('RunResult')
 if type(result)=='string' and string.find(result,'"tutorial"',1,true) then
  return {line='Loot',target=find(screen('RunResults'),'BackToLobby',true)}
 end
 if combat:GetAttribute('TutorialRun')~=true or not player:GetAttribute('RunMember') then return nil end
 local run=RS:FindFirstChild('RogueliteRunState');if not run then return nil end
 seenRunAt=seenRunAt or os.clock()
 if run:GetAttribute('TutorialWon') then
  if not bannerShown then bannerShown=true;ui().banner(string.upper(Config.MapName),'VICTORY',Config.VICTORY_DELAY) end
  return {line='BossDown'}
 end
 if screen('BossIntro') then return {hide=true} end -- the boss entrance has the screen
 local phase,wave=run:GetAttribute('Phase'),run:GetAttribute('Wave') or 1
 if phase=='Combat' then
  if wave==1 then return {line=sawCrystal and 'Crystals' or (os.clock()-seenRunAt<5 and 'Welcome' or 'Pan')} end
  if wave<Config.BOSS_WAVE then return {line='Survive'} end
  return {line=os.clock()<redUntil and 'RedCircle' or 'Boss'}
 end
 if phase~='Shop' then return nil end
 if wave==1 then return {line='Welcome'} end -- waiting for wave 1
 local st=myState()
 if (st and st:GetAttribute('PendingLevelUps') or 0)>0 then
  local card=find(screen('LevelUpOffers'),'Offer1')
  return {line=wave==2 and 'LevelUp' or 'LevelUp2',target=card and find(card,'Choose',true)}
 end
 local shop
 for _,g in pg:GetChildren() do if g:IsA('ScreenGui') and g.Enabled then shop=find(g,'ShopLayout');if shop then break end end end
 local offers=Config.Offers[wave]
 if offers then
  local snap=snapshot()
  for i,o in snap and snap.offers or {} do
   if o.id==offers[1] and not o.sold then
    local card=shop and find(shop,'Offer'..i)
    return {line='Shop',target=card and find(card,'Buy',true)}
   end
  end
  return {line='ShopGo',target=shop and find(shop,'StartWave',true)}
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
local offerOpened,playSince=false,nil
local function openWindow(name,arg)
 local hud=pg:FindFirstChild('RogueliteLobbyHUD');local hook=hud and hud:FindFirstChild('GuideOpenWindow')
 if hook then hook:Fire(name,arg);return true end
 return false
end
local function lobbyStep()
 local step=player:GetAttribute('ProfileTutorial')
 local index=Config.stepIndex(step)
 if not index or index<2 or step=='Done' or player:GetAttribute('LobbyPreviewActive')~=true then return nil end
 local chests,armory=screen('ChestScreen'),screen('Armory')
 local silver=count('ProfileChests',Config.SeedChest)
 if step=='Chests' then
  if chests then
   local results=find(chests,'Results')
   if results then
    if silver>0 then return {line='ChestMore',target=find(results,'Again',true) or find(results,'Claim',true)} end
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
  if weaponTier(Config.Weapon)>=2 then report('Equip') end
  if chests then return {line='Armory',target=find(chests,'Exit',true)} end
  if armory then
   local big=find(armory,'UpgradeBig',true);if big then return {line='Upgrade',target=big} end
   local up=find(armory,'Upgrades',true)
   if up and titled(up.Parent,Weapons.ById[Config.Weapon].name) then return {line='Upgrade',target=up} end
   local card=find(armory,'W_'..Config.Weapon,true)
   return {line='Armory',target=card or find(armory,'Tab_Weapons',true)}
  end
  return {line='Armory',target=lobbyButton('Armory'),dim='Armory'}
 elseif step=='Equip' then
  if wearing(Config.SeedArmorSlot)==Config.SeedArmorSet then report('Offer') end
  if armory then
   local eq=find(armory,'Equip',true)
   local set=Armor.ById[Config.SeedArmorSet]
   if eq and set and titled(eq.Parent,string.upper(set.name)) then return {line='Equip',target=eq} end
   local card=find(armory,'A_'..Config.SeedArmor,true)
   return {line='Equip',target=card or find(armory,'Tab_Armor',true)}
  end
  if chests then return {line='Equip',target=find(chests,'Exit',true)} end
  return {line='Equip',target=lobbyButton('Armory'),dim='Armory'}
 elseif step=='Offer' then
  if armory then return {line='Equipped',target=find(armory,'Close',true)} end
  local hud=pg:FindFirstChild('RogueliteLobbyHUD')
  local open=hud and hud:GetAttribute('OpenWindow')
  if not offerOpened then
   if open==nil and openWindow('Store','Bundles') then offerOpened=true end
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
 g.say(Config.Lines[d.line] or '',d.button)
 g.point(d.target)
 dimOthers(d.dim)
end
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.2 then return end;elapsed=0
 local ok,d=pcall(function() return runStep() or lobbyStep() end)
 if not ok then warn('TutorialGuide:',d);d=nil end
 apply(d)
end)
