-- Temporary Studio server Script; intentionally excluded from the Rojo project.
local C=game.ReplicatedStorage.RogueliteCombat
local Shop=require(game.ServerScriptService.ShopService)
local Characters=require(game.ServerScriptService.CharacterService)
local Catalog=require(C.LevelUpCatalog)
local Stats=require(C.CharacterStats)
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait()
while not (Shop.states[p] and Characters.states[p] and p.Character and p.Character:FindFirstChildOfClass('Humanoid')) do task.wait() end
local count=0
local function check(ok,msg) count+=1;assert(ok,msg) end
local function request(action,index,token,revision)
 local s=Shop.states[p];s.lastRequest=-100
 return Shop.request(p,action,revision or s.revision,index,token or s.upgradeToken)
end
local ok,err=xpcall(function()
 local s=Shop.states[p];local cs=Characters.states[p]
 Shop.phase='Shop';C:SetAttribute('ZombiesEnabled',false)
 s.level=4;s.pendingLevels=3;Shop.prepareUpgrades(p);Shop.publish(p)
 check(#s.upgradeOffers==4,'Four offers')
 local ids={}
 for _,o in s.upgradeOffers do check(Stats.ById[o.id] and not ids[o.id],'Distinct stat, never weapon');ids[o.id]=true end
 check(not request('Start'),'Pending upgrades block starting wave')
 check(not request('Upgrade',5),'Reject out of bounds')
 check(not request('Upgrade',1,'forged'),'Reject forged offer token')
 check(not request('Upgrade',1,nil,s.revision-1),'Reject stale revision')
 local offer=s.upgradeOffers[4];local oldToken=s.upgradeToken;local before=cs.stats[offer.id]
 check(request('Upgrade',4),'Choose the fourth offer')
 check(s.pendingLevels==2,'Consumes one earned level')
 check(math.abs(cs.stats[offer.id]-before-offer.amount)<.001,'Applies exact stat bonus')
 check(not request('Upgrade',1,oldToken),'Replay rejected')
 Shop.bonuses(p);check(math.abs(cs.stats[offer.id]-before-offer.amount)<.001,'Survives item recomputation')
 local E=require(C.EconomyConfig)
 -- Level-up rerolls are Robux/saved only (2026-09-27): shards never pay for them.
 local shards=s.shards
 check(not request('UpgradeReroll'),'Shard level-up reroll rejected')
 check(s.shards==shards,'No shards charged')
 s.freeUpgradeRerolls=1;local before=s.upgradeToken
 check(request('UpgradeReroll'),'Saved/paid reroll used')
 check(s.freeUpgradeRerolls==0 and s.upgradeToken~=before,'Reroll replaced the offers once')
 check(not request('UpgradeBanish',1),'Removed banish action rejected')
 Shop.phase='Combat';check(not request('Upgrade',1),'Combat rejects choosing');Shop.phase='Shop'
 for _,d in Stats.List do
  local maxed=table.clone(cs.stats);maxed[d.id]=d.max
  for _,o in Catalog.roll(maxed,{},10,Random.new(10)) do check(o.id~=d.id,'Capped stat not offered') end
 end
 check(request('Upgrade',1),'Second level');check(request('Upgrade',1),'Third level')
 check(s.pendingLevels==0 and #s.upgradeOffers==0,'Queue drains exactly')
 check(not request('Upgrade',1),'Cannot mint unearned upgrade')
 -- Leave a fresh set for a real client click and reveal inspection.
 s.level=7;s.pendingLevels=3;s.upgradeOffers={};Shop.prepareUpgrades(p);Shop.publish(p)
end,debug.traceback)
script:SetAttribute('Result',game.HttpService:JSONEncode({passed=ok,assertions=count,error=err}))
script:GetAttributeChangedSignal('DamageTest'):Connect(function()
 C.PlayerDamaged:FireClient(p,19)
end)
print('LevelUpTests',ok,count,err)
