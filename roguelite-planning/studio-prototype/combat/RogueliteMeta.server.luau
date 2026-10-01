-- Robux purchases, saved profile actions and the run death flow (revive / give up).
-- Server authority only: clients request; receipts, eligibility and grants are checked here.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Market=game:GetService('MarketplaceService')
local Policy=game:GetService('PolicyService')
local Tags=game:GetService('CollectionService')
local Http=game:GetService('HttpService')
local SSS=game:GetService('ServerScriptService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Config=require(combat:WaitForChild('MonetizationConfig'))
local Chests=require(combat:WaitForChild('ChestConfig'))
local Profiles=require(SSS:WaitForChild('ProfileService'))
local Shop=require(SSS:WaitForChild('ShopService'))
local Characters=require(SSS:WaitForChild('CharacterService'))
local Effects=require(SSS:WaitForChild('CombatEffectsService'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local Admin=require(combat:WaitForChild('AdminConfig'))
local studio=RunService:IsStudio()
-- Admin panel emeralds (developers only): add or set. CharacterService checks the developer and
-- the numbers. In Studio the profile is in memory; on a live server this is a real, saved change
-- to the developer's own account. Grants count as earned; Robux emeralds are clamped to the balance.
Characters.onPracticeEmeralds=function(p,mode,amount)
 local d=Admin.isAdmin(p) and Profiles.get(p);if not d then return false end
 -- Add never cuts a balance already above 1e7 (from Robux) down to the cap; Set stays 0..1e7.
 if mode=='Set' then d.emeralds=math.clamp(amount,0,1e7)
 else d.emeralds=math.clamp(d.emeralds+amount,0,math.max(1e7,d.emeralds)) end
 d.bought=math.min(d.bought or 0,d.emeralds)
 Profiles.publish(p);return true
end

-- Remote events are sandboxed so the sandboxed in-run UI (ShopUI, LevelUpUI) can use them.
local function remote(name,class)
 local r=combat:FindFirstChild(name) or Instance.new(class)
 if r:IsA('RemoteEvent') then
  r.Sandboxed=true
  r.Capabilities=SecurityCapabilities.new(Enum.SecurityCapability.Basic,Enum.SecurityCapability.RemoteEvent)
 end
 r.Name=name;r.Parent=combat;return r
end
local purchaseRequest=remote('PurchaseRequest','RemoteEvent')
local purchaseResult=remote('PurchaseResult','RemoteEvent')
local runAction=remote('RunAction','RemoteEvent')
local profileAction=remote('ProfileAction','RemoteFunction')

-- Paid random items (rerolls, emeralds spent on chests) are hidden where restricted.
local restricted={}
local function checkPolicy(p)
 local ok,info=pcall(Policy.GetPolicyInfoForPlayerAsync,Policy,p)
 restricted[p]=not ok or info.ArePaidRandomItemsRestricted==true
 p:SetAttribute('PaidRandomRestricted',restricted[p])
end

-- Death flow ----------------------------------------------------------------------
-- The run's map is the combat attribute RunMap (Pine Valley when unset or unknown).
local function runMap() local id=combat:GetAttribute('RunMap');return RunSetupRules.MapIndex[id] and id or 'PineValley' end
local RunSetupRules=require(game.ReplicatedStorage:WaitForChild('RunSetupRules'))
local down,revivesUsed={},{}
-- ShopService (required above) creates this folder, so looking it up here cannot deadlock.
local runState=game.ReplicatedStorage:WaitForChild('RogueliteRunState')
-- Harder difficulties pay more emeralds; wins and best waves are saved per map and difficulty.
local function difficulty() return combat:GetAttribute('RunDifficulty') or 'Normal' end
local function emeraldsFor(wave,map) return RunSetupRules.runEmeralds(RunSetupRules.MapIndex[map or runMap()],difficulty(),wave) end
-- Each cleared wave saves the best wave (and the win at wave 20, with its first-win bonus)
-- right away, so a run counts even if it ends without the death screen's Give Up.
Shop.onWaveCleared=function(wavesPassed)
 local map=runMap();local index=RunSetupRules.MapIndex[map]
 local key=RunSetupRules.runKey(map,difficulty())
 for p in Shop.states do
  if not p:GetAttribute('LobbyPreviewActive') then
   Profiles.recordProgress(p,key,wavesPassed,RunSetupRules.firstWinEmeralds(index,difficulty()))
  end
 end
end
local function livingInRun()
 local n=0
 for p in Shop.states do local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid');if h and h.Health>0 and not down[p] then n+=1 end end
 return n
end
local function clearDown(p)
 down[p]=nil;p:SetAttribute('RunDown',nil);p:SetAttribute('DeathInfo',nil)
end
local rise -- defined with revive below
-- Phoenix 4-piece (armor set perk, CharacterStats.ArmorSets): once per run the first death rises
-- right away at the death spot with half health and a fire blast; no death screen, and the paid
-- revive stays unused for a later death. phoenixUsed resets with the run (giveUp, wave 1).
local phoenixUsed={}
local function phoenix(p,at)
 local cs=Characters.states[p];local blast=cs and cs.perks and cs.perks.PhoenixBlast
 if not blast or phoenixUsed[p] or p:GetAttribute('LobbyPreviewActive') then return false end
 phoenixUsed[p]=true;p:SetAttribute('PhoenixUsed',true)
 p:SetAttribute('HoldRespawn',true) -- keep AvatarNormalizer's normal respawn away
 task.delay(.6,function()
  if p.Parent~=Players or not Shop.states[p] or down[p] then return end
  rise(p,at,Stats.ArmorPerks.PhoenixHealth,function(root)
   Effects.armorBlast(p,root.Position,Stats.ArmorPerks.PhoenixRadius,blast)
  end)
 end)
 return true
end
local function onDied(p,character)
 if not Shop.states[p] or down[p] then return end
 local root=character:FindFirstChild('HumanoidRootPart')
 if phoenix(p,root and root.Position or Vector3.zero) then return end
 local s=Shop.states[p]
 -- test: this player went down during a test run. It stays true even if resetRun clears the run flag
 -- before they give up, so a later give-up still pays nothing.
 down[p]={position=root and root.Position or Vector3.zero,wave=Shop.wave,map=runMap(),test=Admin.isTestRun()}
 p:SetAttribute('HoldRespawn',true)
 -- A test run (the admin panel was used) pays nothing, so the death screen shows 0 emeralds.
 p:SetAttribute('DeathInfo',Http:JSONEncode({wave=Shop.wave,level=s.level,emeralds=Admin.isTestRun() and 0 or emeraldsFor(Shop.wave),map=RunSetupRules.Maps[RunSetupRules.MapIndex[runMap()]].name,
  revivesLeft=math.max(0,Config.ReviveLimitPerRun-(revivesUsed[p] or 0))}))
 p:SetAttribute('RunDown',true)
 if livingInRun()==0 then Shop.pause() end
end
-- The flag can be set after a player went down: their death screen shows 0 and their give-up pays nothing.
runState:GetAttributeChangedSignal('AdminTestRun'):Connect(function()
 if runState:GetAttribute('AdminTestRun')~=true then return end
 for p,d in down do
  d.test=true
  local ok,info=pcall(function() return Http:JSONDecode(p:GetAttribute('DeathInfo')) end)
  if ok and type(info)=='table' then info.emeralds=0;p:SetAttribute('DeathInfo',Http:JSONEncode(info)) end
 end
end)
-- A new run (the wave counter goes back to 1) gets its Phoenix rise back.
runState:GetAttributeChangedSignal('Wave'):Connect(function()
 if runState:GetAttribute('Wave')~=1 then return end
 for q in phoenixUsed do if not down[q] then phoenixUsed[q]=nil;q:SetAttribute('PhoenixUsed',nil) end end
end)
local function watch(p)
 p.CharacterAdded:Connect(function(character)
  local h=character:WaitForChild('Humanoid',10)
  if h then h.Died:Connect(function() onDied(p,character) end) end
 end)
end
local respawn=SSS:WaitForChild('AvatarNormalizer'):WaitForChild('RespawnPlayer')
local function canRevive(p) return down[p]~=nil and (revivesUsed[p] or 0)<Config.ReviveLimitPerRun end
-- Respawn at `at` with `health` (fraction of max), a short shield and nearby zombies pushed back.
-- beforePush(root) runs once the body is placed (the Phoenix blast), before the push.
rise=function(p,at,health,beforePush)
 local character=respawn:Invoke(p)
 clearDown(p);p:SetAttribute('HoldRespawn',false)
 task.spawn(function()
  if not character then return end
  local h=character:WaitForChild('Humanoid',10);local root=character:WaitForChild('HumanoidRootPart',10)
  if not h or not root then return end
  -- CharacterService sets full health when its spawn setup finishes (it tags CombatClass);
  -- apply the revive only after that, or it would be overwritten.
  local t0=os.clock()
  while character.Parent and not character:GetAttribute('CombatClass') and os.clock()-t0<5 do task.wait(.05) end
  task.wait(.15)
  if not character.Parent or h.Health<=0 then return end
  character:PivotTo(CFrame.new(at+Vector3.new(0,3,0)))
  h.Health=math.max(1,h.MaxHealth*health)
  -- Named, so the SpawnLocation's own spawn shield timer cannot remove it early.
  for _,f in character:GetChildren() do if f:IsA('ForceField') then f:Destroy() end end
  local shield=Instance.new('ForceField');shield.Name='ReviveShield';shield.Parent=character
  task.delay(Config.ReviveInvulnerableSeconds,function() if shield.Parent then shield:Destroy() end end)
  if beforePush then beforePush(root) end
  for _,npc in Tags:GetTagged('RogueliteZombie') do
   local part=npc:IsA('Model') and npc.PrimaryPart
   if part and npc:IsDescendantOf(workspace) then
    local offset=part.Position-at;offset=Vector3.new(offset.X,0,offset.Z)
    if offset.Magnitude<Config.RevivePushRadius then
     local dir=offset.Magnitude>.1 and offset.Unit or Vector3.new(1,0,0)
     npc:PivotTo(npc:GetPivot()+dir*Config.RevivePushDistance)
    end
   end
  end
 end)
end
local function revive(p)
 if not canRevive(p) then return false end
 local at=down[p].position;revivesUsed[p]=(revivesUsed[p] or 0)+1
 rise(p,at,Config.ReviveHealth)
 Shop.resume()
 return true
end
local function giveUp(p)
 local d=down[p];if not d then return false end
 if not d.test then Profiles.recordRun(p,RunSetupRules.runKey(d.map,difficulty()),math.max(0,d.wave-1),emeraldsFor(d.wave,d.map)) end
 clearDown(p);revivesUsed[p]=0;phoenixUsed[p]=nil;p:SetAttribute('PhoenixUsed',nil)
 if livingInRun()==0 then
  Shop.resetRun();for q in revivesUsed do revivesUsed[q]=0 end
  for q in phoenixUsed do phoenixUsed[q]=nil;q:SetAttribute('PhoenixUsed',nil) end
 else Shop.resetPlayer(p) end
 p:SetAttribute('HoldRespawn',false) -- AvatarNormalizer respawns normally
 return true
end
local useStored -- defined with the purchase code below
runAction.OnServerEvent:Connect(function(p,action,arg)
 if action=='GiveUp' then giveUp(p)
 elseif action=='UseReroll' or action=='UseBanish' then useStored(p,action,arg) end
end)

-- Purchases -----------------------------------------------------------------------
local lastRequest={}
local pendingArg={} -- e.g. which level-up card a bought Banish targets
local function reply(p,key,ok,message) purchaseResult:FireClient(p,key,ok,message) end
-- Returns true when the product can be bought right now (checked before prompting).
local function eligible(p,key,arg)
 local product=Config.Products[key];local d=Profiles.get(p)
 if not product then return false,'Unknown product' end
 if not d then return false,'Profile still loading' end
 if product.random and restricted[p] then return false,'Not available in your region' end
 if key=='Revive' then return canRevive(p),'No revive available right now' end
 if key=='ShopReroll' or key=='UpgradeReroll' then return Shop.states[p]~=nil,'Only during a run' end
 if product.oneTime and d[product.oneTime] then return false,'Already purchased' end
 if product.class and d.classes[product.class] then return false,'Already unlocked' end
 if product.godly then
  if d.bundles[key] then return false,'Already purchased' end
  if not Profiles.weaponIdByName(product.godly) then return false,'Coming soon' end
 end
 if product.godlyPick then
  if d.bundles[key] then return false,'Already purchased' end
  local pick=arg and Config.GodlyWeapons[arg]
  if not pick then return false,'Pick a Godly weapon first' end
  if not Profiles.weaponIdByName(pick[1]) then return false,'Coming soon' end
 end
 return true
end
-- Grants run inside ProcessReceipt (or a Studio simulation). Return true only when delivered.
-- In-run products that can no longer be used are kept as stored rerolls/banishes (or emeralds).
local grants={}
function grants.Revive(p)
 if revive(p) then return true end
 return Profiles.grant(p,{emeralds=50,paid=true})
end
function grants.ShopReroll(p) return Shop.paidReroll(p,'Shop') or Profiles.grant(p,{rerolls=1}) end
function grants.UpgradeReroll(p) return Shop.paidReroll(p,'Upgrade') or Profiles.grant(p,{rerolls=1}) end
-- A bought banish is saved; the player then clicks the card to remove (RunAction UseBanish).
function grants.Banish(p) return Profiles.grant(p,{banishes=1}) end
local function grantProduct(p,key)
 local product=Config.Products[key]
 if grants[key] then return grants[key](p) end
 -- Godly bundle / Godly Starter: never deliver without its weapon (the receipt stays unprocessed
 -- and retries). The Starter's weapon is the pick saved on the profile before the prompt.
 local godlyName=product.godly or product.godlyPick and Profiles.get(p).godlyPick
 local weapon=godlyName and Profiles.weaponIdByName(godlyName)
 if godlyName and not weapon then return false end
 -- paid: Robux emeralds, which regions that restrict paid random items cannot spend on chests.
 return Profiles.grant(p,{emeralds=product.emeralds,paid=true,chests=product.chests,class=product.class,rerolls=product.rerolls,banishes=product.banishes,
  signatureUpgrades=product.signatureUpgrades,starterPack=product.oneTime=='starterPack',
  weapon=weapon,armorSet=product.armorSet,bundle=godlyName and key})
end
Market.ProcessReceipt=function(info)
 local p=Players:GetPlayerByUserId(info.PlayerId)
 local key=Config.byProductId(info.ProductId)
 if not p or not key or not Profiles.get(p) then return Enum.ProductPurchaseDecision.NotProcessedYet end
 if Profiles.hasReceipt(p,info.PurchaseId) then return Enum.ProductPurchaseDecision.PurchaseGranted end
 local ok,granted=pcall(grantProduct,p,key)
 if not ok or not granted then warn('RogueliteMeta: grant failed',key,granted);return Enum.ProductPurchaseDecision.NotProcessedYet end
 Profiles.addReceipt(p,info.PurchaseId);Profiles.save(p)
 reply(p,key,true,Config.Products[key].name..' purchased')
 return Enum.ProductPurchaseDecision.PurchaseGranted
end
local passGrant={VIP={vip=true},QuickOpen={quickOpen=true}}
local passField={VIP='vip',QuickOpen='quickOpen'}
purchaseRequest.OnServerEvent:Connect(function(p,key,arg)
 if type(key)~='string' or os.clock()-(lastRequest[p] or 0)<.5 then return end
 lastRequest[p]=os.clock()
 local pass=Config.Passes[key]
 if pass then
  local d=Profiles.get(p)
  if d and d[passField[key]] then return reply(p,key,false,'Already owned') end
  if pass.gamePassId>0 then Market:PromptGamePassPurchase(p,pass.gamePassId)
  elseif studio then Profiles.grant(p,passGrant[key]);reply(p,key,true,'Studio test: '..pass.name..' granted (not saved)')
  else reply(p,key,false,'Not on sale yet') end
  return
 end
 if type(arg)~='number' then arg=nil end
 local ok,why=eligible(p,key,arg)
 if not ok then return reply(p,key,false,why) end
 pendingArg[p]=pendingArg[p] or {};pendingArg[p][key]=arg
 local product=Config.Products[key]
 -- Saved (not just remembered) so a receipt that arrives after a rejoin still knows the pick.
 if product.godlyPick then Profiles.get(p).godlyPick=Config.GodlyWeapons[arg][1];Profiles.save(p) end
 if product.productId>0 then Market:PromptProductPurchase(p,product.productId)
 elseif studio then
  -- Studio only: simulate a successful receipt so flows can be tested. In-memory, never saved.
  if grantProduct(p,key) then reply(p,key,true,'Studio test: '..product.name..' granted (not saved)') else reply(p,key,false,'Grant failed') end
 else reply(p,key,false,'Not on sale yet') end
end)
Market.PromptGamePassPurchaseFinished:Connect(function(p,id,bought)
 if not bought then return end
 for key,pass in Config.Passes do
  if pass.gamePassId>0 and id==pass.gamePassId then Profiles.grant(p,passGrant[key]);reply(p,key,true,pass.name..' unlocked') end
 end
end)
local function checkPasses(p)
 for key,pass in Config.Passes do
  if pass.gamePassId>0 then
   local ok,owns=pcall(Market.UserOwnsGamePassAsync,Market,p.UserId,pass.gamePassId)
   if ok and owns then Profiles.grant(p,passGrant[key]) end
  end
 end
end

-- Stored rerolls / banishes used during a run (no Robux prompt).
local lastUse={}
useStored=function(p,action,arg)
 if os.clock()-(lastUse[p] or 0)<.3 then return end;lastUse[p]=os.clock()
 local d=Profiles.get(p);if not d or restricted[p] then return end
 if action=='UseReroll' and (arg=='Shop' or arg=='Upgrade') and Shop.states[p] then
  if d.rerolls>0 and Profiles.spend(p,'rerolls') then Shop.paidReroll(p,arg) end
 elseif action=='UseBanish' and Shop.canBanish(p,arg) then
  if d.banishes>0 and Profiles.spend(p,'banishes') then Shop.banish(p,arg) end
 end
end

-- Profile actions (lobby) ---------------------------------------------------------
local lastAction={}
profileAction.OnServerInvoke=function(p,action,a,b,c)
 if type(action)~='string' or os.clock()-(lastAction[p] or 0)<.25 then return {ok=false,message='Slow down'} end
 lastAction[p]=os.clock()
 if not Profiles.get(p) then return {ok=false,message='Profile still loading'} end
 local ok,message,results
 if action=='OpenChest' and type(a)=='string' and type(b)=='number' then ok,message,results=Profiles.openChest(p,a,b)
 elseif action=='BuyChest' and type(a)=='string' and type(b)=='number' then ok,message=Profiles.buyChest(p,a,b,restricted[p])
 elseif action=='Upgrade' and type(a)=='string' then ok,message=Profiles.upgrade(p,a)
 elseif action=='WearArmor' and type(a)=='string' and (b==nil or type(b)=='string') then ok,message=Profiles.wear(p,a,b)
 elseif action=='BuySkill' and type(a)=='string' and #a<=40 then ok,message=Profiles.buySkill(p,a)
 elseif action=='BuyClass' and type(a)=='string' then ok,message=Profiles.buyClass(p,a,Config.ClassEmeraldPrice)
 elseif action=='BuyDeal' and type(a)=='number' then ok,message,results=Profiles.buyDeal(p,a)
 elseif action=='ClaimVipChest' then ok,message=Profiles.claimVipChest(p)
 elseif action=='Redeem' and type(a)=='string' then ok,message=Profiles.redeem(p,a)
 elseif action=='Refresh' then Profiles.publish(p);ok=true;message=''
 elseif action=='DevEmeralds' and studio then ok=Profiles.grant(p,{emeralds=200});message='Studio test: +200 emeralds (not saved)'
 elseif action=='DevResetSkills' and studio then ok,message=Profiles.resetSkills(p)
 else return {ok=false,message='Unknown action'} end
 return {ok=ok==true,message=message,results=results}
end

local function added(p)
 watch(p);task.spawn(checkPolicy,p);task.spawn(checkPasses,p)
end
Players.PlayerAdded:Connect(added)
for _,p in Players:GetPlayers() do added(p);if p.Character then local h=p.Character:FindFirstChildOfClass('Humanoid');if h then h.Died:Connect(function() onDied(p,p.Character) end) end end end
Players.PlayerRemoving:Connect(function(p)
 down[p]=nil;revivesUsed[p]=nil;phoenixUsed[p]=nil;restricted[p]=nil;lastRequest[p]=nil;lastAction[p]=nil;pendingArg[p]=nil;lastUse[p]=nil
 if livingInRun()==0 then Shop.resume() end
end)
